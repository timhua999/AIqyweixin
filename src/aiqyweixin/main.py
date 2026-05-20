"""
FastAPI 应用入口。

职责：
- 创建 FastAPI app
- 注册企业微信回调路由
- 暴露 /health
- 初始化依赖（配置、日志、数据库连接等）
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from aiqyweixin.config import get_settings
from aiqyweixin.health import router as health_router
from aiqyweixin.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    import sys

    msg = f"aiqyweixin 已启动（企微自动回复已启用，LOG_LEVEL={settings.log_level}）"
    logger.info(msg)
    print(f"[aiqyweixin] {msg}", file=sys.stderr, flush=True)
    if settings.database_url:
        from aiqyweixin.persistence import session as db_session

        db_session.init_engine(settings.database_url)
        await db_session.verify_connection()
        logger.info("数据库连接校验通过（启动时 SELECT 1）")
    yield
    if settings.database_url:
        from aiqyweixin.persistence import session as db_session

        await db_session.dispose_engine()


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(
        title="AIqyweixin",
        description="企业微信国际物流智能机器人（单租户 MVP）",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    from aiqyweixin.wecom.webhook import router as wecom_router

    app.include_router(wecom_router)
    settings = get_settings()
    if settings.database_url and (
        settings.enable_debug_routes or (settings.app_env or "").lower() == "development"
    ):
        from aiqyweixin.debug_routes import router as debug_router

        app.include_router(debug_router)
    return app


app = create_app()
