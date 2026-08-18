import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.hr_employee import HrEmployee
from eop_api.models.user import User
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
from eop_api.repositories.work_schedule import WorkScheduleRepository
from eop_api.schemas.work_schedule import WorkScheduleCreate, WorkScheduleUpdate
from eop_api.services.effective_dating_evaluator import AmbiguousEffectiveStateError
from eop_api.services.employee_context import EmployeeContext, RequestContext
from eop_api.services.work_schedule import (
    CorrectionTargetEmployeeMismatchError,
    CorrectionTargetNotFoundError,
    EmployeeNotFoundError,
    OverlappingWorkSchedulePeriodError,
    ShiftNotFoundError,
    WorkScheduleAuthorizationDeniedError,
    WorkScheduleDeletionNotAllowedError,
    WorkScheduleService,
)
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
def service(session_factory: Callable[[], AsyncSession]) -> WorkScheduleService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return WorkScheduleService(uow_factory)


async def _create_hr_employee(
    session_factory: Callable[[], AsyncSession], *, suffix: str
) -> tuple[uuid.UUID, uuid.UUID]:
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
        return employee.id, shift.id


@pytest.fixture
async def employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    eid, _ = await _create_hr_employee(session_factory, suffix="a")
    return eid


@pytest.fixture
async def shift_id(
    session_factory: Callable[[], AsyncSession], employee_id: uuid.UUID
) -> uuid.UUID:
    async with session_factory() as session:
        employee = await HrEmployeeRepository(session).get(employee_id)
        assert employee is not None
        return employee.shift_id


@pytest.fixture
async def other_employee_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    eid, _ = await _create_hr_employee(session_factory, suffix="b")
    return eid


