"""Run the rebate agent against the synthetic evaluation dataset.

The evaluation tools in this file are deliberately separate from the production
prototype tools in agent.py. For each run they expose only the evidence embedded
in that one test case.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field


PROJECT_DIR = Path(__file__).parent
DEFAULT_DATASET = PROJECT_DIR / "evals" / "rebate_investigations.jsonl"
DEFAULT_RESULTS_DIR = PROJECT_DIR / "evals" / "results"
DEFAULT_MODEL = "gpt-5.6-luna"
NUMBER_FIELDS = (
    "eligible_sales",
    "threshold",
    "rebate_rate",
    "expected_rebate",
    "amount_paid",
    "variance",
)


class EvalInvestigationResult(BaseModel):
    """Structured answer used by the deterministic graders."""

    customer: str | None
    quarter: str | None
    status: Literal[
        "completed", "needs_information", "not_found", "review_required"
    ]
    human_review: bool = Field(
        description="True only when a person must resolve or approve the case."
    )
    eligible_sales: float | None
    threshold: float | None
    rebate_rate: float | None
    expected_rebate: float | None
    amount_paid: float | None
    variance: float | None
    evidence_ids: list[str] = Field(
        description="IDs of source records that materially support the conclusion."
    )
    conclusion: str
    next_action: str


@dataclass
class CaseMetrics:
    task_success: bool
    tool_selection_accuracy: float
    evidence_correctness: float
    calculation_accuracy: float | None
    hallucination_rate: float
    escalation_expected: bool
    escalation_observed: bool
    latency_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float | None


def explain(message: str) -> None:
    """Make each major runner step visible in beginner-friendly language."""
    print(f"\n[Eval runner] {message}", flush=True)


def load_cases(dataset_path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    with dataset_path.open(encoding="utf-8") as dataset:
        return [json.loads(line) for line in dataset if line.strip()]


def evidence_ids(value: Any) -> set[str]:
    """Find every source-record ID in nested evidence."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "id" and isinstance(child, str):
                found.add(child)
            else:
                found.update(evidence_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(evidence_ids(child))
    return found


def _request_matches(case: dict[str, Any], customer: str, quarter: str | None) -> bool:
    requested = case["input"]
    customer_matches = customer.strip().casefold() == requested["customer"].strip().casefold()
    quarter_matches = quarter is None or quarter.strip().casefold() == requested["quarter"].strip().casefold()
    return customer_matches and quarter_matches


def build_case_tools(
    case: dict[str, Any], activity: list[dict[str, Any]]
) -> list[Any]:
    """Create three read-only tools scoped to one evaluation case."""
    source = case["source_data"]

    def record(tool: str, arguments: dict[str, str], payload: dict[str, Any]) -> str:
        ids = sorted(evidence_ids(payload))
        activity.append({"tool": tool, "arguments": arguments, "evidence_ids": ids})
        print(
            f"  [Controlled tool] {tool} returned {len(ids)} evidence record(s): "
            f"{', '.join(ids) if ids else 'none'}",
            flush=True,
        )
        return json.dumps(payload, separators=(",", ":"))

    @function_tool(name_override="get_rebate_agreement")
    def agreement_tool(customer: str) -> str:
        """Retrieve agreements, amendments, contract language, and applicable policy for a customer."""
        matches = _request_matches(case, customer, None)
        payload = {
            "customer": customer,
            "agreements": source.get("agreements", []) if matches else [],
            "policy": source.get("policy") if matches else None,
        }
        return record("get_rebate_agreement", {"customer": customer}, payload)

    @function_tool(name_override="get_transactions")
    def transactions_tool(customer: str, quarter: str) -> str:
        """Retrieve transactions and reconciliation controls for a customer and quarter."""
        matches = _request_matches(case, customer, quarter)
        payload = {
            "customer": customer,
            "quarter": quarter,
            "transactions": source.get("transactions", []) if matches else [],
            "transaction_control": source.get("transaction_control") if matches else None,
            "external_claim": source.get("external_claim") if matches else None,
        }
        return record(
            "get_transactions", {"customer": customer, "quarter": quarter}, payload
        )

    @function_tool(name_override="get_rebate_payments")
    def payments_tool(customer: str, quarter: str) -> str:
        """Retrieve rebate payment records for a customer and quarter."""
        matches = _request_matches(case, customer, quarter)
        payload = {
            "customer": customer,
            "quarter": quarter,
            "payments": source.get("payments", []) if matches else [],
        }
        return record(
            "get_rebate_payments", {"customer": customer, "quarter": quarter}, payload
        )

    return [agreement_tool, transactions_tool, payments_tool]


def build_eval_agent(case: dict[str, Any], activity: list[dict[str, Any]], model: str) -> Agent:
    """Build a fresh agent so its tools cannot access another case."""
    return Agent(
        name="Rebate Investigation Eval Agent",
        model=model,
        instructions=(
            "Investigate the user's rebate question using only the supplied read-only tools. "
            "For a full reconciliation, inspect the agreement, transactions, and payments. "
            "Do not assume a missing value is zero. Check effective dates, eligible products, "
            "thresholds, amendments, duplicates, control totals, payment status, ambiguity, and "
            "review policies. Calculate expected rebate as eligible sales times the controlling "
            "rate only when the controlling threshold is met. Variance is expected rebate minus "
            "amount paid. Use null for any number that cannot be established safely. Set "
            "human_review true and status review_required when ambiguity, conflicting evidence, "
            "unreconciled source data, contract coverage, or policy requires a person. Cite only "
            "IDs actually returned by tools. Never invent evidence or terms. Keep the conclusion "
            "and next action concise."
        ),
        tools=build_case_tools(case, activity),
        output_type=EvalInvestigationResult,
    )


def _decimal_equal(expected: str | None, observed: float | None) -> bool:
    if expected is None or observed is None:
        return expected is None and observed is None
    try:
        return Decimal(expected) == Decimal(str(observed))
    except InvalidOperation:
        return False


def grade_case(
    case: dict[str, Any],
    answer: EvalInvestigationResult,
    activity: list[dict[str, Any]],
    latency_seconds: float,
    usage: Any,
    input_cost_per_million: Decimal | None,
    output_cost_per_million: Decimal | None,
) -> tuple[CaseMetrics, dict[str, Any]]:
    """Apply transparent, deterministic graders to one answer."""
    expected = case["expected"]
    observed_tools = [entry["tool"] for entry in activity]
    tool_pass = observed_tools in expected["expected_tool_sets"]

    expected_evidence = set(expected["evidence_ids"])
    observed_evidence = set(answer.evidence_ids)
    available_evidence = evidence_ids(case["source_data"])
    evidence_pass = expected_evidence.issubset(observed_evidence)
    invented_evidence = observed_evidence - available_evidence

    forbidden_claims = [
        phrase
        for phrase in expected["must_not_claim"]
        if phrase.casefold() in answer.conclusion.casefold()
        or phrase.casefold() in answer.next_action.casefold()
    ]
    hallucination_events = len(invented_evidence) + len(forbidden_claims)
    claim_opportunities = max(1, len(observed_evidence) + len(expected["must_not_claim"]))
    hallucination_rate = hallucination_events / claim_opportunities

    numeric_checks = {
        field: _decimal_equal(expected[field], getattr(answer, field))
        for field in NUMBER_FIELDS
    }
    calculation_accuracy = sum(numeric_checks.values()) / len(numeric_checks)
    calculation_pass = all(numeric_checks.values())

    status_pass = answer.status == expected["status"]
    escalation_pass = answer.human_review == expected["human_review"]
    task_success = all(
        (
            tool_pass,
            evidence_pass,
            calculation_pass,
            status_pass,
            escalation_pass,
            hallucination_events == 0,
        )
    )

    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
    cost_usd: float | None = None
    if input_cost_per_million is not None and output_cost_per_million is not None:
        cost = (
            Decimal(input_tokens) * input_cost_per_million
            + Decimal(output_tokens) * output_cost_per_million
        ) / Decimal("1000000")
        cost_usd = float(cost)

    metrics = CaseMetrics(
        task_success=task_success,
        tool_selection_accuracy=float(tool_pass),
        evidence_correctness=float(evidence_pass and not invented_evidence),
        calculation_accuracy=calculation_accuracy,
        hallucination_rate=hallucination_rate,
        escalation_expected=expected["human_review"],
        escalation_observed=answer.human_review,
        latency_seconds=latency_seconds,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )
    details = {
        "status_correct": status_pass,
        "expected_tools": expected["expected_tool_sets"],
        "observed_tools": observed_tools,
        "missing_evidence_ids": sorted(expected_evidence - observed_evidence),
        "invented_evidence_ids": sorted(invented_evidence),
        "forbidden_claims_found": forbidden_claims,
        "numeric_checks": numeric_checks,
    }
    return metrics, details


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [record for record in records if record.get("run_status") == "completed"]
    metrics = [record["metrics"] for record in successful]
    latencies = [metric["latency_seconds"] for metric in metrics]
    costs = [metric["cost_usd"] for metric in metrics if metric["cost_usd"] is not None]

    expected_escalations = [m for m in metrics if m["escalation_expected"]]
    non_escalations = [m for m in metrics if not m["escalation_expected"]]
    true_escalations = sum(m["escalation_observed"] for m in expected_escalations)
    false_escalations = sum(m["escalation_observed"] for m in non_escalations)

    def average(field: str) -> float | None:
        values = [m[field] for m in metrics if m[field] is not None]
        return statistics.fmean(values) if values else None

    task_success_rate = average("task_success")
    total_cost = sum(costs) if metrics and len(costs) == len(metrics) else None
    success_count = sum(m["task_success"] for m in metrics)
    return {
        "cases_requested": len(records),
        "cases_completed": len(successful),
        "cases_failed_to_run": len(records) - len(successful),
        "task_success_rate": task_success_rate,
        "tool_selection_accuracy": average("tool_selection_accuracy"),
        "evidence_correctness": average("evidence_correctness"),
        "calculation_accuracy": average("calculation_accuracy"),
        "hallucination_rate": average("hallucination_rate"),
        "escalation_recall": (
            true_escalations / len(expected_escalations) if expected_escalations else None
        ),
        "false_escalation_rate": (
            false_escalations / len(non_escalations) if non_escalations else None
        ),
        "latency_seconds": {
            "median": statistics.median(latencies) if latencies else None,
            "p95": _percentile(latencies, 0.95),
            "p99": _percentile(latencies, 0.99),
        },
        "average_input_tokens": average("input_tokens"),
        "average_output_tokens": average("output_tokens"),
        "average_total_tokens": average("total_tokens"),
        "average_cost_usd": statistics.fmean(costs) if costs else None,
        "cost_per_successful_task_usd": (
            total_cost / success_count if total_cost is not None and success_count else None
        ),
    }


def select_cases(
    cases: list[dict[str, Any]], case_ids: list[str] | None, run_all: bool, limit: int | None
) -> list[dict[str, Any]]:
    if run_all and case_ids:
        raise ValueError("Use either --all or --case, not both.")
    if not run_all and not case_ids:
        raise ValueError("Choose --case RB-001 (repeatable) or --all.")
    if case_ids:
        by_id = {case["case_id"]: case for case in cases}
        missing = [case_id for case_id in case_ids if case_id not in by_id]
        if missing:
            raise ValueError(f"Unknown case ID(s): {', '.join(missing)}")
        selected = [by_id[case_id] for case_id in case_ids]
    else:
        selected = cases
    return selected[:limit] if limit is not None else selected


def save_results(
    records: list[dict[str, Any]], summary: dict[str, Any], results_dir: Path
) -> tuple[Path, Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    detail_path = results_dir / f"run_{stamp}.jsonl"
    summary_path = results_dir / f"run_{stamp}_summary.json"
    detail_path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return detail_path, summary_path


def run_case(
    case: dict[str, Any],
    model: str,
    input_cost_per_million: Decimal | None,
    output_cost_per_million: Decimal | None,
) -> dict[str, Any]:
    activity: list[dict[str, Any]] = []
    case_id = case["case_id"]
    explain(f"Starting {case_id}: {case['title']}")
    print(f"  Question: {case['input']['question']}")
    print("  I am giving the agent three controlled, read-only tools for this case.")
    agent = build_eval_agent(case, activity, model)

    started = time.perf_counter()
    try:
        result = Runner.run_sync(agent, case["input"]["question"])
        latency = time.perf_counter() - started
        answer = result.final_output
        usage = result.context_wrapper.usage
        metrics, grade_details = grade_case(
            case,
            answer,
            activity,
            latency,
            usage,
            input_cost_per_million,
            output_cost_per_million,
        )
        explain(f"Graded {case_id}: {'PASS' if metrics.task_success else 'FAIL'}")
        print(f"  Tools used: {[entry['tool'] for entry in activity]}")
        print(f"  Conclusion: {answer.conclusion}")
        print(f"  Task success: {metrics.task_success}")
        return {
            "case_id": case_id,
            "category": case["category"],
            "title": case["title"],
            "run_status": "completed",
            "answer": answer.model_dump(mode="json"),
            "tool_activity": activity,
            "metrics": asdict(metrics),
            "grade_details": grade_details,
        }
    except Exception as error:  # Continue the suite while preserving the failure.
        latency = time.perf_counter() - started
        explain(f"{case_id} could not complete; I recorded the error and will continue.")
        print(f"  Error: {type(error).__name__}: {error}")
        return {
            "case_id": case_id,
            "category": case["category"],
            "title": case["title"],
            "run_status": "error",
            "error_type": type(error).__name__,
            "error": str(error),
            "tool_activity": activity,
            "latency_seconds": latency,
        }


def parse_decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic evaluations for the Rebate Investigation Agent."
    )
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument(
        "--case", action="append", dest="case_ids", help="Run one case, e.g. RB-001. Repeat to run several."
    )
    choice.add_argument("--all", action="store_true", help="Run all selected dataset cases.")
    parser.add_argument("--limit", type=int, help="Run only the first N selected cases.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and list cases without calling the API.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to evaluate (default: {DEFAULT_MODEL}).")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument(
        "--input-cost-per-million", help="Optional input-token price in USD per 1M tokens."
    )
    parser.add_argument(
        "--output-cost-per-million", help="Optional output-token price in USD per 1M tokens."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = load_cases(args.dataset)
        selected = select_cases(cases, args.case_ids, args.all, args.limit)
        input_price = parse_decimal(args.input_cost_per_million)
        output_price = parse_decimal(args.output_cost_per_million)
    except (OSError, ValueError, InvalidOperation) as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 2

    if (input_price is None) != (output_price is None):
        print("Setup error: provide both input and output token prices, or neither.", file=sys.stderr)
        return 2

    explain(f"Loaded {len(cases)} cases and selected {len(selected)} case(s).")
    for case in selected:
        print(f"  {case['case_id']} — {case['title']}")

    if args.dry_run:
        explain("Dry run complete. The dataset is readable and no OpenAI API call was made.")
        return 0

    if not os.getenv("OPENAI_API_KEY"):
        print(
            "Setup error: OPENAI_API_KEY is not set in this Terminal window. "
            "Set it before running a live evaluation.",
            file=sys.stderr,
        )
        return 2

    explain(
        f"Beginning live evaluation with {args.model}. Each case may make multiple API requests as the agent uses tools."
    )
    records = [
        run_case(case, args.model, input_price, output_price) for case in selected
    ]
    summary = summarize(records)
    detail_path, summary_path = save_results(records, summary, args.results_dir)

    explain("Evaluation finished. Here is the aggregate scorecard:")
    print(json.dumps(summary, indent=2))
    explain("Saved a detailed record for diagnosis and a smaller summary for comparison.")
    print(f"  Detailed results: {detail_path}")
    print(f"  Summary: {summary_path}")
    if summary["average_cost_usd"] is None:
        print(
            "  Cost is shown as null because token prices were not supplied. Token usage was still recorded."
        )
    return 0 if summary["cases_failed_to_run"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
