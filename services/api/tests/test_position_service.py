import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.department import Department
from eop_api.models.organization import Organization
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.position import PositionCreate, PositionUpdate
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.position import (
    DepartmentNotFoundError,
    DepartmentOrganizationMismatchError,
    DuplicatePositionCodeError,
    OrganizationNotFoundError,
    PositionService,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `positions` table.

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
            await conn.execute(text("TRUNCATE TABLE positions, departments, organizations CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> PositionService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return PositionService(uow_factory)


@pytest.fixture
async def organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Acme Corp")
        await session.commit()
        session.expunge(organization)
        return organization


@pytest.fixture
async def other_organization(session_factory: Callable[[], AsyncSession]) -> Organization:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Globex Corp")
        await session.commit()
        session.expunge(organization)
        return organization


@pytest.fixture
async def department(
    session_factory: Callable[[], AsyncSession], organization: Organization
) -> Department:
    async with session_factory() as session:
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code="ENG", name="Engineering"
        )
        await session.commit()
        session.expunge(department)
        return department


@pytest.fixture
async def other_department(
    session_factory: Callable[[], AsyncSession], organization: Organization
) -> Department:
    async with session_factory() as session:
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code="HR", name="HR"
        )
        await session.commit()
        session.expunge(department)
        return department


@pytest.fixture
async def department_in_other_organization(
    session_factory: Callable[[], AsyncSession], other_organization: Organization
) -> Department:
    async with session_factory() as session:
        department = await DepartmentRepository(session).create(
            organization_id=other_organization.id, code="ENG", name="Engineering (Globex)"
        )
        await session.commit()
        session.expunge(department)
        return department


async def test_create_and_get(
    service: PositionService, organization: Organization, department: Department
):
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Software Engineer",
        )
    )

    fetched = await service.get(position.id)

    assert fetched is not None
    assert fetched.name == "Software Engineer"
    assert fetched.code == "SWE"
    assert fetched.organization_id == organization.id
    assert fetched.department_id == department.id


async def test_create_rejects_missing_organization(
    service: PositionService, department: Department
):
    with pytest.raises(OrganizationNotFoundError):
        await service.create(
            PositionCreate(
                organization_id=uuid.uuid4(),
                department_id=department.id,
                code="SWE",
                name="Engineer",
            )
        )


async def test_create_rejects_missing_department(
    service: PositionService, organization: Organization
):
    with pytest.raises(DepartmentNotFoundError):
        await service.create(
            PositionCreate(
                organization_id=organization.id,
                department_id=uuid.uuid4(),
                code="SWE",
                name="Engineer",
            )
        )


async def test_create_rejects_department_in_different_organization(
    service: PositionService,
    organization: Organization,
    department_in_other_organization: Department,
):
    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.create(
            PositionCreate(
                organization_id=organization.id,
                department_id=department_in_other_organization.id,
                code="SWE",
                name="Engineer",
            )
        )


async def test_create_rejects_duplicate_code(
    service: PositionService, organization: Organization, department: Department
):
    await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    with pytest.raises(DuplicatePositionCodeError):
        await service.create(
            PositionCreate(
                organization_id=organization.id,
                department_id=department.id,
                code="SWE",
                name="Engineer Two",
            )
        )


async def test_create_allows_same_code_in_different_organization(
    service: PositionService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    other = await service.create(
        PositionCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="SWE",
            name="Engineer (Globex)",
        )
    )

    assert other.code == "SWE"
    assert other.organization_id == other_organization.id


async def test_get_missing_returns_none(service: PositionService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(
    service: PositionService, organization: Organization, department: Department
):
    await service.create(
        PositionCreate(
            organization_id=organization.id, department_id=department.id, code="SWE", name="Eng"
        )
    )
    await service.create(
        PositionCreate(
            organization_id=organization.id, department_id=department.id, code="SSWE", name="Sr"
        )
    )

    items = await service.list()

    assert {"Eng", "Sr"}.issubset({item.name for item in items})


async def test_update_existing(
    service: PositionService, organization: Organization, department: Department
):
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Before",
        )
    )

    updated = await service.update(position.id, PositionUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: PositionService):
    assert await service.update(uuid.uuid4(), PositionUpdate(name="After")) is None


async def test_update_rejects_missing_department(
    service: PositionService, organization: Organization, department: Department
):
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    with pytest.raises(DepartmentNotFoundError):
        await service.update(position.id, PositionUpdate(department_id=uuid.uuid4()))


