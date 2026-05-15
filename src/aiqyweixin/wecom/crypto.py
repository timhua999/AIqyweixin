"""
企业微信回调加解密与验签（与官方 WXBizMsgCrypt 算法一致）。
"""

from __future__ import annotations

import base64
import hashlib
import struct
from typing import Final

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

_AES_BLOCK: Final[int] = 16


def aes_key_fingerprint(encoding_aes_key: str) -> str:
    """用于日志比对是否与后台 Key 一致，不输出密钥明文。"""
    try:
        raw = _decode_aes_key(encoding_aes_key)
        return hashlib.sha256(raw).hexdigest()[:16]
    except Exception:
        return "invalid-key"


def wecom_config_diagnostics(
    corp_id: str | None,
    token: str | None,
    encoding_aes_key: str | None,
    env_file: str | None = None,
) -> dict[str, str | int | bool]:
    aes = (encoding_aes_key or "").strip()
    if len(aes) >= 2 and aes[0] == aes[-1] and aes[0] in {'"', "'"}:
        aes = aes[1:-1].strip()
    return {
        "env_file": env_file or "",
        "corp_id_set": bool((corp_id or "").strip()),
        "corp_id_prefix": ((corp_id or "").strip()[:6] + "...") if corp_id else "",
        "token_len": len((token or "").strip()),
        "aes_key_len": len(aes),
        "aes_key_fp": aes_key_fingerprint(aes) if aes else "missing",
        "aes_key_ok_len": len(aes) == 43,
    }


def compute_msg_signature(token: str, timestamp: str, nonce: str, encrypt: str) -> str:
    parts = sorted([token, timestamp, nonce, encrypt])
    raw = "".join(parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def verify_msg_signature(
    token: str, timestamp: str, nonce: str, encrypt: str, msg_signature: str
) -> bool:
    expect = compute_msg_signature(token, timestamp, nonce, encrypt)
    return expect.lower() == (msg_signature or "").lower()


def _decode_aes_key(encoding_aes_key: str) -> bytes:
    key = (encoding_aes_key or "").strip()
    # 避免 .env 写成 WECOM_ENCODING_AES_KEY="xxxx" 时把引号吃进 key
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {'"', "'"}:
        key = key[1:-1].strip()
    if not key:
        raise ValueError("empty EncodingAESKey")
    # 43 字符 Base64，补全 padding
    pad = "=" * ((4 - len(key) % 4) % 4)
    raw = base64.b64decode(key + pad)
    if len(raw) != 32:
        raise ValueError("EncodingAESKey must decode to 32 bytes")
    return raw


def decrypt_callback_aes(encrypt_b64: str, encoding_aes_key: str, receive_id: str) -> str:
    """
    解密 URL 校验 echostr 或消息体 Encrypt 字段。

    明文结构：random(16) + msg_len(4, big-endian) + msg + receive_id。

    - 自建应用接收消息：包尾 receive_id 一般为 **企业 CorpId**。
    - **智能机器人**（官方说明）：GET 校验解密后仅有 random/msg_len/msg 三字段，
      **ReceiveId 为空**；加解密库传 receiveid 用空串。此处允许 **包尾为空** 或 **等于 receive_id**。
    """
    recv = (receive_id or "").strip().replace("\r", "").replace("\ufeff", "")
    aes_key = _decode_aes_key(encoding_aes_key)
    iv = aes_key[:_AES_BLOCK]
    ciphertext = base64.b64decode(encrypt_b64)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    try:
        plain = unpad(cipher.decrypt(ciphertext), _AES_BLOCK)
    except ValueError as e:
        raise ValueError(
            "AES decrypt/padding failed: EncodingAESKey 与企微后台不一致，或 echostr 被破坏 "
            f"(aes_key_fp={aes_key_fingerprint(encoding_aes_key)})"
        ) from e

    if len(plain) < 20:
        raise ValueError("decrypted payload too short")

    msg_len = struct.unpack(">I", plain[16:20])[0]
    if msg_len < 0 or 20 + msg_len > len(plain):
        raise ValueError("invalid msg length in decrypted payload")

    msg = plain[20 : 20 + msg_len].decode("utf-8")
    tail = plain[20 + msg_len :].decode("utf-8").strip().replace("\r", "").replace("\ufeff", "")
    # 智能机器人：tail == ""；普通自建：tail == corp_id
    if tail != recv and tail != "":
        raise ValueError(
            "receive_id suffix mismatch: decrypted tail does not match CorpId / empty "
            f"(tail={tail!r}, expected CorpId={recv!r} or empty for intelligent robot)"
        )
    return msg
