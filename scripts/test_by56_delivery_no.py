#!/usr/bin/env python3
"""百运 §3.7 GetDeliveryNO 联调。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from aiqyweixin.models.dto import BY56_WAYBILL_TYPE_EXPRESS, BY56_WAYBILL_TYPE_FBA, DeliveryNoRequest
from aiqyweixin.services.track_service import by56_enabled, query_delivery_no


async def _main() -> int:
    parser = argparse.ArgumentParser(description="百运 §3.7 获取跟踪号")
    parser.add_argument(
        "waybill_nos",
        nargs="+",
        help="订单号，多个可用空格分隔（内部会拼成逗号）",
    )
    parser.add_argument(
        "--waybill-type",
        type=int,
        default=BY56_WAYBILL_TYPE_EXPRESS,
        help="1=快递/专线, 20=FBA",
    )
    args = parser.parse_args()

    if not by56_enabled():
        print("BY56 未配置完整")
        return 1

    if args.waybill_type not in (BY56_WAYBILL_TYPE_EXPRESS, BY56_WAYBILL_TYPE_FBA):
        print("WaybillType 仅支持 1 或 20")
        return 1

    req = DeliveryNoRequest(waybill_numbers=args.waybill_nos, waybill_type=args.waybill_type)
    result = await query_delivery_no(req)
    print("success:", result.success)
    if result.error_code:
        print("error_code:", result.error_code)
    if result.error_message:
        print("error_message:", result.error_message)
    print("--- markdown ---")
    print(result.to_markdown())
    if result.raw_response is not None:
        print("--- raw ---")
        print(json.dumps(result.raw_response, ensure_ascii=False, indent=2)[:3000])
    return 0 if result.success else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
