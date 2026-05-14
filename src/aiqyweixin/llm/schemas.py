"""
LLM 输出约束（JSON Schema / function calling 结构）。

职责：
- 定义意图识别、询价要素抽取等结构化输出 schema
- 统一错误处理：schema 不符合时的重试/降级策略
"""

