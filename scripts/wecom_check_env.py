#!/usr/bin/env python3
"""检查企微配置（官方 WXBizJsonMsgCrypt，不打印密钥明文）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiqyweixin.config import dotenv_path, get_settings, reload_settings
from aiqyweixin.wecom.wxcrypt import config_diagnostics, create_wxcrypt


def main() -> None:
    reload_settings()
    s = get_settings()
    env = dotenv_path()
    print(f".env 路径: {env} (存在={env.is_file()})")
    diag = config_diagnostics(s.wecom_token, s.wecom_encoding_aes_key, s.wecom_corp_id)
    for k, v in diag.items():
        print(f"  {k}: {v}")
    if not diag.get("aes_key_ok_len"):
        print("\n[错误] EncodingAESKey 长度应为 43")
        sys.exit(1)
    token = (s.wecom_token or "").strip()
    aes = (s.wecom_encoding_aes_key or "").strip()
    for rid in diag["receive_id_candidates"]:
        try:
            create_wxcrypt(token, aes, rid)
            print(f"WXBizJsonMsgCrypt 初始化 OK receive_id={rid!r}")
        except Exception as e:
            print(f"WXBizJsonMsgCrypt 初始化失败 receive_id={rid!r}: {e}")
            sys.exit(1)
    print("\n修改 .env 后请重启 uvicorn。")


if __name__ == "__main__":
    main()
