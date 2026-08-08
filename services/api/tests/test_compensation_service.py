import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.foundation.monetary.types import InvalidMoneyError
from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
from eop_api.repositories.compensation import CompensationRepository
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.compensation import CompensationCreate, CompensationUpdate
from eop_api.services.compensation import (
    CompensationAuthorizationDeniedError,
    CompensationService,
    CorrectionTargetEmployeeMismatchError,
    CorrectionTargetNotFoundError,
    EmployeeNotFoundError,
    OverlappingCompensationPeriodError,
)
from eop_api.services.effective_dating_evaluator import AmbiguousEffectiveStateError
from eop_api.services.employee_context import EmployeeContext, RequestContext
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) tables."""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: Callable[[], AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

    try:
        yield factory
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE TABLE organizations, locations, location_types, "
                    "job_grades, employment_types, employment_statuses, shifts CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> CompensationService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return CompensationService(uow_factory)


async def _create_hr_employee(
    session_factory: Callable[[], AsyncSession], *, suffix: str
) -> uuid.UUID:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name=f"Acme Corp {suffix}")
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code=f"ENG-{suffix}", name="Engineering"
        )
        position = await PositionRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code=f"ENG-1-{suffix}",
            name="Engineer",
        )
        team = await TeamRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code=f"BACKEND-{suffix}",
            name="Backend Team",
        )
        location_type = await LocationTypeRepository(session).create(
            code=f"OFFICE-{suffix}", name="Office"
        )
        location = await LocationRepository(session).create(
            code=f"HQ-{suffix}", name="HQ", location_type_id=location_type.id
        )
        job_grade = await JobGradeRepository(session).create(
            code=f"L1-{suffix}", name="Junior", level=ord(suffix[0]) - ord("a") + 1
        )
        employment_type = await EmploymentTypeRepository(session).create(
            code=f"FT-{suffix}", name="Full-Time"
        )
        employment_status = await EmploymentStatusRepository(session).create(
            code=f"ACTIVE-{suffix}", name="Active"
        )
        shift = await ShiftRepository(session).create(
            code=f"DAY-{suffix}",
            name="Day Shift",
            start_time=datetime(2024, 1, 1, 9, 0).time(),
            end_time=datetime(2024, 1, 1, 17, 0).time(),
        )
        employee = await HrEmployeeRepository(session).create(
            employee_number=f"EMP-{suffix}",
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email=f"ada-{suffix}@example.com",
            organization_id=organization.id,
            department_id=department.id,
            position_id=position.id,
            team_id=team.id,
            location_id=location.id,
            job_grade_id=job_grade.id,
            employment_type_id=employment_type.id,
            employment_status_id=employment_status.id,
            shift_id=shift.id,
            hire_date=datetime(2024, 1, 15).date(),
            employment_status="active",
        )
        await session.commit()
        return employee.id


@pytest.fixture
async def employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_hr_employee(session_factory, suffix="a")


@pytest.fixture
async def other_employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    return await _create_hr_employee(session_factory, suffix="b")


def _request_context(employee_id: uuid.UUID) -> RequestContext:
    """A `RequestContext` built entirely in memory, scoped to `employee_id`.

    Mirrors `test_attendance_event_service.py`'s `_request_context` helper --
    only `employee_context.employee.id` is read by
    `CompensationAuthorizationEvaluator`/`CompensationService`, so the
    `User`/`HrEmployee` here need not be persisted.
    """
    user = User(
        id=uuid.uuid4(),
        email="actor@example.com",
        password_hash="hash",
        full_name="Actor",
        is_active=True,
    )
    employee = HrEmployee(
        id=employee_id,
        employee_number="ACT-1",
        first_name="Actor",
        last_name="One",
        full_name="Actor One",
        email="actor@example.com",
        organization_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        position_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        job_grade_id=uuid.uuid4(),
        employment_type_id=uuid.uuid4(),
        employment_status_id=uuid.uuid4(),
        shift_id=uuid.uuid4(),
        hire_date=date(2020, 1, 1),
        employment_status="active",
        user_id=user.id,
    )
    return RequestContext(user=user, employee_context=EmployeeContext(user=user, employee=employee))


def _create(employee_id: uuid.UUID, **overrides) -> CompensationCreate:
    values = {
        "employee_id": employee_id,
        "base_salary_amount": Decimal("1000.00"),
        "base_salary_currency": "IDR",
        "effective_from": date(2026, 1, 1),
    }
    values.update(overrides)
    return CompensationCreate(**values)


async def test_create_and_get(service: CompensationService, employee_id: uuid.UUID):
    context = _request_context(employee_id)
    compensation = await service.create(_create(employee_id), context)

    fetched = await service.get(compensation.id, context)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.base_salary_amount == Decimal("1000.00")
    assert fetched.base_salary_currency == "IDR"
    assert fetched.is_active is True


async def test_create_normalizes_precision_half_up(
    service: CompensationService, employee_id: uuid.UUID
):
    compensation = await service.create(
        _create(employee_id, base_salary_amount=Decimal("10.125")), _request_context(employee_id)
    )

    assert compensation.base_salary_amount == Decimal("10.13")


async def test_create_rejects_missing_employee(service: CompensationService):
    other_id = uuid.uuid4()
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(other_id), _request_context(other_id))


async def test_create_allows_multiple_historical_rows_for_same_employee(
    service: CompensationService, employee_id: uuid.UUID
):
    """`docs/architecture/capabilities/compensation/decision.md` §17 (Accepted):
    multiple Compensation rows may exist per employee."""
    context = _request_context(employee_id)
    first = await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )
    second = await service.create(_create(employee_id, effective_from=date(2026, 7, 1)), context)

    assert first.id != second.id
    history = await service.list(context)
    assert {c.id for c in history} == {first.id, second.id}


async def test_create_rejects_overlapping_period(
    service: CompensationService, employee_id: uuid.UUID
):
    """§19, Option O1 (Accepted): overlapping effective periods for the same
    employee are rejected."""
    context = _request_context(employee_id)
    await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )

    with pytest.raises(OverlappingCompensationPeriodError):
        await service.create(
            _create(employee_id, effective_from=date(2026, 3, 1), effective_to=date(2026, 9, 30)),
            context,
        )


async def test_create_rejects_open_ended_overlap(
    service: CompensationService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    await service.create(_create(employee_id, effective_from=date(2026, 1, 1)), context)

    with pytest.raises(OverlappingCompensationPeriodError):
        await service.create(_create(employee_id, effective_from=date(2026, 7, 1)), context)


async def test_create_correction_accepted_with_valid_target(
    service: CompensationService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    target = await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )

    correction = await service.create(
        _create(
            employee_id,
            base_salary_amount=Decimal("1100.00"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    assert correction.id != target.id
    assert correction.corrects_id == target.id


async def test_create_correction_rejects_missing_target(
    service: CompensationService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)

    with pytest.raises(CorrectionTargetNotFoundError):
        await service.create(
            _create(employee_id, corrects_id=uuid.uuid4()),
            context,
        )


async def test_create_correction_rejects_target_from_another_employee(
    service: CompensationService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    other_context = _request_context(other_employee_id)
    target = await service.create(_create(other_employee_id), other_context)

    context = _request_context(employee_id)
    with pytest.raises(CorrectionTargetEmployeeMismatchError):
        await service.create(
            _create(employee_id, corrects_id=target.id),
            context,
        )


async def test_create_correction_may_overlap_its_exact_target(
    service: CompensationService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    target = await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )

    correction = await service.create(
        _create(
            employee_id,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    assert correction.corrects_id == target.id


async def test_create_correction_may_not_overlap_unrelated_row(
    service: CompensationService, employee_id: uuid.UUID
):
    """Governance example: correcting A does not gain permission to overlap
    unrelated B. A (Jan-Jun) and B (Jul-Dec) do not overlap each other; a
    correction of A that extends into B's period must still be rejected,
    even though it is exempt from overlapping A itself."""
    context = _request_context(employee_id)
    a = await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )
    await service.create(
        _create(employee_id, effective_from=date(2026, 7, 1), effective_to=date(2026, 12, 31)),
        context,
    )

    with pytest.raises(OverlappingCompensationPeriodError):
        await service.create(
            _create(
                employee_id,
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 8, 31),
                corrects_id=a.id,
            ),
            context,
        )


async def test_create_correction_target_row_remains_unchanged(
    service: CompensationService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    target = await service.create(
        _create(
            employee_id,
            base_salary_amount=Decimal("1000.00"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        ),
        context,
    )

    await service.create(
        _create(
            employee_id,
            base_salary_amount=Decimal("1100.00"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    unchanged = await service.get(target.id, context)
    assert unchanged is not None
    assert unchanged.base_salary_amount == Decimal("1000.00")


async def test_create_rejects_invalid_currency(
    service: CompensationService, employee_id: uuid.UUID
):
    with pytest.raises(InvalidMoneyError):
        await service.create(
            _create(employee_id, base_salary_currency=""), _request_context(employee_id)
        )


async def test_create_denied_for_non_owner(
    service: CompensationService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    """`employee_id` on the payload does not belong to the calling employee."""
    with pytest.raises(CompensationAuthorizationDeniedError):
        await service.create(_create(employee_id), _request_context(other_employee_id))


async def test_get_by_employee(service: CompensationService, employee_id: uuid.UUID):
    context = _request_context(employee_id)
    compensation = await service.create(_create(employee_id), context)

    found = await service.get_by_employee(employee_id, context)

    assert found is not None
    assert found.id == compensation.id


async def test_get_by_employee_without_context_skips_authorization(
    service: CompensationService, employee_id: uuid.UUID
):
    """Mirrors `PayrollCalculationService`'s internal, context-free call."""
    compensation = await service.create(_create(employee_id), _request_context(employee_id))

    found = await service.get_by_employee(employee_id)

    assert found is not None
    assert found.id == compensation.id


