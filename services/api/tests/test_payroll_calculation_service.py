import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.payroll import PayrollRunStatus
from eop_api.db.base import Base
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
from eop_api.repositories.overtime_request import OvertimeRequestRepository
from eop_api.repositories.payroll_run import PayrollRunRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.allowance import AllowanceCreate, AllowanceUpdate
from eop_api.schemas.compensation import CompensationCreate, CompensationUpdate
from eop_api.schemas.deduction import DeductionCreate
from eop_api.schemas.deduction_type import DeductionTypeCreate
from eop_api.schemas.payroll_statutory_parameter import PayrollStatutoryParameterCreate
from eop_api.services.allowance import AllowanceService
from eop_api.services.compensation import CompensationService
from eop_api.services.deduction import DeductionService
from eop_api.services.deduction_type import DeductionTypeService
from eop_api.services.effective_dating_evaluator import AmbiguousEffectiveStateError
from eop_api.services.employee_context import EmployeeContext, RequestContext
from eop_api.services.payroll_calculation import (
    CompensationCurrencyMismatchError,
    CompensationInactiveError,
    CompensationNotFoundError,
    DuplicatePayslipError,
    PayrollCalculationService,
    PayrollRunAlreadyCompletedError,
    PayrollRunMissingPeriodError,
)
from eop_api.services.payroll_run import PayrollRunService
from eop_api.services.payroll_statutory_parameter import PayrollStatutoryParameterService
from eop_api.services.payslip import (
    PayrollRunCompletedError,
    PayrollRunNotFoundError,
    PayslipService,
)
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
                    "job_grades, employment_types, employment_statuses, shifts, "
                    "payroll_runs, deduction_types, payroll_statutory_parameters CASCADE"
                )
            )
        await engine.dispose()


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], AsyncSession],
) -> Callable[[], SQLAlchemyUnitOfWork]:
    return lambda: SQLAlchemyUnitOfWork(session_factory)  # noqa: E731


@pytest.fixture
def service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> PayrollCalculationService:
    return PayrollCalculationService(uow_factory=uow_factory)


@pytest.fixture
def compensation_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> CompensationService:
    return CompensationService(uow_factory)


@pytest.fixture
def allowance_service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> AllowanceService:
    return AllowanceService(uow_factory)


@pytest.fixture
def deduction_type_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> DeductionTypeService:
    return DeductionTypeService(uow_factory)


@pytest.fixture
def deduction_service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> DeductionService:
    return DeductionService(uow_factory)


@pytest.fixture
def parameter_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> PayrollStatutoryParameterService:
    return PayrollStatutoryParameterService(uow_factory)


@pytest.fixture
def payslip_service(uow_factory: Callable[[], SQLAlchemyUnitOfWork]) -> PayslipService:
    return PayslipService(uow_factory)


