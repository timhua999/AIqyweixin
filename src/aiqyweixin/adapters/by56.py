"""
百运（by56.com）适配器。

- §3.1/§3.2：by56_client 公共请求与响应
- §3.1 快递查价：GetCommodityEXP（StartCityKey / CountryKey / Weight 等）
- §3.7：GetDeliveryNO 获取跟踪号（非查价）

官方文档：https://open.by56.com/apicus/#/common/preface
"""

from __future__ import annotations

import logging
from typing import Any

from aiqyweixin.adapters.base import LogisticsAdapter
from aiqyweixin.adapters.by56_client import By56ApiError, By56RouterClient
from aiqyweixin.config import Settings, get_settings
from aiqyweixin.models.dto import (
    BY56_WAYBILL_TYPE_EXPRESS,
    BY56_WAYBILL_TYPE_FBA,
    DeliveryNoItem,
    DeliveryNoRequest,
    DeliveryNoResult,
    QuoteOffer,
    QuoteRequest,
    QuoteResult,
)

logger = logging.getLogger(__name__)

# §3.1 快递查价 GetCommodityEXP：内部 DTO 字段 → 百运业务参数
BY56_QUOTE_FIELD_MAP: dict[str, str] = {
    "origin_city": "StartCityKey",
    "destination_country": "CountryKey",
    "weight_kg": "Weight",
    "volume_cbm": "Volume",
    "pieces": "Quanlity",
    "goods_type_id": "SpecialItems",
    "transport_mode": "ModeCode",
}

# 文档枚举：货物种类 ID（SpecialItems，可多 ID 英文逗号分隔）
BY56_SPECIAL_ITEMS: dict[str, str] = {
    "普货": "139",
    "内置电池": "108",
    "配套电池": "109",
    "移动电源": "111",
    "纯电池": "103",
    "手机 (无电)": "110",
    "手机 (内电)": "204",
    "手机 (配电)": "205",
    "电子烟": "105",
    "电容": "203",
    "纺织品": "106",
    "木箱": "107",
    "食品": "296",
    "防疫物资": "308",
    "电子产品": "320",
}

# extra 中可直接透传的百运字段名
BY56_QUOTE_PASSTHROUGH_KEYS: frozenset[str] = frozenset(
    {
        "StartCityKey",
        "CountryKey",
        "Weight",
        "Volume",
        "SpecialItems",
        "ModeCode",
        "PackgeType",
        "ChannelNames",
        "ChannelCodes",
        "QueryType",
        "Quanlity",
        "GoodInfos",
    }
)

_DEFAULT_START_CITY = "深圳市"
_DEFAULT_PACKGE_TYPE = 1  # 1=WPX, 2=DOC, 3=PAK

_LIST_KEYS = ("ChannelList", "channels", "list", "List", "Items", "PriceList")
_NAME_KEYS = ("ChannelName", "channelName", "ModeName", "ProductName", "Name")
_TOTAL_PRICE_KEYS = ("TotalPrice", "totalPrice", "Amount", "Freight", "TotalFee")
_UNIT_PRICE_KEYS = ("Price", "price")
_CURRENCY_KEYS = ("Currency", "currency", "CurrencyCode")
_TIME_KEYS = ("Period", "TransitTime", "transitTime", "WorkDays", "Days", "Aging")
_WEIGHT_KEYS = ("CharWeight", "ChargeWeight", "chargeWeight", "BillWeight")
_FEE_TOTAL_KEYS = ("FeeTotal", "FeeToal", "feeTotal")

def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    if isinstance(val, (int, float)):
        return bool(val)
    return False


def _parse_delivery_row(row: dict[str, Any]) -> DeliveryNoItem | None:
    """§3.7 Data[] 单条：WaybillNO / IsDeliveryNO / DeliveryNO / ModeCode / BaseModeCode。"""
    wb = row.get("WaybillNO")
    if wb is None or str(wb).strip() == "":
        return None
    delivery = row.get("DeliveryNO")
    return DeliveryNoItem(
        waybill_no=str(wb).strip(),
        is_delivery_no=_parse_bool(row.get("IsDeliveryNO")),
        delivery_no=str(delivery).strip() if delivery is not None and str(delivery).strip() else None,
        mode_code=str(row["ModeCode"]).strip() if row.get("ModeCode") is not None else None,
        base_mode_code=str(row["BaseModeCode"]).strip() if row.get("BaseModeCode") is not None else None,
        raw=row,
    )


