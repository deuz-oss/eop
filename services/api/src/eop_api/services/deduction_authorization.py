from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest


class DeductionAuthorizationEvaluator(AuthorizationEvaluator):
    """Evaluates the Deduction Authorization Policy (Owner Only, read-only).

    Governs only the exposed `GET` routes (`implementation-plan.md` §10.4,
    `Deduction` write routes are deferred). `resource` is the already-loaded
    `Deduction` `DeductionService` has resolved.
    """

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        resource = request.resource
        current_employee_id = request.context.employee_context.employee.id
        if resource is None or resource.employee_id != current_employee_id:
            return AuthorizationDecision(
                allowed=False, reason="Deduction does not belong to the current employee"
            )
        return AuthorizationDecision(allowed=True)
