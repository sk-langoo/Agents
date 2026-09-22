import json
from contextlib import redirect_stdout
from io import StringIO
import unittest

from agent import (
    RebateInvestigationResult,
    _get_rebate_agreement,
    _get_rebate_payments,
    _get_transactions,
    _run_deterministic_investigation,
    show_tool_activity,
)


class RebateToolTests(unittest.TestCase):
    """Free tests for the deterministic, local spreadsheet logic."""

    def test_acme_agreement_is_found(self) -> None:
        result = json.loads(_get_rebate_agreement("Acme Retail"))

        self.assertEqual(result["customer"], "Acme Retail")
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["Agreement ID"], "AGR-1001")

    def test_customer_matching_ignores_case_and_spaces(self) -> None:
        result = json.loads(_get_rebate_agreement("  acme retail  "))

        self.assertEqual(len(result["records"]), 1)

    def test_acme_q2_transaction_totals_are_correct(self) -> None:
        result = json.loads(_get_transactions("Acme Retail", "2026-Q2"))

        self.assertEqual(result["transaction_count"], 5)
        self.assertAlmostEqual(result["total_sales"], 125915.0)
        self.assertAlmostEqual(result["eligible_sales"], 37400.0)

    def test_acme_q2_payment_totals_are_correct(self) -> None:
        result = json.loads(_get_rebate_payments("Acme Retail", "2026-Q2"))

        self.assertEqual(result["payment_count"], 1)
        self.assertAlmostEqual(result["total_paid"], 0.0)

    def test_deterministic_local_investigation_calculates_money(self) -> None:
        result = json.loads(_run_deterministic_investigation("Acme Retail", "2026-Q2"))

        self.assertEqual(result["calculation_version"], "rebate-v1")
        self.assertEqual(result["eligible_sales"], "37400.00")
        self.assertEqual(result["expected_rebate"], "0")
        self.assertEqual(result["variance"], "0.00")

    def test_unknown_customer_returns_empty_records(self) -> None:
        result = json.loads(_get_rebate_agreement("Not A Real Customer"))

        self.assertEqual(result["records"], [])

    def test_tool_activity_is_visible(self) -> None:
        captured_output = StringIO()

        with redirect_stdout(captured_output):
            show_tool_activity(
                "get_transactions", customer="Acme Retail", quarter="2026-Q2"
            )

        self.assertIn("[Tool activity]", captured_output.getvalue())
        self.assertIn("get_transactions", captured_output.getvalue())

    def test_structured_result_schema_accepts_a_complete_result(self) -> None:
        result = RebateInvestigationResult(
            customer="Acme Retail",
            quarter="2026-Q2",
            status="review_required",
            eligible_sales=20625.0,
            quarterly_minimum=15000.0,
            rebate_rate=0.02,
            expected_rebate=412.5,
            amount_paid=0.0,
            variance=412.5,
            conclusion="The expected rebate has not been paid.",
            next_action="Review the payment queue.",
        )

        self.assertEqual(result.expected_rebate, 412.5)
        self.assertEqual(result.variance, 412.5)


if __name__ == "__main__":
    unittest.main()
