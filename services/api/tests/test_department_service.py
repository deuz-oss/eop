import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.organization import Organization
from eop_api.repositories.organization import OrganizationRepository
from eop_api.schemas.department import DepartmentCreate, DepartmentUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.department import (
    DepartmentService,
    DuplicateDepartmentCodeError,
    OrganizationNotFoundError,
    ParentDepartmentNotFoundError,
    ParentOrganizationMismatchError,
    SelfParentDepartmentError,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `departments` table.

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
            await conn.execute(text("TRUNCATE TABLE departments, organizations CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> DepartmentService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return DepartmentService(uow_factory)


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


async def test_create_and_get(service: DepartmentService, organization: Organization):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )

    fetched = await service.get(department.id)

    assert fetched is not None
    assert fetched.name == "Finance"
    assert fetched.code == "FIN"
    assert fetched.organization_id == organization.id


async def test_create_with_parent(service: DepartmentService, organization: Organization):
    parent = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )

    child = await service.create(
        DepartmentCreate(
            organization_id=organization.id,
            code="FIN-AP",
            name="Accounts Payable",
            parent_id=parent.id,
        )
    )

    assert child.parent_id == parent.id


async def test_create_rejects_missing_organization(service: DepartmentService):
    with pytest.raises(OrganizationNotFoundError):
        await service.create(
            DepartmentCreate(organization_id=uuid.uuid4(), code="FIN", name="Finance")
        )


async def test_create_rejects_missing_parent(
    service: DepartmentService, organization: Organization
):
    with pytest.raises(ParentDepartmentNotFoundError):
        await service.create(
            DepartmentCreate(
                organization_id=organization.id,
                code="FIN-AP",
                name="Accounts Payable",
                parent_id=uuid.uuid4(),
            )
        )


async def test_create_rejects_parent_in_different_organization(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    parent = await service.create(
        DepartmentCreate(organization_id=other_organization.id, code="FIN", name="Finance")
    )

    with pytest.raises(ParentOrganizationMismatchError):
        await service.create(
            DepartmentCreate(
                organization_id=organization.id,
                code="FIN-AP",
                name="Accounts Payable",
                parent_id=parent.id,
            )
        )


async def test_create_rejects_duplicate_code(
    service: DepartmentService, organization: Organization
):
    await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )

    with pytest.raises(DuplicateDepartmentCodeError):
        await service.create(
            DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance Two")
        )


async def test_create_allows_same_code_in_different_organization(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )

    other = await service.create(
        DepartmentCreate(organization_id=other_organization.id, code="FIN", name="Finance (Globex)")
    )

    assert other.code == "FIN"
    assert other.organization_id == other_organization.id


async def test_get_missing_returns_none(service: DepartmentService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: DepartmentService, organization: Organization):
    await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    await service.create(DepartmentCreate(organization_id=organization.id, code="HR", name="HR"))

    items = await service.list()

    assert {"Finance", "HR"}.issubset({item.name for item in items})


async def test_update_existing(service: DepartmentService, organization: Organization):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Before")
    )

    updated = await service.update(department.id, DepartmentUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: DepartmentService):
    assert await service.update(uuid.uuid4(), DepartmentUpdate(name="After")) is None


async def test_update_rejects_missing_parent(
    service: DepartmentService, organization: Organization
):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN-AP", name="Accounts Payable")
    )

    with pytest.raises(ParentDepartmentNotFoundError):
        await service.update(department.id, DepartmentUpdate(parent_id=uuid.uuid4()))


async def test_update_accepts_existing_parent(
    service: DepartmentService, organization: Organization
):
    parent = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    child = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN-AP", name="Accounts Payable")
    )

    updated = await service.update(child.id, DepartmentUpdate(parent_id=parent.id))

    assert updated is not None
    assert updated.parent_id == parent.id


