from __future__ import annotations

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import Settings
from app.tools.amap_mcp_adapter import resolve_amap_mcp_config


async def main() -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    settings = Settings()
    config = resolve_amap_mcp_config(settings.amap_mcp)
    url = str(config.get("sse_url") or "https://mcp.amap.com/mcp")
    api_key = str(config.get("api_key") or "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None

    print(f"provider={config.get('provider', settings.amap_mcp.get('provider'))}")
    print(f"mode={config.get('mode')}")
    print(f"url={url}")
    print(f"has_key={bool(api_key)}")

    async with streamablehttp_client(url, headers=headers, timeout=20) as streams:
        read_stream, write_stream, _session_id = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"tool_count={len(tools.tools)}")
            for tool in tools.tools:
                description = getattr(tool, "description", "") or ""
                print(f"- {tool.name}: {description[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
