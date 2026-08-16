import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.models.department import Department
from eop_api.models.organization import Organization
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.schemas.team import TeamCreate, TeamUpdate
from eop_api.services.team import (
    CyclicParentTeamError,
    DepartmentNotFoundError,
    DepartmentOrganizationMismatchError,
    DuplicateTeamCodeError,
    OrganizationNotFoundError,
    ParentDepartmentMismatchError,
    ParentOrganizationMismatchError,
    ParentTeamNotFoundError,
    SelfParentTeamError,
    TeamService,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `teams` table.

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
            await conn.execute(text("TRUNCATE TABLE teams, departments, organizations CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> TeamService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return TeamService(uow_factory)


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
    service: TeamService, organization: Organization, department: Department
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="BACKEND",
            name="Backend Team",
        )
    )

    fetched = await service.get(team.id)

    assert fetched is not None
    assert fetched.name == "Backend Team"
    assert fetched.code == "BACKEND"
    assert fetched.organization_id == organization.id
    assert fetched.department_id == department.id


async def test_create_with_parent(
    service: TeamService, organization: Organization, department: Department
):
    parent = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="BACKEND",
            name="Backend Team",
        )
    )

    child = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
            parent_id=parent.id,
        )
    )

    assert child.parent_id == parent.id


async def test_create_rejects_missing_organization(service: TeamService, department: Department):
    with pytest.raises(OrganizationNotFoundError):
        await service.create(
            TeamCreate(
                organization_id=uuid.uuid4(),
                department_id=department.id,
                code="BACKEND",
                name="Backend Team",
            )
        )


async def test_create_rejects_missing_department(service: TeamService, organization: Organization):
    with pytest.raises(DepartmentNotFoundError):
        await service.create(
            TeamCreate(
                organization_id=organization.id,
                department_id=uuid.uuid4(),
                code="BACKEND",
                name="Backend Team",
            )
        )


async def test_create_rejects_department_in_different_organization(
    service: TeamService,
    organization: Organization,
    department_in_other_organization: Department,
):
    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.create(
            TeamCreate(
                organization_id=organization.id,
                department_id=department_in_other_organization.id,
                code="BACKEND",
                name="Backend Team",
            )
        )


async def test_create_rejects_missing_parent(
    service: TeamService, organization: Organization, department: Department
):
    with pytest.raises(ParentTeamNotFoundError):
        await service.create(
            TeamCreate(
                organization_id=organization.id,
                department_id=department.id,
                code="API",
                name="API Squad",
                parent_id=uuid.uuid4(),
            )
        )


async def test_create_rejects_parent_in_different_organization(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    parent = await service.create(
        TeamCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="BACKEND",
            name="Backend Team (Globex)",
        )
    )

    with pytest.raises(ParentOrganizationMismatchError):
        await service.create(
            TeamCreate(
                organization_id=organization.id,
                department_id=department.id,
                code="API",
                name="API Squad",
                parent_id=parent.id,
            )
        )


async def test_create_rejects_parent_in_different_department(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_department: Department,
):
    parent = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=other_department.id,
            code="HR-OPS",
            name="HR Ops",
        )
    )

    with pytest.raises(ParentDepartmentMismatchError):
        await service.create(
            TeamCreate(
                organization_id=organization.id,
                department_id=department.id,
                code="API",
                name="API Squad",
                parent_id=parent.id,
            )
        )


async def test_create_rejects_duplicate_code(
    service: TeamService, organization: Organization, department: Department
):
    await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="BACKEND",
            name="Backend Team",
        )
    )

    with pytest.raises(DuplicateTeamCodeError):
        await service.create(
            TeamCreate(
                organization_id=organization.id,
                department_id=department.id,
                code="BACKEND",
                name="Backend Team Two",
            )
        )


async def test_create_allows_same_code_in_different_organization(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="BACKEND",
            name="Backend Team",
        )
    )

    other = await service.create(
        TeamCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="BACKEND",
            name="Backend Team (Globex)",
        )
    )

    assert other.code == "BACKEND"
    assert other.organization_id == other_organization.id


