"""
配置加载模块（.env / 环境变量）。

职责：
- 读取 WeCom 配置（corp_id/secret/agent_id/token/EncodingAESKey 等）
- 读取 LLM 配置（base_url/api_key/model/参数）
- 读取 PostgreSQL DATABASE_URL
- 输出强类型配置对象供应用使用
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py 位于 src/aiqyweixin/，向上两级为项目根（含 pyproject.toml、.env）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOTENV_PATH = _PROJECT_ROOT / ".env"


def dotenv_path() -> Path:
    return _DOTENV_PATH


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # 勿仅用 ".env"：从其它 cwd 启动 uvicorn 时会读错目录，导致永不通企微验签解密。
        env_file=str(_DOTENV_PATH) if _DOTENV_PATH.is_file() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", validation_alias=AliasChoices("APP_ENV"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))

    database_url: str | None = Field(default=None, validation_alias=AliasChoices("DATABASE_URL"))

    wecom_corp_id: str | None = Field(default=None, validation_alias=AliasChoices("WECOM_CORP_ID"))
    wecom_agent_id: str | None = Field(default=None, validation_alias=AliasChoices("WECOM_AGENT_ID"))
    wecom_agent_secret: str | None = Field(default=None, validation_alias=AliasChoices("WECOM_AGENT_SECRET"))
    wecom_token: str | None = Field(default=None, validation_alias=AliasChoices("WECOM_TOKEN"))
    wecom_encoding_aes_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("WECOM_ENCODING_AES_KEY"),
    )
    # 智能机器人传空串；自建应用一般为 CorpId。留空则先 "" 再尝试 WECOM_CORP_ID。
    wecom_receive_id: str = Field(default="", validation_alias=AliasChoices("WECOM_RECEIVE_ID"))
    # 主动回复文案；含 {content} 时替换为用户消息摘要。
    wecom_reply_text: str | None = Field(default=None, validation_alias=AliasChoices("WECOM_REPLY_TEXT"))

    llm_enabled: bool = Field(default=True, validation_alias=AliasChoices("LLM_ENABLED"))
    llm_base_url: str | None = Field(default=None, validation_alias=AliasChoices("LLM_BASE_URL"))
    llm_api_key: str | None = Field(default=None, validation_alias=AliasChoices("LLM_API_KEY"))
    llm_model: str | None = Field(default=None, validation_alias=AliasChoices("LLM_MODEL"))
    llm_temperature: float = Field(default=0.2, validation_alias=AliasChoices("LLM_TEMPERATURE"))
    llm_max_tokens: int = Field(default=1024, validation_alias=AliasChoices("LLM_MAX_TOKENS"))
    llm_timeout_seconds: float = Field(default=60.0, validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS"))
    # 留空则使用代码内默认国际物流助手提示词
    llm_system_prompt: str | None = Field(default=None, validation_alias=AliasChoices("LLM_SYSTEM_PROMPT"))
    # 企微询价回复最多展示渠道条数（含渠道描述/附加费/风险提示，不宜过大）
    wecom_quote_max_offers: int = Field(
        default=3,
        validation_alias=AliasChoices("WECOM_QUOTE_MAX_OFFERS"),
    )

    enable_debug_routes: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_DEBUG_ROUTES"),
    )

    # 百运 by56.com Router API（规则见 docs/api/by56-quote-api.md）
    by56_enabled: bool = Field(default=False, validation_alias=AliasChoices("BY56_ENABLED"))
    by56_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BY56_BASE_URL"),
    )
    by56_bykey: str | None = Field(default=None, validation_alias=AliasChoices("BY56_BYKEY"))
    by56_app_id: str | None = Field(default=None, validation_alias=AliasChoices("BY56_APP_ID"))
    by56_app_secret: str | None = Field(default=None, validation_alias=AliasChoices("BY56_APP_SECRET"))
    by56_calls: str = Field(default="byapi", validation_alias=AliasChoices("BY56_CALLS"))
    # 与 §3.1 查价同 method；保留别名便于旧 .env
    by56_method_commodity: str | None = Field(
        default="By56CustomerAPI.byExpOrder.ExpOrder.GetCommodityEXP",
        validation_alias=AliasChoices("BY56_METHOD_COMMODITY"),
    )
    by56_method_delivery_no: str | None = Field(
        default="By56CustomerAPI.byPackOrder.PackOrder.GetDeliveryNO",
        validation_alias=AliasChoices("BY56_METHOD_DELIVERY_NO"),
    )
    # §3.1 快递查价 GetCommodityEXP（非 §3.7）
    by56_method_quote: str | None = Field(
        default="By56CustomerAPI.byExpOrder.ExpOrder.GetCommodityEXP",
        validation_alias=AliasChoices("BY56_METHOD_QUOTE"),
    )
    by56_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices("BY56_TIMEOUT_SECONDS"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """修改 .env 后若未重启进程，可调用以刷新（一般仍建议重启 uvicorn）。"""
    get_settings.cache_clear()
    return get_settings()
