#!/usr/bin/env python3
"""百运查价联调（§3.6 货物种类；查价需配置 BY56_METHOD_QUOTE）。§3.7 跟踪号请用 test_by56_delivery_no.py。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from aiqyweixin.adapters.by56_client import By56RouterClient, create_sign
from aiqyweixin.models.dto import QuoteRequest
from aiqyweixin.services.quote_service import by56_quote_enabled, list_by56_commodities, query_quote


async def _main() -> int:
    parser = argparse.ArgumentParser(description="百运 API 联调")
    parser.add_argument("--list-commodity", action="store_true", help="仅调用 §3.6 获取货物种类")
    parser.add_argument("--origin-country", default="CN")
    parser.add_argument("--origin-city", default="深圳")
    parser.add_argument("--dest-country", default="US")
    parser.add_argument("--dest-city", default="洛杉矶")
    parser.add_argument("--weight-kg", type=float, default=100.0)
    parser.add_argument("--goods-type", default="普货")
    parser.add_argument("--commodity-id", default=None, help="§3.7 直接传 CommodityID")
    args = parser.parse_args()

    if not by56_quote_enabled():
        print("BY56 未启用或未配置：BY56_ENABLED、BY56_BASE_URL、BY56_BYKEY(或 APP_ID)、BY56_APP_SECRET")
        return 1

    client = By56RouterClient()
    print("base_url:", client._url)
    print("method_commodity:", client.method_commodity)
    print("method_quote:", client.method_quote)

    if args.list_commodity:
        rows = await list_by56_commodities()
        print(json.dumps(rows, ensure_ascii=False, indent=2)[:4000])
        return 0

    extra = {}
    if args.commodity_id:
        extra["commodity_id"] = args.commodity_id

    req = QuoteRequest(
        origin_country=args.origin_country,
        origin_city=args.origin_city,
        destination_country=args.dest_country,
        destination_city=args.dest_city,
        weight_kg=args.weight_kg,
        goods_type=args.goods_type,
        extra=extra,
    )
    result = await query_quote(req)
    print("success:", result.success)
    if result.error_code:
        print("error_code:", result.error_code)
    if result.error_message:
        print("error_message:", result.error_message)
    print("--- markdown ---")
    print(result.to_markdown())
    if result.raw_response:
        print("--- raw (truncated) ---")
        print(str(result.raw_response)[:2000])
    return 0 if result.success and result.offers else 2


def _test_sign_vector() -> None:
    """与文档 C# 样例一致的签名单测（可选）。"""
    params = {
        "bykey": "FD981D0B-BC8B-4A55-ABD0-C571B51B4990",
        "method": "By56CustomerAPI.byExpOrder.ExpOrder.GetCommodityEXP",
        "timestamp": "2016-01-01 12:00:00",
        "calls": "byapi",
        "format": "json",
        "sign_method": "md5",
        "id": "1",
    }
    secret = "028D0512-E130-4EB3-8583-BE7F53FF7085"
    print("sign sample:", create_sign(params, secret))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-sign":
        _test_sign_vector()
        raise SystemExit(0)
    raise SystemExit(asyncio.run(_main()))
