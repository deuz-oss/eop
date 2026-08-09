import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.recruitment import ApplicationStatus
from eop_api.db.base import Base
from eop_api.repositories.candidate import CandidateRepository
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.job_requisition import JobRequisitionRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.schemas.application import ApplicationCreate, ApplicationUpdate
from eop_api.services.application import (
    ApplicationService,
    CandidateNotFoundError,
    DuplicateApplicationError,
    InvalidApplicationTransitionError,
    JobRequisitionNotFoundError,
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
            await conn.execute(text("TRUNCATE TABLE organizations, candidates CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> ApplicationService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return ApplicationService(uow_factory)


@pytest.fixture
async def candidate_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        candidate = await CandidateRepository(session).create(
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email="ada@example.com",
        )
        await session.commit()
        return candidate.id


@pytest.fixture
async def job_requisition_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Acme Corp")
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code="ENG", name="Engineering"
        )
        position = await PositionRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code="ENG-1",
            name="Engineer",
        )
        job_requisition = await JobRequisitionRepository(session).create(
            code="REQ-1",
            title="Backend Engineer",
            organization_id=organization.id,
            department_id=department.id,
            position_id=position.id,
            status="open",
        )
        await session.commit()
        return job_requisition.id


@pytest.fixture
async def other_job_requisition_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Globex Corp")
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code="ENG2", name="Engineering"
        )
        position = await PositionRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code="ENG2-1",
            name="Engineer",
        )
        job_requisition = await JobRequisitionRepository(session).create(
            code="REQ-2",
            title="Product Manager",
            organization_id=organization.id,
            department_id=department.id,
            position_id=position.id,
            status="open",
        )
        await session.commit()
        return job_requisition.id


def _create(
    candidate_id: uuid.UUID, job_requisition_id: uuid.UUID, **overrides
) -> ApplicationCreate:
    values = {
        "candidate_id": candidate_id,
        "job_requisition_id": job_requisition_id,
        "applied_date": date(2026, 1, 1),
    }
    values.update(overrides)
    return ApplicationCreate(**values)


