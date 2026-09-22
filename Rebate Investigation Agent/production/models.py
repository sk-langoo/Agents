"""Canonical, typed business objects. Money never uses binary floating point."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DecisionStatus(StrEnum):
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    NOT_FOUND = "not_found"
    DENIED = "denied"
    FAILED = "failed"


class WorkflowState(StrEnum):
    NEW = "new"
    INVESTIGATING = "investigating"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=100)
    tenant_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=200)
    actor_roles: set[str]
    customer: str = Field(min_length=1, max_length=200)
    quarter: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    customer_scope: set[str] = Field(default_factory=set)

    @field_validator("request_id", "tenant_id", "actor_id", "customer")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("control characters are not allowed")
        return value.strip()


class Agreement(BaseModel):
    id: str
    version: str = "1"
    effective_from: date
    effective_to: date
    rate: Decimal = Field(ge=0, le=1)
    threshold: Decimal = Field(ge=0)
    eligible_products: set[str]
    status: str = "active"
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    ambiguous: bool = False
    amendment_priority: int = 0
    supersedes_agreement_id: str | None = None
    human_review_threshold: Decimal | None = None
    source_checksum: str | None = None


class Transaction(BaseModel):
    id: str
    source_version: str = "1"
    transaction_date: date
    product: str
    amount: Decimal
    status: str = "posted"
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    source_checksum: str | None = None
    eligibility_override: bool | None = None
    duplicate_of: str | None = None
    data_quality_flag: str = "OK"


class Payment(BaseModel):
    id: str
    amount: Decimal
    status: str
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    source_checksum: str | None = None
    approval_status: str | None = None
    applied_rate: Decimal | None = None
    agreement_id_used: str | None = None
    adjustment_id: str | None = None


class EvidenceBundle(BaseModel):
    agreements: list[Agreement]
    transactions: list[Transaction]
    payments: list[Payment]
    source_systems: dict[str, str]
    retrieved_at: datetime
    control_total: Decimal | None = None


class InvestigationResult(BaseModel):
    request_id: str
    status: DecisionStatus
    workflow_state: WorkflowState
    eligible_sales: Decimal | None
    threshold: Decimal | None
    rebate_rate: Decimal | None
    expected_rebate: Decimal | None
    amount_paid: Decimal | None
    variance: Decimal | None
    currency: str | None
    reason_codes: list[str]
    evidence_ids: list[str]
    human_review: bool
    calculation_version: str
    metadata: dict[str, Any] = Field(default_factory=dict)
