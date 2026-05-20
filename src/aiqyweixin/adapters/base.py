"""
物流商适配器接口定义。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aiqyweixin.models.dto import QuoteRequest, QuoteResult


class LogisticsAdapter(ABC):
    """查价 / 轨迹等能力的统一入口。"""

    provider: str

    @abstractmethod
    async def quote(self, request: QuoteRequest) -> QuoteResult:
        """询价；价格数字必须来自远端 API 响应，不得由模型编造。"""
