from dataclasses import dataclass

from eop_api.services.employee_context import RequestContext


@dataclass(frozen=True)
class AuthorizationRequest:
    """Immutable description of an authorization evaluation request.

    Wraps the resolved `RequestContext` so `AuthorizationEvaluator`/
    `AuthorizationService` have a stable, extensible request type instead
    of a bare `RequestContext` or a callable. Deliberately holds nothing
    beyond `context` today: Subject, Action, Resource, and any
    ownership/role/permission concept are explicitly not introduced by
    this capability (`ADR-007`). This type exists so a future capability
    can add such fields without changing the `evaluate`/`authorize`
    signatures that consume it.
    """

    context: RequestContext
