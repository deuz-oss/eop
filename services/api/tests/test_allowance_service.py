import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.foundation.monetary.types import InvalidMoneyError
from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
from eop_api.repositories.allowance import AllowanceRepository
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
from eop_api.schemas.allowance import AllowanceCreate, AllowanceUpdate
from eop_api.services.allowance import (
    AllowanceAuthorizationDeniedError,
    AllowanceDeletionNotAllowedError,
    AllowanceService,
    CorrectionTargetEmployeeMismatchError,
    CorrectionTargetNotFoundError,
    EmployeeNotFoundError,
    OverlappingAllowancePeriodError,
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
def service(session_factory: Callable[[], AsyncSession]) -> AllowanceService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return AllowanceService(uow_factory)


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


def _create(employee_id: uuid.UUID, **overrides) -> AllowanceCreate:
    values = {
        "employee_id": employee_id,
        "allowance_type": "TRANSPORT",
        "allowance_amount": Decimal("500000.00"),
        "allowance_currency": "IDR",
        "effective_from": date(2026, 1, 1),
    }
    values.update(overrides)
    return AllowanceCreate(**values)


async def test_create_and_get(service: AllowanceService, employee_id: uuid.UUID):
    context = _request_context(employee_id)
    allowance = await service.create(_create(employee_id), context)

    fetched = await service.get(allowance.id, context)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.allowance_amount == Decimal("500000.00")
    assert fetched.allowance_type == "TRANSPORT"
    assert fetched.is_active is True


async def test_create_rejects_missing_employee(service: AllowanceService):
    other_id = uuid.uuid4()
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(other_id), _request_context(other_id))


async def test_create_allows_multiple_simultaneous_types(
    service: AllowanceService, employee_id: uuid.UUID
):
    """D6: an employee may hold multiple simultaneous allowances of
    different types."""
    context = _request_context(employee_id)
    transport = await service.create(_create(employee_id, allowance_type="TRANSPORT"), context)
    meal = await service.create(_create(employee_id, allowance_type="MEAL"), context)

    assert transport.id != meal.id
    history = await service.list_history(context)
    assert {a.id for a in history} == {transport.id, meal.id}


async def test_create_rejects_overlapping_period_same_type(
    service: AllowanceService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )

    with pytest.raises(OverlappingAllowancePeriodError):
        await service.create(
            _create(employee_id, effective_from=date(2026, 3, 1), effective_to=date(2026, 9, 30)),
            context,
        )


