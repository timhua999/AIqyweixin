"""
健康检查接口。

职责：
- 提供 /health（以及可选 /ready）用于运维探活
- 可选校验数据库连通性与关键配置是否齐全（不回显密钥）
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from aiqyweixin.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    try:
        import importlib.metadata

        version = importlib.metadata.version("aiqyweixin")
    except Exception:
        version = "unknown"
    return {
        "status": "ok",
        "version": version,
        "wecom_auto_reply": True,
    }


@router.get("/ready")
async def ready(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    """返回关键配置是否已填写；若已配置 DATABASE_URL 则探测数据库（不输出任何密钥）。"""
    missing: list[str] = []
    if not settings.database_url:
        missing.append("DATABASE_URL")
    if not settings.wecom_corp_id:
        missing.append("WECOM_CORP_ID")
    if not settings.wecom_agent_secret:
        missing.append("WECOM_AGENT_SECRET")
    if not settings.llm_base_url:
        missing.append("LLM_BASE_URL")
    if not settings.llm_api_key:
        missing.append("LLM_API_KEY")

    database_reachable: bool | None = None
    database_error: str | None = None
    if settings.database_url:
        try:
            from aiqyweixin.persistence import session as db_session

            await db_session.verify_connection()
            database_reachable = True
        except Exception as exc:  # noqa: BLE001 — 健康检查需吞并分类
            database_reachable = False
            database_error = f"{type(exc).__name__}: {exc}"[:200]

    config_ok = len(missing) == 0
    db_ok = database_reachable is not False if settings.database_url else True
    return {
        "ready": config_ok and db_ok,
        "missing_config_keys": missing,
        "database_reachable": database_reachable,
        "database_error": database_error,
    }
