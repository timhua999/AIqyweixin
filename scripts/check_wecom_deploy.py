#!/usr/bin/env python3
"""检查服务器是否具备企微主动回复所需依赖与代码版本。"""

from __future__ import annotations

import importlib.metadata
import sys


def main() -> int:
    print("python:", sys.executable)
    try:
        print("aiqyweixin version:", importlib.metadata.version("aiqyweixin"))
    except Exception as exc:
        print("aiqyweixin version: ERROR", exc)
        return 1

    try:
        import httpx

        print("httpx:", httpx.__version__)
    except ImportError:
        print("httpx: NOT INSTALLED  ->  run: pip install -e .")
        return 1

    from aiqyweixin.wecom import webhook

    print("webhook module:", webhook.__file__)
    has_trace = hasattr(webhook, "_trace")
    print("stderr trace (_trace):", "yes" if has_trace else "no (git pull 最新代码)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