async def test_get_by_employee_denied_for_non_owner(
    service: CompensationService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    await service.create(_create(employee_id), _request_context(employee_id))

    with pytest.raises(CompensationAuthorizationDeniedError):
        await service.get_by_employee(employee_id, _request_context(other_employee_id))


async def test_get_by_employee_resolves_correct_historical_row_for_as_of_date(
    service: CompensationService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    earlier = await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )
    later = await service.create(
        _create(
            employee_id, base_salary_amount=Decimal("1200.00"), effective_from=date(2026, 7, 1)
        ),
        context,
    )

    found_earlier = await service.get_by_employee(employee_id, context, as_of_date=date(2026, 3, 1))
    found_later = await service.get_by_employee(employee_id, context, as_of_date=date(2026, 9, 1))

    assert found_earlier is not None
    assert found_earlier.id == earlier.id
    assert found_later is not None
    assert found_later.id == later.id


async def test_list_history_returns_all_rows_for_caller(
    service: CompensationService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    first = await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )
    second = await service.create(_create(employee_id, effective_from=date(2026, 7, 1)), context)

    history = await service.list_history(context)

    assert [c.id for c in history] == [first.id, second.id]


async def test_get_by_employee_correction_wins_over_corrected_target(
    service: CompensationService, employee_id: uuid.UUID
):
    """§19: correction precedence -- when a correction row and the row it
    corrects are both effective as of the same date, the correction wins."""
    context = _request_context(employee_id)
    target = await service.create(
        _create(
            employee_id,
            base_salary_amount=Decimal("1000.00"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        ),
        context,
    )
    correction = await service.create(
        _create(
            employee_id,
            base_salary_amount=Decimal("1100.00"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    resolved = await service.get_by_employee(employee_id, context, as_of_date=date(2026, 3, 1))

    assert resolved is not None
    assert resolved.id == correction.id
    assert resolved.base_salary_amount == Decimal("1100.00")


async def test_get_by_employee_raises_on_unrelated_ambiguous_rows(
    service: CompensationService,
    employee_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    """Two unrelated (no correction relation) rows effective on the same
    date is genuine ambiguity, never silently resolved.

    Constructed directly via the repository (not `service.create()`),
    which would reject this via O1 overlap validation -- this represents
    invalid/legacy data the read path must still handle safely.
    """
    context = _request_context(employee_id)
    async with session_factory() as session:
        repo = CompensationRepository(session)
        await repo.create(
            employee_id=employee_id,
            base_salary_amount=Decimal("1000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        )
        await repo.create(
            employee_id=employee_id,
            base_salary_amount=Decimal("1200.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        )
        await session.commit()

    with pytest.raises(AmbiguousEffectiveStateError):
        await service.get_by_employee(employee_id, context, as_of_date=date(2026, 3, 1))


async def test_get_missing_returns_none(service: CompensationService, employee_id: uuid.UUID):
    assert await service.get(uuid.uuid4(), _request_context(employee_id)) is None


async def test_get_denied_for_non_owner(
    service: CompensationService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    owner_context = _request_context(employee_id)
    compensation = await service.create(_create(employee_id), owner_context)

    with pytest.raises(CompensationAuthorizationDeniedError):
        await service.get(compensation.id, _request_context(other_employee_id))


async def test_list_returns_created(service: CompensationService, employee_id: uuid.UUID):
    context = _request_context(employee_id)
    await service.create(_create(employee_id), context)

    items = await service.list(context)

    assert len(items) == 1
    assert items[0].employee_id == employee_id


async def test_list_returns_only_owned(
    service: CompensationService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    await service.create(_create(employee_id), _request_context(employee_id))
    await service.create(_create(other_employee_id), _request_context(other_employee_id))

    items = await service.list(_request_context(employee_id))

    assert {item.employee_id for item in items} == {employee_id}


async def test_update_only_changes_is_active_not_historical_fields(
    service: CompensationService, employee_id: uuid.UUID
):
    """`CompensationUpdate` carries only `is_active`
    (`docs/architecture/capabilities/compensation/decision.md` §7/§17,
    §18 -- Accepted): `base_salary_amount` cannot be changed via `update()`,
    since that would mutate a historical fact in place."""
    context = _request_context(employee_id)
    compensation = await service.create(_create(employee_id), context)

    updated = await service.update(compensation.id, CompensationUpdate(is_active=False), context)

    assert updated is not None
    assert updated.id == compensation.id
    assert updated.base_salary_amount == compensation.base_salary_amount
    assert updated.is_active is False
    assert len(await service.list(context)) == 1


async def test_update_missing_returns_none(service: CompensationService, employee_id: uuid.UUID):
    assert (
        await service.update(
            uuid.uuid4(),
            CompensationUpdate(is_active=False),
            _request_context(employee_id),
        )
        is None
    )


async def test_update_denied_for_non_owner(
    service: CompensationService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    compensation = await service.create(_create(employee_id), _request_context(employee_id))

    with pytest.raises(CompensationAuthorizationDeniedError):
        await service.update(
            compensation.id,
            CompensationUpdate(is_active=False),
            _request_context(other_employee_id),
        )


async def test_update_can_deactivate(service: CompensationService, employee_id: uuid.UUID):
    context = _request_context(employee_id)
    compensation = await service.create(_create(employee_id), context)

    updated = await service.update(compensation.id, CompensationUpdate(is_active=False), context)

    assert updated is not None
    assert updated.is_active is False


async def test_delete_existing(service: CompensationService, employee_id: uuid.UUID):
    context = _request_context(employee_id)
    compensation = await service.create(_create(employee_id), context)

    deleted = await service.delete(compensation.id, context)

    assert deleted is True
    assert await service.get(compensation.id, context) is None


async def test_delete_missing_returns_false(service: CompensationService, employee_id: uuid.UUID):
    assert await service.delete(uuid.uuid4(), _request_context(employee_id)) is False


async def test_delete_target_with_correction_is_restricted(
    service: CompensationService, employee_id: uuid.UUID
):
    """`corrects_id` is `ON DELETE RESTRICT` (mirrors `Department.parent_id`/
    `HrEmployee.manager_id`): a corrected row cannot be deleted while a
    correction still references it, protecting correction lineage."""
    context = _request_context(employee_id)
    target = await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )
    await service.create(
        _create(
            employee_id,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    with pytest.raises(IntegrityError):
        await service.delete(target.id, context)


async def test_delete_denied_for_non_owner(
    service: CompensationService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    compensation = await service.create(_create(employee_id), _request_context(employee_id))

    with pytest.raises(CompensationAuthorizationDeniedError):
        await service.delete(compensation.id, _request_context(other_employee_id))


async def test_list_active_returns_only_active(
    service: CompensationService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    active = await service.create(_create(employee_id), _request_context(employee_id))
    inactive = await service.create(_create(other_employee_id), _request_context(other_employee_id))
    await service.update(
        inactive.id, CompensationUpdate(is_active=False), _request_context(other_employee_id)
    )

    items = await service.list_active()

    assert {item.id for item in items} == {active.id}
