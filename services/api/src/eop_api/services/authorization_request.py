from dataclasses import dataclass
from typing import Any

from eop_api.services.employee_context import RequestContext


@dataclass(frozen=True)
class AuthorizationRequest:
    """Immutable description of an authorization evaluation request.

    Wraps the resolved `RequestContext` so `AuthorizationEvaluator`/
    `AuthorizationService` have a stable, extensible request type instead
    of a bare `RequestContext` or a callable. Subject, Action, and any
    ownership/role/permission concept remain explicitly not introduced by
    this capability (`ADR-007`).

    `resource` is the extension point anticipated by the original design
    ("a future capability can add such fields without changing the
    evaluate/authorize signatures that consume it"): it carries whatever
    the calling Service has already resolved -- e.g. the entity being
    authorized against -- so a resource-based `AuthorizationEvaluator` can
    evaluate both the authenticated subject (`context`) and the resource
    without ever querying a repository itself. `AuthorizationRequest`,
    `AuthorizationEvaluator`, and `AuthorizationService` all treat
    `resource` as opaque; only the concrete Service that resolves it and
    the concrete Evaluator that interprets it know its shape. Resolving
    `resource` remains the Service's responsibility -- Authorization
    Foundation performs no persistence and gains none by carrying it.
    Defaults to `None` so every existing caller (e.g. Approval
    Authorization, `ADR-008`) is unaffected.
    """

    context: RequestContext
    resource: Any | None = None
