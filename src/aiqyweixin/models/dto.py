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
