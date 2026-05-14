"""
转人工兜底服务。

职责：
- 根据意图/关键词/org_unit 等规则选择目标客服（userid 列表）
- 群聊场景：生成“名片 + @ + 邀请入群（若不在群）”的策略载荷（以企微能力为准）
- 单聊场景：返回降级话术（handoff_dm_fallback_message）
- 写入未答工单：route_rule_id、指派 userid、触发原因码等
"""

