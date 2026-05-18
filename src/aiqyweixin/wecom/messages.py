"""
解析智能机器人回调 JSON，提取用户文本等字段。
"""

from __future__ import annotations

from typing import Any


def extract_user_text(payload: dict[str, Any]) -> str | None:
    """从 text / voice / mixed 消息中提取可读文本。"""
    msgtype = payload.get("msgtype")
    if msgtype == "text":
        text = payload.get("text")
        if isinstance(text, dict):
            content = text.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return None
    if msgtype == "voice":
        voice = payload.get("voice")
        if isinstance(voice, dict):
            content = voice.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return None
    if msgtype == "mixed":
        mixed = payload.get("mixed")
        if not isinstance(mixed, dict):
            return None
        parts: list[str] = []
        for item in mixed.get("msg_item") or []:
            if not isinstance(item, dict) or item.get("msgtype") != "text":
                continue
            text = item.get("text")
            if isinstance(text, dict):
                content = text.get("content")
                if isinstance(content, str) and content.strip():
                    parts.append(content.strip())
        return "\n".join(parts) if parts else None
    return None


def should_reply(payload: dict[str, Any]) -> bool:
    """是否应对该回调做主动回复（含 response_url 且非流式刷新）。"""
    if payload.get("msgtype") == "stream":
        return False
    url = payload.get("response_url")
    return isinstance(url, str) and bool(url.strip())


def format_reply_text(user_text: str | None, template: str) -> str:
    """按模板生成回复正文；模板含 {content} 时替换，否则整段为固定文案。"""
    snippet = (user_text or "").strip() or "（无文本内容）"
    if "{content}" in template:
        return template.replace("{content}", snippet)
    return template