async def test_create_and_get(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await service.create(_create(candidate_id, job_requisition_id))

    fetched = await service.get(application.id)

    assert fetched is not None
    assert fetched.status == ApplicationStatus.APPLIED
    assert fetched.candidate_id == candidate_id
    assert fetched.job_requisition_id == job_requisition_id


async def test_create_always_starts_applied(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    """D1: no incoming edge exists into any stage but `APPLIED`
    (`core/recruitment.py`) -- `ApplicationCreate` has no `status` field at
    all, so this is enforced structurally, not just by convention."""
    application = await service.create(_create(candidate_id, job_requisition_id))

    assert application.status == ApplicationStatus.APPLIED


async def test_create_rejects_missing_candidate(
    service: ApplicationService, job_requisition_id: uuid.UUID
):
    with pytest.raises(CandidateNotFoundError):
        await service.create(_create(uuid.uuid4(), job_requisition_id))


async def test_create_rejects_missing_job_requisition(
    service: ApplicationService, candidate_id: uuid.UUID
):
    with pytest.raises(JobRequisitionNotFoundError):
        await service.create(_create(candidate_id, uuid.uuid4()))


async def test_create_rejects_duplicate_application(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    await service.create(_create(candidate_id, job_requisition_id))

    with pytest.raises(DuplicateApplicationError):
        await service.create(
            _create(candidate_id, job_requisition_id, applied_date=date(2026, 1, 2))
        )


async def test_get_missing_returns_none(service: ApplicationService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(
    service: ApplicationService,
    candidate_id: uuid.UUID,
    job_requisition_id: uuid.UUID,
    other_job_requisition_id: uuid.UUID,
):
    a = await service.create(_create(candidate_id, job_requisition_id))
    b = await service.create(_create(candidate_id, other_job_requisition_id))

    items = await service.list()

    assert {a.id, b.id}.issubset({item.id for item in items})


async def test_update_existing(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await service.create(_create(candidate_id, job_requisition_id))

    updated = await service.update(application.id, ApplicationUpdate(applied_date=date(2026, 2, 1)))

    assert updated is not None
    assert updated.applied_date == date(2026, 2, 1)


async def test_update_missing_returns_none(service: ApplicationService):
    assert (
        await service.update(uuid.uuid4(), ApplicationUpdate(applied_date=date(2026, 1, 1))) is None
    )


async def test_update_rejects_duplicate_application(
    service: ApplicationService,
    candidate_id: uuid.UUID,
    job_requisition_id: uuid.UUID,
    other_job_requisition_id: uuid.UUID,
):
    await service.create(_create(candidate_id, job_requisition_id))
    other = await service.create(_create(candidate_id, other_job_requisition_id))

    with pytest.raises(DuplicateApplicationError):
        await service.update(other.id, ApplicationUpdate(job_requisition_id=job_requisition_id))


async def test_delete_existing(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await service.create(_create(candidate_id, job_requisition_id))

    deleted = await service.delete(application.id)

    assert deleted is True
    assert await service.get(application.id) is None


async def test_delete_missing_returns_false(service: ApplicationService):
    assert await service.delete(uuid.uuid4()) is False


# --- Lifecycle transitions (D1, Approved: Standard Funnel) ---


async def test_transition_applied_to_screening(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await service.create(_create(candidate_id, job_requisition_id))

    updated = await service.transition(application.id, ApplicationStatus.SCREENING)

    assert updated is not None
    assert updated.status == ApplicationStatus.SCREENING


async def test_transition_full_forward_path_to_hired(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await service.create(_create(candidate_id, job_requisition_id))

    await service.transition(application.id, ApplicationStatus.SCREENING)
    await service.transition(application.id, ApplicationStatus.INTERVIEWING)
    await service.transition(application.id, ApplicationStatus.OFFERED)
    updated = await service.transition(application.id, ApplicationStatus.HIRED)

    assert updated is not None
    assert updated.status == ApplicationStatus.HIRED


@pytest.mark.parametrize(
    "from_status",
    [
        ApplicationStatus.APPLIED,
        ApplicationStatus.SCREENING,
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.OFFERED,
    ],
)
async def test_transition_to_rejected_from_any_non_terminal_stage(
    service: ApplicationService,
    candidate_id: uuid.UUID,
    job_requisition_id: uuid.UUID,
    from_status: ApplicationStatus,
):
    application = await service.create(_create(candidate_id, job_requisition_id))
    _PATH = {
        ApplicationStatus.APPLIED: [],
        ApplicationStatus.SCREENING: [ApplicationStatus.SCREENING],
        ApplicationStatus.INTERVIEWING: [
            ApplicationStatus.SCREENING,
            ApplicationStatus.INTERVIEWING,
        ],
        ApplicationStatus.OFFERED: [
            ApplicationStatus.SCREENING,
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.OFFERED,
        ],
    }
    for step in _PATH[from_status]:
        await service.transition(application.id, step)

    updated = await service.transition(application.id, ApplicationStatus.REJECTED)

    assert updated is not None
    assert updated.status == ApplicationStatus.REJECTED


async def test_transition_to_withdrawn_from_applied(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await service.create(_create(candidate_id, job_requisition_id))

    updated = await service.transition(application.id, ApplicationStatus.WITHDRAWN)

    assert updated is not None
    assert updated.status == ApplicationStatus.WITHDRAWN


async def test_transition_rejects_skipping_a_stage(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await service.create(_create(candidate_id, job_requisition_id))

    with pytest.raises(InvalidApplicationTransitionError):
        await service.transition(application.id, ApplicationStatus.INTERVIEWING)


async def test_transition_rejects_backward_move(
    service: ApplicationService, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await service.create(_create(candidate_id, job_requisition_id))
    await service.transition(application.id, ApplicationStatus.SCREENING)

    with pytest.raises(InvalidApplicationTransitionError):
        await service.transition(application.id, ApplicationStatus.APPLIED)


@pytest.mark.parametrize(
    "terminal_status",
    [ApplicationStatus.HIRED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN],
)
async def test_transition_rejects_leaving_a_terminal_state(
    service: ApplicationService,
    candidate_id: uuid.UUID,
    job_requisition_id: uuid.UUID,
    terminal_status: ApplicationStatus,
):
    application = await service.create(_create(candidate_id, job_requisition_id))
    if terminal_status == ApplicationStatus.HIRED:
        for step in (
            ApplicationStatus.SCREENING,
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.OFFERED,
        ):
            await service.transition(application.id, step)
    await service.transition(application.id, terminal_status)

    with pytest.raises(InvalidApplicationTransitionError):
        await service.transition(application.id, ApplicationStatus.APPLIED)


async def test_transition_missing_returns_none(service: ApplicationService):
    assert await service.transition(uuid.uuid4(), ApplicationStatus.SCREENING) is None
