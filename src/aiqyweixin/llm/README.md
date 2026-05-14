## llm/

- **用途**：云端大模型调用封装（可配置 `base_url` + `api_key`，兼容 OpenAI 协议）。
- **原则**：
  - 用 JSON schema / function calling 约束输出（意图、要素抽取等）。
  - 价格结果只来自物流商 API，不允许模型生成数字报价。

