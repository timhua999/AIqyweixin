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
    明文结构：random(16) + msg_len(4, big-endian) + msg + receive_id（一般为 CorpId）
    """
    aes_key = _decode_aes_key(encoding_aes_key)
    iv = aes_key[:_AES_BLOCK]
    ciphertext = base64.b64decode(encrypt_b64)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    plain = unpad(cipher.decrypt(ciphertext), _AES_BLOCK)

    if len(plain) < 20:
        raise ValueError("decrypted payload too short")

    msg_len = struct.unpack(">I", plain[16:20])[0]
    if msg_len < 0 or 20 + msg_len > len(plain):
        raise ValueError("invalid msg length in decrypted payload")

    msg = plain[20 : 20 + msg_len].decode("utf-8")
    tail = plain[20 + msg_len :].decode("utf-8")
    if tail != receive_id:
        raise ValueError("receive_id suffix mismatch")
    return msg
