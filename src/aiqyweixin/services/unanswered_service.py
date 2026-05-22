"""未答工单查询（管理端）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiqyweixin.models.db import UnansweredTicket


async def list_unanswered_tickets(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[UnansweredTicket]:
    stmt = select(UnansweredTicket).order_by(UnansweredTicket.created_at.desc())
    if status:
        stmt = stmt.where(UnansweredTicket.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
