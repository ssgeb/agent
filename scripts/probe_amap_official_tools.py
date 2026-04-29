from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools.amap_mcp_adapter import AmapMcpClient


async def main() -> None:
    client = AmapMcpClient(
        mode="streamable-http",
        sse_url="https://mcp.amap.com/mcp",
        api_key="1647ca10b221586df9bd7a54e22e18f9",
        timeout_seconds=20,
    )

    tests = [
        ("maps_geo", {"address": "杭州东站", "city": "杭州"}),
        ("maps_schema_take_taxi", {"origin": "杭州东站", "destination": "西湖", "city": "杭州"}),
        ("maps_schema_navi", {"origin": "杭州东站", "destination": "西湖", "city": "杭州"}),
        ("maps_direction_driving", {"origin": "120.208,30.289", "destination": "120.140,30.250", "city": "杭州"}),
    ]
    for tool_name, args in tests:
        print(f"=== {tool_name} ===")
        try:
            result = await client(tool_name, args)
            print(result)
        except Exception as exc:
            print(type(exc).__name__, exc)

    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    print("=== tool schemas ===")
    async with streamablehttp_client("https://mcp.amap.com/mcp?key=1647ca10b221586df9bd7a54e22e18f9", timeout=20) as streams:
        read_stream, write_stream, _session_id = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            for tool in tools.tools:
                if tool.name in {"maps_schema_take_taxi", "maps_schema_navi", "maps_geo", "maps_direction_driving"}:
                    print(tool.name)
                    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
                    print(json.dumps(schema, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
