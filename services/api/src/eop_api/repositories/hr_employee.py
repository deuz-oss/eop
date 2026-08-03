from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.hr_employee import HrEmployee
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (
    HrEmployee.employee_number,
    HrEmployee.first_name,
    HrEmployee.last_name,
    HrEmployee.full_name,
    HrEmployee.email,
)
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "organization_id": HrEmployee.organization_id,
    "department_id": HrEmployee.department_id,
    "position_id": HrEmployee.position_id,
    "team_id": HrEmployee.team_id,
    "location_id": HrEmployee.location_id,
    "employment_status": HrEmployee.employment_status,
}


class HrEmployeeRepository(BaseRepository[HrEmployee]):
    """Data access layer for `HrEmployee`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HrEmployee)

    async def get_by_employee_number(self, employee_number: str) -> HrEmployee | None:
        return await self.get_by(HrEmployee.employee_number, employee_number)

    async def get_by_email(self, email: str) -> HrEmployee | None:
        return await self.get_by(HrEmployee.email, email)

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[HrEmployee]:
        """Paginated listing, text-searched against `employee_number`/`first_name`/
        `last_name`/`full_name`/`email`.

        Filterable by `organization_id`, `department_id`, `position_id`,
        `team_id`, `location_id`, and `employment_status`.
        """
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
