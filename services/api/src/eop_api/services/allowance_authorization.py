from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest


class AllowanceAuthorizationEvaluator(AuthorizationEvaluator):
    """Evaluates the Allowance Authorization Policy (Owner Only).

    Mirrors `CompensationAuthorizationEvaluator` exactly: Allowance is
    Compensation-domain (D6), and Compensation's own resolved policy is
    Owner Only (`compensation/decision.md` §12 Addendum). `resource` is
    whichever `AllowanceCreate`/`Allowance` `AllowanceService` has already
    resolved and attached to `AuthorizationRequest.resource`.
    """

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        resource = request.resource
        current_employee_id = request.context.employee_context.employee.id
        if resource is None or resource.employee_id != current_employee_id:
            return AuthorizationDecision(
                allowed=False, reason="Allowance does not belong to the current employee"
            )
        return AuthorizationDecision(allowed=True)
