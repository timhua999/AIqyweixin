"""
企业微信「接收消息」回调：使用官方 WXBizJsonMsgCrypt（智能机器人 JSON）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from fastapi import APIRouter, HTTPException, Query, Request, Response

from aiqyweixin.config import get_settings
from aiqyweixin.orchestrator.chat import build_wecom_reply
from aiqyweixin.wecom.messages import extract_message_context, extract_user_text, should_reply
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


def _trace(msg: str) -> None:
    """写入 stderr，避免被 Uvicorn 日志配置挡住（部署排查用）。"""
    print(f"[aiqyweixin] {msg}", file=sys.stderr, flush=True)

# 同一 msgid 只处理一次（企微可能重试/并发回调，避免多次调 LLM、多次抢 response_url）
_replied_msgids: set[str] = set()
_inflight_msgids: set[str] = set()
_max_msgid_cache = 5000
_webhook_lock = asyncio.Lock()


def _already_handled(msgid: str) -> bool:
    return bool(msgid) and (msgid in _replied_msgids or msgid in _inflight_msgids)


def _mark_inflight(msgid: str) -> None:
    if not msgid:
        return
    _inflight_msgids.add(msgid)
    if len(_inflight_msgids) > _max_msgid_cache:
        _inflight_msgids.clear()


def _mark_replied(msgid: str) -> None:
    if not msgid:
        return
    _inflight_msgids.discard(msgid)
    _replied_msgids.add(msgid)
    if len(_replied_msgids) > _max_msgid_cache:
        _replied_msgids.clear()


def _clear_inflight(msgid: str) -> None:
    if msgid:
        _inflight_msgids.discard(msgid)


async def _send_auto_reply(response_url: str, content: str, msgid: str) -> None:
    await post_active_reply(response_url, content)
    _mark_replied(msgid)
    logger.info("企微主动回复成功 msgid=%s 字符数=%s", msgid or "(none)", len(content))
    _trace(f"主动回复成功 msgid={msgid or '(none)'} 字符数={len(content)}")


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
    _trace(f"解密成功: {plain[:200]}")

    try:
        payload = json.loads(plain)
    except json.JSONDecodeError:
        logger.warning("解密结果非 JSON，跳过主动回复")
        _trace("解密结果非 JSON，跳过回复")
        return Response(content="success", media_type="text/plain; charset=utf-8")

    if not isinstance(payload, dict):
        return Response(content="success", media_type="text/plain; charset=utf-8")

    msgid = str(payload.get("msgid") or "")
    msgtype = payload.get("msgtype")

    if not should_reply(payload):
        logger.info(
            "跳过主动回复 msgtype=%s response_url=%s",
            msgtype,
            "有" if (payload.get("response_url") or "").strip() else "无",
        )
        has_url = "有" if (payload.get("response_url") or "").strip() else "无"
        _trace(f"跳过回复 msgtype={msgtype} response_url={has_url}")
        return Response(content="success", media_type="text/plain; charset=utf-8")

    async with _webhook_lock:
        if _already_handled(msgid):
            logger.info("msgid 已处理或处理中，跳过: %s", msgid)
            _trace(f"msgid 已处理或处理中，跳过: {msgid}")
            return Response(content="success", media_type="text/plain; charset=utf-8")
        _mark_inflight(msgid)

    response_url = str(payload["response_url"]).strip()
    user_text = extract_user_text(payload)
    msg_ctx = extract_message_context(payload)
    try:
        _trace(f"开始生成回复 msgid={msgid} msgtype={msgtype}")
        reply_content = await build_wecom_reply(user_text, msg_ctx)
        logger.info(
            "LLM/回复就绪 msgid=%s msgtype=%s 字符数=%s 日志预览(非全文)=%s",
            msgid or "(none)",
            msgtype,
            len(reply_content),
            reply_content[:80],
        )
        await _send_auto_reply(response_url, reply_content, msgid)
    except Exception as exc:
        _clear_inflight(msgid)
        logger.exception("企微回复流程失败 msgid=%s", msgid or "(none)")
        _trace(f"回复失败 msgid={msgid}: {exc}")

    return Response(content="success", media_type="text/plain; charset=utf-8")
