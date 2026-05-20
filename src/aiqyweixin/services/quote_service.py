"""
询价服务：调用物流适配器，输出统一 QuoteResult。
"""

from __future__ import annotations

import logging

from aiqyweixin.adapters.registry import get_quote_adapter
from aiqyweixin.config import get_settings
from aiqyweixin.models.dto import QuoteRequest, QuoteResult

logger = logging.getLogger(__name__)


def by56_quote_enabled() -> bool:
    s = get_settings()
    bykey = (s.by56_bykey or s.by56_app_id or "").strip()
    return bool(s.by56_enabled and s.by56_base_url and bykey and s.by56_app_secret)


async def list_by56_commodities() -> list[dict[str, object]]:
    """§3.6 货物种类列表。"""
    from aiqyweixin.adapters.by56 import By56Adapter

    adapter = By56Adapter()
    return await adapter.list_commodities()


async def query_quote(request: QuoteRequest, *, provider: str | None = None) -> QuoteResult:
    """执行查价；价格仅来自适配器返回的 offers。"""
    adapter = get_quote_adapter(provider)
    logger.info(
        "查价 provider=%s %s->%s %.2fkg",
        adapter.provider,
        request.origin_country,
        request.destination_country,
        request.weight_kg,
    )
    return await adapter.quote(request)