async def test_update_accepts_existing_department_in_same_organization(
    service: PositionService,
    organization: Organization,
    department: Department,
    other_department: Department,
):
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    updated = await service.update(position.id, PositionUpdate(department_id=other_department.id))

    assert updated is not None
    assert updated.department_id == other_department.id


async def test_update_rejects_department_in_different_organization(
    service: PositionService,
    organization: Organization,
    department: Department,
    department_in_other_organization: Department,
):
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.update(
            position.id, PositionUpdate(department_id=department_in_other_organization.id)
        )


async def test_update_rejects_duplicate_code(
    service: PositionService, organization: Organization, department: Department
):
    await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )
    other = await service.create(
        PositionCreate(
            organization_id=organization.id, department_id=department.id, code="HRM", name="HR"
        )
    )

    with pytest.raises(DuplicatePositionCodeError):
        await service.update(other.id, PositionUpdate(code="SWE"))


async def test_update_allows_same_code_in_different_organization(
    service: PositionService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )
    other = await service.create(
        PositionCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="HRM",
            name="HR (Globex)",
        )
    )

    updated = await service.update(other.id, PositionUpdate(code="SWE"))

    assert updated is not None
    assert updated.code == "SWE"


async def test_update_allows_unchanged_code(
    service: PositionService, organization: Organization, department: Department
):
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    updated = await service.update(position.id, PositionUpdate(code="SWE", name="Engineer Renamed"))

    assert updated is not None
    assert updated.name == "Engineer Renamed"


async def test_update_rejects_missing_organization(
    service: PositionService, organization: Organization, department: Department
):
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    with pytest.raises(OrganizationNotFoundError):
        await service.update(position.id, PositionUpdate(organization_id=uuid.uuid4()))


async def test_update_organization_accepts_department_in_new_organization(
    service: PositionService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    updated = await service.update(
        position.id,
        PositionUpdate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
        ),
    )

    assert updated is not None
    assert updated.organization_id == other_organization.id
    assert updated.department_id == department_in_other_organization.id


async def test_update_organization_rejects_department_not_in_new_organization(
    service: PositionService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
):
    """A department explicitly provided alongside a new `organization_id` must
    belong to that new organization, not the position's current one."""
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.update(
            position.id,
            PositionUpdate(organization_id=other_organization.id, department_id=department.id),
        )


async def test_update_organization_without_touching_department_rejects_now_mismatched_department(
    service: PositionService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
):
    """The effective department is always validated against the effective
    organization, even when `department_id` itself is absent from this
    update -- a position must never end up pointing at a department in
    another organization."""
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.update(position.id, PositionUpdate(organization_id=other_organization.id))


async def test_update_unrelated_field_revalidates_existing_department_without_error(
    service: PositionService, organization: Organization, department: Department
):
    """An update that touches neither `organization_id` nor `department_id`
    still re-validates the (unchanged, already-consistent) effective
    department, and must not raise."""
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )

    updated = await service.update(position.id, PositionUpdate(name="Engineer Renamed"))

    assert updated is not None
    assert updated.name == "Engineer Renamed"
    assert updated.department_id == department.id


async def test_delete_existing(
    service: PositionService, organization: Organization, department: Department
):
    position = await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="To Delete",
        )
    )

    deleted = await service.delete(position.id)

    assert deleted is True
    assert await service.get(position.id) is None


async def test_delete_missing_returns_false(service: PositionService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(
    service: PositionService, organization: Organization, department: Department
):
    for i in range(5):
        await service.create(
            PositionCreate(
                organization_id=organization.id,
                department_id=department.id,
                code=f"P-{i}",
                name=f"Position {i}",
            )
        )

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(
    service: PositionService, organization: Organization, department: Department
):
    await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Software Engineer",
        )
    )
    await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="HRM",
            name="HR Manager",
        )
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="software")
    )

    assert page.total == 1
    assert page.items[0].name == "Software Engineer"


async def test_list_paginated_passes_through_filters(
    service: PositionService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
) -> None:
    await service.create(
        PositionCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="SWE",
            name="Engineer",
        )
    )
    await service.create(
        PositionCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="SWE",
            name="Engineer (Globex)",
        )
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50),
        filters=FilterParams(values={"organization_id": organization.id}),
    )

    assert page.total == 1
    assert page.items[0].organization_id == organization.id
