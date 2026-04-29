from app.config.settings import Settings
from app.tools import AgentReachAdapter, AmapMcpAdapter


def test_api_routes_use_configured_tool_provider():
    from app.api import routes

    # 根据配置，工具提供者可能是 AmapMcpAdapter 或 AgentReachAdapter
    assert isinstance(routes.tool_provider, (AmapMcpAdapter, AgentReachAdapter))


def test_worker_uses_configured_tool_provider(tmp_path):
    from app.workers.run_worker import build_worker

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'worker.db'}",
        use_mock_only=False,
        enable_agent_reach=True,
        enable_amap_mcp=False,
        redis_url="",
    )

    worker = build_worker(settings)
    provider = worker.runner.chat_service.planner_agent.agents[0].tool_provider

    assert isinstance(provider, AgentReachAdapter)
