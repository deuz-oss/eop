from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest


class CompensationAuthorizationEvaluator(AuthorizationEvaluator):
    """Evaluates the Compensation Authorization Policy (Owner Only).

    Formal rule (`docs/architecture/capabilities/compensation/decision.md` §12
    Addendum, `docs/architecture/capabilities/payroll-authorization/decision.md`
    Addendum): `resource.employee_id == context.employee_context.employee.id`.
    `resource` is whichever `CompensationCreate`/`Compensation`
    `CompensationService` has already resolved and attached to
    `AuthorizationRequest.resource` -- this evaluator performs no persistence
    and inspects no repository or service. No other authorization rule is
    evaluated.
    """

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        resource = request.resource
        current_employee_id = request.context.employee_context.employee.id
        if resource is None or resource.employee_id != current_employee_id:
            return AuthorizationDecision(
                allowed=False, reason="Compensation does not belong to the current employee"
            )
        return AuthorizationDecision(allowed=True)
