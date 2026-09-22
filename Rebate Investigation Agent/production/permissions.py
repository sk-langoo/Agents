"""Server-side authorization policy. Model output is never an authorization input."""

from dataclasses import dataclass

from .models import InvestigationRequest


class AuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class PermissionPolicy:
    investigate_roles: frozenset[str] = frozenset({"investigator", "reviewer", "admin"})
    approve_roles: frozenset[str] = frozenset({"reviewer", "admin"})

    def authorize_investigation(self, request: InvestigationRequest) -> None:
        if not request.actor_roles.intersection(self.investigate_roles):
            raise AuthorizationError("actor lacks the investigation role")
        if request.customer_scope and request.customer not in request.customer_scope:
            raise AuthorizationError("customer is outside the actor's authorized scope")

    def authorize_approval(
        self, *, actor_id: str, actor_roles: set[str], original_actor_id: str
    ) -> None:
        if not actor_roles.intersection(self.approve_roles):
            raise AuthorizationError("actor lacks the approval role")
        if actor_id == original_actor_id:
            raise AuthorizationError("the investigator cannot approve their own case")
