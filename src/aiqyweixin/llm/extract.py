"""
从 LLM 回复中解析 JSON（询价参数抽取等）。
"""

from __future__ import annotations

import json
import re


def parse_json_object(text: str) -> dict:
    """解析 LLM 输出的 JSON 对象，容忍 ```json 围栏。"""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("空内容")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```\s*$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("非 JSON 对象")
    return data
