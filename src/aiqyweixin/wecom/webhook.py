"""
企业微信「接收消息」回调：使用官方 WXBizJsonMsgCrypt（智能机器人 JSON）。
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response

from aiqyweixin.config import get_settings
from aiqyweixin.wecom.messages import extract_user_text, format_reply_text, should_reply
from aiqyweixin.wecom.reply import post_active_reply
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

_DEFAULT_REPLY_TEMPLATE = "已收到您的消息：{content}"
_seen_msgids: set[str] = set()
_MAX_SEEN_MSGIDS = 5000


def _mark_msgid_seen(msgid: str) -> bool:
    """返回 True 表示重复 msgid（应跳过回复）。"""
    if not msgid:
        return False
    if msgid in _seen_msgids:
        return True
    _seen_msgids.add(msgid)
    if len(_seen_msgids) > _MAX_SEEN_MSGIDS:
        _seen_msgids.clear()
    return False


def _reply_template() -> str:
    custom = (get_settings().wecom_reply_text or "").strip()
    return custom or _DEFAULT_REPLY_TEMPLATE


async def _send_auto_reply(response_url: str, content: str, msgid: str) -> None:
    try:
        await post_active_reply(response_url, content)
        logger.info("企微主动回复成功 msgid=%s", msgid or "(none)")
    except Exception:
        logger.exception("企微主动回复失败 msgid=%s", msgid or "(none)")


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
    background_tasks: BackgroundTasks,
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(..., alias="timestamp"),
    nonce: str = Query(..., alias="nonce"),
) -> Response:
    corp_id, token, aes_key = _require_wecom_crypto_settings()
    body_bytes = await request.body()
    post_data = body_bytes.decode("utf-8")

    # 智能机器人为 JSON：{"encrypt":"..."}，与 Sample.DecryptMsg 一致（只需含 encrypt 字段）
    stripped = post_data.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(post_data)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="invalid json body") from e
        if not isinstance(data, dict) or "encrypt" not in data:
            raise HTTPException(status_code=400, detail="missing encrypt in json")
        if not (data.get("encrypt") and str(data["encrypt"]).strip()):
            raise HTTPException(status_code=400, detail="empty encrypt in json")

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

    try:
        payload = json.loads(plain)
    except json.JSONDecodeError:
        logger.warning("解密结果非 JSON，跳过主动回复")
        return Response(content="success", media_type="text/plain; charset=utf-8")

    if not isinstance(payload, dict):
        return Response(content="success", media_type="text/plain; charset=utf-8")

    msgid = str(payload.get("msgid") or "")
    if _mark_msgid_seen(msgid):
        logger.info("重复 msgid，跳过主动回复: %s", msgid)
        return Response(content="success", media_type="text/plain; charset=utf-8")

    if not should_reply(payload):
        logger.debug(
            "无需主动回复 msgtype=%s has_url=%s",
            payload.get("msgtype"),
            bool((payload.get("response_url") or "").strip()),
        )
        return Response(content="success", media_type="text/plain; charset=utf-8")

    response_url = str(payload["response_url"]).strip()
    user_text = extract_user_text(payload)
    reply_content = format_reply_text(user_text, _reply_template())
    background_tasks.add_task(_send_auto_reply, response_url, reply_content, msgid)

    return Response(content="success", media_type="text/plain; charset=utf-8")
