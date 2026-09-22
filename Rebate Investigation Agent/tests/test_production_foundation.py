import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from production.audit import AuditLog
from production.engine import DeterministicRebateEngine
from production.eval_gate import evaluate_release
from production.models import Agreement, EvidenceBundle, InvestigationRequest, Payment, Transaction
from production.permissions import AuthorizationError, PermissionPolicy
from production.security import redact
from production.service import InvestigationService
from production.tools import InMemoryEvidenceProvider
from production.workflow import CaseWorkflow
from production.models import WorkflowState


def request(**overrides):
    values = {
        "request_id": "REQ-00001",
        "tenant_id": "tenant-a",
        "actor_id": "person-1",
        "actor_roles": {"investigator"},
        "customer": "Acme",
        "quarter": "2026-Q1",
        "customer_scope": {"Acme"},
    }
    values.update(overrides)
    return InvestigationRequest(**values)


def evidence(**overrides):
    values = {
        "agreements": [Agreement(id="AGR-1", effective_from=date(2026, 1, 1), effective_to=date(2026, 12, 31), rate=Decimal("0.02"), threshold=Decimal("100"), eligible_products={"A"})],
        "transactions": [Transaction(id="TX-1", transaction_date=date(2026, 2, 1), product="A", amount=Decimal("120"))],
        "payments": [Payment(id="PAY-1", amount=Decimal("2.40"), status="paid")],
        "source_systems": {"agreements": "contract-system", "transactions": "erp", "payments": "payments"},
        "retrieved_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return EvidenceBundle(**values)


class ProductionFoundationTests(unittest.TestCase):
    def test_deterministic_calculation_reconciles(self):
        result = DeterministicRebateEngine().calculate(request(), evidence())
        self.assertEqual(result.expected_rebate, Decimal("2.40"))
        self.assertEqual(result.variance, Decimal("0.00"))
        self.assertFalse(result.human_review)

    def test_duplicate_transaction_requires_review(self):
        duplicate = Transaction(id="TX-1", transaction_date=date(2026, 2, 2), product="A", amount=Decimal("10"))
        result = DeterministicRebateEngine().calculate(request(), evidence(transactions=evidence().transactions + [duplicate]))
        self.assertTrue(result.human_review)
        self.assertIn("DUPLICATE_TRANSACTION_ID", result.reason_codes)

    def test_payment_using_wrong_rate_requires_review(self):
        wrong_rate_payment = Payment(
            id="PAY-1",
            amount=Decimal("3.60"),
            status="paid",
            approval_status="approved",
            applied_rate=Decimal("0.03"),
            agreement_id_used="AGR-1",
        )
        result = DeterministicRebateEngine().calculate(
            request(), evidence(payments=[wrong_rate_payment])
        )

        self.assertTrue(result.human_review)
        self.assertEqual(result.expected_rebate, Decimal("2.40"))
        self.assertIn("PAYMENT_RATE_MISMATCH", result.reason_codes)

    def test_permissions_enforce_customer_scope(self):
        with self.assertRaises(AuthorizationError):
            PermissionPolicy().authorize_investigation(request(customer="Other"))

    def test_reviewer_cannot_self_approve(self):
        workflow = CaseWorkflow("REQ-00001", "person-1", WorkflowState.REVIEW_PENDING)
        with self.assertRaises(AuthorizationError):
            workflow.review(approve=True, actor_id="person-1", actor_roles={"reviewer"}, rationale="Checked", policy=PermissionPolicy())

    def test_audit_chain_detects_tampering(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            audit = AuditLog(path)
            audit.append("started", "REQ-00001", "person-1", {"token": "secret"})
            audit.append("completed", "REQ-00001", "person-1", {"status": "ok"})
            self.assertTrue(audit.verify())
            rows = path.read_text().splitlines()
            event = json.loads(rows[0])
            event["details"]["status"] = "tampered"
            rows[0] = json.dumps(event)
            path.write_text("\n".join(rows) + "\n")
            self.assertFalse(audit.verify())

    def test_security_redacts_secrets(self):
        self.assertEqual(redact({"api_key": "abc"}), {"api_key": "[REDACTED]"})

    def test_eval_gate_blocks_regression(self):
        result = evaluate_release({"task_success_rate": 0.5})
        self.assertFalse(result["approved"])

    def test_service_authorizes_calculates_measures_and_audits(self):
        with TemporaryDirectory() as directory:
            audit = AuditLog(Path(directory) / "audit.jsonl")
            provider = InMemoryEvidenceProvider({("tenant-a", "Acme", "2026-Q1"): evidence()})
            service = InvestigationService(provider=provider, audit_log=audit)

            result = service.investigate(request())

            self.assertEqual(result.expected_rebate, Decimal("2.40"))
            self.assertEqual(service.metrics.counters["investigation.completed"], 1)
            self.assertTrue(audit.verify())
            self.assertEqual(len((Path(directory) / "audit.jsonl").read_text().splitlines()), 2)

    def test_service_denies_before_evidence_retrieval(self):
        class ProviderThatMustNotRun:
            def retrieve(self, request):
                raise AssertionError("evidence must not be retrieved")

        with TemporaryDirectory() as directory:
            service = InvestigationService(
                provider=ProviderThatMustNotRun(),
                audit_log=AuditLog(Path(directory) / "audit.jsonl"),
            )
            with self.assertRaises(AuthorizationError):
                service.investigate(request(customer="Outside scope"))
            self.assertEqual(service.metrics.counters["investigation.denied"], 1)


if __name__ == "__main__":
    unittest.main()
