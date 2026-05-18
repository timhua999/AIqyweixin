"""
企业微信「接收消息」回调：使用官方 WXBizJsonMsgCrypt（智能机器人 JSON）。
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response

from aiqyweixin.config import get_settings
from aiqyweixin.wecom.vendor.callback_json_python3 import ierror
from aiqyweixin.wecom.wxcrypt import (
    WecomCryptError,
    config_diagnostics,
    decrypt_post_body,
    ierror_name,
    verify_url,
)

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
            detail="缺少 WECOM_CORP_ID / WECOM_TOKEN / WECOM_ENCODING_AES_KEY",
        )
    return corp, token, aes


def _http_status_for_crypt_error(exc: WecomCryptError) -> int:
    if exc.code == ierror.WXBizMsgCrypt_ValidateSignature_Error:
        return 403
    return 400


def _log_crypt_failure(stage: str, corp_id: str, token: str, aes: str, exc: Exception) -> None:
    diag = config_diagnostics(token, aes, corp_id)
    logger.error(
        "企微 %s 失败: %s | env_file=%s token_len=%s aes_key_len=%s aes_key_ok_len=%s "
        "receive_id_candidates=%s",
        stage,
        exc,
        diag["env_file"],
        diag["token_len"],
        diag["aes_key_len"],
        diag["aes_key_ok_len"],
        diag["receive_id_candidates"],
    )


@router.get("/callback")
async def wecom_callback_verify(
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(..., alias="timestamp"),
    nonce: str = Query(..., alias="nonce"),
    echostr: str = Query(..., alias="echostr"),
) -> Response:
    corp_id, token, aes_key = _require_wecom_crypto_settings()
    try:
        _rid, plain = verify_url(token, aes_key, corp_id, msg_signature, timestamp, nonce, echostr)
    except WecomCryptError as e:
        _log_crypt_failure("URL校验", corp_id, token, aes_key, e)
        raise HTTPException(
            status_code=_http_status_for_crypt_error(e),
            detail=f"wecom verify failed: {ierror_name(e.code)}",
        ) from e

    return Response(content=plain, media_type="text/plain; charset=utf-8")


@router.post("/callback")
async def wecom_callback_message(
    request: Request,
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(..., alias="timestamp"),
    nonce: str = Query(..., alias="nonce"),
) -> Response:
    corp_id, token, aes_key = _require_wecom_crypto_settings()
    body_bytes = await request.body()
    post_data = body_bytes.decode("utf-8")

    # 智能机器人为 JSON；若仅有 encrypt 字段则包成官方示例格式
    stripped = post_data.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(post_data)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="invalid json body") from e
        if isinstance(data, dict) and "encrypt" in data and len(data) == 1:
            post_data = json.dumps({"encrypt": data["encrypt"]}, ensure_ascii=False)
        elif isinstance(data, dict) and "encrypt" not in data:
            raise HTTPException(status_code=400, detail="missing encrypt in json")

    try:
        _rid, plain = decrypt_post_body(
            token, aes_key, corp_id, post_data, msg_signature, timestamp, nonce
        )
    except WecomCryptError as e:
        _log_crypt_failure("POST消息", corp_id, token, aes_key, e)
        raise HTTPException(
            status_code=_http_status_for_crypt_error(e),
            detail=f"wecom decrypt failed: {ierror_name(e.code)}",
        ) from e

    logger.info("企微消息解密成功（前 500 字符）: %s", plain[:500])
    return Response(content="success", media_type="text/plain; charset=utf-8")
