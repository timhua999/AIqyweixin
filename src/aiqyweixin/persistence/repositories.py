"""
数据仓储（Repository）层。

职责：
- 未答工单的写入与查询
- handoff 规则与 staff_org_map 的读写（待实现）
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from aiqyweixin.models.db import UnansweredTicket


async def create_unanswered_ticket(
    db: AsyncSession,
    *,
    wecom_user_id: str,
    raw_user_text: str,
    conversation_id: str | None = None,
    intent: str | None = None,
    model_or_rule_notes: str | None = None,
    api_called: bool = False,
    api_error: str | None = None,
    status: str = "pending",
    handoff_reason_code: str | None = None,
    route_rule_id: str | None = None,
    assigned_userids_json: str | None = None,
    mention_sent: bool | None = None,
    invite_sent: bool | None = None,
) -> UnansweredTicket:
    """插入一条未答工单并 flush（调用方负责 commit）。"""
    row = UnansweredTicket(
        wecom_user_id=wecom_user_id,
        conversation_id=conversation_id,
        raw_user_text=raw_user_text,
        intent=intent,
        model_or_rule_notes=model_or_rule_notes,
        api_called=api_called,
        api_error=api_error,
        status=status,
        handoff_reason_code=handoff_reason_code,
        route_rule_id=route_rule_id,
        assigned_userids_json=assigned_userids_json,
        mention_sent=mention_sent,
        invite_sent=invite_sent,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row