async def test_get_missing_returns_none(service: TeamService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(
    service: TeamService, organization: Organization, department: Department
):
    await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )
    await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="FE", name="Frontend"
        )
    )

    items = await service.list()

    assert {"Backend", "Frontend"}.issubset({item.name for item in items})


async def test_update_existing(
    service: TeamService, organization: Organization, department: Department
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Before"
        )
    )

    updated = await service.update(team.id, TeamUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: TeamService):
    assert await service.update(uuid.uuid4(), TeamUpdate(name="After")) is None


async def test_update_rejects_missing_department(
    service: TeamService, organization: Organization, department: Department
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )

    with pytest.raises(DepartmentNotFoundError):
        await service.update(team.id, TeamUpdate(department_id=uuid.uuid4()))


async def test_update_accepts_existing_department_in_same_organization(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_department: Department,
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )

    updated = await service.update(team.id, TeamUpdate(department_id=other_department.id))

    assert updated is not None
    assert updated.department_id == other_department.id


async def test_update_rejects_department_in_different_organization(
    service: TeamService,
    organization: Organization,
    department: Department,
    department_in_other_organization: Department,
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )

    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.update(team.id, TeamUpdate(department_id=department_in_other_organization.id))


async def test_update_rejects_missing_parent(
    service: TeamService, organization: Organization, department: Department
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
        )
    )

    with pytest.raises(ParentTeamNotFoundError):
        await service.update(team.id, TeamUpdate(parent_id=uuid.uuid4()))


async def test_update_accepts_existing_parent(
    service: TeamService, organization: Organization, department: Department
):
    parent = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )
    child = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
        )
    )

    updated = await service.update(child.id, TeamUpdate(parent_id=parent.id))

    assert updated is not None
    assert updated.parent_id == parent.id


async def test_update_rejects_parent_in_different_organization(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
        )
    )
    other_parent = await service.create(
        TeamCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="BE",
            name="Backend (Globex)",
        )
    )

    with pytest.raises(ParentOrganizationMismatchError):
        await service.update(team.id, TeamUpdate(parent_id=other_parent.id))


async def test_update_rejects_parent_in_different_department(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_department: Department,
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
        )
    )
    other_parent = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=other_department.id,
            code="HR-OPS",
            name="HR Ops",
        )
    )

    with pytest.raises(ParentDepartmentMismatchError):
        await service.update(team.id, TeamUpdate(parent_id=other_parent.id))


async def test_update_rejects_self_parent(
    service: TeamService, organization: Organization, department: Department
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )

    with pytest.raises(SelfParentTeamError):
        await service.update(team.id, TeamUpdate(parent_id=team.id))


async def test_update_rejects_direct_two_node_cycle(
    service: TeamService, organization: Organization, department: Department
):
    """A -> B (B's parent is A); setting A's parent to B would close A -> B -> A."""
    a = await service.create(
        TeamCreate(organization_id=organization.id, department_id=department.id, code="A", name="A")
    )
    b = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="B",
            name="B",
            parent_id=a.id,
        )
    )

    with pytest.raises(CyclicParentTeamError):
        await service.update(a.id, TeamUpdate(parent_id=b.id))


async def test_update_rejects_three_node_cycle(
    service: TeamService, organization: Organization, department: Department
):
    """A -> B -> C (chain); setting A's parent to C would close the cycle."""
    a = await service.create(
        TeamCreate(organization_id=organization.id, department_id=department.id, code="A", name="A")
    )
    b = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="B",
            name="B",
            parent_id=a.id,
        )
    )
    c = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="C",
            name="C",
            parent_id=b.id,
        )
    )

    with pytest.raises(CyclicParentTeamError):
        await service.update(a.id, TeamUpdate(parent_id=c.id))


async def test_update_allows_valid_reparenting(
    service: TeamService, organization: Organization, department: Department
):
    a = await service.create(
        TeamCreate(organization_id=organization.id, department_id=department.id, code="A", name="A")
    )
    b = await service.create(
        TeamCreate(organization_id=organization.id, department_id=department.id, code="B", name="B")
    )

    updated = await service.update(b.id, TeamUpdate(parent_id=a.id))

    assert updated is not None
    assert updated.parent_id == a.id


