"""
数据库模型定义（PostgreSQL）。

职责：
- 未答工单：记录用户原文、意图、触发原因码、API 错误等（FR-3.7）
- 后续扩展：handoff_default / handoff_rule / staff_org_map / org_unit 等表
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Identity, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """ORM 基类（所有表模型继承此类）。"""


class UnansweredTicket(Base):
    """
    未答工单（FR-3.7.1 / FR-3.7.2）。

    assigned_userids_json：指派客服企微 userid 列表的 JSON 字符串（如 ["zhangsan"]）。
    """

    __tablename__ = "unanswered_tickets"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    wecom_user_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    raw_user_text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_or_rule_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    api_called: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    api_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        index=True,
    )

    handoff_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route_rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_userids_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    mention_sent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    invite_sent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
