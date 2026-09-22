import json
from decimal import Decimal
from pathlib import Path
import unittest


DATASET_PATH = Path(__file__).parents[1] / "evals" / "rebate_investigations.jsonl"

EXPECTED_CATEGORY_COUNTS = {
    "eligible_rebate": 3,
    "threshold_missed": 3,
    "excluded_products": 3,
    "contract_date_mismatch": 2,
    "missing_transactions": 2,
    "duplicate_transactions": 2,
    "incorrect_rebate_rate": 2,
    "incorrect_payment": 3,
    "ambiguous_language": 2,
    "conflicting_amendments": 2,
    "missing_agreement": 2,
    "human_review": 4,
}

NUMERIC_FIELDS = {
    "eligible_sales",
    "threshold",
    "rebate_rate",
    "expected_rebate",
    "amount_paid",
    "variance",
}


def load_cases() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as dataset:
        return [json.loads(line) for line in dataset if line.strip()]


class EvalDatasetTests(unittest.TestCase):
    """Free structural checks for the synthetic evaluation dataset."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases()

    def test_dataset_contains_30_unique_cases(self) -> None:
        case_ids = [case["case_id"] for case in self.cases]

        self.assertEqual(len(case_ids), 30)
        self.assertEqual(len(set(case_ids)), 30)
        self.assertEqual(case_ids, [f"RB-{number:03d}" for number in range(1, 31)])

    def test_category_coverage_is_exact(self) -> None:
        actual_counts = {
            category: sum(case["category"] == category for case in self.cases)
            for category in EXPECTED_CATEGORY_COUNTS
        }

        self.assertEqual(actual_counts, EXPECTED_CATEGORY_COUNTS)

    def test_required_sections_exist(self) -> None:
        for case in self.cases:
            with self.subTest(case_id=case["case_id"]):
                self.assertTrue(case["title"])
                self.assertTrue(case["input"]["question"])
                self.assertIn("agreements", case["source_data"])
                self.assertIn("transactions", case["source_data"])
                self.assertIn("payments", case["source_data"])
                self.assertTrue(case["expected"]["expected_tool_sets"])
                self.assertTrue(case["expected"]["decision"])
                self.assertIn(case["expected"]["status"], {
                    "completed",
                    "needs_information",
                    "not_found",
                    "review_required",
                })

    def test_numeric_expectations_are_decimal_strings_or_null(self) -> None:
        for case in self.cases:
            for field in NUMERIC_FIELDS:
                with self.subTest(case_id=case["case_id"], field=field):
                    value = case["expected"][field]
                    if value is not None:
                        self.assertIsInstance(value, str)
                        Decimal(value)

    def test_review_status_and_human_review_flag_agree(self) -> None:
        for case in self.cases:
            with self.subTest(case_id=case["case_id"]):
                if case["expected"]["status"] == "review_required":
                    self.assertTrue(case["expected"]["human_review"])

    def test_expected_calculations_are_consistent(self) -> None:
        """Check the answer key with exact decimal arithmetic."""
        for case in self.cases:
            with self.subTest(case_id=case["case_id"]):
                expected = case["expected"]
                if any(expected[field] is None for field in NUMERIC_FIELDS):
                    continue

                eligible_sales = Decimal(expected["eligible_sales"])
                threshold = Decimal(expected["threshold"])
                rebate_rate = Decimal(expected["rebate_rate"])
                expected_rebate = Decimal(expected["expected_rebate"])
                amount_paid = Decimal(expected["amount_paid"])
                variance = Decimal(expected["variance"])

                calculated_rebate = (
                    eligible_sales * rebate_rate
                    if eligible_sales >= threshold
                    else Decimal("0")
                )
                self.assertEqual(expected_rebate, calculated_rebate)
                self.assertEqual(variance, expected_rebate - amount_paid)


if __name__ == "__main__":
    unittest.main()
