## wecom/

- **用途**：企业微信接入层。
- **回调加解密**：使用官方 `WXBizJsonMsgCrypt`（`vendor/callback_json_python3/`，源自 `weworkapi_python-master/callback_json_python3`），适用于**智能机器人 JSON 回调**。
- **配置**：`WECOM_TOKEN`、`WECOM_ENCODING_AES_KEY`、`WECOM_CORP_ID`；智能机器人 `WECOM_RECEIVE_ID` 留空（默认先空串再试 CorpId）。
- **路由**：`GET/POST /wecom/callback`（见 `webhook.py`）。

