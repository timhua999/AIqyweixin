"""
临时调试路由（勿在生产环境依赖；默认仅在开发或显式开关下注册）。

POST /debug/unanswered-ticket：插入一条测试未答工单。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aiqyweixin.config import Settings, get_settings
from aiqyweixin.persistence.repositories import create_unanswered_ticket
from aiqyweixin.persistence.session import get_db

router = APIRouter(prefix="/debug", tags=["debug"])


class UnansweredTicketDebugBody(BaseModel):
    """可选 JSON 体；省略字段则用默认值。"""

    wecom_user_id: str = Field(default="debug_user", max_length=128)
    raw_user_text: str = Field(default="debug: 测试未答工单")
    conversation_id: str | None = Field(default=None, max_length=256)
    intent: str | None = Field(default="other", max_length=64)
    model_or_rule_notes: str | None = None
    api_called: bool = False
    api_error: str | None = None
    status: str = Field(default="pending", max_length=32)
    handoff_reason_code: str | None = None
    route_rule_id: str | None = None
    assigned_userids_json: str | None = None


def _debug_allowed(settings: Settings) -> bool:
    env = (settings.app_env or "").lower()
    return settings.enable_debug_routes or env == "development"


@router.post("/unanswered-ticket")
async def post_debug_unanswered_ticket(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: UnansweredTicketDebugBody | None = Body(default=None),
) -> dict[str, object]:
    """
    插入一条 `unanswered_tickets` 测试记录并 commit。

    未启用调试或未配置数据库时返回 404 / 503。
    """
    if not _debug_allowed(settings):
        raise HTTPException(status_code=404, detail="Not Found")
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")

    payload = body.model_dump() if body is not None else UnansweredTicketDebugBody().model_dump()
    row = await create_unanswered_ticket(db, **payload)
    await db.commit()
    return {
        "id": row.id,
        "status": row.status,
        "wecom_user_id": row.wecom_user_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
