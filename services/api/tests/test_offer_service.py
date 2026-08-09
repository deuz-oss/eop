import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.repositories.application import ApplicationRepository
from eop_api.repositories.candidate import CandidateRepository
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.job_requisition import JobRequisitionRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.schemas.offer import OfferCreate, OfferUpdate
from eop_api.services.offer import ApplicationNotFoundError, OfferService
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
def service(session_factory: Callable[[], AsyncSession]) -> OfferService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return OfferService(uow_factory)


@pytest.fixture
async def application_id(session_factory: Callable[[], AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        candidate = await CandidateRepository(session).create(
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email="ada@example.com",
        )
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
        application = await ApplicationRepository(session).create(
            candidate_id=candidate.id,
            job_requisition_id=job_requisition.id,
            status="applied",
            applied_date=date(2026, 1, 1),
        )
        await session.commit()
        return application.id


def _create(application_id: uuid.UUID, **overrides) -> OfferCreate:
    values = {"application_id": application_id, "issued_date": date(2026, 3, 1)}
    values.update(overrides)
    return OfferCreate(**values)


async def test_create_and_get(service: OfferService, application_id: uuid.UUID):
    offer = await service.create(_create(application_id))

    fetched = await service.get(offer.id)

    assert fetched is not None
    assert fetched.application_id == application_id


async def test_create_rejects_missing_application(service: OfferService):
    with pytest.raises(ApplicationNotFoundError):
        await service.create(_create(uuid.uuid4()))


async def test_get_missing_returns_none(service: OfferService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: OfferService, application_id: uuid.UUID):
    first = await service.create(_create(application_id))
    second = await service.create(_create(application_id, issued_date=date(2026, 3, 15)))

    items = await service.list()

    assert {first.id, second.id}.issubset({item.id for item in items})


async def test_update_existing(service: OfferService, application_id: uuid.UUID):
    offer = await service.create(_create(application_id))

    updated = await service.update(offer.id, OfferUpdate(notes="Revised"))

    assert updated is not None
    assert updated.notes == "Revised"


async def test_update_missing_returns_none(service: OfferService):
    assert await service.update(uuid.uuid4(), OfferUpdate(notes="x")) is None


async def test_update_rejects_missing_application(service: OfferService, application_id: uuid.UUID):
    offer = await service.create(_create(application_id))

    with pytest.raises(ApplicationNotFoundError):
        await service.update(offer.id, OfferUpdate(application_id=uuid.uuid4()))


async def test_delete_existing(service: OfferService, application_id: uuid.UUID):
    offer = await service.create(_create(application_id))

    deleted = await service.delete(offer.id)

    assert deleted is True
    assert await service.get(offer.id) is None


async def test_delete_missing_returns_false(service: OfferService):
    assert await service.delete(uuid.uuid4()) is False
