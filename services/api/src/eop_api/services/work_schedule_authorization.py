from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest


class WorkScheduleAuthorizationEvaluator(AuthorizationEvaluator):
    """Evaluates the Work Schedule Authorization Policy (Owner Only).

    Formal rule (`docs/architecture/capabilities/work-schedule/
    iteration-1-implementation-plan.md` §1 #4, §6):
    `resource.employee_id == context.employee_context.employee.id`. Mirrors
    `CompensationAuthorizationEvaluator` exactly. `resource` is whichever
    `WorkScheduleCreate`/`WorkSchedule` `WorkScheduleService` has already
    resolved and attached to `AuthorizationRequest.resource` -- this
    evaluator performs no persistence and inspects no repository or service.
    """

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        resource = request.resource
        current_employee_id = request.context.employee_context.employee.id
        if resource is None or resource.employee_id != current_employee_id:
            return AuthorizationDecision(
                allowed=False, reason="Work schedule does not belong to the current employee"
            )
        return AuthorizationDecision(allowed=True)
