"""One controlled request path joining authorization, evidence, rules, metrics, and audit."""

from .audit import AuditLog
from .engine import DeterministicRebateEngine
from .models import InvestigationRequest, InvestigationResult
from .observability import Metrics, Timer
from .permissions import PermissionPolicy
from .security import canonical_checksum
from .tools import EvidenceProvider


class InvestigationService:
    def __init__(
        self,
        *,
        provider: EvidenceProvider,
        audit_log: AuditLog,
        permissions: PermissionPolicy | None = None,
        engine: DeterministicRebateEngine | None = None,
        metrics: Metrics | None = None,
    ) -> None:
        self.provider = provider
        self.audit_log = audit_log
        self.permissions = permissions or PermissionPolicy()
        self.engine = engine or DeterministicRebateEngine()
        self.metrics = metrics or Metrics()

    def investigate(self, request: InvestigationRequest) -> InvestigationResult:
        """Fail closed: authorize before retrieving any customer evidence."""
        with Timer(self.metrics, "investigation.duration_seconds"):
            try:
                self.permissions.authorize_investigation(request)
            except Exception as error:
                self.metrics.increment("investigation.denied")
                self.audit_log.append(
                    "investigation_denied",
                    request.request_id,
                    request.actor_id,
                    {"tenant_id": request.tenant_id, "reason": type(error).__name__},
                )
                raise

            self.audit_log.append(
                "investigation_started",
                request.request_id,
                request.actor_id,
                {
                    "tenant_id": request.tenant_id,
                    "customer_hash": canonical_checksum(request.customer),
                    "quarter": request.quarter,
                },
            )
            try:
                evidence = self.provider.retrieve(request)
                result = self.engine.calculate(request, evidence)
            except Exception as error:
                self.metrics.increment("investigation.failed")
                self.audit_log.append(
                    "investigation_failed",
                    request.request_id,
                    request.actor_id,
                    {"error_type": type(error).__name__},
                )
                raise

            self.metrics.increment("investigation.completed")
            if result.human_review:
                self.metrics.increment("investigation.review_required")
            self.audit_log.append(
                "investigation_completed",
                request.request_id,
                request.actor_id,
                {
                    "status": result.status,
                    "reason_codes": result.reason_codes,
                    "evidence_ids": result.evidence_ids,
                    "calculation_version": result.calculation_version,
                    "human_review": result.human_review,
                },
            )
            return result
