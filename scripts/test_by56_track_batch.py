#!/usr/bin/env python3
"""百运 §3.6 货物追踪 QueryBatch 联调。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from aiqyweixin.models.dto import TrackQueryRequest
from aiqyweixin.services.track_service import by56_enabled, query_track_batch


async def _main() -> int:
    parser = argparse.ArgumentParser(description="百运 §3.6 QueryBatch")
    parser.add_argument(
        "track_nos",
        nargs="+",
        help="TrackNo：订单号/代理单号/跟踪号，最多 5 个",
    )
    args = parser.parse_args()

    if not by56_enabled():
        print("BY56 未配置完整")
        return 1

    req = TrackQueryRequest(track_numbers=args.track_nos)
    result = await query_track_batch(req)
    print("success:", result.success)
    if result.error_code:
        print("error_code:", result.error_code)
    if result.error_message:
        print("error_message:", result.error_message)
    print("--- markdown ---")
    print(result.to_markdown())
    if result.raw_response is not None:
        print("--- raw ---")
        print(json.dumps(result.raw_response, ensure_ascii=False, indent=2)[:4000])
    return 0 if result.success else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
