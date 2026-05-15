#!/usr/bin/env python3
"""在服务器上检查进程实际读到的企微配置（不打印 Token/Key 明文）。"""

from __future__ import annotations

import sys
from pathlib import Path

# 允许从项目根执行: python scripts/wecom_check_env.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiqyweixin.config import dotenv_path, get_settings, reload_settings
from aiqyweixin.wecom.crypto import wecom_config_diagnostics


def main() -> None:
    reload_settings()
    s = get_settings()
    env = dotenv_path()
    print(f".env 路径: {env} (存在={env.is_file()})")
    diag = wecom_config_diagnostics(
        s.wecom_corp_id,
        s.wecom_token,
        s.wecom_encoding_aes_key,
        str(env),
    )
    for k, v in diag.items():
        print(f"  {k}: {v}")
    if not diag.get("aes_key_ok_len"):
        print("\n[错误] EncodingAESKey 长度应为 43")
        sys.exit(1)
    print("\n若 aes_key_fp 与企微后台 Key 对不上，说明 .env 与后台不一致。")
    print("修改 .env 后必须重启 uvicorn（get_settings 有缓存）。")


if __name__ == "__main__":
    main()
