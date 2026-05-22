# 知识库、转人工与未答工单

## 对话处理顺序

```text
用户消息
  → 显式「转人工」？ → 转人工 + 入库
  → 轨迹/跟踪号（百运 §3.6 / §3.7）
  → 询价（百运 §3.1）
  → 知识库检索 + LLM 归纳
  → 知识库未命中且 UNANSWERED_ON_KB_MISS=true → 转人工 + 入库
  → 通用 LLM
  → LLM 失败且 UNANSWERED_ON_LLM_FALLBACK=true → 转人工 + 入库
```

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `DATABASE_URL` | — | PostgreSQL，未答工单入库必填 |
| `KB_ENABLED` | true | 启用知识库问答 |
| `KB_DATA_DIR` | `data/knowledge` | 知识库 Markdown 目录 |
| `KB_TOP_K` | 3 | 检索片段数 |
| `KB_MIN_SCORE` | 1 | 最低关键词命中分 |
| `HANDOFF_ENABLED` | true | 启用转人工话术与入库 |
| `HANDOFF_DEFAULT_USERIDS` | — | 默认客服 userid，逗号分隔或 JSON 数组 |
| `HANDOFF_DM_FALLBACK_MESSAGE` | 内置文案 | 单聊降级提示 |
| `HANDOFF_KEYWORD_RULES` | — | 每行 `关键词=>userid1,userid2` |
| `UNANSWERED_SAVE_ENABLED` | true | 是否写入 `unanswered_tickets` |
| `UNANSWERED_ON_KB_MISS` | false | 知识库无命中是否转人工 |
| `UNANSWERED_ON_LLM_FALLBACK` | true | LLM 失败是否转人工 |
| `ENABLE_ADMIN_ROUTES` | false | 开启 `GET /admin/unanswered-tickets` |

## 知识库维护

1. 在 `data/knowledge/` 增加 `.md` / `.txt`，用 `##` 标题分节便于检索。
2. 修改后重启进程（或后续可做热加载）。
3. 勿在知识库写具体运价；价格仅来自百运查价 API。

## 未答工单表

迁移：`alembic upgrade head`（表 `unanswered_tickets`）。

管理查询（需 `ENABLE_ADMIN_ROUTES=true` 或 `APP_ENV=development`）：

```bash
curl "http://127.0.0.1:8000/admin/unanswered-tickets?status=pending&limit=20"
```

## 生产部署检查

```env
DATABASE_URL=postgresql://...
KB_ENABLED=true
HANDOFF_ENABLED=true
HANDOFF_DEFAULT_USERIDS=zhangsan,lisi
UNANSWERED_SAVE_ENABLED=true
```

重启服务后：发送「转人工」应看到转人工话术；数据库应有新记录。
