from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import Settings
from app.tools.amap_mcp_adapter import AmapMcpClient, resolve_amap_mcp_config


def _resolve_active_amap_config(settings: Settings) -> dict:
    return resolve_amap_mcp_config(settings.amap_mcp)


def run_qwen_agent(settings: Settings, api_key: str) -> bool:
    try:
        from qwen_agent.agents import Assistant
    except ImportError as exc:
        print('缺少 qwen-agent，请先运行：pip install -U "qwen-agent[mcp]"')
        print(f"导入失败详情：{exc}")
        return False

    os.environ["DASHSCOPE_API_KEY"] = api_key

    active_config = _resolve_active_amap_config(settings)
    llm_cfg = {
        "model": settings.llm_model or "qwen-max",
    }
    system = (
        "你是一个天气和地图查询智能体。"
        "你必须优先调用名为 amap-maps 的 MCP 服务获取结构化数据，"
        "不要凭空编造实时天气、地点或路线信息。"
    )
    tools = [
        {
            "mcpServers": {
                "amap-maps": {
                    "type": "streamable-http",
                    "url": active_config.get("sse_url")
                    or "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp",
                    "headers": {
                        "Authorization": f"Bearer {api_key}",
                    },
                }
            }
        }
    ]

    try:
        bot = Assistant(
            llm=llm_cfg,
            name="amap-maps-test-agent",
            description="Amap Maps MCP test agent",
            system_message=system,
            function_list=tools,
        )
    except Exception as exc:
        print(f"Qwen Agent 初始化 MCP 失败：{exc.__class__.__name__}: {exc}")
        return False

    messages = [{"role": "user", "content": "请调用 amap-maps 查询杭州今日天气。"}]
    print("正在通过 Qwen Agent + 阿里云百炼 Amap MCP 查询杭州天气...")
    print("=" * 60)

    final_content = ""
    for response in bot.run(messages):
        print(response)
        if isinstance(response, list):
            for item in response:
                if isinstance(item, dict) and item.get("role") == "assistant" and item.get("content"):
                    final_content = str(item["content"])
        elif isinstance(response, dict) and response.get("content"):
            final_content = str(response["content"])

    print("=" * 60)
    print(final_content or "未能获取最终回复。")
    return True


async def run_direct_mcp(settings: Settings, api_key: str) -> None:
    active_config = _resolve_active_amap_config(settings)
    client = AmapMcpClient(
        mode=str(active_config.get("mode") or "streamable-http"),
        sse_url=str(active_config.get("sse_url") or "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp"),
        api_key=api_key,
        timeout_seconds=20,
    )
    print("正在通过 Python MCP SDK 直连阿里云百炼 Amap MCP 查询杭州天气...")
    print("=" * 60)
    result = await client("maps_weather", {"city": "杭州"})
    print(result)


def main() -> None:
    settings = Settings()
    active_config = _resolve_active_amap_config(settings)
    api_key = active_config.get("api_key") or settings.llm_api_key or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("缺少百炼 API Key，请在 config.yaml 的 amap_mcp.api_key 中配置，或设置 DASHSCOPE_API_KEY。")
        return

    if "--direct" in sys.argv:
        import asyncio

        asyncio.run(run_direct_mcp(settings, api_key))
        return

    if run_qwen_agent(settings, api_key):
        return

    print("可单独运行直连模式继续测试：")
    print("conda run -n leetcode python scripts\\test_bailian_qwen_agent_mcp.py --direct")


if __name__ == "__main__":
    main()
