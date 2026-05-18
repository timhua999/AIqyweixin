"""
智能机器人主动回复（POST response_url，无需加解密）。

文档：https://developer.work.weixin.qq.com/document/path/101138
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def markdown_reply_body(content: str) -> dict[str, Any]:
    return {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }


async def post_active_reply(response_url: str, content: str) -> None:
    """向回调中的 response_url 发送一条 markdown 主动回复。"""
    url = response_url.strip()
    if not url:
        raise ValueError("empty response_url")

    body = markdown_reply_body(content)
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        if resp.content:
            logger.debug("response_url 响应: %s %s", resp.status_code, resp.text[:500])
