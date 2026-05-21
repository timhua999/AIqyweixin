"""
企微询价编排：LLM 抽取百运 §3.1 入参 → 调用查价 → 格式化回复。
"""

from __future__ import annotations

import logging
import re

from aiqyweixin.config import get_settings
from aiqyweixin.llm.client import LlmError, get_llm_client
from aiqyweixin.llm.extract import parse_json_object
from aiqyweixin.models.dto import QuoteRequest
from aiqyweixin.services.quote_service import by56_quote_enabled, query_quote

logger = logging.getLogger(__name__)

_EXTRACT_SYSTEM = """你是国际物流询价参数抽取助手。根据用户一条消息，判断意图并提取百运快递查价（GetCommodityEXP）所需字段。

只输出一个 JSON 对象，不要 markdown、不要解释。字段：
- intent: "quote"=询价/运费/报价/多少钱；"track"=查轨迹/运单/跟踪号；其它="chat"
- origin_city: 起运城市中文，未提及则 "深圳市"
- destination_country_code: 目的国家/地区 ISO 3166-1 二位大写字母（如 US、GB、DE、AU、CA、JP）。用户说「美国」则 US。
- weight_kg: 重量(kg)，数字；无法确定则 null
- volume_cbm: 体积立方米，未提及则 0
- goods_type: 货物种类中文（普货、内置电池、配套电池、纺织品、木箱、电子产品等），未提及则 "普货"
- pieces: 件数，未提及则 1
- packge_type: 包裹类型整数 1=WPX包裹 2=DOC文件 3=PAK，未提及则 1
- missing_fields: 字符串数组，列出仍无法从消息得到的必填项（必填：destination_country_code、weight_kg）

示例：
{"intent":"quote","origin_city":"深圳市","destination_country_code":"US","weight_kg":10,"volume_cbm":0,"goods_type":"普货","pieces":1,"packge_type":1,"missing_fields":[]}
"""

_WECOM_REPLY_MAX_CHARS = 3800
_DEFAULT_MAX_OFFERS = 3
_QUOTE_HINTS = (
    "询价",
    "查价",
    "报价",
    "运费",
    "价格",
    "多少钱",
    "多少錢",
    "快递",
    "普货",
    "发货",
    "发到",
    "寄到",
    "kg",
    "公斤",
    "立方",
)


def _might_be_quote(text: str) -> bool:
    """粗判是否可能询价，减少无关消息的二次 LLM。"""
    if not text:
        return False
    if any(h in text for h in _QUOTE_HINTS):
        return True
    if re.search(r"\d+(\.\d+)?\s*(kg|kgs|公斤)", text, re.IGNORECASE):
        return True
    return False


def _llm_ready() -> bool:
    s = get_settings()
    if not s.llm_enabled:
        return False
    return get_llm_client().is_configured


def quote_flow_available() -> bool:
    return by56_quote_enabled() and _llm_ready()


def _truncate_wecom(text: str, limit: int = _WECOM_REPLY_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n（回复过长已截断，可补充条件后重新询价）"


def _normalize_country_code(val: object) -> str | None:
    if val is None:
        return None
    code = str(val).strip().upper()
    if re.fullmatch(r"[A-Z]{2}", code):
        return code
    return None


def _to_float(val: object) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _build_missing_prompt(missing: list[str]) -> str:
    labels = "、".join(missing) if missing else "目的地国家（二字码）、重量(kg)"
    return (
        "**询价信息不完整**\n\n"
        f"还缺少：{labels}。\n\n"
        "请补充后重新发送，例如：\n"
        "> 深圳发美国，普货，10kg，体积0"
    )


def _quote_request_from_extracted(data: dict) -> tuple[QuoteRequest | None, list[str]]:
    missing: list[str] = []
    raw_missing = data.get("missing_fields")
    if isinstance(raw_missing, list):
        missing.extend(str(x) for x in raw_missing if x)

    country = _normalize_country_code(data.get("destination_country_code"))
    if not country:
        if "destination_country_code" not in missing and "目的国" not in "".join(missing):
            missing.append("目的国")

    weight = _to_float(data.get("weight_kg"))
    if weight is None or weight <= 0:
        if not any("重量" in m or "weight" in m.lower() for m in missing):
            missing.append("重量(kg)")

    if missing:
        return None, missing

    packge = data.get("packge_type", 1)
    try:
        packge_i = int(packge)
    except (TypeError, ValueError):
        packge_i = 1
    if packge_i not in (1, 2, 3):
        packge_i = 1

    pieces = data.get("pieces", 1)
    try:
        pieces_i = int(pieces)
    except (TypeError, ValueError):
        pieces_i = 1
    if pieces_i < 1:
        pieces_i = 1

    volume = _to_float(data.get("volume_cbm"))
    if volume is None:
        volume = 0.0

    origin_city = str(data.get("origin_city") or "深圳市").strip() or "深圳市"
    goods_type = str(data.get("goods_type") or "普货").strip() or "普货"

    req = QuoteRequest(
        origin_country="CN",
        destination_country=country or "US",
        origin_city=origin_city,
        weight_kg=weight or 0.0,
        volume_cbm=volume,
        pieces=pieces_i,
        goods_type=goods_type,
        extra={"PackgeType": packge_i},
    )
    return req, []


async def _extract_quote_params(user_text: str) -> dict:
    client = get_llm_client()
    result = await client.chat(user_text, system_prompt=_EXTRACT_SYSTEM)
    return parse_json_object(result.content)


async def try_build_quote_reply(
    user_text: str,
    *,
    max_offers: int | None = None,
) -> str | None:
    """
    若判定为询价且参数足够，返回百运查价 markdown；否则返回 None 走通用对话。
    """
    if not quote_flow_available():
        return None

    if max_offers is None:
        max_offers = max(1, int(get_settings().wecom_quote_max_offers))

    text = (user_text or "").strip()
    if not text:
        return None
    if not _might_be_quote(text):
        return None

    try:
        extracted = await _extract_quote_params(text)
    except (LlmError, ValueError, Exception):
        logger.exception("询价参数抽取失败，回退通用 LLM")
        return None

    intent = str(extracted.get("intent") or "chat").strip().lower()
    logger.info("询价意图抽取 intent=%s keys=%s", intent, list(extracted.keys()))

    if intent == "track":
        return None
    if intent != "quote":
        return None

    req, missing = _quote_request_from_extracted(extracted)
    if req is None:
        return _build_missing_prompt(missing)

    logger.info(
        "百运查价 %s -> %s %.2fkg 货类=%s",
        req.origin_city,
        req.destination_country,
        req.weight_kg,
        req.goods_type,
    )
    result = await query_quote(req)
    if not result.success:
        code = result.error_code or ""
        msg = result.error_message or "查价失败"
        return _truncate_wecom(f"**查价失败**（{code}）\n\n{msg}")

    body = result.to_markdown(max_offers=max_offers)
    total = len(result.offers)
    if total > max_offers:
        body += f"\n\n共返回 **{total}** 条渠道，以上展示前 **{max_offers}** 条（按总价从低到高）。"
    return _truncate_wecom(body)
