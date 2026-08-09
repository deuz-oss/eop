from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest


class VisitAuthorizationEvaluator(AuthorizationEvaluator):
    """Evaluates the Visit Authorization Policy (Owner Only).

    Formal rule (`docs/architecture/capabilities/visit/
    iteration-1-scope-and-implementation-plan.md` §4):
    `resource.employee_id == context.employee_context.employee.id`.
    `resource` is whichever `Visit`/`VisitCreate` `VisitService` has already
    resolved and attached to `AuthorizationRequest.resource` (`ADR-007`
    addendum) -- this evaluator performs no persistence and inspects no
    repository or service. Mirrors `AttendanceAuthorizationEvaluator`'s
    exact shape -- reuse of the existing Owner Only mechanism, not new
    authorization infrastructure. No other authorization rule is evaluated.
    """

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        resource = request.resource
        current_employee_id = request.context.employee_context.employee.id
        if resource is None or resource.employee_id != current_employee_id:
            return AuthorizationDecision(
                allowed=False, reason="Visit does not belong to the current employee"
            )
        return AuthorizationDecision(allowed=True)
