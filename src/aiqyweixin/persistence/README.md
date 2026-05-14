## persistence/

- **用途**：数据库连接与数据访问层。
- **包含**：
  - `session.py`：`SQLAlchemy 2.x` 异步 engine（`asyncpg`）、`get_db` 依赖、启动时 `SELECT 1` 校验。
  - `repositories.py`：工单、路由规则、配置等的增删改查（待实现）。

### `DATABASE_URL` 写法

- 支持 `postgresql://...` 或 `postgresql+asyncpg://...`（前者会在代码里自动加上 `+asyncpg`）。
- 应用启动时若配置了 `DATABASE_URL`，会初始化连接池并执行一次 `SELECT 1`；失败则进程启动失败（便于及早发现配置错误）。

### 在路由里使用会话（示例）

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from aiqyweixin.persistence.session import get_db

@router.get("/example")
async def example(db: Annotated[AsyncSession, Depends(get_db)]):
    ...
```