async def test_update_rejects_parent_in_different_organization(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    other_parent = await service.create(
        DepartmentCreate(organization_id=other_organization.id, code="FIN", name="Finance (Globex)")
    )

    with pytest.raises(ParentOrganizationMismatchError):
        await service.update(department.id, DepartmentUpdate(parent_id=other_parent.id))


async def test_update_rejects_self_parent(service: DepartmentService, organization: Organization):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )

    with pytest.raises(SelfParentDepartmentError):
        await service.update(department.id, DepartmentUpdate(parent_id=department.id))


async def test_update_rejects_duplicate_code(
    service: DepartmentService, organization: Organization
):
    await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    other = await service.create(
        DepartmentCreate(organization_id=organization.id, code="HR", name="HR")
    )

    with pytest.raises(DuplicateDepartmentCodeError):
        await service.update(other.id, DepartmentUpdate(code="FIN"))


async def test_update_allows_same_code_in_different_organization(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    other = await service.create(
        DepartmentCreate(organization_id=other_organization.id, code="HR", name="HR (Globex)")
    )

    updated = await service.update(other.id, DepartmentUpdate(code="FIN"))

    assert updated is not None
    assert updated.code == "FIN"


async def test_update_allows_unchanged_code(service: DepartmentService, organization: Organization):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )

    updated = await service.update(
        department.id, DepartmentUpdate(code="FIN", name="Finance Renamed")
    )

    assert updated is not None
    assert updated.name == "Finance Renamed"


async def test_update_allows_changing_organization(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )

    updated = await service.update(
        department.id, DepartmentUpdate(organization_id=other_organization.id)
    )

    assert updated is not None
    assert updated.organization_id == other_organization.id


async def test_update_rejects_missing_organization(
    service: DepartmentService, organization: Organization
):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )

    with pytest.raises(OrganizationNotFoundError):
        await service.update(department.id, DepartmentUpdate(organization_id=uuid.uuid4()))


async def test_update_organization_accepts_parent_in_new_organization(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    parent = await service.create(
        DepartmentCreate(organization_id=other_organization.id, code="FIN", name="Finance (Globex)")
    )
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN-AP", name="Accounts Payable")
    )

    updated = await service.update(
        department.id,
        DepartmentUpdate(organization_id=other_organization.id, parent_id=parent.id),
    )

    assert updated is not None
    assert updated.organization_id == other_organization.id
    assert updated.parent_id == parent.id


async def test_update_organization_rejects_parent_not_in_new_organization(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    """A parent explicitly provided alongside a new `organization_id` must belong
    to that new organization, not the department's current one."""
    parent = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN-AP", name="Accounts Payable")
    )

    with pytest.raises(ParentOrganizationMismatchError):
        await service.update(
            department.id,
            DepartmentUpdate(organization_id=other_organization.id, parent_id=parent.id),
        )


