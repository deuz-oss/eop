import uuid

from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest


class ApprovalAuthorizationEvaluator(AuthorizationEvaluator):
    """Evaluates the Approval Authorization Policy (`ADR-008`, Manager Approval).

    Formal rule (`docs/architecture/capabilities/approval-authorization/decision.md`):
    `request.employee.manager_id == approver.employee.id`. `requester_manager_id`
    is the target request's owning `HrEmployee.manager_id`, resolved by
    `ApprovalService` before authorization is evaluated -- this evaluator
    performs no persistence and inspects no repository, per `ADR-008`
    ("Authorization Foundation remains policy-agnostic") and the Capability
    Decision ("no recursive traversal, no hierarchy inference, no
    organizational lookup"). A `None` `requester_manager_id` (no manager
    assigned) can never equal an approver's employee id, so it is denied by
    the same comparison without a separate branch.
    """

    def __init__(self, requester_manager_id: uuid.UUID | None) -> None:
        self._requester_manager_id = requester_manager_id

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        approver_employee_id = request.context.employee_context.employee.id
        if self._requester_manager_id == approver_employee_id:
            return AuthorizationDecision(allowed=True)
        return AuthorizationDecision(
            allowed=False, reason="Approver is not the requester's direct manager"
        )
