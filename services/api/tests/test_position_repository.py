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
from eop_api.models.department import Department
from eop_api.models.organization import Organization
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
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
def repo(session: AsyncSession) -> PositionRepository:
    return PositionRepository(session)


@pytest.fixture
def organization_repo(session: AsyncSession) -> OrganizationRepository:
    return OrganizationRepository(session)


@pytest.fixture
def department_repo(session: AsyncSession) -> DepartmentRepository:
    return DepartmentRepository(session)


@pytest.fixture
async def organization(organization_repo: OrganizationRepository) -> Organization:
    return await organization_repo.create(name="Acme Corp")


@pytest.fixture
async def other_organization(organization_repo: OrganizationRepository) -> Organization:
    return await organization_repo.create(name="Globex Corp")


@pytest.fixture
async def department(
    department_repo: DepartmentRepository, organization: Organization
) -> Department:
    return await department_repo.create(
        organization_id=organization.id, code="ENG", name="Engineering"
    )


@pytest.fixture
async def other_department(
    department_repo: DepartmentRepository, organization: Organization
) -> Department:
    return await department_repo.create(organization_id=organization.id, code="HR", name="HR")


async def test_create_and_get(
    repo: PositionRepository, organization: Organization, department: Department
):
    position = await repo.create(
        organization_id=organization.id,
        department_id=department.id,
        code="SWE",
        name="Software Engineer",
    )

    fetched = await repo.get(position.id)

    assert fetched is not None
    assert fetched.name == "Software Engineer"
    assert fetched.code == "SWE"
    assert fetched.organization_id == organization.id
    assert fetched.department_id == department.id
    assert fetched.description is None


async def test_get_missing_returns_none(repo: PositionRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(
    repo: PositionRepository, organization: Organization, department: Department
):
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="SSWE", name="Senior"
    )

    items = await repo.list()

    assert {"Engineer", "Senior"}.issubset({item.name for item in items})


async def test_update_existing(
    repo: PositionRepository, organization: Organization, department: Department
):
    position = await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Before"
    )

    updated = await repo.update(position.id, name="After")

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(repo: PositionRepository):
    assert await repo.update(uuid.uuid4(), name="After") is None


async def test_update_organization_id(
    repo: PositionRepository,
    organization: Organization,
    other_organization: Organization,
    department: Department,
):
    position = await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )

    updated = await repo.update(position.id, organization_id=other_organization.id)

    assert updated is not None
    assert updated.organization_id == other_organization.id
    assert await repo.get_by_organization_and_code(organization.id, "SWE") is None
    found_in_new_org = await repo.get_by_organization_and_code(other_organization.id, "SWE")
    assert found_in_new_org is not None
    assert found_in_new_org.id == position.id


async def test_delete_existing(
    repo: PositionRepository, organization: Organization, department: Department
):
    position = await repo.create(
        organization_id=organization.id,
        department_id=department.id,
        code="SWE",
        name="To Delete",
    )

    deleted = await repo.delete(position.id)

    assert deleted is True
    assert await repo.get(position.id) is None


async def test_delete_missing_returns_false(repo: PositionRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_delete_department_with_positions_is_restricted(
    repo: PositionRepository, department_repo: DepartmentRepository, organization: Organization
):
    department = await department_repo.create(
        organization_id=organization.id, code="TEMP", name="Temp"
    )
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )

    with pytest.raises(IntegrityError):
        await department_repo.delete(department.id)


async def test_delete_organization_with_positions_is_restricted(
    repo: PositionRepository,
    organization_repo: OrganizationRepository,
    organization: Organization,
    department: Department,
):
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )

    with pytest.raises(IntegrityError):
        await organization_repo.delete(organization.id)


async def test_get_by_organization_and_code(
    repo: PositionRepository, organization: Organization, department: Department
):
    position = await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )

    found = await repo.get_by_organization_and_code(organization.id, "SWE")

    assert found is not None
    assert found.id == position.id
    assert await repo.get_by_organization_and_code(organization.id, "missing") is None


