"""LLM 调用模块（云端 OpenAI 兼容 API）。"""

from aiqyweixin.llm.client import ChatResult, LlmClient, LlmError, LlmNotConfiguredError, get_llm_client

__all__ = ["ChatResult", "LlmClient", "LlmError", "LlmNotConfiguredError", "get_llm_client"]
