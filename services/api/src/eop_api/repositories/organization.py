from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.organization import Organization
from eop_api.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Data access layer for `Organization`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Organization)
