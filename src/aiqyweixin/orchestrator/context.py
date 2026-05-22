"""企微回调上下文（供编排与工单入库）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WecomMessageContext:
    msgid: str
    wecom_user_id: str
    conversation_id: str | None = None
    chat_type: str | None = None
