"""
轨迹（§3.6）与跟踪号（§3.7）查询服务。
"""

from __future__ import annotations

import logging

from aiqyweixin.adapters.by56 import By56Adapter
from aiqyweixin.config import get_settings
from aiqyweixin.models.dto import (
    DeliveryNoRequest,
    DeliveryNoResult,
    TrackBatchResult,
    TrackQueryRequest,
)

logger = logging.getLogger(__name__)


def by56_enabled() -> bool:
    s = get_settings()
    bykey = (s.by56_bykey or s.by56_app_id or "").strip()
    return bool(s.by56_enabled and s.by56_base_url and bykey and s.by56_app_secret)


async def query_delivery_no(request: DeliveryNoRequest) -> DeliveryNoResult:
    """§3.7 百运获取跟踪号（GetDeliveryNO）。"""
    adapter = By56Adapter()
    logger.info(
        "§3.7 查询跟踪号 waybills=%s type=%s",
        request.waybill_no_param(),
        request.waybill_type,
    )
    return await adapter.get_delivery_no(request)


async def query_track_batch(request: TrackQueryRequest) -> TrackBatchResult:
    """§3.6 百运货物追踪（QueryBatch）。"""
    adapter = By56Adapter()
    logger.info("§3.6 货物追踪 TrackNo=%s", request.track_no_param())
    return await adapter.query_track_batch(request)
