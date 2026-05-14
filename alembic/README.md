## Alembic 数据库迁移

- **配置**：在项目根目录 `.env` 中设置 `DATABASE_URL`（与运行应用相同）。
- **升级库结构到最新**（在项目根执行）：

```powershell
cd D:\myobject\AIObject\AIqyweixin
alembic upgrade head
```

- **查看当前版本**：

```powershell
alembic current
```

- **生成新迁移（模型改完后）**：

```powershell
alembic revision --autogenerate -m "describe_change"
```

首次已包含迁移：`20260213_0001_create_unanswered_tickets.py`（表 `unanswered_tickets`）。

### Windows 说明

`alembic.ini` 请保持 **纯 ASCII** 注释；在部分 Windows 区域设置下，该文件若含非 ASCII 字符可能导致 `alembic` 读取失败。
