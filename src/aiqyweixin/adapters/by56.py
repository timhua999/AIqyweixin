"""
百运（by56.com）快递查价适配器。

实现文档 docs/api/by56-quote-api.md：
- §3.1 公共请求（by56_client）
- §3.2 公共响应 ResultCode/Message/Data
- §3.6 获取货物种类 GetCommodityEXP（可配置 method）
- §3.7 快递查价（可配置 method）

官方文档：https://open.by56.com/apicus/#/common/preface
"""

from __future__ import annotations

import logging
from typing import Any

from aiqyweixin.adapters.base import LogisticsAdapter
from aiqyweixin.adapters.by56_client import By56ApiError, By56RouterClient
from aiqyweixin.config import Settings, get_settings
from aiqyweixin.models.dto import QuoteOffer, QuoteRequest, QuoteResult

logger = logging.getLogger(__name__)

# §3.7 查价：内部 QuoteRequest -> 百运业务参数名（请按 open.by56 接口详细 §3.7 调整）
BY56_QUOTE_FIELD_MAP: dict[str, str] = {
    "origin_city": "StartCity",
    "destination_country": "DestCountry",
    "destination_city": "DestCity",
    "weight_kg": "Weight",
    "volume_cbm": "Volume",
    "pieces": "Quantity",
    "goods_type_id": "CommodityID",
    "origin_country": "StartCountry",
}

# 响应 Data 内渠道列表可能的字段名
_LIST_KEYS = ("ChannelList", "channels", "list", "List", "Items", "PriceList")
_NAME_KEYS = ("ChannelName", "channelName", "ModeName", "ProductName", "Name")
_PRICE_KEYS = ("TotalPrice", "totalPrice", "Price", "price", "Amount", "Freight", "TotalFee")
_CURRENCY_KEYS = ("Currency", "currency", "CurrencyCode")
_TIME_KEYS = ("TransitTime", "transitTime", "WorkDays", "Days", "Aging")
_WEIGHT_KEYS = ("ChargeWeight", "chargeWeight", "BillWeight", "Weight")


def _first_key(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in item and item[k] is not None:
            return item[k]
    return None


def _unwrap_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in _LIST_KEYS:
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def _parse_offers_from_data(data: Any) -> list[QuoteOffer]:
    offers: list[QuoteOffer] = []
    for item in _unwrap_list(data):
        name = _first_key(item, _NAME_KEYS)
        price = _first_key(item, _PRICE_KEYS)
        if name is None or price is None:
            continue
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            continue
        cw = _first_key(item, _WEIGHT_KEYS)
        charge: float | None = None
        if cw is not None:
            try:
                charge = float(cw)
            except (TypeError, ValueError):
                charge = None
        tt = _first_key(item, _TIME_KEYS)
        cur = _first_key(item, _CURRENCY_KEYS) or "CNY"
        offers.append(
            QuoteOffer(
                channel_name=str(name),
                total_price=price_f,
                currency=str(cur),
                transit_time=str(tt) if tt is not None else None,
                charge_weight_kg=charge,
                provider="by56",
                raw=item,
            )
        )
    return offers


class By56Adapter(LogisticsAdapter):
    provider = "by56"

    def __init__(self, settings: Settings | None = None) -> None:
        self._client = By56RouterClient(settings)

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured

    def _build_quote_business(self, request: QuoteRequest) -> dict[str, str]:
        internal: dict[str, Any] = {
            "origin_city": request.origin_city,
            "origin_country": request.origin_country,
            "destination_country": request.destination_country,
            "destination_city": request.destination_city,
            "weight_kg": request.weight_kg,
            "volume_cbm": request.volume_cbm,
            "pieces": request.pieces,
            "goods_type_id": request.extra.get("commodity_id") if request.extra else None,
        }
        internal.update(request.extra or {})

        biz: dict[str, str] = {}
        for inner_key, by56_key in BY56_QUOTE_FIELD_MAP.items():
            val = internal.get(inner_key)
            if val is not None and val != "":
                biz[by56_key] = str(val)
        return biz

    async def _resolve_commodity_id_async(self, goods_type: str | None) -> str | None:
        if not goods_type or not str(goods_type).strip():
            return None
        text = str(goods_type).strip()
        if text.isdigit():
            return text
        if not self._client.method_commodity:
            return None
        try:
            data = await self._client.get_commodity_exp()
        except By56ApiError:
            logger.warning("§3.6 获取货物种类失败，跳过 CommodityID 映射")
            return None

        for row in _unwrap_list(data):
            name = _first_key(row, ("Name", "name", "CommodityName", "GoodsName"))
            cid = _first_key(row, ("ID", "Id", "id", "CommodityID", "CommodityId"))
            if name and cid and text in str(name):
                return str(cid)
        return None

    async def list_commodities(self) -> list[dict[str, Any]]:
        """§3.6 获取货物种类列表。"""
        data = await self._client.get_commodity_exp()
        return _unwrap_list(data)

    async def quote(self, request: QuoteRequest) -> QuoteResult:
        if not self.is_configured:
            return QuoteResult(
                success=False,
                error_code="BY56_NOT_CONFIGURED",
                error_message="未配置 BY56_BASE_URL / BY56_BYKEY / BY56_APP_SECRET",
            )

        biz = self._build_quote_business(request)
        if request.goods_type and "CommodityID" not in biz:
            cid = await self._resolve_commodity_id_async(request.goods_type)
            if cid:
                biz["CommodityID"] = cid

        try:
            data = await self._client.query_price_exp(biz)
        except By56ApiError as exc:
            logger.exception("BY56 §3.7 查价失败")
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
                error_message="查价成功但未解析到渠道列表，请核对 §3.7 响应字段或 BY56_QUOTE_FIELD_MAP",
                raw_response=data if isinstance(data, dict) else {"Data": data},
            )
        return QuoteResult(
            success=True,
            offers=offers,
            raw_response=data if isinstance(data, dict) else {"Data": data},
        )
