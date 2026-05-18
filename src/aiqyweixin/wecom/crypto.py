"""
已改用官方 WXBizJsonMsgCrypt（见 wecom.wxcrypt / vendor.callback_json_python3）。
本模块仅保留兼容导入，请勿在新代码中使用。
"""

from aiqyweixin.wecom.wxcrypt import (  # noqa: F401
    WecomCryptError,
    config_diagnostics as wecom_config_diagnostics,
    verify_url,
)

__all__ = ["WecomCryptError", "wecom_config_diagnostics", "verify_url"]
