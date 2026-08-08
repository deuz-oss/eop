import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.payslip_line_item import PayslipLineItem
from eop_api.repositories.base import BaseRepository


class PayslipLineItemRepository(BaseRepository[PayslipLineItem]):
    """Data access layer for `PayslipLineItem`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PayslipLineItem)

    async def list_by_payslip(self, payslip_id: uuid.UUID) -> Sequence[PayslipLineItem]:
        stmt = select(PayslipLineItem).where(PayslipLineItem.payslip_id == payslip_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
