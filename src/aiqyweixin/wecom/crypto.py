"""
企业微信回调加解密与验签。

职责：
- URL 验证（首次配置回调时）
- 消息体解密/加密（EncodingAESKey）
- 签名校验（msg_signature / timestamp / nonce）
"""

