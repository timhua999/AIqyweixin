"""
日志配置：为 aiqyweixin 包单独挂 Handler，避免被 Uvicorn 重置 root logger 后看不到 INFO。
"""

from __future__ import annotations

import logging
import sys

_PKG_LOGGER = "aiqyweixin"
_handler: logging.StreamHandler | None = None


def configure_logging(level: str = "INFO") -> None:
    global _handler
    lvl = getattr(logging, (level or "INFO").upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    pkg = logging.getLogger(_PKG_LOGGER)
    pkg.setLevel(lvl)
    pkg.propagate = False

    if _handler is None:
        _handler = logging.StreamHandler(sys.stderr)
        pkg.addHandler(_handler)
    _handler.setLevel(lvl)
    _handler.setFormatter(fmt)