async def test_update_allows_reparenting_to_root(
    service: TeamService, organization: Organization, department: Department
):
    """Clearing `parent_id` to make a node a root is valid and must not be
    mistaken for a cycle."""
    a = await service.create(
        TeamCreate(organization_id=organization.id, department_id=department.id, code="A", name="A")
    )
    b = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="B",
            name="B",
            parent_id=a.id,
        )
    )
    c = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="C",
            name="C",
            parent_id=b.id,
        )
    )

    updated = await service.update(c.id, TeamUpdate(parent_id=None))

    assert updated is not None
    assert updated.parent_id is None


async def test_update_allows_deep_valid_hierarchy(
    service: TeamService, organization: Organization, department: Department
):
    """A long, non-cyclic ancestor chain must be walked correctly and must
    not be mistaken for a cycle."""
    deepest_id: uuid.UUID | None = None
    for i in range(6):
        node = await service.create(
            TeamCreate(
                organization_id=organization.id,
                department_id=department.id,
                code=f"N{i}",
                name=f"N{i}",
                parent_id=deepest_id,
            )
        )
        deepest_id = node.id

    leaf = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="LEAF", name="Leaf"
        )
    )

    updated = await service.update(leaf.id, TeamUpdate(parent_id=deepest_id))

    assert updated is not None
    assert updated.parent_id == deepest_id


async def test_update_rejects_duplicate_code(
    service: TeamService, organization: Organization, department: Department
):
    await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )
    other = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="FE", name="Frontend"
        )
    )

    with pytest.raises(DuplicateTeamCodeError):
        await service.update(other.id, TeamUpdate(code="BE"))


async def test_update_allows_same_code_in_different_organization(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )
    other = await service.create(
        TeamCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="FE",
            name="Frontend (Globex)",
        )
    )

    updated = await service.update(other.id, TeamUpdate(code="BE"))

    assert updated is not None
    assert updated.code == "BE"


async def test_update_allows_unchanged_code(
    service: TeamService, organization: Organization, department: Department
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )

    updated = await service.update(team.id, TeamUpdate(code="BE", name="Backend Renamed"))

    assert updated is not None
    assert updated.name == "Backend Renamed"


async def test_update_allows_changing_organization(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )

    updated = await service.update(
        team.id,
        TeamUpdate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
        ),
    )

    assert updated is not None
    assert updated.organization_id == other_organization.id
    assert updated.department_id == department_in_other_organization.id


async def test_update_rejects_missing_organization(
    service: TeamService, organization: Organization, department: Department
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )

    with pytest.raises(OrganizationNotFoundError):
        await service.update(team.id, TeamUpdate(organization_id=uuid.uuid4()))


async def test_update_organization_rejects_department_not_in_new_organization(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
):
    """A department explicitly provided alongside a new `organization_id` must
    belong to that new organization, not the team's current one."""
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )

    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.update(
            team.id,
            TeamUpdate(organization_id=other_organization.id, department_id=department.id),
        )


async def test_update_organization_without_touching_department_rejects_now_mismatched_department(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
):
    """The effective department is always validated against the effective
    organization, even when `department_id` itself is absent from this
    update -- a team must never end up pointing at a department in another
    organization."""
    team = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )

    with pytest.raises(DepartmentOrganizationMismatchError):
        await service.update(team.id, TeamUpdate(organization_id=other_organization.id))


async def test_update_organization_accepts_parent_in_new_organization_and_department(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    parent = await service.create(
        TeamCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="BE",
            name="Backend (Globex)",
        )
    )
    team = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
        )
    )

    updated = await service.update(
        team.id,
        TeamUpdate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            parent_id=parent.id,
        ),
    )

    assert updated is not None
    assert updated.organization_id == other_organization.id
    assert updated.department_id == department_in_other_organization.id
    assert updated.parent_id == parent.id


