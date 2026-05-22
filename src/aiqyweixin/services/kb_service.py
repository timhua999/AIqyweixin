"""
知识库问答（文件型 MVP：Markdown 分块 + 关键词检索 + LLM 归纳）。

职责：
- 加载 data/knowledge 下 .md/.txt
- 检索相关片段后调用 LLM 生成回答（不编造价格，价格仍走百运 API）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from aiqyweixin.config import Settings, get_settings
from aiqyweixin.llm.client import LlmError, get_llm_client

logger = logging.getLogger(__name__)

_KB_SYSTEM = """你是企业微信国际物流知识库助手。仅根据「参考资料」回答用户问题。

规则：
- 参考资料未提及的内容，明确说「知识库暂无说明」，不要编造价格、时效、渠道名。
- 运费/报价必须引导用户使用询价功能（说明起运地、目的国、重量等），不得编造具体金额。
- 回答简洁专业，可用 markdown 列表。
"""


@dataclass(frozen=True)
class KbChunk:
    source: str
    title: str
    body: str

    def score(self, query: str) -> int:
        """简单关键词命中计分。"""
        q = _tokenize(query)
        if not q:
            return 0
        text = (self.title + "\n" + self.body).lower()
        return sum(1 for t in q if t in text)


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    parts = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{2,}", text)
    stop = {"请问", "什么", "怎么", "如何", "可以", "吗", "的", "了", "是"}
    return [p for p in parts if p not in stop]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_kb_dir(settings: Settings) -> Path:
    raw = (settings.kb_data_dir or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else _project_root() / p
    return _project_root() / "data" / "knowledge"


@lru_cache(maxsize=4)
def _load_chunks_cached(kb_dir_str: str) -> tuple[KbChunk, ...]:
    kb_dir = Path(kb_dir_str)
    chunks: list[KbChunk] = []
    if not kb_dir.is_dir():
        return tuple()
    for path in sorted(kb_dir.rglob("*")):
        if path.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            logger.warning("无法读取知识库文件: %s", path)
            continue
        if not text:
            continue
        rel = str(path.relative_to(kb_dir))
        sections = re.split(r"\n(?=#{1,3}\s)", text)
        if len(sections) <= 1:
            chunks.append(KbChunk(source=rel, title=path.stem, body=text))
            continue
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue
            lines = sec.splitlines()
            title = lines[0].lstrip("#").strip() if lines else path.stem
            chunks.append(KbChunk(source=rel, title=title, body=sec))
    return tuple(chunks)


def kb_enabled() -> bool:
    s = get_settings()
    if not s.kb_enabled or not s.llm_enabled:
        return False
    return get_llm_client().is_configured


def load_kb_chunks() -> list[KbChunk]:
    s = get_settings()
    return list(_load_chunks_cached(str(_resolve_kb_dir(s))))


def search_kb(query: str, *, top_k: int | None = None) -> list[KbChunk]:
    s = get_settings()
    k = top_k or s.kb_top_k
    scored = [(c, c.score(query)) for c in load_kb_chunks()]
    scored = [(c, sc) for c, sc in scored if sc >= s.kb_min_score]
    scored.sort(key=lambda x: (-x[1], x[0].source))
    return [c for c, _ in scored[:k]]


def _format_context(chunks: list[KbChunk]) -> str:
    parts: list[str] = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"### 参考{i}（{c.source} / {c.title}）\n{c.body}")
    return "\n\n".join(parts)


async def try_answer_from_kb(user_text: str) -> str | None:
    """
    命中知识库则返回 markdown 回答；未命中返回 None。
    """
    if not kb_enabled():
        return None
    text = (user_text or "").strip()
    if not text:
        return None

    chunks = search_kb(text)
    if not chunks:
        logger.debug("知识库未命中: %s", text[:60])
        return None

    context = _format_context(chunks)
    prompt = f"参考资料：\n\n{context}\n\n---\n\n用户问题：{text}"
    try:
        result = await get_llm_client().chat(prompt, system_prompt=_KB_SYSTEM)
        body = result.content.strip()
        if not body:
            return None
        sources = "、".join({c.source for c in chunks})
        return f"**知识库参考**（{sources}）\n\n{body}"
    except LlmError:
        logger.exception("知识库 LLM 回答失败")
        return None
