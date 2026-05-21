#!/usr/bin/env python3
"""百运 §3.1 快递查价联调（GetCommodityEXP）。§3.7 跟踪号请用 test_by56_delivery_no.py。"""

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
    parser.add_argument("--list-commodity", action="store_true", help="列出 §3.1 SpecialItems 货物种类 ID")
    parser.add_argument("--origin-country", default="CN", help="内部 DTO，查价 API 不使用")
    parser.add_argument("--origin-city", default="深圳市", help="对应 StartCityKey")
    parser.add_argument("--dest-country", default="US", help="CountryKey 二字码")
    parser.add_argument("--volume", type=float, default=0.0, help="Volume 必填")
    parser.add_argument("--weight-kg", type=float, default=100.0)
    parser.add_argument("--goods-type", default="普货", help="映射为 SpecialItems，如 139 或 普货")
    parser.add_argument("--packge-type", type=int, default=1, choices=[1, 2, 3], help="1=WPX 2=DOC 3=PAK")
    parser.add_argument("--special-items", default=None, help="直接传 SpecialItems，如 139 或 139,108")
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

    extra: dict = {"PackgeType": args.packge_type}
    if args.special_items:
        extra["SpecialItems"] = args.special_items

    req = QuoteRequest(
        origin_country=args.origin_country,
        origin_city=args.origin_city,
        destination_country=args.dest_country,
        weight_kg=args.weight_kg,
        volume_cbm=args.volume,
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
    """与文档样例 + CallInterface.py CreateSign 对照。"""
    import copy
    import hashlib

    def _sign_call_interface(paraments: dict, secret: str) -> str:
        sort1 = copy.deepcopy(paraments)
        for key, value in list(sort1.items()):
            if key == "" or value == "":
                del sort1[key]
        sorted_param = sorted(sort1.items(), key=lambda d: d[0].lower())
        query = [secret.upper()]
        for k, v in sorted_param:
            query.append(k)
            query.append(v)
        s = "".join(query) + secret.upper()
        return hashlib.md5(s.encode("utf8")).hexdigest().upper()

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
    ours = create_sign(params, secret)
    official = _sign_call_interface(params, secret)
    print("sign sample (doc):", ours)
    print("CallInterface.py:  ", official, "OK" if ours == official else "MISMATCH")

    with_biz = {
        **params,
        "method": "By56CustomerAPI.byPackOrder.PackOrder.GetDeliveryNO",
        "WaybillNO": "WE001",
        "WaybillType": "1",
    }
    with_biz["method"] = with_biz["method"].upper()
    ours2 = create_sign(with_biz, secret)
    off2 = _sign_call_interface(with_biz, secret)
    print("with WaybillNO:    ", ours2)
    print("CallInterface.py:  ", off2, "OK" if ours2 == off2 else "MISMATCH")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-sign":
        _test_sign_vector()
        raise SystemExit(0)
    raise SystemExit(asyncio.run(_main()))