async def test_update_organization_without_touching_parent_rejects_now_mismatched_parent(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    """The effective parent is always validated against the effective
    organization and department, even when `parent_id` itself is absent from
    this update -- moving only `organization_id`/`department_id` (both to
    valid, matching values) must still fail because the untouched parent is
    left behind in the old organization."""
    parent = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )
    child = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
            parent_id=parent.id,
        )
    )

    with pytest.raises(ParentOrganizationMismatchError):
        await service.update(
            child.id,
            TeamUpdate(
                organization_id=other_organization.id,
                department_id=department_in_other_organization.id,
            ),
        )


async def test_update_unrelated_field_revalidates_existing_parent_without_error(
    service: TeamService, organization: Organization, department: Department
):
    """An update that touches neither `organization_id`, `department_id`, nor
    `parent_id` still re-validates the (unchanged, already-consistent)
    effective parent, and must not raise."""
    parent = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )
    child = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
            parent_id=parent.id,
        )
    )

    updated = await service.update(child.id, TeamUpdate(name="API Squad Renamed"))

    assert updated is not None
    assert updated.name == "API Squad Renamed"
    assert updated.parent_id == parent.id


async def test_update_organization_rejects_duplicate_code_in_new_organization(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    await service.create(
        TeamCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="OPS",
            name="Operations",
        )
    )
    team = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="OPS",
            name="Operations (Acme)",
        )
    )

    with pytest.raises(DuplicateTeamCodeError):
        await service.update(
            team.id,
            TeamUpdate(
                organization_id=other_organization.id,
                department_id=department_in_other_organization.id,
            ),
        )


async def test_update_organization_does_not_move_children(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
):
    """Reassigning a team's organization is not recursive: its children keep
    their original `organization_id`, `department_id`, and `parent_id`."""
    parent = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )
    child = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
            parent_id=parent.id,
        )
    )

    await service.update(
        parent.id,
        TeamUpdate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
        ),
    )

    unchanged_child = await service.get(child.id)
    assert unchanged_child is not None
    assert unchanged_child.organization_id == organization.id
    assert unchanged_child.department_id == department.id
    assert unchanged_child.parent_id == parent.id


async def test_delete_existing(
    service: TeamService, organization: Organization, department: Department
):
    team = await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="BE",
            name="To Delete",
        )
    )

    deleted = await service.delete(team.id)

    assert deleted is True
    assert await service.get(team.id) is None


async def test_delete_missing_returns_false(service: TeamService):
    assert await service.delete(uuid.uuid4()) is False


async def test_delete_parent_with_children_is_restricted(
    service: TeamService, organization: Organization, department: Department
):
    parent = await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )
    await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="API",
            name="API Squad",
            parent_id=parent.id,
        )
    )

    with pytest.raises(IntegrityError):
        await service.delete(parent.id)


async def test_list_paginated_passes_through_offset_and_limit(
    service: TeamService, organization: Organization, department: Department
):
    for i in range(5):
        await service.create(
            TeamCreate(
                organization_id=organization.id,
                department_id=department.id,
                code=f"T-{i}",
                name=f"Team {i}",
            )
        )

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(
    service: TeamService, organization: Organization, department: Department
):
    await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="BE",
            name="Backend Team",
        )
    )
    await service.create(
        TeamCreate(
            organization_id=organization.id,
            department_id=department.id,
            code="FE",
            name="Frontend Team",
        )
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="backend")
    )

    assert page.total == 1
    assert page.items[0].name == "Backend Team"


async def test_list_paginated_passes_through_filters(
    service: TeamService,
    organization: Organization,
    department: Department,
    other_organization: Organization,
    department_in_other_organization: Department,
) -> None:
    await service.create(
        TeamCreate(
            organization_id=organization.id, department_id=department.id, code="BE", name="Backend"
        )
    )
    await service.create(
        TeamCreate(
            organization_id=other_organization.id,
            department_id=department_in_other_organization.id,
            code="BE",
            name="Backend (Globex)",
        )
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50),
        filters=FilterParams(values={"organization_id": organization.id}),
    )

    assert page.total == 1
    assert page.items[0].organization_id == organization.id
