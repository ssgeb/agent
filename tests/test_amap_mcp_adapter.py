import pytest

from app.tools.amap_mcp_adapter import AmapMcpAdapter, AmapMcpClient, resolve_amap_mcp_config


@pytest.mark.asyncio
async def test_search_attraction_uses_amap_text_search_and_normalizes_pois():
    calls = []

    async def client(tool_name: str, arguments: dict):
        calls.append((tool_name, arguments))
        return {
            "pois": [
                {
                    "name": "西湖风景名胜区",
                    "address": "杭州市西湖区",
                    "location": "120.141,30.259",
                    "type": "风景名胜",
                }
            ]
        }

    adapter = AmapMcpAdapter(client=client)

    results = await adapter.search_attraction({"destination": "杭州", "keyword": "西湖"})

    assert calls == [
        (
            "maps_text_search",
            {
                "city": "杭州",
                "keywords": "西湖",
            },
        )
    ]
    assert results == [
        {
            "name": "西湖风景名胜区",
            "address": "杭州市西湖区",
            "location": "120.141,30.259",
            "type": "风景名胜",
            "source": "amap_mcp",
        }
    ]


@pytest.mark.asyncio
async def test_search_transport_prefers_transit_when_origin_and_destination_are_available():
    calls = []

    async def client(tool_name: str, arguments: dict):
        calls.append((tool_name, arguments))
        if tool_name == "maps_geo":
            if arguments["address"] == "上海虹桥站":
                return {"geocodes": [{"location": "121.318,31.194"}]}
            if arguments["address"] == "杭州东站":
                return {"geocodes": [{"location": "120.212,30.293"}]}
        if tool_name == "maps_direction_transit_integrated":
            return {"route": {"transits": [{"duration": "3600", "cost": "12"}]}}
        raise AssertionError(f"unexpected tool {tool_name}")

    adapter = AmapMcpAdapter(client=client)

    results = await adapter.search_transport({"origin": "上海虹桥站", "destination": "杭州东站", "city": "上海"})

    assert calls == [
        ("maps_geo", {"address": "上海虹桥站", "city": "上海"}),
        ("maps_geo", {"address": "杭州东站", "city": "上海"}),
        (
            "maps_direction_transit_integrated",
            {
                "origin": "121.318,31.194",
                "destination": "120.212,30.293",
                "city": "上海",
            },
        )
    ]
    assert results == [
        {
            "mode": "transit",
            "from": "上海虹桥站",
            "to": "杭州东站",
            "duration_seconds": 3600,
            "cost": 12.0,
            "source": "amap_mcp",
        }
    ]


@pytest.mark.asyncio
async def test_rag_search_uses_weather_when_query_mentions_weather():
    calls = []

    async def client(tool_name: str, arguments: dict):
        calls.append((tool_name, arguments))
        return {"forecasts": [{"city": "杭州", "weather": "晴", "temperature": "24"}]}

    adapter = AmapMcpAdapter(client=client)

    results = await adapter.rag_search("杭州天气")

    assert calls == [("maps_weather", {"city": "杭州"})]
    assert results == [
        {
            "title": "杭州天气",
            "content": "晴 24",
            "source": "amap_mcp",
        }
    ]


@pytest.mark.asyncio
async def test_adapter_falls_back_to_mock_when_mcp_client_fails():
    async def client(tool_name: str, arguments: dict):
        raise RuntimeError("mcp unavailable")

    adapter = AmapMcpAdapter(client=client)

    results = await adapter.search_attraction({"destination": "杭州"})

    assert results == [
        {"name": "杭州西湖", "duration_hours": 3},
        {"name": "杭州灵隐寺", "duration_hours": 2.5},
        {"name": "杭州河坊街", "duration_hours": 2},
    ]


@pytest.mark.asyncio
async def test_route_driving_geocodes_text_addresses_before_calling_route_tool():
    calls = []

    async def client(tool_name: str, arguments: dict):
        calls.append((tool_name, arguments))
        if tool_name == "maps_geo":
            if arguments["address"] == "杭州东站":
                return {"geocodes": [{"location": "120.208,30.289"}]}
            if arguments["address"] == "西湖":
                return {"geocodes": [{"location": "120.140,30.250"}]}
        if tool_name == "maps_direction_driving":
            return {"route": {"paths": [{"duration": "1800", "distance": "12000"}]}}
        raise AssertionError(f"unexpected tool {tool_name}")

    adapter = AmapMcpAdapter(client=client)

    results = await adapter.route_driving({"origin": "杭州东站", "destination": "西湖", "city": "杭州"})

    assert calls == [
        ("maps_geo", {"address": "杭州东站", "city": "杭州"}),
        ("maps_geo", {"address": "西湖", "city": "杭州"}),
        ("maps_direction_driving", {"origin": "120.208,30.289", "destination": "120.140,30.250", "city": "杭州"}),
    ]
    assert results == [
        {
            "mode": "driving",
            "from": "杭州东站",
            "to": "西湖",
            "duration_seconds": 1800,
            "distance_meters": 12000.0,
            "source": "amap_mcp",
        }
    ]


