"""
日志配置：使 aiqyweixin.* 的 INFO 能在控制台输出（与 LOG_LEVEL 一致）。
"""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    lvl = getattr(logging, (level or "INFO").upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=lvl, format=fmt, datefmt=datefmt, stream=sys.stderr)
    else:
        root.setLevel(lvl)
        for handler in root.handlers:
            handler.setLevel(lvl)

    logging.getLogger("aiqyweixin").setLevel(lvl)
