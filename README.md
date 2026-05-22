# AIqyweixin

企业微信国际物流智能机器人（单租户独立部署 · MVP）。

- 需求文档见 `docs/SRS-企业微信国际物流智能机器人.md`
- 技术方案见 `docs/plans/企微物流机器人需求与方案_65042efd.plan.md`

## 本地运行（最小 FastAPI）

1. 复制环境变量模板：`copy .env.example .env`（Windows）并填写真实值（不要将 `.env` 提交到 Git）。
2. 创建虚拟环境并安装（Python 3.13+）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

3. 启动服务：

```powershell
uvicorn aiqyweixin.main:app --reload --host 0.0.0.0 --port 8000
```

或使用入口脚本：`aiqyweixin-serve`（默认 `HOST`/`PORT`/`RELOAD` 可用环境变量覆盖）。

4. 浏览器访问：`http://127.0.0.1:8000/health`；可选：`http://127.0.0.1:8000/ready`（检查 `.env` 关键项是否已配置，**不返回任何密钥**；若已配置 `DATABASE_URL`，会返回 `database_reachable`）。

## 数据库（PostgreSQL 已接入）

- `.env` 中设置 `DATABASE_URL`（可用 `postgresql://user:pass@127.0.0.1:5432/dbname`，代码会自动改为 `postgresql+asyncpg://`）。
- 启动时会对数据库执行一次 `SELECT 1`；失败则服务无法启动（请检查账号、库名、防火墙）。
- 依赖：`sqlalchemy[asyncio]`、`asyncpg`、`alembic`（见 `pyproject.toml`）。安装：`pip install -e .`

## 数据库迁移（Alembic）

在项目根目录、已配置 `.env` 的 `DATABASE_URL` 后执行：

```powershell
alembic upgrade head
```

说明见 [alembic/README.md](alembic/README.md)。首次迁移会创建表 `unanswered_tickets`（未答工单）。

## 临时调试接口（仅开发）

当 **`APP_ENV=development`** 或 **`ENABLE_DEBUG_ROUTES=true`**，且已配置 **`DATABASE_URL`** 时，会注册 `POST /debug/unanswered-ticket`（插入一条测试未答工单；可选 JSON 体覆盖默认字段）。

示例（空 body 使用默认）：

```powershell
curl.exe -X POST http://127.0.0.1:8000/debug/unanswered-ticket
```

生产请将 `APP_ENV=production` 且 `ENABLE_DEBUG_ROUTES=false`，该路由不会注册。

## 产品能力：知识库、转人工、未答工单

配置 `DATABASE_URL` 并执行 `alembic upgrade head` 后，企微对话将按顺序处理：**转人工关键词 → 百运查价/轨迹 → 知识库问答 → 通用 LLM**；转人工或（可选）知识库/LLM 失败时会写入 `unanswered_tickets`。

- 知识库：在 `data/knowledge/` 放置 Markdown（见示例 `faq-packaging.md`）。
- 环境变量与流程说明：[docs/product-kb-handoff.md](docs/product-kb-handoff.md)
- 管理列表：`ENABLE_ADMIN_ROUTES=true` 时 `GET /admin/unanswered-tickets?status=pending`

