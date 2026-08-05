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

from fastapi import Depends

from eop_api.dependencies.auth import CurrentUser
from eop_api.services.employee_context import (
    EmployeeContext,
    EmployeeContextResolver,
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
    return await resolver.resolve(current_user)


CurrentEmployeeContext = Annotated[EmployeeContext, Depends(get_employee_context)]


def get_request_context(
    current_user: CurrentUser, employee_context: CurrentEmployeeContext
) -> RequestContext:
    return RequestContext(user=current_user, employee_context=employee_context)


CurrentRequestContext = Annotated[RequestContext, Depends(get_request_context)]