def _parse_delivery_items(data: Any) -> list[DeliveryNoItem]:
    if isinstance(data, list):
        items: list[DeliveryNoItem] = []
        for row in data:
            if isinstance(row, dict):
                item = _parse_delivery_row(row)
                if item:
                    items.append(item)
        return items
    if isinstance(data, dict):
        item = _parse_delivery_row(data)
        return [item] if item else []
    return []


def _first_key(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in item and item[k] is not None:
            return item[k]
    return None


def _unwrap_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in _LIST_KEYS + ("Data", "Items", "List"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_fee_list(raw: Any) -> list[dict[str, Any]]:
    """保留接口 FeeList 原字段名与条目，全量入列表。"""
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("FeeName")
        if name is None or str(name).strip() == "":
            continue
        items.append(
            {
                "FeeName": str(name),
                "FeePrice": entry.get("FeePrice"),
            }
        )
    return items


def _parse_risk_warning(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text if text else None


def _parse_quote_row(row: dict[str, Any]) -> QuoteOffer | None:
    """§3.1 查价 Data[] 单条（ChannelName / TotalPrice / Period / CharWeight 等）。"""
    name = _first_key(row, _NAME_KEYS)
    total = _to_float(_first_key(row, _TOTAL_PRICE_KEYS))
    if name is None or total is None:
        return None
    channel = row.get("Channel")
    return QuoteOffer(
        channel_name=str(name),
        total_price=total,
        currency=str(_first_key(row, _CURRENCY_KEYS) or "CNY"),
        transit_time=str(v) if (v := _first_key(row, _TIME_KEYS)) is not None else None,
        charge_weight_kg=_to_float(_first_key(row, _WEIGHT_KEYS)),
        channel_id=str(channel).strip() if channel is not None and str(channel).strip() else None,
        mode_code=str(row["ModeCode"]).strip() if row.get("ModeCode") is not None else None,
        unit_price=_to_float(_first_key(row, _UNIT_PRICE_KEYS)),
        start_city=str(row["StartCityName"]).strip() if row.get("StartCityName") else None,
        country_name=str(row["CountryName"]).strip() if row.get("CountryName") else None,
        fee_total=_to_float(_first_key(row, _FEE_TOTAL_KEYS)),
        channel_description=_parse_risk_warning(row.get("ChannelDescription")),
        fee_list=_parse_fee_list(row.get("FeeList")),
        risk_warning=_parse_risk_warning(row.get("RiskWarning")),
        traffic_amount=_to_float(row.get("TrafficAmount")),
        is_tax=_parse_bool(row["IsTax"]) if row.get("IsTax") is not None else None,
        provider="by56",
        raw=row,
    )


def _parse_offers_from_data(data: Any) -> list[QuoteOffer]:
    offers: list[QuoteOffer] = []
    for item in _unwrap_list(data):
        if not isinstance(item, dict):
            continue
        offer = _parse_quote_row(item)
        if offer:
            offers.append(offer)
    offers.sort(key=lambda o: o.total_price)
    return offers


class By56Adapter(LogisticsAdapter):
    provider = "by56"

    def __init__(self, settings: Settings | None = None) -> None:
        self._client = By56RouterClient(settings)

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured

    async def list_commodities(self) -> list[dict[str, Any]]:
        """§3.1 文档枚举的货物种类（SpecialItems ID），非独立列表接口。"""
        return [{"id": vid, "name": name} for name, vid in BY56_SPECIAL_ITEMS.items()]

    async def get_delivery_no(self, request: DeliveryNoRequest) -> DeliveryNoResult:
        """§3.7 获取百运跟踪号。"""
        if not self.is_configured:
            return DeliveryNoResult(
                success=False,
                error_code="BY56_NOT_CONFIGURED",
                error_message="未配置 BY56_BASE_URL / BY56_BYKEY / BY56_APP_SECRET",
            )

        waybill_param = request.waybill_no_param()
        if not waybill_param:
            return DeliveryNoResult(
                success=False,
                error_code="INVALID_PARAM",
                error_message="WaybillNO 不能为空",
            )

        if request.waybill_type not in (BY56_WAYBILL_TYPE_EXPRESS, BY56_WAYBILL_TYPE_FBA):
            return DeliveryNoResult(
                success=False,
                error_code="INVALID_PARAM",
                error_message="WaybillType 仅支持 1（快递/专线）或 20（FBA）",
            )

        biz = {
            "WaybillNO": waybill_param,
            "WaybillType": str(request.waybill_type),
        }

        try:
            data = await self._client.get_delivery_no(biz)
        except By56ApiError as exc:
            logger.exception("BY56 §3.7 GetDeliveryNO 失败")
            return DeliveryNoResult(
                success=False,
                error_code=str(exc.result_code) if exc.result_code is not None else "BY56_ERROR",
                error_message=str(exc),
                raw_response=exc.raw,
            )

        items = _parse_delivery_items(data)
        return DeliveryNoResult(success=True, items=items, raw_response=data)

    def _resolve_special_items(self, goods_type: str | None, extra: dict[str, Any] | None) -> str | None:
        if extra:
            for key in ("SpecialItems", "special_items", "commodity_id", "goods_type_id"):
                val = extra.get(key)
                if val is not None and str(val).strip():
                    return str(val).strip()
        if not goods_type or not str(goods_type).strip():
            return None
        text = str(goods_type).strip()
        if text.isdigit() or ("," in text and all(p.strip().isdigit() for p in text.split(","))):
            return text
        if text in BY56_SPECIAL_ITEMS:
            return BY56_SPECIAL_ITEMS[text]
        for name, vid in BY56_SPECIAL_ITEMS.items():
            if name in text or text in name:
                return vid
        return None

    def _build_quote_business(self, request: QuoteRequest) -> dict[str, str]:
        extra = request.extra or {}
        internal: dict[str, Any] = {
            "origin_city": request.origin_city or extra.get("origin_city") or _DEFAULT_START_CITY,
            "destination_country": request.destination_country,
            "weight_kg": request.weight_kg,
            "volume_cbm": request.volume_cbm if request.volume_cbm is not None else extra.get("volume", 0),
            "pieces": request.pieces,
            "goods_type_id": self._resolve_special_items(request.goods_type, extra),
            "transport_mode": request.transport_mode,
        }
        biz: dict[str, str] = {}
        for inner_key, by56_key in BY56_QUOTE_FIELD_MAP.items():
            val = internal.get(inner_key)
            if val is not None and val != "":
                biz[by56_key] = str(val)

        packge = extra.get("PackgeType", extra.get("packge_type", _DEFAULT_PACKGE_TYPE))
        biz.setdefault("PackgeType", str(packge))

        for key in BY56_QUOTE_PASSTHROUGH_KEYS:
            if key in extra and extra[key] is not None and str(extra[key]).strip() != "":
                biz[key] = str(extra[key])
        return biz

    def _validate_quote_business(self, biz: dict[str, str]) -> str | None:
        if not biz.get("StartCityKey"):
            return "缺少起运城市 StartCityKey"
        country = (biz.get("CountryKey") or "").strip()
        if len(country) != 2:
            return "CountryKey 须为目的地国家二字码（如 US、GB）"
        if not biz.get("Weight"):
            return "缺少重量 Weight"
        if biz.get("Volume") is None:
            return "缺少体积 Volume"
        if not biz.get("SpecialItems"):
            return "缺少货物种类 SpecialItems（ID 或中文如「普货」）"
        if not biz.get("PackgeType"):
            return "缺少包裹类型 PackgeType（1=WPX，2=DOC，3=PAK）"
        return None

    async def quote(self, request: QuoteRequest) -> QuoteResult:
        if not self.is_configured:
            return QuoteResult(
                success=False,
                error_code="BY56_NOT_CONFIGURED",
                error_message="未配置 BY56_BASE_URL / BY56_BYKEY / BY56_APP_SECRET",
            )
        method = self._client.method_quote or self._client.method_commodity
        if not method:
            return QuoteResult(
                success=False,
                error_code="BY56_QUOTE_NOT_CONFIGURED",
                error_message="未配置 BY56_METHOD_QUOTE（§3.1 GetCommodityEXP 快递查价）",
            )

        biz = self._build_quote_business(request)
        err = self._validate_quote_business(biz)
        if err:
            return QuoteResult(success=False, error_code="INVALID_PARAM", error_message=err)

        try:
            data = await self._client.call_ok(method, biz)
        except By56ApiError as exc:
            logger.exception("BY56 查价失败")
            return QuoteResult(
                success=False,
                error_code=str(exc.result_code) if exc.result_code is not None else "BY56_ERROR",
                error_message=str(exc),
                raw_response=exc.raw if isinstance(exc.raw, dict) else None,
            )

        offers = _parse_offers_from_data(data)
        if not offers:
            return QuoteResult(
                success=True,
                offers=[],
                error_message="查价成功但未解析到渠道列表，请核对 Data 是否为渠道数组",
                raw_response=data if isinstance(data, dict) else {"Data": data},
            )
        return QuoteResult(
            success=True,
            offers=offers,
            raw_response=data if isinstance(data, dict) else {"Data": data},
        )
