from eop_api.services.authorization_decision import AuthorizationDecision
from eop_api.services.authorization_evaluator import AuthorizationEvaluator
from eop_api.services.authorization_request import AuthorizationRequest


class AuthorizationService:
    """Application entry point for authorization (`ADR-007`).

    Coordinates evaluation via `AuthorizationEvaluator` and returns its
    `AuthorizationDecision`. Owns no workflow, persistence, or transport
    behavior -- those remain the caller's responsibility. Not wired into
    any router or business service: this capability adds no endpoint
    behavior.
    """

    def __init__(self, evaluator: AuthorizationEvaluator | None = None) -> None:
        self._evaluator = evaluator or AuthorizationEvaluator()

    def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        return self._evaluator.evaluate(request)
