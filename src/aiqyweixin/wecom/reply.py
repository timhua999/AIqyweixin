"""
智能机器人主动回复（POST response_url，无需加解密）。

文档：https://developer.work.weixin.qq.com/document/path/101138
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# 企微 markdown 单条上限（字节）；预留余量
_WECOM_MARKDOWN_MAX_BYTES = 20480


class WecomReplyError(Exception):
    def __init__(self, errcode: int, errmsg: str) -> None:
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"企微主动回复 errcode={errcode} errmsg={errmsg}")


def markdown_reply_body(content: str) -> dict[str, Any]:
    return {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }


def truncate_for_wecom_markdown(content: str, max_bytes: int = _WECOM_MARKDOWN_MAX_BYTES) -> str:
    """按 UTF-8 字节截断，避免超过企微 markdown 上限被服务端截断。"""
    raw = content.encode("utf-8")
    if len(raw) <= max_bytes:
        return content
    truncated = raw[: max_bytes - 20].decode("utf-8", errors="ignore")
    return truncated + "\n\n…（内容过长已截断）"


def _check_wecom_business_error(resp: httpx.Response) -> None:
    """企微常在 HTTP 200 下返回 errcode != 0（如 60140 response_url 已失效）。"""
    if not resp.content:
        return
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict):
        return
    errcode = data.get("errcode", 0)
    if errcode not in (0, "0", None):
        errmsg = str(data.get("errmsg") or "")
        raise WecomReplyError(int(errcode), errmsg)


async def post_active_reply(response_url: str, content: str) -> None:
    """向回调中的 response_url 发送一条 markdown 主动回复。"""
    url = response_url.strip()
    if not url:
        raise ValueError("empty response_url")

    safe_content = truncate_for_wecom_markdown(content)
    if len(safe_content) != len(content):
        logger.warning(
            "回复超长已截断: %s -> %s 字符",
            len(content),
            len(safe_content),
        )

    body = markdown_reply_body(safe_content)
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(url, json=body)

    body_preview = (resp.text or "")[:500]
    if resp.status_code >= 400:
        logger.error("response_url 失败 HTTP %s body=%s", resp.status_code, body_preview)
        resp.raise_for_status()

    try:
        _check_wecom_business_error(resp)
    except WecomReplyError:
        logger.error("response_url 业务失败 body=%s", body_preview)
        raise

    logger.info(
        "response_url 成功 HTTP %s 发送字符数=%s body=%s",
        resp.status_code,
        len(safe_content),
        body_preview or "(empty)",
    )
