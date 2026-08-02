import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.exc import IntegrityError
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
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.schemas.search import FilterParams, SearchParams

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
def repo(session: AsyncSession) -> DepartmentRepository:
    return DepartmentRepository(session)


@pytest.fixture
def organization_repo(session: AsyncSession) -> OrganizationRepository:
    return OrganizationRepository(session)


@pytest.fixture
async def organization(organization_repo: OrganizationRepository) -> Organization:
    return await organization_repo.create(name="Acme Corp")


@pytest.fixture
async def other_organization(organization_repo: OrganizationRepository) -> Organization:
    return await organization_repo.create(name="Globex Corp")


async def test_create_and_get(repo: DepartmentRepository, organization: Organization):
    department = await repo.create(organization_id=organization.id, code="FIN", name="Finance")

    fetched = await repo.get(department.id)

    assert fetched is not None
    assert fetched.name == "Finance"
    assert fetched.code == "FIN"
    assert fetched.organization_id == organization.id
    assert fetched.parent_id is None


async def test_create_with_parent(repo: DepartmentRepository, organization: Organization):
    parent = await repo.create(organization_id=organization.id, code="FIN", name="Finance")

    child = await repo.create(
        organization_id=organization.id,
        code="FIN-AP",
        name="Accounts Payable",
        parent_id=parent.id,
    )

    fetched = await repo.get(child.id)

    assert fetched is not None
    assert fetched.parent_id == parent.id


async def test_get_missing_returns_none(repo: DepartmentRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: DepartmentRepository, organization: Organization):
    await repo.create(organization_id=organization.id, code="FIN", name="Finance")
    await repo.create(organization_id=organization.id, code="HR", name="HR")

    items = await repo.list()

    assert {"Finance", "HR"}.issubset({item.name for item in items})


async def test_update_existing(repo: DepartmentRepository, organization: Organization):
    department = await repo.create(organization_id=organization.id, code="FIN", name="Before")

    updated = await repo.update(department.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: DepartmentRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_update_organization_id(
    repo: DepartmentRepository, organization: Organization, other_organization: Organization
):
    department = await repo.create(organization_id=organization.id, code="FIN", name="Finance")

    updated = await repo.update(department.id, organization_id=other_organization.id)

    assert updated is not None
    assert updated.organization_id == other_organization.id
    assert await repo.get_by_organization_and_code(organization.id, "FIN") is None
    found_in_new_org = await repo.get_by_organization_and_code(other_organization.id, "FIN")
    assert found_in_new_org is not None
    assert found_in_new_org.id == department.id


async def test_delete_existing(repo: DepartmentRepository, organization: Organization):
    department = await repo.create(organization_id=organization.id, code="FIN", name="To Delete")

    deleted = await repo.delete(department.id)

    assert deleted is True
    assert await repo.get(department.id) is None


async def test_delete_missing_returns_false(repo: DepartmentRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_delete_parent_with_children_is_restricted(
    repo: DepartmentRepository, organization: Organization
):
    parent = await repo.create(organization_id=organization.id, code="FIN", name="Finance")
    await repo.create(
        organization_id=organization.id, code="FIN-AP", name="Accounts Payable", parent_id=parent.id
    )

    with pytest.raises(IntegrityError):
        await repo.delete(parent.id)


async def test_get_by_organization_and_code(repo: DepartmentRepository, organization: Organization):
    department = await repo.create(organization_id=organization.id, code="FIN", name="Finance")

    found = await repo.get_by_organization_and_code(organization.id, "FIN")

    assert found is not None
    assert found.id == department.id
    assert await repo.get_by_organization_and_code(organization.id, "missing") is None


async def test_get_by_organization_and_code_scoped_per_organization(
    repo: DepartmentRepository, organization: Organization, other_organization: Organization
):
    """Same code in two different organizations must not collide."""
    await repo.create(organization_id=organization.id, code="FIN", name="Finance")
    other = await repo.create(
        organization_id=other_organization.id, code="FIN", name="Finance (Globex)"
    )

    found_in_other = await repo.get_by_organization_and_code(other_organization.id, "FIN")

    assert found_in_other is not None
    assert found_in_other.id == other.id


async def test_paginate_returns_total_and_page_slice(
    repo: DepartmentRepository, organization: Organization
):
    for i in range(5):
        await repo.create(organization_id=organization.id, code=f"D-{i}", name=f"Dept {i}")

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: DepartmentRepository, organization: Organization):
    for i in range(3):
        await repo.create(organization_id=organization.id, code=f"D-{i}", name=f"Dept {i}")

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_name(
    repo: DepartmentRepository, organization: Organization
):
    await repo.create(organization_id=organization.id, code="FIN", name="Finance Department")
    await repo.create(organization_id=organization.id, code="HR", name="Human Resources")

    page = await repo.paginate(search=SearchParams(q="finance"))

    assert page.total == 1
    assert page.items[0].name == "Finance Department"


async def test_paginate_search_returns_matching_rows_by_code(
    repo: DepartmentRepository, organization: Organization
):
    await repo.create(organization_id=organization.id, code="FIN-ALPHA", name="Finance")
    await repo.create(organization_id=organization.id, code="HR-BETA", name="HR")

    page = await repo.paginate(search=SearchParams(q="alpha"))

    assert page.total == 1
    assert page.items[0].code == "FIN-ALPHA"


async def test_paginate_no_search_returns_all_rows(
    repo: DepartmentRepository, organization: Organization
):
    await repo.create(organization_id=organization.id, code="FIN", name="Finance")
    await repo.create(organization_id=organization.id, code="HR", name="HR")

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_filters_by_organization_id(
    repo: DepartmentRepository, organization: Organization, other_organization: Organization
):
    await repo.create(organization_id=organization.id, code="FIN", name="Finance")
    await repo.create(organization_id=other_organization.id, code="FIN", name="Finance (Globex)")

    page = await repo.paginate(filters=FilterParams(values={"organization_id": organization.id}))

    assert page.total == 1
    assert page.items[0].organization_id == organization.id


async def test_paginate_filters_by_parent_id(
    repo: DepartmentRepository, organization: Organization
):
    parent = await repo.create(organization_id=organization.id, code="FIN", name="Finance")
    child = await repo.create(
        organization_id=organization.id, code="FIN-AP", name="AP", parent_id=parent.id
    )
    await repo.create(organization_id=organization.id, code="HR", name="HR")

    page = await repo.paginate(filters=FilterParams(values={"parent_id": parent.id}))

    assert page.total == 1
    assert page.items[0].id == child.id


async def test_paginate_without_filters_returns_all_rows(
    repo: DepartmentRepository, organization: Organization, other_organization: Organization
):
    await repo.create(organization_id=organization.id, code="FIN", name="Finance")
    await repo.create(organization_id=other_organization.id, code="FIN", name="Finance (Globex)")

    page = await repo.paginate()

    assert page.total == 2