@pytest.mark.asyncio
async def test_take_taxi_returns_schema_link():
    calls = []

    async def client(tool_name: str, arguments: dict):
        calls.append((tool_name, arguments))
        if tool_name == "maps_geo":
            if arguments["address"] == "杭州东站":
                return {"results": [{"location": "120.208,30.289"}]}
            if arguments["address"] == "西湖":
                return {"results": [{"location": "120.140,30.250"}]}
        if tool_name == "maps_schema_take_taxi":
            return {"text": "唤端URI，直接完整展示，禁止任何加工amapuri://drive/takeTaxi?sourceApplication=amapplatform&slat=30.289&slon=120.208&sname=%E6%9D%AD%E5%B7%9E%E4%B8%9C%E7%AB%99&dlon=120.140&dlat=30.250&dname=%E8%A5%BF%E6%B9%96"}
        raise AssertionError(f"unexpected tool {tool_name}")

    adapter = AmapMcpAdapter(client=client)

    result = await adapter.take_taxi({"origin": "杭州东站", "destination": "西湖", "city": "杭州"})

    assert calls == [
        ("maps_geo", {"address": "杭州东站", "city": "杭州"}),
        ("maps_geo", {"address": "西湖", "city": "杭州"}),
        (
            "maps_schema_take_taxi",
            {"slon": "120.208", "slat": "30.289", "sname": "杭州东站", "dlon": "120.140", "dlat": "30.250", "dname": "西湖"},
        )
    ]
    assert result == [
        {
            "title": "打车",
            "content": "amapuri://drive/takeTaxi?sourceApplication=amapplatform&slat=30.289&slon=120.208&sname=%E6%9D%AD%E5%B7%9E%E4%B8%9C%E7%AB%99&dlon=120.140&dlat=30.250&dname=%E8%A5%BF%E6%B9%96",
            "source": "amap_mcp",
        }
    ]


def test_stdio_client_reports_available_when_command_exists(monkeypatch):
    monkeypatch.setattr("app.tools.amap_mcp_adapter.shutil.which", lambda command: "C:/node/npm.cmd")

    client = AmapMcpClient(mode="stdio", command=["npx", "-y", "@amap/amap-maps-mcp-server"])

    assert client.is_available() is True


def test_sse_client_requires_url_and_optional_mcp_sdk(monkeypatch):
    monkeypatch.setattr("app.tools.amap_mcp_adapter.importlib.util.find_spec", lambda name: None)

    client = AmapMcpClient(mode="sse", sse_url="https://example.com/sse")

    assert client.is_available() is False


def test_streamable_http_client_requires_url_and_mcp_sdk(monkeypatch):
    monkeypatch.setattr("app.tools.amap_mcp_adapter.importlib.util.find_spec", lambda name: object())

    client = AmapMcpClient(mode="streamable-http", sse_url="https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp")

    assert client.is_available() is True


def test_amap_official_streamable_http_url_appends_key_without_bearer_header():
    client = AmapMcpClient(
        mode="streamable-http",
        sse_url="https://mcp.amap.com/mcp",
        api_key="amap-web-service-key",
    )

    url, headers = client.connection_options()

    assert url == "https://mcp.amap.com/mcp?key=amap-web-service-key"
    assert headers == {}


def test_amap_official_streamable_http_keeps_existing_key_query():
    client = AmapMcpClient(
        mode="streamable-http",
        sse_url="https://mcp.amap.com/mcp?key=already-in-url",
        api_key="ignored-key",
    )

    url, headers = client.connection_options()

    assert url == "https://mcp.amap.com/mcp?key=already-in-url"
    assert headers == {}


def test_resolve_amap_mcp_config_selects_requested_profile():
    config = {
        "provider": "aliyun",
        "aliyun": {"mode": "streamable-http", "sse_url": "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp", "api_key": "aliyun-key"},
        "amap": {"mode": "stdio", "command": ["npx", "-y", "@amap/amap-maps-mcp-server"], "api_key": "amap-key"},
    }

    resolved = resolve_amap_mcp_config(config)

    assert resolved["mode"] == "streamable-http"
    assert resolved["sse_url"] == "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp"
    assert resolved["api_key"] == "aliyun-key"
