## wecom/

- **用途**：企业微信接入层。
- **回调加解密**：使用官方 `WXBizJsonMsgCrypt`（`vendor/callback_json_python3/`，源自 `weworkapi_python-master/callback_json_python3`），适用于**智能机器人 JSON 回调**。
- **配置**（与 `callback_json_python3/Sample.py` 对应）：
  - `WECOM_TOKEN` ← `sToken`
  - `WECOM_ENCODING_AES_KEY` ← `sEncodingAESKey`
  - `WECOM_CORP_ID` ← 我的企业 → 企业ID
  - `WECOM_RECEIVE_ID` ← 构造加解密库的第三参；**智能机器人收消息请留空**（官方 receiveid 为空串）
- **路由**：`GET/POST /wecom/callback`（见 `webhook.py`）。

