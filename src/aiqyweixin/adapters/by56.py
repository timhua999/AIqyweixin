"""
百运（by56.com）适配器。

- §3.1/§3.2：by56_client 公共请求与响应
- §3.6：GetCommodityEXP 货物种类
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

# 查价字段映射（待 open.by56 查价接口文档补全后使用）
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

_LIST_KEYS = ("ChannelList", "channels", "list", "List", "Items", "PriceList")
_NAME_KEYS = ("ChannelName", "channelName", "ModeName", "ProductName", "Name")
_PRICE_KEYS = ("TotalPrice", "totalPrice", "Price", "price", "Amount", "Freight", "TotalFee")
_CURRENCY_KEYS = ("Currency", "currency", "CurrencyCode")
_TIME_KEYS = ("TransitTime", "transitTime", "WorkDays", "Days", "Aging")
_WEIGHT_KEYS = ("ChargeWeight", "chargeWeight", "BillWeight", "Weight")

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

    async def list_commodities(self) -> list[dict[str, Any]]:
        """§3.6 获取货物种类列表。"""
        data = await self._client.get_commodity_exp()
        return _unwrap_list(data)

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

    async def quote(self, request: QuoteRequest) -> QuoteResult:
        if not self.is_configured:
            return QuoteResult(
                success=False,
                error_code="BY56_NOT_CONFIGURED",
                error_message="未配置 BY56_BASE_URL / BY56_BYKEY / BY56_APP_SECRET",
            )
        if not self._client.method_quote:
            return QuoteResult(
                success=False,
                error_code="BY56_QUOTE_NOT_CONFIGURED",
                error_message="未配置 BY56_METHOD_QUOTE；§3.7 为 GetDeliveryNO 跟踪号接口，请用 get_delivery_no",
            )

        biz = self._build_quote_business(request)
        if request.goods_type and "CommodityID" not in biz:
            cid = await self._resolve_commodity_id_async(request.goods_type)
            if cid:
                biz["CommodityID"] = cid

        try:
            data = await self._client.query_price_exp(biz)
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
                error_message="查价成功但未解析到渠道列表，请核对响应字段或 BY56_QUOTE_FIELD_MAP",
                raw_response=data if isinstance(data, dict) else {"Data": data},
            )
        return QuoteResult(
            success=True,
            offers=offers,
            raw_response=data if isinstance(data, dict) else {"Data": data},
        )
