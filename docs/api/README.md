## docs/api/

- **用途**：对接接口契约与示例（建议优先 OpenAPI）。
- **建议**：
  - `quote.openapi.yaml`：查价接口（请求/响应/错误码/鉴权）。
  - `track.openapi.yaml`：轨迹接口（请求/响应/错误码/鉴权）。
- **百运 Router API（交接）**：[by56-quote-api.md](./by56-quote-api.md) — §3.1 查价 / §3.6 轨迹 / §3.7 跟踪号，与 `adapters/by56.py`、企微 `quote_flow` / `track_flow` 同步。