@pytest.fixture
def payroll_run_service(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> PayrollRunService:
    return PayrollRunService(uow_factory)


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


@pytest.fixture
async def payroll_run_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        payroll_run = await PayrollRunRepository(session).create(
            code="RUN-001",
            name="First Run",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            currency="IDR",
        )
        await session.commit()
        return payroll_run.id


def _request_context(employee_id: uuid.UUID) -> RequestContext:
    """A `RequestContext` built entirely in memory, scoped to `employee_id`.

    Mirrors `test_compensation_service.py`'s `_request_context` helper --
    used here only so this file's own direct `compensation_service.create`/
    `.update`/`allowance_service.create` fixture calls (setup for
    `PayrollCalculationService`, not `PayrollCalculationService` itself,
    which always calls internal services with `request_context=None`)
    satisfy those services' now-required `request_context` parameter as
    the resource's owner.
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


async def _add_active_compensation(
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    *,
    amount: Decimal = Decimal("5000000.00"),
) -> None:
    await compensation_service.create(
        CompensationCreate(
            employee_id=employee_id,
            base_salary_amount=amount,
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(employee_id),
    )


# ---------------------------------------------------------------------------
# Base-tier behavior (Iteration 1-3), unchanged by Advanced Payroll
# ---------------------------------------------------------------------------


async def test_calculate_sets_net_equal_to_gross_with_zero_configuration(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    """No allowance, overtime, deduction, or statutory parameter configured
    -- gross = net = base salary, exactly as Iteration 1-3 already shipped.
    Advanced Payroll must not require any configuration before a basic
    calculation succeeds."""
    await _add_active_compensation(compensation_service, employee_id)

    payslip = await service.calculate(payroll_run_id, employee_id)

    assert payslip.gross_salary_amount == Decimal("5000000.00")
    assert payslip.net_salary_amount == Decimal("5000000.00")
    assert payslip.gross_salary_currency == "IDR"
    assert payslip.net_salary_currency == "IDR"
    assert payslip.employee_id == employee_id
    assert payslip.payroll_run_id == payroll_run_id
    assert len(payslip.line_items) == 1
    assert payslip.line_items[0].component_type == "BASE_SALARY"


async def test_calculate_rejects_missing_compensation(
    service: PayrollCalculationService, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
):
    with pytest.raises(CompensationNotFoundError):
        await service.calculate(payroll_run_id, employee_id)


async def test_calculate_rejects_inactive_compensation(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    compensation = await compensation_service.create(
        CompensationCreate(
            employee_id=employee_id,
            base_salary_amount=Decimal("5000000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(employee_id),
    )
    await compensation_service.update(
        compensation.id, CompensationUpdate(is_active=False), _request_context(employee_id)
    )

    with pytest.raises(CompensationInactiveError):
        await service.calculate(payroll_run_id, employee_id)


async def test_calculate_rejects_duplicate_payslip(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await service.calculate(payroll_run_id, employee_id)

    with pytest.raises(DuplicatePayslipError):
        await service.calculate(payroll_run_id, employee_id)


async def test_calculate_batch_processes_eligible_employees(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    payroll_run_service: PayrollRunService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await _add_active_compensation(compensation_service, other_employee_id)

    payslips = await service.calculate_batch(payroll_run_id)

    assert {p.employee_id for p in payslips} == {employee_id, other_employee_id}
    for payslip in payslips:
        assert payslip.gross_salary_amount == Decimal("5000000.00")
        assert payslip.net_salary_amount == Decimal("5000000.00")

    payroll_run = await payroll_run_service.get(payroll_run_id)
    assert payroll_run is not None
    assert payroll_run.status == PayrollRunStatus.COMPLETED


async def test_calculate_batch_excludes_inactive_compensation(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    inactive = await compensation_service.create(
        CompensationCreate(
            employee_id=other_employee_id,
            base_salary_amount=Decimal("3000000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(other_employee_id),
    )
    await compensation_service.update(
        inactive.id, CompensationUpdate(is_active=False), _request_context(other_employee_id)
    )

    payslips = await service.calculate_batch(payroll_run_id)

    assert {p.employee_id for p in payslips} == {employee_id}


async def test_calculate_batch_rejects_missing_payroll_run(
    service: PayrollCalculationService, employee_id: uuid.UUID
):
    with pytest.raises(PayrollRunNotFoundError):
        await service.calculate_batch(uuid.uuid4())


async def test_calculate_batch_rejects_already_completed_run(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await service.calculate_batch(payroll_run_id)

    with pytest.raises(PayrollRunAlreadyCompletedError):
        await service.calculate_batch(payroll_run_id)


async def test_calculate_rejects_completed_run(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await service.calculate_batch(payroll_run_id)

    with pytest.raises(PayrollRunAlreadyCompletedError):
        await service.calculate(payroll_run_id, employee_id)


async def test_calculate_rejects_run_with_no_period_configured(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    """A legacy Iteration 1-3 PayrollRun (no period/currency, per
    `models/payroll_run.py`'s nullable-for-history-only columns) cannot be
    calculated by Advanced Payroll."""
    await _add_active_compensation(compensation_service, employee_id)
    async with session_factory() as session:
        legacy_run = await PayrollRunRepository(session).create(code="LEGACY-001", name="Legacy")
        await session.commit()
        legacy_run_id = legacy_run.id

    with pytest.raises(PayrollRunMissingPeriodError):
        await service.calculate(legacy_run_id, employee_id)


# ---------------------------------------------------------------------------
# D9/E5 -- rerun before completion, immutability after completion
# ---------------------------------------------------------------------------


async def test_calculate_batch_recovers_from_partial_failure(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    payroll_run_service: PayrollRunService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    """D9's real-world target: if `calculate_batch` fails partway (here,
    genuinely ambiguous Compensation data for one employee), the run is
    left `PROCESSING` with partial Payslips -- not permanently stuck, per
    `implementation-plan.md` §1.1's own "stuck in PROCESSING" finding about
    the pre-Advanced-Payroll behavior. A second `calculate_batch` call
    clears the partial results and completes successfully once the data is
    fixed.
    """
    await _add_active_compensation(compensation_service, employee_id)
    # Two unrelated (no correction relation), overlapping Compensation rows
    # for other_employee_id -- genuine ambiguity, constructed directly via
    # the repository since CompensationService.create's own O1 overlap
    # validation would reject this (mirrors
    # test_compensation_service.py::test_get_by_employee_raises_on_unrelated_ambiguous_rows).
    async with session_factory() as session:
        repo = CompensationRepository(session)
        await repo.create(
            employee_id=other_employee_id,
            base_salary_amount=Decimal("3000000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        await repo.create(
            employee_id=other_employee_id,
            base_salary_amount=Decimal("3200000.00"),
            base_salary_currency="IDR",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        await session.commit()

    with pytest.raises(AmbiguousEffectiveStateError):
        await service.calculate_batch(payroll_run_id)

    stuck_run = await payroll_run_service.get(payroll_run_id)
    assert stuck_run is not None
    assert stuck_run.status == PayrollRunStatus.PROCESSING

    # Fix the ambiguity, then rerun -- the partial run is not stuck.
    async with session_factory() as session:
        repo = CompensationRepository(session)
        rows = await repo.list_by_employee_id(other_employee_id)
        await repo.delete(rows[1].id)
        await session.commit()

    payslips = await service.calculate_batch(payroll_run_id)

    assert {p.employee_id for p in payslips} == {employee_id, other_employee_id}
    completed_run = await payroll_run_service.get(payroll_run_id)
    assert completed_run is not None
    assert completed_run.status == PayrollRunStatus.COMPLETED


async def test_delete_by_payroll_run_clears_payslips_before_completion(
    payslip_service: PayslipService,
    compensation_service: CompensationService,
    service: PayrollCalculationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    """Exercises the internal rerun mechanism directly: while a run is not
    `COMPLETED`, `delete_by_payroll_run` clears its Payslips so
    `calculate_batch` can safely recompute from scratch."""
    await _add_active_compensation(compensation_service, employee_id)
    payslip = await service.calculate(payroll_run_id, employee_id)

    deleted_count = await payslip_service.delete_by_payroll_run(payroll_run_id)

    assert deleted_count == 1
    assert (
        await payslip_service.get_by_employee_and_payroll_run(employee_id, payroll_run_id) is None
    )
    # Recompute succeeds -- no DuplicatePayslipError, since the prior row is gone.
    recomputed = await service.calculate(payroll_run_id, employee_id)
    assert recomputed.id != payslip.id


async def test_delete_by_payroll_run_rejects_completed_run(
    payslip_service: PayslipService,
    compensation_service: CompensationService,
    service: PayrollCalculationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await service.calculate_batch(payroll_run_id)

    with pytest.raises(PayrollRunCompletedError):
        await payslip_service.delete_by_payroll_run(payroll_run_id)


# ---------------------------------------------------------------------------
# D8/E7 -- one currency per PayrollRun
# ---------------------------------------------------------------------------


async def test_calculate_rejects_currency_mismatch(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    """`payroll_run_id` fixture is IDR-denominated; a USD Compensation must
    be rejected outright, not silently converted."""
    await compensation_service.create(
        CompensationCreate(
            employee_id=employee_id,
            base_salary_amount=Decimal("5000.00"),
            base_salary_currency="USD",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(employee_id),
    )

    with pytest.raises(CompensationCurrencyMismatchError):
        await service.calculate(payroll_run_id, employee_id)


async def test_calculate_batch_excludes_currency_mismatched_employee(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    other_employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await compensation_service.create(
        CompensationCreate(
            employee_id=other_employee_id,
            base_salary_amount=Decimal("5000.00"),
            base_salary_currency="USD",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(other_employee_id),
    )

    payslips = await service.calculate_batch(payroll_run_id)

    assert {p.employee_id for p in payslips} == {employee_id}


# ---------------------------------------------------------------------------
# D6 -- Allowance (Compensation-owned), consumed read-only by Payroll
# ---------------------------------------------------------------------------


async def test_calculate_includes_active_allowances(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    allowance_service: AllowanceService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await allowance_service.create(
        AllowanceCreate(
            employee_id=employee_id,
            allowance_type="TRANSPORT",
            allowance_amount=Decimal("500000.00"),
            allowance_currency="IDR",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(employee_id),
    )
    await allowance_service.create(
        AllowanceCreate(
            employee_id=employee_id,
            allowance_type="MEAL",
            allowance_amount=Decimal("300000.00"),
            allowance_currency="IDR",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(employee_id),
    )

    payslip = await service.calculate(payroll_run_id, employee_id)

    assert payslip.gross_salary_amount == Decimal("5800000.00")
    assert payslip.net_salary_amount == Decimal("5800000.00")
    line_item_types = sorted(item.component_type for item in payslip.line_items)
    assert line_item_types == ["ALLOWANCE", "ALLOWANCE", "BASE_SALARY"]


async def test_calculate_excludes_inactive_allowance(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    allowance_service: AllowanceService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    allowance = await allowance_service.create(
        AllowanceCreate(
            employee_id=employee_id,
            allowance_type="TRANSPORT",
            allowance_amount=Decimal("500000.00"),
            allowance_currency="IDR",
            effective_from=date(2026, 1, 1),
        ),
        _request_context(employee_id),
    )
    await allowance_service.update(
        allowance.id, AllowanceUpdate(is_active=False), _request_context(employee_id)
    )

    payslip = await service.calculate(payroll_run_id, employee_id)

    assert payslip.gross_salary_amount == Decimal("5000000.00")


# ---------------------------------------------------------------------------
# D4 -- Payroll owns overtime monetary conversion
# ---------------------------------------------------------------------------


async def test_calculate_includes_overtime_pay(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    parameter_service: PayrollStatutoryParameterService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    await _add_active_compensation(compensation_service, employee_id, amount=Decimal("4400000.00"))
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STANDARD_WORKING_DAYS_PER_MONTH",
            value=Decimal("22"),
            effective_from=date(2026, 1, 1),
        )
    )
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STANDARD_DAILY_HOURS", value=Decimal("8"), effective_from=date(2026, 1, 1)
        )
    )
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="OVERTIME_MULTIPLIER_WEEKDAY",
            value=Decimal("1.5"),
            effective_from=date(2026, 1, 1),
        )
    )
    # daily_rate = 4,400,000 / 22 = 200,000; hourly_rate = 200,000 / 8 = 25,000
    async with session_factory() as session:
        await OvertimeRequestRepository(session).create(
            employee_id=employee_id,
            overtime_date=date(2026, 1, 15),
            start_time=time(18, 0),
            end_time=time(20, 0),
            status="approved",
        )
        await session.commit()

    payslip = await service.calculate(payroll_run_id, employee_id)

    # 2 hours * 25,000 * 1.5 = 75,000
    overtime_items = [item for item in payslip.line_items if item.component_type == "OVERTIME"]
    assert len(overtime_items) == 1
    assert overtime_items[0].line_amount == Decimal("75000.00")
    assert payslip.gross_salary_amount == Decimal("4475000.00")


async def test_calculate_ignores_unapproved_overtime(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    await _add_active_compensation(compensation_service, employee_id)
    async with session_factory() as session:
        await OvertimeRequestRepository(session).create(
            employee_id=employee_id,
            overtime_date=date(2026, 1, 15),
            start_time=time(18, 0),
            end_time=time(20, 0),
            status="pending",
        )
        await session.commit()

    payslip = await service.calculate(payroll_run_id, employee_id)

    assert payslip.gross_salary_amount == Decimal("5000000.00")
    assert not any(item.component_type == "OVERTIME" for item in payslip.line_items)


async def test_calculate_ignores_overtime_outside_period(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    parameter_service: PayrollStatutoryParameterService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
):
    await _add_active_compensation(compensation_service, employee_id)
    async with session_factory() as session:
        await OvertimeRequestRepository(session).create(
            employee_id=employee_id,
            overtime_date=date(2026, 2, 1),  # outside the January run's period
            start_time=time(18, 0),
            end_time=time(20, 0),
            status="approved",
        )
        await session.commit()

    payslip = await service.calculate(payroll_run_id, employee_id)

    assert not any(item.component_type == "OVERTIME" for item in payslip.line_items)


# ---------------------------------------------------------------------------
# D7 -- explicit, per-run, non-statutory Deduction records
# ---------------------------------------------------------------------------


async def test_calculate_includes_explicit_deductions(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    deduction_type_service: DeductionTypeService,
    deduction_service: DeductionService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    deduction_type = await deduction_type_service.create(
        DeductionTypeCreate(code="LOAN", name="Loan Repayment")
    )
    await deduction_service.create(
        DeductionCreate(
            employee_id=employee_id,
            deduction_type_id=deduction_type.id,
            payroll_run_id=payroll_run_id,
            deduction_amount=Decimal("100000.00"),
            deduction_currency="IDR",
        )
    )

    payslip = await service.calculate(payroll_run_id, employee_id)

    assert payslip.gross_salary_amount == Decimal("5000000.00")
    assert payslip.net_salary_amount == Decimal("4900000.00")
    assert any(item.component_type == "NON_STATUTORY_DEDUCTION" for item in payslip.line_items)


# ---------------------------------------------------------------------------
# D2/E4 -- statutory tax, configurable data, code-based engine
# ---------------------------------------------------------------------------


async def test_calculate_applies_configured_statutory_tax(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    parameter_service: PayrollStatutoryParameterService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)
    await parameter_service.create(
        PayrollStatutoryParameterCreate(
            key="STATUTORY_TAX_RATE", value=Decimal("0.05"), effective_from=date(2026, 1, 1)
        )
    )

    payslip = await service.calculate(payroll_run_id, employee_id)

    assert payslip.gross_salary_amount == Decimal("5000000.00")
    assert payslip.net_salary_amount == Decimal("4750000.00")
    tax_items = [
        item for item in payslip.line_items if item.component_type == "STATUTORY_DEDUCTION"
    ]
    assert len(tax_items) == 1
    assert tax_items[0].line_amount == Decimal("250000.00")


async def test_calculate_omits_tax_line_item_when_unconfigured(
    service: PayrollCalculationService,
    compensation_service: CompensationService,
    employee_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
):
    await _add_active_compensation(compensation_service, employee_id)

    payslip = await service.calculate(payroll_run_id, employee_id)

    assert not any(item.component_type == "STATUTORY_DEDUCTION" for item in payslip.line_items)
