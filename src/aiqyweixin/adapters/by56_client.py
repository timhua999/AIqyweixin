"""
百运开放平台 Router API 客户端（TOP 风格）。

- 单入口 POST `application/x-www-form-urlencoded`
- 公共参数 §3.1：bykey, method, timestamp, calls, format, sign_method, sign
- 公共响应 §3.2：ResultCode, Message, Data
- 官方文档：https://open.by56.com/apicus/#/common/preface
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from aiqyweixin.config import Settings, get_settings

logger = logging.getLogger(__name__)

_CN_TZ = ZoneInfo("Asia/Shanghai")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]")
# 文档 C# 样例（用于检测 BYKEY / APP_SECRET 填反）
_DOC_SAMPLE_BYKEY = "FD981D0B-BC8B-4A55-ABD0-C571B51B4990"
_DOC_SAMPLE_SECRET = "028D0512-E130-4EB3-8583-BE7F53FF7085"


class By56ApiError(Exception):
    def __init__(self, message: str, *, result_code: Any = None, raw: Any = None) -> None:
        self.result_code = result_code
        self.raw = raw
        super().__init__(message)


def create_sign(params: dict[str, str], secret: str) -> str:
    """
    百运 TOP 签名（与文档 §2.1 C# CreateSign 一致）：
    secret + key1value1key2value2... + secret → MD5 → 大写十六进制。
    """
    secret_u = secret.upper()
    filtered = {k: str(v) for k, v in params.items() if k != "sign" and k and v is not None and str(v) != ""}
    parts = secret_u
    for key in sorted(filtered.keys()):
        parts += key + filtered[key]
    parts += secret_u
    return hashlib.md5(parts.encode("utf-8")).hexdigest().upper()


def _now_timestamp() -> str:
    """百运要求 GMT+8：yyyy-MM-dd HH:mm:ss（中间为空格，不是 ISO 的 T）。"""
    return datetime.now(_CN_TZ).strftime("%Y-%m-%d %H:%M:%S")


_SYSTEM_PARAM_KEYS = frozenset(
    {"bykey", "method", "timestamp", "calls", "format", "sign_method", "sign"}
)


class By56RouterClient:
    """百运 Router API 调用封装。"""

    def __init__(self, settings: Settings | None = None) -> None:
        s = settings or get_settings()
        self._url = (s.by56_base_url or "").strip()
        self._bykey = (s.by56_bykey or s.by56_app_id or "").strip()
        self._secret = (s.by56_app_secret or "").strip()
        self._calls = (s.by56_calls or "byapi").strip()
        self._timeout = httpx.Timeout(float(s.by56_timeout_seconds), connect=10.0)
        self.method_commodity = (s.by56_method_commodity or "").strip()
        self.method_delivery_no = (s.by56_method_delivery_no or "").strip()
        self.method_quote = (s.by56_method_quote or "").strip()
        self._warn_credential_swap()

    def _warn_credential_swap(self) -> None:
        bk = self._bykey.upper()
        sec = self._secret.upper()
        if bk == _DOC_SAMPLE_SECRET and sec == _DOC_SAMPLE_BYKEY:
            logger.warning(
                "BY56_BYKEY 与 BY56_APP_SECRET 很可能填反了（与文档 C# 样例对调）"
            )
        elif bk == _DOC_SAMPLE_SECRET:
            logger.warning(
                "BY56_BYKEY 与文档样例中的 appSecret 相同，请确认未把签名密钥填进 BY56_BYKEY"
            )

    @property
    def is_configured(self) -> bool:
        return bool(self._url and self._bykey and self._secret)

    def _system_params(self, method: str) -> dict[str, str]:
        return {
            "bykey": self._bykey.upper(),
            "method": method,
            "timestamp": _now_timestamp(),
            "calls": self._calls,
            "format": "json",
            "sign_method": "md5",
        }

    def _encode_form(self, params: dict[str, str]) -> str:
        from urllib.parse import quote_plus

        return "&".join(f"{k}={quote_plus(v)}" for k, v in params.items() if k)

    async def call(self, method: str, business: dict[str, Any] | None = None) -> dict[str, Any]:
        """调用任意 method，返回完整 JSON 对象（含 ResultCode/Message/Data）。"""
        if not self.is_configured:
            raise By56ApiError("未配置 BY56_BASE_URL / BY56_BYKEY(或 APP_ID) / BY56_APP_SECRET")

        biz: dict[str, str] = {}
        for k, v in (business or {}).items():
            if v is None:
                continue
            biz[str(k)] = str(v)

        params = {**self._system_params(method), **biz}
        if "T" in params.get("timestamp", "") and " " not in params["timestamp"]:
            raise By56ApiError(
                "timestamp 须为 yyyy-MM-dd HH:mm:ss（空格分隔），勿用 ISO 格式带 T"
            )
        params["sign"] = create_sign(params, self._secret)

        biz_keys = sorted(k for k in params if k not in _SYSTEM_PARAM_KEYS)
        logger.info(
            "BY56 call method=%s bykey=%s... biz_keys=%s",
            method,
            (self._bykey[:8] + "…") if len(self._bykey) > 8 else self._bykey,
            biz_keys or "(无业务参数)",
        )
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url,
                content=self._encode_form(params).encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        text = _CONTROL_CHARS.sub("", resp.text or "")
        if resp.status_code >= 400:
            raise By56ApiError(f"HTTP {resp.status_code}: {text[:500]}", raw=text)

        try:
            data = resp.json()
        except Exception as exc:
            raise By56ApiError(f"响应非 JSON: {text[:300]}", raw=text) from exc

        if not isinstance(data, dict):
            raise By56ApiError("响应不是 JSON 对象", raw=data)
        return data

    @staticmethod
    def parse_result(data: dict[str, Any]) -> tuple[int, str | None, Any]:
        """§3.2 公共返回：ResultCode, Message, Data。"""
        code = data.get("ResultCode")
        if code is None:
            code = data.get("resultCode", data.get("code", -1))
        try:
            code_i = int(code)
        except (TypeError, ValueError):
            code_i = -1
        msg = data.get("Message") or data.get("message")
        payload = data.get("Data")
        if payload is None:
            payload = data.get("data")
        return code_i, str(msg) if msg is not None else None, payload

    async def call_ok(self, method: str, business: dict[str, Any] | None = None) -> Any:
        """调用并在 ResultCode==0 时返回 Data。"""
        raw = await self.call(method, business)
        code, msg, payload = self.parse_result(raw)
        if code != 0:
            raise By56ApiError(
                msg or f"ResultCode={code}",
                result_code=code,
                raw=raw,
            )
        return payload

    async def get_commodity_exp(self, business: dict[str, Any] | None = None) -> Any:
        """§3.1 快递查价 GetCommodityEXP（与 method_quote 默认同 method）。"""
        method = self.method_quote or self.method_commodity
        if not method:
            raise By56ApiError("未配置 BY56_METHOD_QUOTE / BY56_METHOD_COMMODITY（§3.1）")
        return await self.call_ok(method, business)

    async def get_delivery_no(self, business: dict[str, Any] | None = None) -> Any:
        """§3.7 获取百运跟踪号 GetDeliveryNO。"""
        if not self.method_delivery_no:
            raise By56ApiError("未配置 BY56_METHOD_DELIVERY_NO（§3.7）")
        return await self.call_ok(self.method_delivery_no, business)

    async def query_price_exp(self, business: dict[str, Any] | None = None) -> Any:
        """§3.1 快递查价（BY56_METHOD_QUOTE，与 §3.7 无关）。"""
        method = self.method_quote or self.method_commodity
        if not method:
            raise By56ApiError("未配置 BY56_METHOD_QUOTE（§3.1 GetCommodityEXP）")
        return await self.call_ok(method, business)
