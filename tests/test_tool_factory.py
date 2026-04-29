from app.config.settings import Settings
from app.tools import AgentReachAdapter, AmapMcpAdapter, MockProvider
from app.tools.factory import create_tool_provider


def test_create_tool_provider_returns_mock_when_mock_only():
    settings = Settings(use_mock_only=True, enable_agent_reach=True)

    provider = create_tool_provider(settings)

    assert isinstance(provider, MockProvider)


def test_create_tool_provider_returns_agent_reach_when_enabled():
    settings = Settings(use_mock_only=False, enable_amap_mcp=False, enable_agent_reach=True, tool_timeout=7)

    provider = create_tool_provider(settings)

    assert isinstance(provider, AgentReachAdapter)
    assert provider.timeout_seconds == 7


def test_create_tool_provider_returns_amap_mcp_when_enabled():
    settings = Settings(
        use_mock_only=False,
        enable_amap_mcp=True,
        enable_agent_reach=True,
        amap_mcp={
            "provider": "amap",
            "aliyun": {"mode": "streamable-http", "sse_url": "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp", "api_key": "aliyun-key"},
            "amap": {"mode": "stdio", "command": ["npx", "-y", "@amap/amap-maps-mcp-server"], "api_key": "amap-key"},
        },
    )

    provider = create_tool_provider(settings)

    # AmapMcpAdapter 优先用于实际 API 调用
    assert isinstance(provider, AmapMcpAdapter)
    assert provider.client.mode == "stdio"


def test_create_tool_provider_falls_back_to_mock_when_disabled():
    settings = Settings(use_mock_only=False, enable_amap_mcp=False, enable_agent_reach=False)

    provider = create_tool_provider(settings)

    assert isinstance(provider, MockProvider)
