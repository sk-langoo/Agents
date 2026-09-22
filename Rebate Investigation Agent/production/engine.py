"""Deterministic financial logic. The language model does not do this arithmetic."""

from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

from .models import (
    DecisionStatus,
    EvidenceBundle,
    InvestigationRequest,
    InvestigationResult,
    WorkflowState,
)


CALCULATION_VERSION = "rebate-v1"
MONEY_QUANTUM = Decimal("0.01")


class DeterministicRebateEngine:
    def calculate(
        self, request: InvestigationRequest, evidence: EvidenceBundle
    ) -> InvestigationResult:
        reasons: list[str] = []
        evidence_ids = sorted(
            {item.id for item in evidence.agreements + evidence.transactions + evidence.payments}
        )

        if not evidence.agreements:
            return self._review(request, evidence_ids, ["MISSING_AGREEMENT"])

        duplicate_ids = [
            item_id
            for item_id, count in Counter(item.id for item in evidence.transactions).items()
            if count > 1
        ]
        if duplicate_ids:
            return self._review(
                request, evidence_ids, ["DUPLICATE_TRANSACTION_ID"], {"duplicate_ids": duplicate_ids}
            )

        active = [agreement for agreement in evidence.agreements if agreement.status == "active"]
        if not active:
            return self._review(request, evidence_ids, ["AGREEMENT_CONFLICT_OR_STATUS"])
        highest_priority = max(agreement.amendment_priority for agreement in active)
        controlling = [agreement for agreement in active if agreement.amendment_priority == highest_priority]
        if len(controlling) != 1:
            return self._review(request, evidence_ids, ["CONFLICTING_CONTROLLING_AGREEMENTS"])
        agreement = controlling[0]
        if agreement.ambiguous:
            return self._review(request, evidence_ids, ["AMBIGUOUS_AGREEMENT"])

        currencies = {agreement.currency}
        currencies.update(item.currency for item in evidence.transactions)
        currencies.update(item.currency for item in evidence.payments)
        if len(currencies) != 1:
            return self._review(request, evidence_ids, ["CURRENCY_MISMATCH"])

        posted = [transaction for transaction in evidence.transactions if transaction.status == "posted"]
        if any(item.data_quality_flag.casefold() != "ok" for item in posted):
            return self._review(request, evidence_ids, ["TRANSACTION_DATA_QUALITY_ERROR"])
        if evidence.control_total is not None:
            observed_total = sum((item.amount for item in posted), Decimal("0"))
            if observed_total != evidence.control_total:
                return self._review(request, evidence_ids, ["CONTROL_TOTAL_MISMATCH"])

        eligible = [
            transaction
            for transaction in posted
            if agreement.effective_from <= transaction.transaction_date <= agreement.effective_to
            and (
                transaction.eligibility_override is True
                or (
                    transaction.eligibility_override is None
                    and transaction.product in agreement.eligible_products
                )
            )
        ]
        eligible_sales = sum((item.amount for item in eligible), Decimal("0"))
        expected = Decimal("0")
        if eligible_sales >= agreement.threshold:
            expected = (eligible_sales * agreement.rate).quantize(
                MONEY_QUANTUM, rounding=ROUND_HALF_UP
            )
        approved_paid = [
            payment
            for payment in evidence.payments
            if payment.status == "paid"
            and (payment.approval_status or "approved") == "approved"
        ]
        amount_paid = sum(
            (
                payment.amount
                for payment in approved_paid
            ),
            Decimal("0"),
        ).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        variance = expected - amount_paid
        if eligible_sales < agreement.threshold:
            reasons.append("THRESHOLD_NOT_MET")
        elif variance == 0:
            reasons.append("PAYMENT_RECONCILED")
        elif variance > 0:
            reasons.append("UNDERPAYMENT")
        else:
            reasons.append("OVERPAYMENT")

        payment_control_reasons: list[str] = []
        if any(
            payment.applied_rate is not None and payment.applied_rate != agreement.rate
            for payment in approved_paid
        ):
            payment_control_reasons.append("PAYMENT_RATE_MISMATCH")
        if any(
            payment.agreement_id_used
            and payment.agreement_id_used != agreement.id
            for payment in approved_paid
        ):
            payment_control_reasons.append("PAYMENT_AGREEMENT_VERSION_MISMATCH")
        if expected > 0 and any(
            payment.status in {"pending", "under review"}
            for payment in evidence.payments
        ):
            payment_control_reasons.append("PAYMENT_PENDING_REVIEW")
        reasons.extend(payment_control_reasons)

        human_review = bool(payment_control_reasons) or (
            agreement.human_review_threshold is not None
            and expected >= agreement.human_review_threshold
        )
        if human_review:
            reasons.append("MATERIALITY_APPROVAL_REQUIRED")

        return InvestigationResult(
            request_id=request.request_id,
            status=DecisionStatus.REVIEW_REQUIRED if human_review else DecisionStatus.COMPLETED,
            workflow_state=WorkflowState.REVIEW_PENDING if human_review else WorkflowState.COMPLETED,
            eligible_sales=eligible_sales.quantize(MONEY_QUANTUM),
            threshold=agreement.threshold,
            rebate_rate=agreement.rate,
            expected_rebate=expected,
            amount_paid=amount_paid,
            variance=variance,
            currency=agreement.currency,
            reason_codes=reasons,
            evidence_ids=evidence_ids,
            human_review=human_review,
            calculation_version=CALCULATION_VERSION,
        )

    def _review(
        self,
        request: InvestigationRequest,
        evidence_ids: list[str],
        reasons: list[str],
        metadata: dict | None = None,
    ) -> InvestigationResult:
        return InvestigationResult(
            request_id=request.request_id,
            status=DecisionStatus.REVIEW_REQUIRED,
            workflow_state=WorkflowState.REVIEW_PENDING,
            eligible_sales=None,
            threshold=None,
            rebate_rate=None,
            expected_rebate=None,
            amount_paid=None,
            variance=None,
            currency=None,
            reason_codes=reasons,
            evidence_ids=evidence_ids,
            human_review=True,
            calculation_version=CALCULATION_VERSION,
            metadata=metadata or {},
        )
