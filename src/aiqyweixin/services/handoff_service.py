"""
转人工兜底服务。

- 关键词 / 意图规则 → 目标客服 userid（.env 配置）
- 写入未答工单（需 DATABASE_URL）
- 单聊返回降级话术（智能机器人无法 @ 时仅文字提示）
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from aiqyweixin.config import Settings, get_settings

logger = logging.getLogger(__name__)

# 用户明确要求人工
_HANDOFF_KEYWORDS = (
    "转人工",
    "人工客服",
    "找客服",
    "联系客服",
    "真人",
    "人工服务",
)


@dataclass(frozen=True)
class HandoffDecision:
    reason_code: str
    route_rule_id: str | None
    target_userids: list[str]
    reply_markdown: str


def handoff_enabled() -> bool:
    s = get_settings()
    return bool(s.handoff_enabled)


def user_requests_handoff(text: str) -> bool:
    if not text:
        return False
    return any(k in text for k in _HANDOFF_KEYWORDS)


def _parse_userid_list(raw: str | None) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    text = str(raw).strip()
    if text.startswith("["):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [p.strip() for p in re.split(r"[,，;；\s]+", text) if p.strip()]


def resolve_handoff_targets(
    user_text: str,
    *,
    intent: str | None = None,
    reason_code: str = "manual_or_fallback",
) -> HandoffDecision:
    s = get_settings()
    targets = _parse_userid_list(s.handoff_default_userids)
    rule_id: str | None = "default"

    if user_requests_handoff(user_text):
        reason_code = "user_request_handoff"
        rule_id = "keyword_handoff"

    rules_raw = (s.handoff_keyword_rules or "").strip()
    if rules_raw:
        for line in rules_raw.splitlines():
            line = line.strip()
            if not line or "=>" not in line:
                continue
            kw, ids_part = line.split("=>", 1)
            if kw.strip() and kw.strip() in user_text:
                extra = _parse_userid_list(ids_part)
                if extra:
                    targets = extra
                    rule_id = f"keyword:{kw.strip()}"
                    reason_code = "keyword_rule"
                    break

    mention = ""
    if targets:
        ids_text = "、".join(f"**{u}**" for u in targets)
        mention = f"\n\n已通知客服：{ids_text}"
    fallback = (s.handoff_dm_fallback_message or "").strip() or (
        "您的问题已记录，客服将尽快通过企业微信与您联系。"
    )
    reply = f"**已转人工客服**{mention}\n\n{fallback}"
    return HandoffDecision(
        reason_code=reason_code,
        route_rule_id=rule_id,
        target_userids=targets,
        reply_markdown=reply,
    )


async def record_and_build_handoff(
    user_text: str,
    *,
    wecom_user_id: str,
    conversation_id: str | None = None,
    intent: str | None = None,
    reason_code: str = "fallback",
    model_or_rule_notes: str | None = None,
    api_called: bool = False,
    api_error: str | None = None,
) -> HandoffDecision:
    """写入未答工单（若已配置库）并返回对用户展示文案。"""
    decision = resolve_handoff_targets(
        user_text,
        intent=intent,
        reason_code=reason_code,
    )
    await _persist_ticket(
        user_text=user_text,
        wecom_user_id=wecom_user_id,
        conversation_id=conversation_id,
        intent=intent,
        decision=decision,
        model_or_rule_notes=model_or_rule_notes,
        api_called=api_called,
        api_error=api_error,
    )
    return decision


async def _persist_ticket(
    *,
    user_text: str,
    wecom_user_id: str,
    conversation_id: str | None,
    intent: str | None,
    decision: HandoffDecision,
    model_or_rule_notes: str | None,
    api_called: bool,
    api_error: str | None,
) -> None:
    s = get_settings()
    if not s.database_url or not s.unanswered_save_enabled:
        return
    try:
        from aiqyweixin.persistence.session import get_session_factory
        from aiqyweixin.persistence.repositories import create_unanswered_ticket

        assigned = json.dumps(decision.target_userids, ensure_ascii=False) if decision.target_userids else None
        factory = get_session_factory()
        async with factory() as db:
            await create_unanswered_ticket(
                db,
                wecom_user_id=wecom_user_id or "unknown",
                raw_user_text=user_text,
                conversation_id=conversation_id,
                intent=intent,
                model_or_rule_notes=model_or_rule_notes,
                api_called=api_called,
                api_error=api_error,
                status="pending",
                handoff_reason_code=decision.reason_code,
                route_rule_id=decision.route_rule_id,
                assigned_userids_json=assigned,
            )
            await db.commit()
        logger.info(
            "未答工单已入库 reason=%s user=%s",
            decision.reason_code,
            wecom_user_id,
        )
    except Exception:
        logger.exception("未答工单入库失败（仍返回转人工话术）")
