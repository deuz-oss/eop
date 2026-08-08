"""DI wiring for the Identity & Authorization Foundation (`ADR-005`, `ADR-006`).

Distinct from `eop_api.core.request_context`: that module propagates cheap
primitives (request id, user id) via `ContextVar` for logging/tracing and is
read from anywhere without threading `Request` through the call stack. This
module instead assembles the request-scoped `EmployeeContext`/`RequestContext`
objects (`eop_api.services.employee_context`) via ordinary FastAPI `Depends()`
composition, for capabilities that need the resolved employee identity. The
two modules are unrelated despite the similar vocabulary -- kept in separate
files (`core/request_context.py` vs. this one) precisely to avoid conflating
them.

Not wired into any router: this capability adds no endpoint behavior.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.services.employee_context import (
    EmployeeContext,
    EmployeeContextNotFoundError,
    EmployeeContextResolver,
    MultipleEmployeeContextError,
    RequestContext,
)


def get_employee_context_resolver() -> EmployeeContextResolver:
    return EmployeeContextResolver()


EmployeeContextResolverDep = Annotated[
    EmployeeContextResolver, Depends(get_employee_context_resolver)
]


async def get_employee_context(
    current_user: CurrentUser, resolver: EmployeeContextResolverDep
) -> EmployeeContext:
    """Resolves `current_user`'s `EmployeeContext`, mapping resolution
    failures to HTTP responses at the boundary (`TD-001`).

    Centralized here, in Identity Context's own dependency wiring, rather
    than in any individual consumer (Approval Authorization, Leave
    Management, Overtime Management, Timesheet Management, or any other
    capability composing `CurrentRequestContext`/`CurrentEmployeeContext`)
    -- mirrors `dependencies/auth.py`'s `get_current_user`, which maps its
    own domain exception (`InvalidTokenError`) to `HTTPException` at the
    same DI layer rather than leaving it to propagate to the generic
    handler.

    `EmployeeContextNotFoundError` -> 403: the user is authenticated but
    lacks the employee linkage required for any employee-scoped operation
    -- a standing/entitlement gap, not a missing named resource (404) or
    an authentication failure (401).
    `MultipleEmployeeContextError` -> 409: the server-side data cannot be
    resolved to one deterministic identity -- a state conflict, not a
    client input error.
    """
    try:
        return await resolver.resolve(current_user)
    except EmployeeContextNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user has no linked employee record",
        ) from exc
    except MultipleEmployeeContextError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Authenticated user has multiple linked employee records",
        ) from exc


CurrentEmployeeContext = Annotated[EmployeeContext, Depends(get_employee_context)]


def get_request_context(
    current_user: CurrentUser, employee_context: CurrentEmployeeContext
) -> RequestContext:
    return RequestContext(user=current_user, employee_context=employee_context)


CurrentRequestContext = Annotated[RequestContext, Depends(get_request_context)]
