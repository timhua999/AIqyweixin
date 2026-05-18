"""
企业微信官方 WXBizJsonMsgCrypt 封装（智能机器人 JSON 回调）。

源码来自 weworkapi_python callback_json_python3，已 vendoring 至
aiqyweixin.wecom.vendor.callback_json_python3。
"""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path
from urllib.parse import unquote, unquote_plus

from aiqyweixin.config import dotenv_path, get_settings

logger = logging.getLogger(__name__)

_VENDOR_DIR = Path(__file__).resolve().parent / "vendor" / "callback_json_python3"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

from WXBizJsonMsgCrypt import WXBizJsonMsgCrypt  # noqa: E402

from aiqyweixin.wecom.vendor.callback_json_python3 import ierror  # noqa: E402

_IERROR_NAMES: dict[int, str] = {
    ierror.WXBizMsgCrypt_OK: "OK",
    ierror.WXBizMsgCrypt_ValidateSignature_Error: "ValidateSignature_Error",
    ierror.WXBizMsgCrypt_ParseJson_Error: "ParseJson_Error",
    ierror.WXBizMsgCrypt_ComputeSignature_Error: "ComputeSignature_Error",
    ierror.WXBizMsgCrypt_IllegalAesKey: "IllegalAesKey",
    ierror.WXBizMsgCrypt_ValidateCorpid_Error: "ValidateCorpid_Error",
    ierror.WXBizMsgCrypt_EncryptAES_Error: "EncryptAES_Error",
    ierror.WXBizMsgCrypt_DecryptAES_Error: "DecryptAES_Error",
    ierror.WXBizMsgCrypt_IllegalBuffer: "IllegalBuffer",
}


def ierror_name(code: int) -> str:
    return _IERROR_NAMES.get(code, f"UnknownError({code})")


def _normalize_aes_key(key: str) -> str:
    k = (key or "").strip()
    if len(k) >= 2 and k[0] == k[-1] and k[0] in {'"', "'"}:
        k = k[1:-1].strip()
    return k


def receive_id_candidates(corp_id: str) -> list[str]:
    """
    智能机器人：ReceiveId 传空串；自建应用：一般为 CorpId。
    可通过 WECOM_RECEIVE_ID 显式指定；未指定时先空串再 CorpId。
    """
    s = get_settings()
    explicit = (s.wecom_receive_id if s.wecom_receive_id is not None else "").strip()
    corp = (corp_id or "").strip()
    if explicit:
        return [explicit]
    out: list[str] = [""]
    if corp and corp not in out:
        out.append(corp)
    return out


def compute_msg_signature(token: str, timestamp: str, nonce: str, encrypt: str) -> str:
    """与官方 SHA1.getSHA1 相同算法。"""
    parts = sorted([str(token), str(timestamp), str(nonce), str(encrypt)])
    return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()


def _echostr_variants(echostr: str) -> list[str]:
    """Urldecode 后用于验签/解密的 echostr 候选（避免 + 被当成空格等）。"""
    s = (echostr or "").strip()
    out: list[str] = []

    def add(v: str) -> None:
        v = (v or "").strip()
        if v and v not in out:
            out.append(v)

    add(s)
    add(s.replace(" ", "+"))
    add(unquote(s))
    add(unquote_plus(s))
    return out


def create_wxcrypt(token: str, encoding_aes_key: str, receive_id: str) -> WXBizJsonMsgCrypt:
    return WXBizJsonMsgCrypt(
        (token or "").strip(),
        _normalize_aes_key(encoding_aes_key),
        receive_id,
    )


def verify_url(
    token: str,
    encoding_aes_key: str,
    corp_id: str,
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
) -> tuple[str, str]:
    """
    GET 回调 URL 验证。返回 (使用的 receive_id, 明文 echostr)。
    """
    token = (token or "").strip()
    last_code = ierror.WXBizMsgCrypt_ValidateSignature_Error
    for ech in _echostr_variants(echostr):
        for rid in receive_id_candidates(corp_id):
            wxcpt = create_wxcrypt(token, encoding_aes_key, rid)
            ret, plain = wxcpt.VerifyURL(msg_signature, timestamp, nonce, ech)
            if ret == ierror.WXBizMsgCrypt_OK and plain is not None:
                logger.info(
                    "企微 VerifyURL 成功 receive_id=%r echostr_len=%d",
                    rid or "(empty)",
                    len(ech),
                )
                return rid, plain
            last_code = ret
            if ret == ierror.WXBizMsgCrypt_ValidateSignature_Error:
                computed = compute_msg_signature(token, timestamp, nonce, ech)
                logger.warning(
                    "企微验签失败 receive_id=%r echostr_len=%d computed_sig=%s msg_signature=%s "
                    "token_len=%d（请核对 .env 的 WECOM_TOKEN 与企微后台/调试工具是否完全一致）",
                    rid or "(empty)",
                    len(ech),
                    computed,
                    msg_signature,
                    len(token),
                )
            else:
                logger.warning(
                    "企微 VerifyURL 失败 ret=%s (%s) receive_id=%r",
                    ret,
                    ierror_name(ret),
                    rid or "(empty)",
                )
    raise WecomCryptError(last_code, "VerifyURL")


def decrypt_post_body(
    token: str,
    encoding_aes_key: str,
    corp_id: str,
    post_data: str,
    msg_signature: str,
    timestamp: str,
    nonce: str,
) -> tuple[str, str]:
    """POST 消息解密。返回 (使用的 receive_id, 明文 JSON 字符串)。"""
    last_code = ierror.WXBizMsgCrypt_DecryptAES_Error
    for rid in receive_id_candidates(corp_id):
        wxcpt = create_wxcrypt(token, encoding_aes_key, rid)
        ret, plain = wxcpt.DecryptMsg(post_data, msg_signature, timestamp, nonce)
        if ret == ierror.WXBizMsgCrypt_OK and plain is not None:
            logger.info("企微 DecryptMsg 成功 receive_id=%r", rid or "(empty)")
            return rid, plain
        last_code = ret
        logger.warning(
            "企微 DecryptMsg 失败 ret=%s (%s) receive_id=%r",
            ret,
            ierror_name(ret),
            rid or "(empty)",
        )
    raise WecomCryptError(last_code, "DecryptMsg")


class WecomCryptError(Exception):
    def __init__(self, code: int, stage: str) -> None:
        self.code = code
        self.stage = stage
        super().__init__(f"{stage}: {ierror_name(code)} (code={code})")


def config_diagnostics(token: str | None, encoding_aes_key: str | None, corp_id: str | None) -> dict:
    aes = _normalize_aes_key(encoding_aes_key or "")
    return {
        "env_file": str(dotenv_path()),
        "corp_id_set": bool((corp_id or "").strip()),
        "token_len": len((token or "").strip()),
        "aes_key_len": len(aes),
        "aes_key_ok_len": len(aes) == 43,
        "receive_id_candidates": receive_id_candidates((corp_id or "").strip()),
    }
