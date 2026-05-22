"""
企微对话回复编排：

轨迹/跟踪号 → 询价 → 知识库 → 通用 LLM → 转人工 + 未答入库。
"""

from __future__ import annotations

import logging

from aiqyweixin.config import get_settings
from aiqyweixin.llm.client import LlmError, LlmNotConfiguredError, get_llm_client
from aiqyweixin.orchestrator.context import WecomMessageContext
from aiqyweixin.orchestrator.quote_flow import try_build_quote_reply
from aiqyweixin.orchestrator.track_flow import try_build_track_reply
from aiqyweixin.services.handoff_service import (
    handoff_enabled,
    record_and_build_handoff,
    user_requests_handoff,
)
from aiqyweixin.services.kb_service import kb_enabled, try_answer_from_kb
from aiqyweixin.wecom.messages import format_reply_text

logger = logging.getLogger(__name__)

_DEFAULT_REPLY_TEMPLATE = "已收到您的消息：{content}"
_LLM_FALLBACK = "抱歉，智能回复暂时不可用，请稍后再试或联系人工客服。"


def _template_reply(user_text: str | None) -> str:
    custom = (get_settings().wecom_reply_text or "").strip()
    template = custom or _DEFAULT_REPLY_TEMPLATE
    return format_reply_text(user_text, template)


def llm_is_enabled() -> bool:
    settings = get_settings()
    if not settings.llm_enabled:
        return False
    return get_llm_client().is_configured


async def _handoff_reply(
    user_text: str,
    ctx: WecomMessageContext,
    *,
    reason_code: str,
    intent: str | None = None,
    notes: str | None = None,
    api_called: bool = False,
    api_error: str | None = None,
) -> str:
    decision = await record_and_build_handoff(
        user_text,
        wecom_user_id=ctx.wecom_user_id,
        conversation_id=ctx.conversation_id,
        intent=intent,
        reason_code=reason_code,
        model_or_rule_notes=notes,
        api_called=api_called,
        api_error=api_error,
    )
    return decision.reply_markdown


async def build_wecom_reply(
    user_text: str | None,
    ctx: WecomMessageContext | None = None,
) -> str:
    """
    生成发往企微的 markdown 正文。
    """
    settings = get_settings()
    msg_ctx = ctx or WecomMessageContext(msgid="", wecom_user_id="unknown")
    text = (user_text or "").strip()

    if not text:
        return "您好，请直接发送您的问题（例如询价、轨迹、渠道咨询等）。说「转人工」可联系客服。"

    if handoff_enabled() and user_requests_handoff(text):
        logger.info("用户请求转人工")
        return await _handoff_reply(text, msg_ctx, reason_code="user_request_handoff", intent="handoff")

    if not llm_is_enabled():
        logger.debug("LLM 未启用，使用模板或转人工")
        if handoff_enabled():
            return await _handoff_reply(
                text,
                msg_ctx,
                reason_code="llm_disabled",
                notes="LLM 未配置",
            )
        return _template_reply(user_text)

    track_reply = await try_build_track_reply(text)
    if track_reply is not None:
        logger.info("走百运轨迹/跟踪号回复 字符数=%s", len(track_reply))
        return track_reply

    quote_reply = await try_build_quote_reply(text)
    if quote_reply is not None:
        logger.info("走百运询价回复 字符数=%s", len(quote_reply))
        return quote_reply

    if kb_enabled():
        kb_reply = await try_answer_from_kb(text)
        if kb_reply is not None:
            logger.info("走知识库回复 字符数=%s", len(kb_reply))
            return kb_reply
        if settings.unanswered_on_kb_miss and handoff_enabled():
            logger.info("知识库未命中，转人工并入库")
            return await _handoff_reply(
                text,
                msg_ctx,
                reason_code="kb_miss",
                intent="faq",
                notes="知识库无匹配片段",
            )

    try:
        result = await get_llm_client().chat(text)
        reply = result.content
        if result.finish_reason == "length":
            reply += "\n\n（回复较长，若未看全可追问「继续」或调大 LLM_MAX_TOKENS）"
        logger.info(
            "LLM 回复成功 字符数=%s finish_reason=%s",
            len(reply),
            result.finish_reason or "stop",
        )
        return reply
    except LlmNotConfiguredError:
        if handoff_enabled():
            return await _handoff_reply(text, msg_ctx, reason_code="llm_not_configured")
        return _template_reply(user_text)
    except LlmError:
        logger.exception("LLM 调用失败")
        if settings.unanswered_on_llm_fallback and handoff_enabled():
            return await _handoff_reply(
                text,
                msg_ctx,
                reason_code="llm_error",
                notes="LLM 调用异常",
            )
        custom = (settings.wecom_reply_text or "").strip()
        if custom:
            return _template_reply(user_text)
        return _LLM_FALLBACK
