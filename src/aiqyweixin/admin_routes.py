"""
管理端 API（需 ENABLE_ADMIN_ROUTES=true 或开发环境）。

- GET /admin/unanswered-tickets：未答工单列表
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from aiqyweixin.config import Settings, get_settings
from aiqyweixin.persistence.session import get_db
from aiqyweixin.services.unanswered_service import list_unanswered_tickets

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_allowed(settings: Settings) -> bool:
    env = (settings.app_env or "").lower()
    return settings.enable_admin_routes or env == "development"


def _ticket_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "wecom_user_id": row.wecom_user_id,
        "conversation_id": row.conversation_id,
        "raw_user_text": row.raw_user_text,
        "intent": row.intent,
        "model_or_rule_notes": row.model_or_rule_notes,
        "api_called": row.api_called,
        "api_error": row.api_error,
        "status": row.status,
        "handoff_reason_code": row.handoff_reason_code,
        "route_rule_id": row.route_rule_id,
        "assigned_userids_json": row.assigned_userids_json,
    }


@router.get("/unanswered-tickets")
async def get_unanswered_tickets(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(default=None, description="pending / resolved 等"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    if not _admin_allowed(settings):
        raise HTTPException(status_code=404, detail="Not Found")
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")

    rows = await list_unanswered_tickets(db, status=status, limit=limit, offset=offset)
    return {
        "total_returned": len(rows),
        "items": [_ticket_to_dict(r) for r in rows],
    }
