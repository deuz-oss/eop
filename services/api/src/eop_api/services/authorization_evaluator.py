from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_request import AuthorizationRequest


class AuthorizationEvaluator:
    """Evaluates an `AuthorizationRequest` and produces an `AuthorizationDecision`.

    Foundation-phase evaluator (`ADR-007`): no permission, ownership, or
    role model exists yet, so the default implementation carries no
    business rule and allows every request. This class is the replaceable
    extension point named by `ADR-007` ("remains replaceable") -- future
    authorization models replace or subclass `AuthorizationEvaluator`
    rather than being injected as a per-call predicate. Contains no
    persistence, workflow, or transport logic.
    """

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        return AuthorizationDecision(allowed=True)