async def test_update_organization_without_touching_parent_rejects_now_mismatched_parent(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    """The effective parent is always validated against the effective
    organization, even when `parent_id` itself is absent from this update --
    a department must never end up pointing at a parent in another
    organization."""
    parent = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    child = await service.create(
        DepartmentCreate(
            organization_id=organization.id,
            code="FIN-AP",
            name="Accounts Payable",
            parent_id=parent.id,
        )
    )

    with pytest.raises(ParentOrganizationMismatchError):
        await service.update(child.id, DepartmentUpdate(organization_id=other_organization.id))


async def test_update_organization_without_touching_parent_succeeds_when_still_consistent(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    """Moving both a parent and its child to the same new organization (in two
    separate calls) keeps the effective parent valid, since nothing but
    `organization_id` differs between the two update calls."""
    parent = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    child = await service.create(
        DepartmentCreate(
            organization_id=organization.id,
            code="FIN-AP",
            name="Accounts Payable",
            parent_id=parent.id,
        )
    )
    await service.update(parent.id, DepartmentUpdate(organization_id=other_organization.id))

    updated = await service.update(
        child.id, DepartmentUpdate(organization_id=other_organization.id)
    )

    assert updated is not None
    assert updated.organization_id == other_organization.id
    assert updated.parent_id == parent.id


async def test_update_unrelated_field_revalidates_existing_parent_without_error(
    service: DepartmentService, organization: Organization
):
    """An update that touches neither `organization_id` nor `parent_id` still
    re-validates the (unchanged, already-consistent) effective parent, and
    must not raise."""
    parent = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    child = await service.create(
        DepartmentCreate(
            organization_id=organization.id,
            code="FIN-AP",
            name="Accounts Payable",
            parent_id=parent.id,
        )
    )

    updated = await service.update(child.id, DepartmentUpdate(name="AP Renamed"))

    assert updated is not None
    assert updated.name == "AP Renamed"
    assert updated.parent_id == parent.id


async def test_update_organization_rejects_duplicate_code_in_new_organization(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    await service.create(
        DepartmentCreate(organization_id=other_organization.id, code="OPS", name="Operations")
    )
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="OPS", name="Operations (Acme)")
    )

    with pytest.raises(DuplicateDepartmentCodeError):
        await service.update(department.id, DepartmentUpdate(organization_id=other_organization.id))


async def test_update_organization_allows_non_conflicting_code_in_new_organization(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="OPS", name="Operations")
    )

    updated = await service.update(
        department.id, DepartmentUpdate(organization_id=other_organization.id)
    )

    assert updated is not None
    assert updated.organization_id == other_organization.id
    assert updated.code == "OPS"


async def test_update_organization_does_not_move_children(
    service: DepartmentService, organization: Organization, other_organization: Organization
):
    """Reassigning a department's organization is not recursive: its children
    keep their original `organization_id` and `parent_id`."""
    parent = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    child = await service.create(
        DepartmentCreate(
            organization_id=organization.id,
            code="FIN-AP",
            name="Accounts Payable",
            parent_id=parent.id,
        )
    )

    await service.update(parent.id, DepartmentUpdate(organization_id=other_organization.id))

    unchanged_child = await service.get(child.id)
    assert unchanged_child is not None
    assert unchanged_child.organization_id == organization.id
    assert unchanged_child.parent_id == parent.id


async def test_delete_existing(service: DepartmentService, organization: Organization):
    department = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="To Delete")
    )

    deleted = await service.delete(department.id)

    assert deleted is True
    assert await service.get(department.id) is None


async def test_delete_missing_returns_false(service: DepartmentService):
    assert await service.delete(uuid.uuid4()) is False


async def test_delete_parent_with_children_is_restricted(
    service: DepartmentService, organization: Organization
):
    parent = await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    await service.create(
        DepartmentCreate(
            organization_id=organization.id,
            code="FIN-AP",
            name="Accounts Payable",
            parent_id=parent.id,
        )
    )

    with pytest.raises(IntegrityError):
        await service.delete(parent.id)


async def test_list_paginated_passes_through_offset_and_limit(
    service: DepartmentService, organization: Organization
):
    for i in range(5):
        await service.create(
            DepartmentCreate(organization_id=organization.id, code=f"D-{i}", name=f"Dept {i}")
        )

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(
    service: DepartmentService, organization: Organization
):
    await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance Department")
    )
    await service.create(
        DepartmentCreate(organization_id=organization.id, code="HR", name="Human Resources")
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="finance")
    )

    assert page.total == 1
    assert page.items[0].name == "Finance Department"


async def test_list_paginated_passes_through_filters(
    service: DepartmentService, organization: Organization, other_organization: Organization
) -> None:
    await service.create(
        DepartmentCreate(organization_id=organization.id, code="FIN", name="Finance")
    )
    await service.create(
        DepartmentCreate(organization_id=other_organization.id, code="FIN", name="Finance (Globex)")
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50),
        filters=FilterParams(values={"organization_id": organization.id}),
    )

    assert page.total == 1
    assert page.items[0].organization_id == organization.id
