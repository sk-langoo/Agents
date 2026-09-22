"""Contracts for secure evidence retrieval.

Real implementations must enforce tenant filters in their database/API query.
The in-memory implementation exists only for local tests and demonstrations.
"""

from typing import Protocol

from .models import EvidenceBundle, InvestigationRequest


class EvidenceProvider(Protocol):
    def retrieve(self, request: InvestigationRequest) -> EvidenceBundle: ...


class InMemoryEvidenceProvider:
    def __init__(self, evidence_by_tenant_customer_quarter: dict[tuple[str, str, str], EvidenceBundle]) -> None:
        self._evidence = evidence_by_tenant_customer_quarter

    def retrieve(self, request: InvestigationRequest) -> EvidenceBundle:
        key = (request.tenant_id, request.customer, request.quarter)
        if key not in self._evidence:
            raise LookupError("no evidence found in the authorized scope")
        return self._evidence[key]
