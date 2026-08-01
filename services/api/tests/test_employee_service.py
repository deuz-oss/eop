import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.organization import Organization
from eop_api.repositories.organization import OrganizationRepository
from eop_api.schemas.employee import EmployeeCreate, EmployeeUpdate
from eop_api.services.employee import (
    DuplicateEmployeeEmailError,
    EmployeeService,
    OrganizationNotFoundError,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) tables.

    Unlike the repository tests, the service commits internally (it owns the
    transaction boundary), so rows are truncated after each test instead of
    relying on a rolled-back transaction.
    """
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: Callable[[], AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

    try:
        yield factory
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE organizations CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> EmployeeService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return EmployeeService(uow_factory)


@pytest.fixture
async def organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        org = await OrganizationRepository(session).create(name="Acme Corp")
        await session.commit()
        session.expunge(org)
        return org


async def test_create_and_get(service: EmployeeService, organization: Organization):
    employee = await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
    )

    fetched = await service.get(employee.id)

    assert fetched is not None
    assert fetched.first_name == "Ada"
    assert fetched.email == "ada@example.com"


async def test_create_rejects_missing_organization(service: EmployeeService):
    with pytest.raises(OrganizationNotFoundError):
        await service.create(
            EmployeeCreate(
                organization_id=uuid.uuid4(),
                first_name="Ada",
                last_name="Lovelace",
                email="ada@example.com",
            )
        )


async def test_create_rejects_duplicate_email(service: EmployeeService, organization: Organization):
    await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
    )

    with pytest.raises(DuplicateEmployeeEmailError):
        await service.create(
            EmployeeCreate(
                organization_id=organization.id,
                first_name="Ada 2",
                last_name="Lovelace",
                email="ada@example.com",
            )
        )


async def test_get_missing_returns_none(service: EmployeeService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: EmployeeService, organization: Organization):
    await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="Alpha",
            last_name="One",
            email="alpha@example.com",
        )
    )
    await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="Beta",
            last_name="Two",
            email="beta@example.com",
        )
    )

    items = await service.list()

    assert {"Alpha", "Beta"}.issubset({item.first_name for item in items})


async def test_update_existing(service: EmployeeService, organization: Organization):
    employee = await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="Before",
            last_name="Name",
            email="before@example.com",
        )
    )

    updated = await service.update(employee.id, EmployeeUpdate(first_name="After"))

    assert updated is not None
    assert updated.first_name == "After"


async def test_update_missing_returns_none(service: EmployeeService):
    assert await service.update(uuid.uuid4(), EmployeeUpdate(first_name="After")) is None


async def test_update_rejects_missing_organization(
    service: EmployeeService, organization: Organization
):
    employee = await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
    )

    with pytest.raises(OrganizationNotFoundError):
        await service.update(employee.id, EmployeeUpdate(organization_id=uuid.uuid4()))


async def test_update_rejects_duplicate_email(service: EmployeeService, organization: Organization):
    await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
    )
    other = await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="Zeus",
            last_name="Olympus",
            email="zeus@example.com",
        )
    )

    with pytest.raises(DuplicateEmployeeEmailError):
        await service.update(other.id, EmployeeUpdate(email="ada@example.com"))


async def test_update_allows_unchanged_email(service: EmployeeService, organization: Organization):
    employee = await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
    )

    updated = await service.update(
        employee.id, EmployeeUpdate(email="ada@example.com", first_name="Ada Renamed")
    )

    assert updated is not None
    assert updated.first_name == "Ada Renamed"


async def test_delete_existing(service: EmployeeService, organization: Organization):
    employee = await service.create(
        EmployeeCreate(
            organization_id=organization.id,
            first_name="To",
            last_name="Delete",
            email="delete@example.com",
        )
    )

    deleted = await service.delete(employee.id)

    assert deleted is True
    assert await service.get(employee.id) is None


async def test_delete_missing_returns_false(service: EmployeeService):
    assert await service.delete(uuid.uuid4()) is False
