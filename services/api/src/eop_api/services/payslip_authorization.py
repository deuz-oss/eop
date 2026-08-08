from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest


class PayslipAuthorizationEvaluator(AuthorizationEvaluator):
    """Evaluates the Payslip Authorization Policy (Owner Only).

    Formal rule (`docs/architecture/capabilities/payslip/decision.md` §8
    Addendum, `docs/architecture/capabilities/payroll-authorization/decision.md`
    Addendum): `resource.employee_id == context.employee_context.employee.id`.
    `resource` is whichever `PayslipCreate`/`Payslip` `PayslipService` has
    already resolved and attached to `AuthorizationRequest.resource` -- this
    evaluator performs no persistence and inspects no repository or service.
    No other authorization rule is evaluated.
    """

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        resource = request.resource
        current_employee_id = request.context.employee_context.employee.id
        if resource is None or resource.employee_id != current_employee_id:
            return AuthorizationDecision(
                allowed=False, reason="Payslip does not belong to the current employee"
            )
        return AuthorizationDecision(allowed=True)
