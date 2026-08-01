import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.organization import Organization
from eop_api.repositories.employee import EmployeeRepository
from eop_api.repositories.organization import OrganizationRepository

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def connection() -> AsyncGenerator[AsyncConnection]:
    """A single connection with its own transaction, rolled back after the test.

    The tables are real, migration-managed tables shared with the running
    application, so tests must never commit or drop them. Everything a test does
    happens inside one uncommitted transaction that is discarded on teardown.
    """
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    conn = await engine.connect()
    trans = await conn.begin()
    try:
        yield conn
    finally:
        await trans.rollback()
        await conn.close()
        await engine.dispose()


@pytest.fixture
def session(connection: AsyncConnection) -> AsyncSession:
    return async_sessionmaker(bind=connection, expire_on_commit=False)()


@pytest.fixture
def repo(session: AsyncSession) -> EmployeeRepository:
    return EmployeeRepository(session)


@pytest.fixture
async def organization(session: AsyncSession) -> Organization:
    return await OrganizationRepository(session).create(name="Acme Corp")


async def test_create_and_get(repo: EmployeeRepository, organization: Organization):
    employee = await repo.create(
        organization_id=organization.id,
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
    )

    fetched = await repo.get(employee.id)

    assert fetched is not None
    assert fetched.first_name == "Ada"
    assert fetched.last_name == "Lovelace"
    assert fetched.email == "ada@example.com"
    assert fetched.organization_id == organization.id


async def test_get_missing_returns_none(repo: EmployeeRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: EmployeeRepository, organization: Organization):
    await repo.create(
        organization_id=organization.id,
        first_name="Alpha",
        last_name="One",
        email="alpha@example.com",
    )
    await repo.create(
        organization_id=organization.id,
        first_name="Beta",
        last_name="Two",
        email="beta@example.com",
    )

    items = await repo.list()

    assert {"Alpha", "Beta"}.issubset({item.first_name for item in items})


async def test_update_existing(repo: EmployeeRepository, organization: Organization):
    employee = await repo.create(
        organization_id=organization.id,
        first_name="Before",
        last_name="Name",
        email="before@example.com",
    )

    updated = await repo.update(employee.id, first_name="After")

    assert updated is not None
    assert updated.first_name == "After"


async def test_update_missing_returns_none(repo: EmployeeRepository):
    assert await repo.update(uuid.uuid4(), first_name="After") is None


async def test_delete_existing(repo: EmployeeRepository, organization: Organization):
    employee = await repo.create(
        organization_id=organization.id,
        first_name="To",
        last_name="Delete",
        email="delete@example.com",
    )

    deleted = await repo.delete(employee.id)

    assert deleted is True
    assert await repo.get(employee.id) is None


async def test_delete_missing_returns_false(repo: EmployeeRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_exists(repo: EmployeeRepository, organization: Organization):
    employee = await repo.create(
        organization_id=organization.id,
        first_name="Exists",
        last_name="Name",
        email="exists@example.com",
    )

    assert await repo.exists(employee.id) is True
    assert await repo.exists(uuid.uuid4()) is False


async def test_count(repo: EmployeeRepository, organization: Organization):
    await repo.create(
        organization_id=organization.id, first_name="A", last_name="A", email="a@example.com"
    )
    await repo.create(
        organization_id=organization.id, first_name="B", last_name="B", email="b@example.com"
    )
    await repo.create(
        organization_id=organization.id, first_name="C", last_name="C", email="c@example.com"
    )

    assert await repo.count() == 3


async def test_get_by_email(repo: EmployeeRepository, organization: Organization):
    employee = await repo.create(
        organization_id=organization.id,
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
    )

    found = await repo.get_by_email("ada@example.com")

    assert found is not None
    assert found.id == employee.id
    assert await repo.get_by_email("missing@example.com") is None
