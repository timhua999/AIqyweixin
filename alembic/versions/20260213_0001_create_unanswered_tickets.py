"""create unanswered_tickets table

Revision ID: 20260213_0001
Revises:
Create Date: 2026-02-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260213_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unanswered_tickets",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("wecom_user_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.String(length=256), nullable=True),
        sa.Column("raw_user_text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=True),
        sa.Column("model_or_rule_notes", sa.Text(), nullable=True),
        sa.Column(
            "api_called",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("api_error", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("handoff_reason_code", sa.String(length=64), nullable=True),
        sa.Column("route_rule_id", sa.String(length=64), nullable=True),
        sa.Column("assigned_userids_json", sa.Text(), nullable=True),
        sa.Column("mention_sent", sa.Boolean(), nullable=True),
        sa.Column("invite_sent", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_unanswered_tickets_conversation_id"),
        "unanswered_tickets",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_unanswered_tickets_status"),
        "unanswered_tickets",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_unanswered_tickets_wecom_user_id"),
        "unanswered_tickets",
        ["wecom_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_unanswered_tickets_wecom_user_id"), table_name="unanswered_tickets")
    op.drop_index(op.f("ix_unanswered_tickets_status"), table_name="unanswered_tickets")
    op.drop_index(op.f("ix_unanswered_tickets_conversation_id"), table_name="unanswered_tickets")
    op.drop_table("unanswered_tickets")
