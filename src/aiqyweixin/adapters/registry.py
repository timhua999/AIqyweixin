"""
适配器注册与选择。
"""

from __future__ import annotations

from aiqyweixin.adapters.base import LogisticsAdapter
from aiqyweixin.adapters.by56 import By56Adapter
from aiqyweixin.config import get_settings


def get_quote_adapter(provider: str | None = None) -> LogisticsAdapter:
    """
    获取查价适配器。默认在 BY56_ENABLED 时使用百运。
    """
    name = (provider or "").strip().lower() or "by56"
    settings = get_settings()

    if name == "by56":
        if not settings.by56_enabled:
            raise ValueError("BY56_ENABLED 未开启")
        return By56Adapter(settings)

    raise ValueError(f"未知物流适配器: {name}")
