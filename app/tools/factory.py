from __future__ import annotations

from app.config.settings import Settings
from app.tools.agent_reach_adapter import AgentReachAdapter
from app.tools.amap_mcp_adapter import AmapMcpAdapter
from app.tools.interface import ToolInterface
from app.tools.mock_provider import MockProvider


def create_tool_provider(settings: Settings | None = None) -> ToolInterface:
    settings = settings or Settings()
    if settings.use_mock_only:
        return MockProvider()

    # AmapMcpAdapter 用于实际 API 调用（打车、路径规划、酒店/景点搜索）
    if settings.enable_amap_mcp:
        return AmapMcpAdapter(
            timeout_seconds=float(settings.tool_timeout),
            config=settings.amap_mcp,
        )

    # AgentReachAdapter 用于搜索小红书、携程等内容平台
    if settings.enable_agent_reach:
        return AgentReachAdapter(
            timeout_seconds=float(settings.tool_timeout),
            config=settings.agent_reach,
        )

    return MockProvider()
