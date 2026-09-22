import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from eval_runner import (
    EvalInvestigationResult,
    build_eval_agent,
    evidence_ids,
    grade_case,
    load_cases,
    save_results,
    select_cases,
    summarize,
)


class FakeUsage:
    input_tokens = 1000
    output_tokens = 200
    total_tokens = 1200


class EvalRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases()
        cls.case = cls.cases[0]

    def test_evidence_ids_finds_nested_records(self) -> None:
        self.assertEqual(
            evidence_ids({"records": [{"id": "A"}], "control": {"id": "B"}}),
            {"A", "B"},
        )

    def test_select_single_case(self) -> None:
        selected = select_cases(self.cases, ["RB-002"], False, None)
        self.assertEqual([case["case_id"] for case in selected], ["RB-002"])

    def test_case_agent_has_three_controlled_tools(self) -> None:
        activity = []
        agent = build_eval_agent(self.case, activity, "gpt-5.6-luna")

        self.assertEqual(
            [tool.name for tool in agent.tools],
            ["get_rebate_agreement", "get_transactions", "get_rebate_payments"],
        )

    def test_perfect_answer_passes_all_graders(self) -> None:
        expected = self.case["expected"]
        answer = EvalInvestigationResult(
            customer=self.case["input"]["customer"],
            quarter=self.case["input"]["quarter"],
            status=expected["status"],
            human_review=expected["human_review"],
            eligible_sales=float(expected["eligible_sales"]),
            threshold=float(expected["threshold"]),
            rebate_rate=float(expected["rebate_rate"]),
            expected_rebate=float(expected["expected_rebate"]),
            amount_paid=float(expected["amount_paid"]),
            variance=float(expected["variance"]),
            evidence_ids=expected["evidence_ids"],
            conclusion=expected["decision"],
            next_action="Close the investigation.",
        )
        activity = [{"tool": name} for name in expected["expected_tool_sets"][0]]
        metrics, details = grade_case(
            self.case,
            answer,
            activity,
            1.5,
            FakeUsage(),
            Decimal("1"),
            Decimal("2"),
        )

        self.assertTrue(metrics.task_success)
        self.assertEqual(metrics.cost_usd, 0.0014)
        self.assertEqual(details["invented_evidence_ids"], [])

    def test_invented_evidence_fails_case(self) -> None:
        expected = self.case["expected"]
        answer = EvalInvestigationResult(
            customer="Atlas Retail",
            quarter="2026-Q1",
            status="completed",
            human_review=False,
            eligible_sales=120000,
            threshold=100000,
            rebate_rate=0.02,
            expected_rebate=2400,
            amount_paid=2400,
            variance=0,
            evidence_ids=expected["evidence_ids"] + ["MADE-UP-ID"],
            conclusion=expected["decision"],
            next_action="Close.",
        )
        activity = [{"tool": name} for name in expected["expected_tool_sets"][0]]
        metrics, details = grade_case(
            self.case, answer, activity, 1.0, FakeUsage(), None, None
        )

        self.assertFalse(metrics.task_success)
        self.assertGreater(metrics.hallucination_rate, 0)
        self.assertEqual(details["invented_evidence_ids"], ["MADE-UP-ID"])

    def test_summary_calculates_escalation_metrics(self) -> None:
        records = [
            {
                "run_status": "completed",
                "metrics": {
                    "task_success": True,
                    "tool_selection_accuracy": 1.0,
                    "evidence_correctness": 1.0,
                    "calculation_accuracy": 1.0,
                    "hallucination_rate": 0.0,
                    "escalation_expected": True,
                    "escalation_observed": True,
                    "latency_seconds": 2.0,
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                    "cost_usd": None,
                },
            },
            {
                "run_status": "completed",
                "metrics": {
                    "task_success": False,
                    "tool_selection_accuracy": 1.0,
                    "evidence_correctness": 1.0,
                    "calculation_accuracy": 0.5,
                    "hallucination_rate": 0.0,
                    "escalation_expected": False,
                    "escalation_observed": True,
                    "latency_seconds": 4.0,
                    "input_tokens": 200,
                    "output_tokens": 40,
                    "total_tokens": 240,
                    "cost_usd": None,
                },
            },
        ]
        result = summarize(records)
        self.assertEqual(result["task_success_rate"], 0.5)
        self.assertEqual(result["escalation_recall"], 1.0)
        self.assertEqual(result["false_escalation_rate"], 1.0)
        self.assertEqual(result["latency_seconds"]["median"], 3.0)

    def test_save_results_writes_json_files(self) -> None:
        with TemporaryDirectory() as directory:
            detail, summary_path = save_results(
                [{"case_id": "RB-001"}], {"task_success_rate": 1.0}, Path(directory)
            )
            self.assertTrue(detail.exists())
            self.assertEqual(json.loads(summary_path.read_text())["task_success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
