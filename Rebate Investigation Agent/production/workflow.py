"""Human-review state transitions with separation of duties."""

from dataclasses import dataclass

from .models import WorkflowState
from .permissions import PermissionPolicy


ALLOWED_TRANSITIONS = {
    WorkflowState.NEW: {WorkflowState.INVESTIGATING},
    WorkflowState.INVESTIGATING: {WorkflowState.REVIEW_PENDING, WorkflowState.COMPLETED, WorkflowState.FAILED},
    WorkflowState.REVIEW_PENDING: {WorkflowState.APPROVED, WorkflowState.REJECTED},
    WorkflowState.APPROVED: {WorkflowState.COMPLETED},
    WorkflowState.REJECTED: set(),
    WorkflowState.COMPLETED: set(),
    WorkflowState.FAILED: set(),
}


@dataclass
class CaseWorkflow:
    request_id: str
    original_actor_id: str
    state: WorkflowState = WorkflowState.NEW

    def transition(self, target: WorkflowState) -> None:
        if target not in ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"invalid workflow transition: {self.state} -> {target}")
        self.state = target

    def review(
        self,
        *,
        approve: bool,
        actor_id: str,
        actor_roles: set[str],
        rationale: str,
        policy: PermissionPolicy,
    ) -> None:
        if self.state != WorkflowState.REVIEW_PENDING:
            raise ValueError("case is not awaiting review")
        if not rationale.strip():
            raise ValueError("review rationale is required")
        policy.authorize_approval(
            actor_id=actor_id,
            actor_roles=actor_roles,
            original_actor_id=self.original_actor_id,
        )
        self.transition(WorkflowState.APPROVED if approve else WorkflowState.REJECTED)
