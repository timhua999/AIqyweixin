"""
内部标准 DTO（服务层 ↔ 适配器层契约）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuoteRequest:
    """统一查价入参。"""

    origin_country: str
    destination_country: str
    weight_kg: float
    origin_city: str | None = None
    destination_city: str | None = None
    volume_cbm: float | None = None
    pieces: int = 1
    goods_type: str | None = None
    transport_mode: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuoteOffer:
    """单条渠道报价。"""

    channel_name: str
    total_price: float
    currency: str = "CNY"
    transit_time: str | None = None
    charge_weight_kg: float | None = None
    provider: str = "by56"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuoteResult:
    """查价结果。"""

    success: bool
    offers: list[QuoteOffer] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] | None = None

    def to_markdown(self, *, max_offers: int = 5) -> str:
        """格式化为企微 markdown（价格仅来自 API 出参）。"""
        if not self.success:
            msg = self.error_message or "查价失败"
            if self.error_code:
                return f"**查价失败**（{self.error_code}）\n\n{msg}"
            return f"**查价失败**\n\n{msg}"

        if not self.offers:
            return "**查价成功**，但未返回可用渠道，请检查参数或联系业务系统。"

        lines = ["**查价结果**（数据来源：百运 API）", ""]
        for i, offer in enumerate(self.offers[:max_offers], start=1):
            price = offer.total_price
            cur = offer.currency or "CNY"
            tt = f"，时效 {offer.transit_time}" if offer.transit_time else ""
            cw = ""
            if offer.charge_weight_kg is not None:
                cw = f"，计费重 {offer.charge_weight_kg}kg"
            lines.append(f"{i}. **{offer.channel_name}**：**{price} {cur}**{tt}{cw}")
        if len(self.offers) > max_offers:
            lines.append(f"\n… 另有 {len(self.offers) - max_offers} 条渠道未展示")
        return "\n".join(lines)


# 百运 §3.7 WaybillType
BY56_WAYBILL_TYPE_EXPRESS: int = 1  # 快递、专线
BY56_WAYBILL_TYPE_FBA: int = 20


@dataclass
class DeliveryNoRequest:
    """§3.7 获取百运跟踪号入参。"""

    waybill_numbers: list[str]
    waybill_type: int = BY56_WAYBILL_TYPE_EXPRESS

    def waybill_no_param(self) -> str:
        """多个订单号用英文逗号拼接。"""
        parts = [n.strip() for n in self.waybill_numbers if n and str(n).strip()]
        return ",".join(parts)


@dataclass
class DeliveryNoItem:
    """§3.7 Data 数组单条。"""

    waybill_no: str
    is_delivery_no: bool = False
    delivery_no: str | None = None
    mode_code: str | None = None
    base_mode_code: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryNoResult:
    success: bool
    items: list[DeliveryNoItem] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    raw_response: Any = None

    def to_markdown(self) -> str:
        if not self.success:
            msg = self.error_message or "查询失败"
            code = f"（{self.error_code}）" if self.error_code else ""
            return f"**跟踪号查询失败**{code}\n\n{msg}"
        if not self.items:
            return "**跟踪号查询成功**，但未返回数据。"
        lines = ["**百运跟踪号查询结果**", ""]
        for row in self.items:
            mode_parts = [p for p in (row.base_mode_code, row.mode_code) if p]
            mode = f"（{' / '.join(mode_parts)}）" if mode_parts else ""
            if row.is_delivery_no and row.delivery_no:
                lines.append(
                    f"- 订单号 **{row.waybill_no}** → 跟踪号 **{row.delivery_no}**{mode}"
                )
            else:
                lines.append(f"- 订单号 **{row.waybill_no}**：暂无跟踪号{mode}")
        return "\n".join(lines)
