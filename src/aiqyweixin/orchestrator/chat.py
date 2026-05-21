"""
企微对话回复编排：询价走百运 API + LLM 抽参；其它走 LLM/模板。
"""

from __future__ import annotations

import logging

from aiqyweixin.config import get_settings
from aiqyweixin.llm.client import LlmError, LlmNotConfiguredError, get_llm_client
from aiqyweixin.orchestrator.quote_flow import try_build_quote_reply
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


async def build_wecom_reply(user_text: str | None) -> str:
    """
    生成发往企微的 markdown 正文。
    已配置且启用 LLM 时走大模型；否则或失败时回退模板文案。
    """
    text = (user_text or "").strip()
    if not text:
        return "您好，请直接发送您的问题（例如询价、轨迹、渠道咨询等）。"

    if not llm_is_enabled():
        logger.debug("LLM 未启用或未配置，使用模板回复")
        return _template_reply(user_text)

    quote_reply = await try_build_quote_reply(text)
    if quote_reply is not None:
        logger.info("走百运询价回复 字符数=%s", len(quote_reply))
        return quote_reply

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
        return _template_reply(user_text)
    except LlmError:
        logger.exception("LLM 调用失败，回退模板")
        custom = (get_settings().wecom_reply_text or "").strip()
        if custom:
            return _template_reply(user_text)
        return _LLM_FALLBACK
