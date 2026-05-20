## llm/

- **用途**：云端大模型调用封装（可配置 `base_url` + `api_key`，兼容 OpenAI 协议）。
- **原则**：
  - 用 JSON schema / function calling 约束输出（意图、要素抽取等）。
  - 价格结果只来自物流商 API，不允许模型生成数字报价。

### 阿里云通义千问（百炼）

```env
LLM_ENABLED=true
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-...        # 百炼控制台 API-KEY
LLM_MODEL=qwen-plus       # 或 qwen-turbo / qwen-max
```

API Key：[百炼控制台](https://bailian.console.aliyun.com/) → API-KEY（需与地域一致）。  
国际站新加坡：`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