async def test_create_allows_overlapping_period_different_type(
    service: AllowanceService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    await service.create(
        _create(employee_id, allowance_type="TRANSPORT", effective_from=date(2026, 1, 1)),
        context,
    )

    meal = await service.create(
        _create(employee_id, allowance_type="MEAL", effective_from=date(2026, 1, 1)), context
    )

    assert meal.allowance_type == "MEAL"


async def test_create_correction_accepted_with_valid_target(
    service: AllowanceService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    target = await service.create(
        _create(employee_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)),
        context,
    )

    correction = await service.create(
        _create(
            employee_id,
            allowance_amount=Decimal("600000.00"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    assert correction.corrects_id == target.id


async def test_create_correction_rejects_missing_target(
    service: AllowanceService, employee_id: uuid.UUID
):
    with pytest.raises(CorrectionTargetNotFoundError):
        await service.create(
            _create(employee_id, corrects_id=uuid.uuid4()), _request_context(employee_id)
        )


async def test_create_correction_rejects_target_from_another_employee(
    service: AllowanceService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    other_context = _request_context(other_employee_id)
    target = await service.create(_create(other_employee_id), other_context)

    context = _request_context(employee_id)
    with pytest.raises(CorrectionTargetEmployeeMismatchError):
        await service.create(_create(employee_id, corrects_id=target.id), context)


async def test_create_rejects_invalid_currency(service: AllowanceService, employee_id: uuid.UUID):
    with pytest.raises(InvalidMoneyError):
        await service.create(
            _create(employee_id, allowance_currency=""), _request_context(employee_id)
        )


async def test_create_denied_for_non_owner(
    service: AllowanceService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    with pytest.raises(AllowanceAuthorizationDeniedError):
        await service.create(_create(employee_id), _request_context(other_employee_id))


async def test_list_active_for_employee_resolves_correct_row_per_type(
    service: AllowanceService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    await service.create(
        _create(
            employee_id,
            allowance_type="TRANSPORT",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        ),
        context,
    )
    later_transport = await service.create(
        _create(
            employee_id,
            allowance_type="TRANSPORT",
            allowance_amount=Decimal("700000.00"),
            effective_from=date(2026, 7, 1),
        ),
        context,
    )
    meal = await service.create(
        _create(employee_id, allowance_type="MEAL", effective_from=date(2026, 1, 1)), context
    )

    active = await service.list_active_for_employee(employee_id, date(2026, 9, 1))

    assert {a.id for a in active} == {later_transport.id, meal.id}


async def test_list_active_for_employee_correction_wins(
    service: AllowanceService, employee_id: uuid.UUID
):
    context = _request_context(employee_id)
    target = await service.create(
        _create(
            employee_id,
            allowance_amount=Decimal("500000.00"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        ),
        context,
    )
    await service.create(
        _create(
            employee_id,
            allowance_amount=Decimal("600000.00"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    active = await service.list_active_for_employee(employee_id, date(2026, 3, 1))

    assert len(active) == 1
    assert active[0].allowance_amount == Decimal("600000.00")


async def test_list_active_for_employee_raises_on_unrelated_ambiguous_rows(
    service: AllowanceService,
    employee_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    async with session_factory() as session:
        repo = AllowanceRepository(session)
        await repo.create(
            employee_id=employee_id,
            allowance_type="TRANSPORT",
            allowance_amount=Decimal("500000.00"),
            allowance_currency="IDR",
            effective_from=date(2026, 1, 1),
        )
        await repo.create(
            employee_id=employee_id,
            allowance_type="TRANSPORT",
            allowance_amount=Decimal("600000.00"),
            allowance_currency="IDR",
            effective_from=date(2026, 1, 1),
        )
        await session.commit()

    with pytest.raises(AmbiguousEffectiveStateError):
        await service.list_active_for_employee(employee_id, date(2026, 3, 1))


async def test_update_only_changes_is_active(service: AllowanceService, employee_id: uuid.UUID):
    context = _request_context(employee_id)
    allowance = await service.create(_create(employee_id), context)

    updated = await service.update(allowance.id, AllowanceUpdate(is_active=False), context)

    assert updated is not None
    assert updated.is_active is False
    assert updated.allowance_amount == allowance.allowance_amount


async def test_update_denied_for_non_owner(
    service: AllowanceService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    allowance = await service.create(_create(employee_id), _request_context(employee_id))

    with pytest.raises(AllowanceAuthorizationDeniedError):
        await service.update(
            allowance.id, AllowanceUpdate(is_active=False), _request_context(other_employee_id)
        )


async def test_delete_existing_leaf_row_is_rejected(
    service: AllowanceService, employee_id: uuid.UUID
):
    """Allowance Delete Integrity: an uncorrected/leaf row -- including the
    currently-effective row a real payroll calculation would read -- can
    never be deleted. `repo.delete()` is never called; the row remains
    exactly as it was."""
    context = _request_context(employee_id)
    allowance = await service.create(_create(employee_id), context)

    with pytest.raises(AllowanceDeletionNotAllowedError):
        await service.delete(allowance.id, context)

    assert await service.get(allowance.id, context) is not None


async def test_delete_missing_returns_false(service: AllowanceService, employee_id: uuid.UUID):
    assert await service.delete(uuid.uuid4(), _request_context(employee_id)) is False


async def test_delete_target_already_referenced_by_correction_is_rejected(
    service: AllowanceService, employee_id: uuid.UUID
):
    """A row already referenced by another row's `corrects_id` is rejected
    the same clean way as any other row -- not via the raw `IntegrityError`
    the `ON DELETE RESTRICT` FK on `corrects_id` would otherwise surface,
    since `delete()` now never reaches `repo.delete()` for any existing
    row."""
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

    with pytest.raises(AllowanceDeletionNotAllowedError):
        await service.delete(target.id, context)

    assert await service.get(target.id, context) is not None


async def test_delete_denied_for_non_owner(
    service: AllowanceService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    """Authorization failure occurs before the deletion-prohibited check is
    ever reached."""
    allowance = await service.create(_create(employee_id), _request_context(employee_id))

    with pytest.raises(AllowanceAuthorizationDeniedError):
        await service.delete(allowance.id, _request_context(other_employee_id))


async def test_list_returns_only_owned(
    service: AllowanceService, employee_id: uuid.UUID, other_employee_id: uuid.UUID
):
    await service.create(_create(employee_id), _request_context(employee_id))
    await service.create(_create(other_employee_id), _request_context(other_employee_id))

    items = await service.list(_request_context(employee_id))

    assert {item.employee_id for item in items} == {employee_id}
