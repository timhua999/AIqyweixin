"""
命令行入口：启动 Uvicorn（开发默认开启 reload）。

使用：
- `python -m aiqyweixin`
- 或安装后的 `aiqyweixin-serve`
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() in {"1", "true", "yes"}

    uvicorn.run(
        "aiqyweixin.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
