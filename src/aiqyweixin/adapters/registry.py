"""
适配器注册与选择。

职责：
- 按配置启用/实例化不同物流商适配器
- 为 services 层提供统一的 get_adapter(provider_name) 入口
"""