def _request_context(employee_id: uuid.UUID) -> RequestContext:
    """A `RequestContext` built entirely in memory, scoped to `employee_id`.

    Mirrors `test_compensation_service.py`'s identical helper -- only
    `employee_context.employee.id` is read by
    `WorkScheduleAuthorizationEvaluator`/`WorkScheduleService`, so the
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


def _create(employee_id: uuid.UUID, shift_id: uuid.UUID, **overrides) -> WorkScheduleCreate:
    values = {
        "employee_id": employee_id,
        "shift_id": shift_id,
        "works_monday": True,
        "works_tuesday": True,
        "works_wednesday": True,
        "works_thursday": True,
        "works_friday": True,
        "works_saturday": False,
        "works_sunday": False,
        "effective_from": date(2026, 1, 1),
    }
    values.update(overrides)
    return WorkScheduleCreate(**values)


async def test_create_and_get(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    work_schedule = await service.create(_create(employee_id, shift_id), context)

    fetched = await service.get(work_schedule.id, context)

    assert fetched is not None
    assert fetched.employee_id == employee_id
    assert fetched.shift_id == shift_id
    assert fetched.works_monday is True
    assert fetched.works_saturday is False
    assert fetched.is_active is True


async def test_create_rejects_missing_employee(service: WorkScheduleService, shift_id: uuid.UUID):
    other_id = uuid.uuid4()
    with pytest.raises(EmployeeNotFoundError):
        await service.create(_create(other_id, shift_id), _request_context(other_id))


async def test_create_rejects_missing_shift(service: WorkScheduleService, employee_id: uuid.UUID):
    with pytest.raises(ShiftNotFoundError):
        await service.create(_create(employee_id, uuid.uuid4()), _request_context(employee_id))


async def test_create_allows_multiple_historical_rows_for_same_employee(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    first = await service.create(
        _create(
            employee_id, shift_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)
        ),
        context,
    )
    second = await service.create(
        _create(employee_id, shift_id, effective_from=date(2026, 7, 1)), context
    )

    assert first.id != second.id
    history = await service.list(context)
    assert {w.id for w in history} == {first.id, second.id}


async def test_create_rejects_overlapping_period(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    await service.create(
        _create(
            employee_id, shift_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)
        ),
        context,
    )

    with pytest.raises(OverlappingWorkSchedulePeriodError):
        await service.create(
            _create(
                employee_id,
                shift_id,
                effective_from=date(2026, 3, 1),
                effective_to=date(2026, 9, 30),
            ),
            context,
        )


async def test_create_correction_accepted_with_valid_target(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    target = await service.create(
        _create(
            employee_id, shift_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)
        ),
        context,
    )

    correction = await service.create(
        _create(
            employee_id,
            shift_id,
            works_saturday=True,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    assert correction.id != target.id
    assert correction.corrects_id == target.id


async def test_create_correction_rejects_missing_target(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)

    with pytest.raises(CorrectionTargetNotFoundError):
        await service.create(
            _create(employee_id, shift_id, corrects_id=uuid.uuid4()),
            context,
        )


async def test_create_correction_rejects_target_from_another_employee(
    service: WorkScheduleService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    other_employee_id: uuid.UUID,
):
    other_context = _request_context(other_employee_id)
    target = await service.create(_create(other_employee_id, shift_id), other_context)

    context = _request_context(employee_id)
    with pytest.raises(CorrectionTargetEmployeeMismatchError):
        await service.create(
            _create(employee_id, shift_id, corrects_id=target.id),
            context,
        )


async def test_create_correction_may_overlap_its_exact_target(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    target = await service.create(
        _create(
            employee_id, shift_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)
        ),
        context,
    )

    correction = await service.create(
        _create(
            employee_id,
            shift_id,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    assert correction.corrects_id == target.id


async def test_create_correction_target_row_remains_unchanged(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    target = await service.create(
        _create(
            employee_id,
            shift_id,
            works_saturday=False,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        ),
        context,
    )

    await service.create(
        _create(
            employee_id,
            shift_id,
            works_saturday=True,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    unchanged = await service.get(target.id, context)
    assert unchanged is not None
    assert unchanged.works_saturday is False


async def test_create_denied_for_non_owner(
    service: WorkScheduleService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    other_employee_id: uuid.UUID,
):
    with pytest.raises(WorkScheduleAuthorizationDeniedError):
        await service.create(_create(employee_id, shift_id), _request_context(other_employee_id))


async def test_get_by_employee(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    work_schedule = await service.create(_create(employee_id, shift_id), context)

    found = await service.get_by_employee(employee_id, context)

    assert found is not None
    assert found.id == work_schedule.id


async def test_get_by_employee_without_context_skips_authorization(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    work_schedule = await service.create(
        _create(employee_id, shift_id), _request_context(employee_id)
    )

    found = await service.get_by_employee(employee_id)

    assert found is not None
    assert found.id == work_schedule.id


async def test_get_by_employee_denied_for_non_owner(
    service: WorkScheduleService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    other_employee_id: uuid.UUID,
):
    await service.create(_create(employee_id, shift_id), _request_context(employee_id))

    with pytest.raises(WorkScheduleAuthorizationDeniedError):
        await service.get_by_employee(employee_id, _request_context(other_employee_id))


async def test_get_by_employee_resolves_correct_historical_row_for_as_of_date(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    earlier = await service.create(
        _create(
            employee_id, shift_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)
        ),
        context,
    )
    later = await service.create(
        _create(employee_id, shift_id, works_saturday=True, effective_from=date(2026, 7, 1)),
        context,
    )

    found_earlier = await service.get_by_employee(employee_id, context, as_of_date=date(2026, 3, 1))
    found_later = await service.get_by_employee(employee_id, context, as_of_date=date(2026, 9, 1))

    assert found_earlier is not None
    assert found_earlier.id == earlier.id
    assert found_later is not None
    assert found_later.id == later.id


async def test_get_by_employee_correction_wins_over_corrected_target(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    target = await service.create(
        _create(
            employee_id,
            shift_id,
            works_saturday=False,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        ),
        context,
    )
    correction = await service.create(
        _create(
            employee_id,
            shift_id,
            works_saturday=True,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    resolved = await service.get_by_employee(employee_id, context, as_of_date=date(2026, 3, 1))

    assert resolved is not None
    assert resolved.id == correction.id
    assert resolved.works_saturday is True


async def test_get_by_employee_raises_on_unrelated_ambiguous_rows(
    service: WorkScheduleService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    context = _request_context(employee_id)
    async with session_factory() as session:
        repo = WorkScheduleRepository(session)
        await repo.create(
            employee_id=employee_id,
            shift_id=shift_id,
            effective_from=date(2026, 1, 1),
            works_monday=True,
            works_tuesday=True,
            works_wednesday=True,
            works_thursday=True,
            works_friday=True,
            works_saturday=False,
            works_sunday=False,
        )
        await repo.create(
            employee_id=employee_id,
            shift_id=shift_id,
            effective_from=date(2026, 1, 1),
            works_monday=True,
            works_tuesday=True,
            works_wednesday=True,
            works_thursday=True,
            works_friday=True,
            works_saturday=True,
            works_sunday=False,
        )
        await session.commit()

    with pytest.raises(AmbiguousEffectiveStateError):
        await service.get_by_employee(employee_id, context, as_of_date=date(2026, 3, 1))


async def test_get_missing_returns_none(service: WorkScheduleService, employee_id: uuid.UUID):
    assert await service.get(uuid.uuid4(), _request_context(employee_id)) is None


async def test_list_history_returns_all_rows_for_caller(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    first = await service.create(
        _create(
            employee_id, shift_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)
        ),
        context,
    )
    second = await service.create(
        _create(employee_id, shift_id, effective_from=date(2026, 7, 1)), context
    )

    history = await service.list_history(context)

    assert [w.id for w in history] == [first.id, second.id]


async def test_list_returns_only_owned(
    service: WorkScheduleService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    other_employee_id: uuid.UUID,
):
    await service.create(_create(employee_id, shift_id), _request_context(employee_id))
    await service.create(_create(other_employee_id, shift_id), _request_context(other_employee_id))

    items = await service.list(_request_context(employee_id))

    assert {item.employee_id for item in items} == {employee_id}


async def test_update_only_changes_is_active_not_historical_fields(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    context = _request_context(employee_id)
    work_schedule = await service.create(_create(employee_id, shift_id), context)

    updated = await service.update(work_schedule.id, WorkScheduleUpdate(is_active=False), context)

    assert updated is not None
    assert updated.id == work_schedule.id
    assert updated.works_monday == work_schedule.works_monday
    assert updated.is_active is False
    assert len(await service.list(context)) == 1


async def test_update_denied_for_non_owner(
    service: WorkScheduleService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    other_employee_id: uuid.UUID,
):
    work_schedule = await service.create(
        _create(employee_id, shift_id), _request_context(employee_id)
    )

    with pytest.raises(WorkScheduleAuthorizationDeniedError):
        await service.update(
            work_schedule.id,
            WorkScheduleUpdate(is_active=False),
            _request_context(other_employee_id),
        )


async def test_delete_existing_leaf_row_is_rejected(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    """Work Schedule Delete Integrity: an uncorrected/leaf row -- including
    the currently-effective row a real payroll deduction calculation would
    read -- can never be deleted. `repo.delete()` is never called: the row
    remains exactly as it was, provable by `get()` still returning it."""
    context = _request_context(employee_id)
    work_schedule = await service.create(_create(employee_id, shift_id), context)

    with pytest.raises(WorkScheduleDeletionNotAllowedError):
        await service.delete(work_schedule.id, context)

    assert await service.get(work_schedule.id, context) is not None


async def test_delete_missing_returns_false(service: WorkScheduleService, employee_id: uuid.UUID):
    assert await service.delete(uuid.uuid4(), _request_context(employee_id)) is False


async def test_delete_target_already_referenced_by_correction_is_rejected(
    service: WorkScheduleService, employee_id: uuid.UUID, shift_id: uuid.UUID
):
    """A row already referenced by another row's `corrects_id` is rejected
    the same clean way as any other row -- not via the raw `IntegrityError`
    the `ON DELETE RESTRICT` FK on `corrects_id` would otherwise surface,
    since `delete()` now never reaches `repo.delete()` for any existing
    row."""
    context = _request_context(employee_id)
    target = await service.create(
        _create(
            employee_id, shift_id, effective_from=date(2026, 1, 1), effective_to=date(2026, 6, 30)
        ),
        context,
    )
    await service.create(
        _create(
            employee_id,
            shift_id,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            corrects_id=target.id,
        ),
        context,
    )

    with pytest.raises(WorkScheduleDeletionNotAllowedError):
        await service.delete(target.id, context)

    assert await service.get(target.id, context) is not None


async def test_delete_denied_for_non_owner(
    service: WorkScheduleService,
    employee_id: uuid.UUID,
    shift_id: uuid.UUID,
    other_employee_id: uuid.UUID,
):
    work_schedule = await service.create(
        _create(employee_id, shift_id), _request_context(employee_id)
    )

    with pytest.raises(WorkScheduleAuthorizationDeniedError):
        await service.delete(work_schedule.id, _request_context(other_employee_id))
