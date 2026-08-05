from collections.abc import Callable
from dataclasses import dataclass

from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeContextNotFoundError(Exception):
    """Raised when the authenticated user has no linked `HrEmployee`.

    Per ADR-006: a silent empty context would create security ambiguity for
    employee-scoped business operations, so this is an explicit error rather
    than a `None`/empty context.
    """


class MultipleEmployeeContextError(Exception):
    """Raised when the authenticated user has more than one linked `HrEmployee`.

    Per ADR-006: `hr_employees.user_id` carries no uniqueness constraint
    (cardinality is an open business decision, `ADR-004`), but authorization
    requires a deterministic employee identity, so multiple matches are
    rejected rather than resolved by picking one.
    """


@dataclass(frozen=True)
class EmployeeContext:
    """The `HrEmployee` resolved for an authenticated `User`.

    Contains only `user` and `employee` -- no additional business state, per
    the Identity & Authorization Foundation decision.
    """

    user: User
    employee: HrEmployee


@dataclass(frozen=True)
class RequestContext:
    """Passive platform context carrying the authenticated user and their
    resolved employee context through a request.

    Per the Identity & Authorization Foundation capability, this is
    infrastructure for future authorization capabilities to build on, not
    authorization behavior itself: no authorization logic, permission
    evaluation, policy logic, or role resolution belongs here.
    """

    user: User
    employee_context: EmployeeContext


class EmployeeContextResolver:
    """Resolves an authenticated `User` into its `EmployeeContext`.

    Belongs to the Application Capability Layer per ADR-006 -- not API, not
    Repository, not Database. Reuses `HrEmployeeRepository.get_by_user_id`,
    which returns a `Sequence` rather than a single row because `user_id`
    cardinality is unresolved (`ADR-004`); this resolver is where that
    sequence is turned into a deterministic outcome (zero/multiple ->
    error, exactly one -> context), per `ADR-006`.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def resolve(self, user: User) -> EmployeeContext:
        async with self._uow_factory() as uow:
            employees = await HrEmployeeRepository(uow.session).get_by_user_id(user.id)

            if len(employees) == 0:
                raise EmployeeContextNotFoundError(str(user.id))
            if len(employees) > 1:
                raise MultipleEmployeeContextError(str(user.id))

            employee = employees[0]
            uow.session.expunge(employee)
            return EmployeeContext(user=user, employee=employee)
