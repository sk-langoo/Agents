"""Release gate for eval summaries. Thresholds must be approved before production."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvalThresholds:
    task_success_rate: float = 0.98
    evidence_correctness: float = 0.99
    calculation_accuracy: float = 1.0
    hallucination_rate_max: float = 0.005
    escalation_recall: float = 1.0
    false_escalation_rate_max: float = 0.05
    failed_runs_max: int = 0


def evaluate_release(summary: dict[str, Any], thresholds: EvalThresholds = EvalThresholds()) -> dict[str, Any]:
    checks = {
        "task_success_rate": summary.get("task_success_rate", 0) >= thresholds.task_success_rate,
        "evidence_correctness": summary.get("evidence_correctness", 0) >= thresholds.evidence_correctness,
        "calculation_accuracy": summary.get("calculation_accuracy", 0) >= thresholds.calculation_accuracy,
        "hallucination_rate": summary.get("hallucination_rate", 1) <= thresholds.hallucination_rate_max,
        "escalation_recall": summary.get("escalation_recall", 0) >= thresholds.escalation_recall,
        "false_escalation_rate": summary.get("false_escalation_rate", 1) <= thresholds.false_escalation_rate_max,
        "failed_runs": summary.get("cases_failed_to_run", 1) <= thresholds.failed_runs_max,
    }
    return {"approved": all(checks.values()), "checks": checks}
