"""
企业微信「接收消息」回调：GET 做 URL 验证，POST 解密事件/消息（MVP 仅 ack success）。
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from fastapi import APIRouter, HTTPException, Query, Request, Response

from aiqyweixin.config import get_settings
from aiqyweixin.wecom.crypto import decrypt_callback_aes, verify_msg_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wecom", tags=["wecom"])


def _require_wecom_crypto_settings():
    s = get_settings()
    corp = (s.wecom_corp_id or "").strip()
    token = (s.wecom_token or "").strip()
    aes = (s.wecom_encoding_aes_key or "").strip()
    if not corp or not token or not aes:
        raise HTTPException(
            status_code=503,
            detail="缺少 WECOM_CORP_ID / WECOM_TOKEN / WECOM_ENCODING_AES_KEY，无法处理企微回调",
        )
    return corp, token, aes


@router.get("/callback")
async def wecom_callback_verify(
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(..., alias="timestamp"),
    nonce: str = Query(..., alias="nonce"),
    echostr: str = Query(..., alias="echostr"),
) -> Response:
    """
    保存回调 URL 时企微会 GET 本接口：验签后解密 echostr，响应体为明文 echostr（非 JSON）。
    """
    corp_id, token, aes_key = _require_wecom_crypto_settings()
    # 部分链路会把 Base64 里的「+」变成空格，需还原才能解密
    echostr = echostr.replace(" ", "+")
    if not verify_msg_signature(token, timestamp, nonce, echostr, msg_signature):
        logger.warning("企微 URL 校验：msg_signature 不匹配")
        raise HTTPException(status_code=403, detail="invalid signature")

    try:
        plain = decrypt_callback_aes(echostr, aes_key, corp_id)
    except Exception as e:
        logger.exception("企微 URL 校验：解密失败")
        raise HTTPException(status_code=400, detail="decrypt failed") from e

    return Response(content=plain, media_type="text/plain; charset=utf-8")


@router.post("/callback")
async def wecom_callback_message(
    request: Request,
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(..., alias="timestamp"),
    nonce: str = Query(..., alias="nonce"),
) -> Response:
    """
    接收加密消息/事件；当前仅验签+解密日志，业务编排后续再接。
    """
    corp_id, token, aes_key = _require_wecom_crypto_settings()
    body = await request.body()
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail="invalid xml") from e

    encrypt_el = root.find("Encrypt")
    if encrypt_el is None or not (encrypt_el.text and encrypt_el.text.strip()):
        raise HTTPException(status_code=400, detail="missing Encrypt")

    encrypt = encrypt_el.text.strip()
    if not verify_msg_signature(token, timestamp, nonce, encrypt, msg_signature):
        logger.warning("企微消息推送：msg_signature 不匹配")
        raise HTTPException(status_code=403, detail="invalid signature")

    try:
        xml_plain = decrypt_callback_aes(encrypt, aes_key, corp_id)
    except Exception as e:
        logger.exception("企微消息推送：解密失败")
        raise HTTPException(status_code=400, detail="decrypt failed") from e

    logger.info("企微消息解密成功（前 500 字符）: %s", xml_plain[:500])

    # 暂不回复用户时返回明文 success（兼容/明文场景；若后台仅开安全模式且要求密文回复再扩展）
    return Response(content="success", media_type="text/plain; charset=utf-8")