async def test_get_by_organization_and_code_scoped_per_organization(
    repo: PositionRepository,
    organization: Organization,
    other_organization: Organization,
    department: Department,
    department_repo: DepartmentRepository,
):
    """Same code in two different organizations must not collide."""
    other_department = await department_repo.create(
        organization_id=other_organization.id, code="ENG", name="Engineering (Globex)"
    )
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )
    other = await repo.create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="SWE",
        name="Engineer (Globex)",
    )

    found_in_other = await repo.get_by_organization_and_code(other_organization.id, "SWE")

    assert found_in_other is not None
    assert found_in_other.id == other.id


async def test_paginate_returns_total_and_page_slice(
    repo: PositionRepository, organization: Organization, department: Department
):
    for i in range(5):
        await repo.create(
            organization_id=organization.id,
            department_id=department.id,
            code=f"P-{i}",
            name=f"Position {i}",
        )

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(
    repo: PositionRepository, organization: Organization, department: Department
):
    for i in range(3):
        await repo.create(
            organization_id=organization.id,
            department_id=department.id,
            code=f"P-{i}",
            name=f"Position {i}",
        )

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_returns_matching_rows_by_name(
    repo: PositionRepository, organization: Organization, department: Department
):
    await repo.create(
        organization_id=organization.id,
        department_id=department.id,
        code="SWE",
        name="Software Engineer",
    )
    await repo.create(
        organization_id=organization.id,
        department_id=department.id,
        code="HRM",
        name="HR Manager",
    )

    page = await repo.paginate(search=SearchParams(q="software"))

    assert page.total == 1
    assert page.items[0].name == "Software Engineer"


async def test_paginate_search_returns_matching_rows_by_code(
    repo: PositionRepository, organization: Organization, department: Department
):
    await repo.create(
        organization_id=organization.id,
        department_id=department.id,
        code="SWE-ALPHA",
        name="Engineer",
    )
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="HR-BETA", name="HR"
    )

    page = await repo.paginate(search=SearchParams(q="alpha"))

    assert page.total == 1
    assert page.items[0].code == "SWE-ALPHA"


async def test_paginate_no_search_returns_all_rows(
    repo: PositionRepository, organization: Organization, department: Department
):
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="HR", name="HR"
    )

    page = await repo.paginate(search=None)

    assert page.total == 2


async def test_paginate_filters_by_organization_id(
    repo: PositionRepository,
    organization: Organization,
    other_organization: Organization,
    department: Department,
    department_repo: DepartmentRepository,
):
    other_department = await department_repo.create(
        organization_id=other_organization.id, code="ENG", name="Engineering (Globex)"
    )
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )
    await repo.create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="SWE",
        name="Engineer (Globex)",
    )

    page = await repo.paginate(filters=FilterParams(values={"organization_id": organization.id}))

    assert page.total == 1
    assert page.items[0].organization_id == organization.id


async def test_paginate_filters_by_department_id(
    repo: PositionRepository,
    organization: Organization,
    department: Department,
    other_department: Department,
):
    position = await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )
    await repo.create(
        organization_id=organization.id,
        department_id=other_department.id,
        code="HRM",
        name="HR Manager",
    )

    page = await repo.paginate(filters=FilterParams(values={"department_id": department.id}))

    assert page.total == 1
    assert page.items[0].id == position.id


async def test_paginate_without_filters_returns_all_rows(
    repo: PositionRepository,
    organization: Organization,
    other_organization: Organization,
    department: Department,
    department_repo: DepartmentRepository,
):
    other_department = await department_repo.create(
        organization_id=other_organization.id, code="ENG", name="Engineering (Globex)"
    )
    await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )
    await repo.create(
        organization_id=other_organization.id,
        department_id=other_department.id,
        code="SWE",
        name="Engineer (Globex)",
    )

    page = await repo.paginate()

    assert page.total == 2


async def test_create_rejects_department_in_different_organization_at_service_layer_only(
    repo: PositionRepository, organization: Organization, department: Department
):
    """The FK only requires the department to exist -- it does not check that
    it belongs to the same organization. That invariant is enforced by
    `PositionService`, not the database, so the repository allows it."""
    position = await repo.create(
        organization_id=organization.id, department_id=department.id, code="SWE", name="Engineer"
    )

    assert position.department_id == department.id


async def test_create_rejects_missing_department(
    repo: PositionRepository, organization: Organization
):
    with pytest.raises(IntegrityError):
        await repo.create(
            organization_id=organization.id,
            department_id=uuid.uuid4(),
            code="SWE",
            name="Engineer",
        )
