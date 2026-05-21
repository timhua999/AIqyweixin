"""
企微轨迹/跟踪号编排：LLM 抽参 → §3.6 QueryBatch 或 §3.7 GetDeliveryNO。
"""

from __future__ import annotations

import logging
import re

from aiqyweixin.config import get_settings
from aiqyweixin.llm.client import LlmError, get_llm_client
from aiqyweixin.llm.extract import parse_json_object
from aiqyweixin.models.dto import (
    BY56_TRACK_MAX_NUMBERS,
    BY56_WAYBILL_TYPE_EXPRESS,
    BY56_WAYBILL_TYPE_FBA,
    DeliveryNoRequest,
    TrackQueryRequest,
)
from aiqyweixin.services.track_service import (
    by56_enabled,
    query_delivery_no,
    query_track_batch,
)

logger = logging.getLogger(__name__)

_EXTRACT_SYSTEM = """你是国际物流单号识别助手。根据用户消息判断要办的事，只输出 JSON。

意图 intent（必填）：
- "track"：§3.6 查物流轨迹/货物在哪/上网状态/物流节点（QueryBatch）
- "delivery_no"：§3.7 用订单号向百运换取承运跟踪号（GetDeliveryNO），不是查轨迹
- "chat"：其它咨询

字段：
- track_numbers: 字符串数组，单号列表（订单号、代理单号、跟踪号均可），最多 5 个
- waybill_type: 仅 intent=delivery_no 时有效，整数 1=快递专线 20=FBA，未提及则 1
- missing_fields: 仍缺的必填项中文说明（track/delivery_no 必填 track_numbers）

示例轨迹：
{"intent":"track","track_numbers":["WE01709009681"],"waybill_type":1,"missing_fields":[]}

示例换跟踪号：
{"intent":"delivery_no","track_numbers":["WE01711001841"],"waybill_type":1,"missing_fields":[]}
"""

_WECOM_REPLY_MAX_CHARS = 3800
_TRACK_HINTS = (
    "轨迹",
    "运单",
    "跟踪",
    "物流",
    "在哪",
    "上网",
    "查询",
    "单号",
    "waybill",
    "WE0",
)
_ORDER_NO_RE = re.compile(r"\b(WE\d{8,}|400\d{6,}|\d{10,})\b", re.IGNORECASE)


def _llm_ready() -> bool:
    s = get_settings()
    if not s.llm_enabled:
        return False
    return get_llm_client().is_configured


def track_flow_available() -> bool:
    return by56_enabled() and _llm_ready()


def _truncate_wecom(text: str, limit: int = _WECOM_REPLY_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n（回复过长已截断）"


def _might_be_track_or_delivery(text: str) -> bool:
    if not text:
        return False
    if any(h in text for h in _TRACK_HINTS):
        return True
    return bool(_ORDER_NO_RE.search(text))


def _numbers_from_text(text: str) -> list[str]:
    found = _ORDER_NO_RE.findall(text)
    return list(dict.fromkeys(n.strip() for n in found if n.strip()))[:BY56_TRACK_MAX_NUMBERS]


def _parse_numbers(data: dict, fallback_text: str) -> list[str]:
    raw = data.get("track_numbers") or data.get("numbers") or data.get("waybill_numbers")
    nums: list[str] = []
    if isinstance(raw, list):
        for x in raw:
            if x is not None and str(x).strip():
                nums.append(str(x).strip())
    elif isinstance(raw, str) and raw.strip():
        nums = [p.strip() for p in re.split(r"[,，\s]+", raw) if p.strip()]
    if not nums:
        nums = _numbers_from_text(fallback_text)
    return nums[:BY56_TRACK_MAX_NUMBERS]


def _missing_track_prompt(missing: list[str]) -> str:
    labels = "、".join(missing) if missing else "单号（订单号/跟踪号，最多 5 个）"
    return (
        f"**信息不完整**\n\n还缺少：{labels}。\n\n"
        "示例：\n> 查轨迹 WE01709009681\n> 查跟踪号 WE01711001841"
    )


async def _extract_params(user_text: str) -> dict:
    client = get_llm_client()
    result = await client.chat(user_text, system_prompt=_EXTRACT_SYSTEM)
    return parse_json_object(result.content)


async def try_build_track_reply(user_text: str) -> str | None:
    """§3.6 轨迹或 §3.7 换跟踪号；非此类返回 None。"""
    if not track_flow_available():
        return None

    text = (user_text or "").strip()
    if not text or not _might_be_track_or_delivery(text):
        return None

    try:
        data = await _extract_params(text)
    except (LlmError, ValueError, Exception):
        logger.exception("轨迹/跟踪号参数抽取失败")
        nums = _numbers_from_text(text)
        if not nums:
            return None
        data = {"intent": "track", "track_numbers": nums, "missing_fields": []}

    intent = str(data.get("intent") or "chat").strip().lower()
    nums = _parse_numbers(data, text)
    missing = data.get("missing_fields")
    miss_list = [str(x) for x in missing] if isinstance(missing, list) else []

    if intent not in ("track", "delivery_no"):
        return None

    if not nums:
        if not miss_list:
            miss_list.append("单号")
        return _missing_track_prompt(miss_list)

    logger.info("百运 intent=%s numbers=%s", intent, nums)

    if intent == "delivery_no":
        try:
            wt = int(data.get("waybill_type", BY56_WAYBILL_TYPE_EXPRESS))
        except (TypeError, ValueError):
            wt = BY56_WAYBILL_TYPE_EXPRESS
        if wt not in (BY56_WAYBILL_TYPE_EXPRESS, BY56_WAYBILL_TYPE_FBA):
            wt = BY56_WAYBILL_TYPE_EXPRESS
        req = DeliveryNoRequest(waybill_numbers=nums, waybill_type=wt)
        result = await query_delivery_no(req)
        return _truncate_wecom(result.to_markdown())

    req = TrackQueryRequest(track_numbers=nums)
    result = await query_track_batch(req)
    return _truncate_wecom(result.to_markdown())
