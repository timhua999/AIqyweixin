"""
轨迹 / 跟踪号查询服务。
"""

from __future__ import annotations

import logging

from aiqyweixin.adapters.by56 import By56Adapter
from aiqyweixin.config import get_settings
from aiqyweixin.models.dto import DeliveryNoRequest, DeliveryNoResult

logger = logging.getLogger(__name__)


def by56_enabled() -> bool:
    s = get_settings()
    bykey = (s.by56_bykey or s.by56_app_id or "").strip()
    return bool(s.by56_enabled and s.by56_base_url and bykey and s.by56_app_secret)


async def query_delivery_no(request: DeliveryNoRequest) -> DeliveryNoResult:
    """§3.7 百运获取跟踪号（GetDeliveryNO）。"""
    adapter = By56Adapter()
    logger.info(
        "查询跟踪号 waybills=%s type=%s",
        request.waybill_no_param(),
        request.waybill_type,
    )
    return await adapter.get_delivery_no(request)
