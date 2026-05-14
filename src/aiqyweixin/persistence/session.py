"""
数据库连接与会话管理（PostgreSQL，SQLAlchemy 2.x 异步 + asyncpg）。

职责：
- 将 DATABASE_URL 规范为 postgresql+asyncpg://（若写成 postgresql:// 会自动补驱动前缀）
- 创建异步 engine / session_factory
- 启动时校验连通性；关闭时释放连接池
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def normalize_async_database_url(url: str) -> str:
    """把常见写法转成 SQLAlchemy 异步 URL（asyncpg）。"""
    u = url.strip()
    if u.startswith("postgresql+asyncpg://"):
        return u
    if u.startswith("postgresql://"):
        return "postgresql+asyncpg://" + u[len("postgresql://") :]
    if u.startswith("postgres://"):
        return "postgresql+asyncpg://" + u[len("postgres://") :]
    raise ValueError(
        "DATABASE_URL 需以 postgresql://、postgres:// 或 postgresql+asyncpg:// 开头"
    )


def init_engine(database_url: str) -> None:
    """根据 DATABASE_URL 初始化全局 engine 与 session_factory（进程内单例）。"""
    global _engine, _session_factory
    if _engine is not None:
        return
    async_url = normalize_async_database_url(database_url)
    _engine = create_async_engine(
        async_url,
        pool_pre_ping=True,
        echo=False,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    logger.info("数据库 engine 已初始化")


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("数据库未初始化：请先调用 init_engine(DATABASE_URL)")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("数据库未初始化：请先调用 init_engine(DATABASE_URL)")
    return _session_factory


async def verify_connection() -> None:
    """执行 SELECT 1，用于启动探活与健康检查。"""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def dispose_engine() -> None:
    """应用关闭时释放连接池。"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("数据库 engine 已关闭")


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每个请求一个 AsyncSession。写操作请在业务代码中显式 commit。"""
    factory = get_session_factory()
    async with factory() as session:
        yield session
