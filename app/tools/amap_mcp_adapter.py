from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import shutil
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.tools.interface import ToolInterface
from app.tools.mock_provider import MockProvider


AmapMcpCallable = Callable[[str, dict], Awaitable[Any]]


def resolve_amap_mcp_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}

    resolved = dict(config)
    selected_provider = str(
        resolved.get("provider") or resolved.get("active_provider") or resolved.get("profile") or ""
    ).strip().lower()
    if not selected_provider:
        return resolved

    selected_profile = resolved.get(selected_provider)
    if not isinstance(selected_profile, dict):
        return resolved

    merged = dict(selected_profile)
    for key in ("mode", "sse_url", "api_key", "command", "timeout_seconds"):
        value = resolved.get(key)
        if key not in merged and value not in (None, "", []):
            merged[key] = value
    return merged


class AmapMcpClient:
    def __init__(
        self,
        *,
        mode: str = "stdio",
        sse_url: str = "",
        api_key: str = "",
        command: list[str] | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.mode = mode
        self.sse_url = sse_url
        self.api_key = api_key
        self.command = command or ["npx", "-y", "@amap/amap-maps-mcp-server"]
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        if self.mode in {"sse", "streamable-http", "streamable_http", "http"}:
            return bool(self.sse_url) and importlib.util.find_spec("mcp") is not None
        executable = self.command[0] if self.command else ""
        return bool(executable) and shutil.which(executable) is not None

    async def __call__(self, tool_name: str, arguments: dict) -> Any:
        if self.mode in {"streamable-http", "streamable_http", "http"}:
            return await self._call_streamable_http(tool_name, arguments)
        if self.mode == "sse" and self.sse_url.rstrip("/").endswith("/mcp"):
            return await self._call_streamable_http(tool_name, arguments)
        if self.mode == "sse":
            return await self._call_sse(tool_name, arguments)
        return await self._call_stdio(tool_name, arguments)

    async def _call_streamable_http(self, tool_name: str, arguments: dict) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError("Python MCP SDK is required for Streamable HTTP mode") from exc

        url, headers = self.connection_options()

        async with streamablehttp_client(
            url,
            headers=headers or None,
            timeout=self.timeout_seconds,
        ) as streams:
            read_stream, write_stream, _get_session_id = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return self._normalize_mcp_result(result)

    async def _call_sse(self, tool_name: str, arguments: dict) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError as exc:
            raise RuntimeError("Python MCP SDK is required for SSE mode") from exc

        url, headers = self.connection_options()

        async with sse_client(url, headers=headers or None) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return self._normalize_mcp_result(result)

    def connection_options(self) -> tuple[str, dict[str, str]]:
        if "mcp.amap.com" in self.sse_url:
            return self._amap_official_connection_options()

        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return self.sse_url, headers

    def _amap_official_connection_options(self) -> tuple[str, dict[str, str]]:
        parsed = urlparse(self.sse_url)
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if self.api_key and not any(key == "key" for key, _value in query_pairs):
            query_pairs.append(("key", self.api_key))
        url = urlunparse(parsed._replace(query=urlencode(query_pairs)))
        return url, {}

    async def _call_stdio(self, tool_name: str, arguments: dict) -> Any:
        env = os.environ.copy()
        if self.api_key:
            env["AMAP_MAPS_API_KEY"] = self.api_key

        process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            await self._send_json_rpc(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            await self._read_json_rpc_response(process, 1)
            await self._send_json_rpc(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            await self._send_json_rpc(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                },
            )
            response = await self._read_json_rpc_response(process, 2)
            if "error" in response:
                raise RuntimeError(str(response["error"]))
            return self._normalize_mcp_result(response.get("result"))
        finally:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=1)
            except asyncio.TimeoutError:
                process.kill()

    async def _send_json_rpc(self, process: asyncio.subprocess.Process, payload: dict) -> None:
        if process.stdin is None:
            raise RuntimeError("mcp process stdin is not available")
        process.stdin.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
        await process.stdin.drain()

    async def _read_json_rpc_response(self, process: asyncio.subprocess.Process, response_id: int) -> dict:
        if process.stdout is None:
            raise RuntimeError("mcp process stdout is not available")

        async def read_until_response() -> dict:
            while True:
                line = await process.stdout.readline()
                if not line:
                    raise RuntimeError("mcp process closed before response")
                try:
                    payload = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                if payload.get("id") == response_id:
                    return payload

        return await asyncio.wait_for(read_until_response(), timeout=self.timeout_seconds)

    def _normalize_mcp_result(self, result: Any) -> Any:
        if result is None:
            return {}
        if isinstance(result, dict):
            content = result.get("content")
        else:
            content = getattr(result, "content", None)

        if not content:
            return result

        fragments: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)
            if text:
                fragments.append(str(text))

        if not fragments:
            return result

        text_payload = "\n".join(fragments).strip()
        try:
            return json.loads(text_payload)
        except json.JSONDecodeError:
            return {"text": text_payload}


class AmapMcpAdapter(ToolInterface):
    def __init__(
        self,
        *,
        client: AmapMcpCallable | None = None,
        timeout_seconds: float = 5.0,
        config: dict[str, Any] | None = None,
    ) -> None:
        config = resolve_amap_mcp_config(config or {})
        self.timeout_seconds = timeout_seconds
        self.client = client or AmapMcpClient(
            mode=str(config.get("mode") or "stdio"),
            sse_url=str(config.get("sse_url") or ""),
            api_key=str(config.get("api_key") or os.environ.get("AMAP_MAPS_API_KEY", "")),
            command=list(config.get("command") or ["npx", "-y", "@amap/amap-maps-mcp-server"]),
            timeout_seconds=timeout_seconds,
        )
        self._mock = MockProvider()

    async def search_transport(self, params: dict) -> list[dict]:
        result = await self.route_transit(params)
        return result or await self._mock.search_transport(params)

    async def search_hotel(self, params: dict) -> list[dict]:
        destination = str(params.get("destination") or params.get("city") or "")
        keyword = str(params.get("keyword") or params.get("near") or "酒店")
        payload = {"keywords": keyword}
        if destination:
            payload["city"] = destination

        result = await self._call_with_fallback("maps_text_search", payload)
        if result is None:
            return await self._mock.search_hotel(params)
        hotels = self._normalize_pois(result)
        return hotels or await self._mock.search_hotel(params)

    async def search_attraction(self, params: dict) -> list[dict]:
        destination = str(params.get("destination") or params.get("city") or "")
        keyword = str(params.get("keyword") or params.get("query") or destination or "景点")
        payload = {"keywords": keyword}
        if destination:
            payload["city"] = destination

        result = await self._call_with_fallback("maps_text_search", payload)
        if result is None:
            return await self._mock.search_attraction(params)
        attractions = self._normalize_pois(result)
        return attractions or await self._mock.search_attraction(params)

    async def geocode(self, address: str, city: str = "") -> dict[str, Any] | None:
        payload: dict[str, Any] = {"address": address}
        if city:
            payload["city"] = city
        result = await self._call_with_fallback("maps_geo", payload)
        if result is None:
            return None
        location = self._extract_geocode_location(result)
        if not location:
            return None
        return {"location": location, "raw": result}

    async def reverse_geocode(self, location: str) -> dict[str, Any] | None:
        result = await self._call_with_fallback("maps_regeocode", {"location": location})
        if result is None:
            return None
        address = self._extract_regeocode_address(result)
        if not address:
            return None
        return {"address": address, "raw": result}

    async def route_driving(self, params: dict) -> list[dict]:
        return await self._route_with_mode(params, mode="driving", tool_name="maps_direction_driving")

    async def route_transit(self, params: dict) -> list[dict]:
        return await self._route_with_mode(params, mode="transit", tool_name="maps_direction_transit_integrated")

    async def route_walking(self, params: dict) -> list[dict]:
        return await self._route_with_mode(params, mode="walking", tool_name="maps_direction_walking")

    async def route_bicycling(self, params: dict) -> list[dict]:
        return await self._route_with_mode(params, mode="bicycling", tool_name="maps_direction_bicycling")

    async def take_taxi(self, params: dict) -> list[dict]:
        origin = str(params.get("origin") or "")
        destination = str(params.get("destination") or "")
        if not origin or not destination:
            return []

        city = str(params.get("city") or params.get("origin_city") or params.get("destination_city") or "")
        origin_city = str(params.get("origin_city") or city or "")
        destination_city = str(params.get("destination_city") or city or "")
        origin_location = await self._resolve_place_location(origin, origin_city)
        destination_location = await self._resolve_place_location(destination, destination_city)
        if not origin_location or not destination_location:
            return []

        origin_lon, origin_lat = self._split_location(origin_location)
        destination_lon, destination_lat = self._split_location(destination_location)
        if not all([origin_lon, origin_lat, destination_lon, destination_lat]):
            return []

        payload: dict[str, Any] = {
            "slon": origin_lon,
            "slat": origin_lat,
            "sname": origin,
            "dlon": destination_lon,
            "dlat": destination_lat,
            "dname": destination,
        }
        result = await self._call_with_fallback("maps_schema_take_taxi", payload)
        if result is None:
            return []
        uri = self._extract_schema_uri(result)
        if not uri:
            return []
        return [{"title": "打车", "content": uri, "source": "amap_mcp"}]

    async def navigate(self, params: dict) -> list[dict]:
        destination = str(params.get("destination") or "")
        if not destination:
            return []

        city = str(params.get("city") or params.get("destination_city") or params.get("origin_city") or "")
        destination_city = str(params.get("destination_city") or city or "")
        destination_location = await self._resolve_place_location(destination, destination_city)
        if not destination_location:
            return []
        lon, lat = self._split_location(destination_location)
        if not lon or not lat:
            return []

        payload: dict[str, Any] = {
            "lon": lon,
            "lat": lat,
        }
        result = await self._call_with_fallback("maps_schema_navi", payload)
        if result is None:
            return []
        uri = self._extract_schema_uri(result)
        if not uri:
            return []
        return [{"title": "导航", "content": uri, "source": "amap_mcp"}]

    async def rag_search(self, query: str) -> list[dict]:
        if "天气" in query:
            city = self._extract_city(query)
            result = await self._call_with_fallback("maps_weather", {"city": city})
            if result is not None:
                weather = self._normalize_weather(result, city)
                if weather:
                    return weather

        result = await self._call_with_fallback("maps_text_search", {"keywords": query})
        if result is None:
            return await self._mock.rag_search(query)
        return [
            {
                "title": item.get("name", ""),
                "content": item.get("address", "") or item.get("type", ""),
                "source": "amap_mcp",
            }
            for item in self._normalize_pois(result)
        ] or await self._mock.rag_search(query)

    async def _route_with_mode(self, params: dict, *, mode: str, tool_name: str) -> list[dict]:
        origin = str(params.get("origin") or "")
        destination = str(params.get("destination") or "")
        if not origin or not destination:
            return []

        city = str(params.get("city") or params.get("origin_city") or params.get("destination_city") or "")
        origin_city = str(params.get("origin_city") or city or "")
        destination_city = str(params.get("destination_city") or city or "")
        resolved_origin = await self._resolve_place_location(origin, origin_city)
        resolved_destination = await self._resolve_place_location(destination, destination_city)
        payload: dict[str, Any] = {
            "origin": resolved_origin or origin,
            "destination": resolved_destination or destination,
        }
        if city:
            payload["city"] = city

        result = await self._call_with_fallback(tool_name, payload)
        if result is None:
            return []
        return self._normalize_route(result, origin, destination, mode)

    async def _resolve_place_location(self, place: str, city: str = "") -> str | None:
        if self._looks_like_location(place):
            return place
        geocoded = await self.geocode(place, city)
        if geocoded:
            return str(geocoded["location"])
        return None

    def _looks_like_location(self, value: str) -> bool:
        return bool(re.fullmatch(r"\s*\-?\d+(?:\.\d+)?\s*,\s*\-?\d+(?:\.\d+)?\s*", value))

    async def _call_with_fallback(self, tool_name: str, arguments: dict) -> Any | None:
        try:
            return await asyncio.wait_for(self.client(tool_name, arguments), timeout=self.timeout_seconds)
        except (asyncio.TimeoutError, Exception):
            return None

    def _normalize_pois(self, result: Any) -> list[dict]:
        pois = self._extract_list(result, ("pois", "data", "results"))
        normalized = []
        for item in pois:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "name": item.get("name") or item.get("title") or "",
                    "address": item.get("address") or "",
                    "location": item.get("location") or "",
                    "type": item.get("type") or "",
                    "source": "amap_mcp",
                }
            )
        return normalized

    def _normalize_route(self, result: Any, origin: str, destination: str, mode: str) -> list[dict]:
        route_items = self._extract_list(result, ("paths", "transits", "rides", "routes"))
        if not route_items and isinstance(result, dict):
            route = result.get("route")
            if isinstance(route, dict):
                route_items = self._extract_list(route, ("paths", "transits", "rides", "routes"))

        normalized = []
        for item in route_items:
            if not isinstance(item, dict):
                continue
            entry: dict[str, Any] = {
                "mode": mode,
                "from": origin,
                "to": destination,
                "duration_seconds": self._to_int(item.get("duration")),
                "source": "amap_mcp",
            }
            distance = item.get("distance") or item.get("dist")
            if distance is not None:
                entry["distance_meters"] = self._to_float(distance)
            cost = item.get("cost") or item.get("price")
            if cost is not None:
                entry["cost"] = self._to_float(cost)
            normalized.append(entry)
        return normalized

    def _normalize_weather(self, result: Any, city: str) -> list[dict]:
        forecasts = self._extract_list(result, ("forecasts", "lives", "data"))
        normalized = []
        for item in forecasts:
            if not isinstance(item, dict):
                continue
            weather = item.get("weather") or item.get("dayweather") or ""
            temperature = item.get("temperature") or item.get("daytemp") or ""
            normalized.append(
                {
                    "title": f"{item.get('city') or city}天气",
                    "content": f"{weather} {temperature}".strip(),
                    "source": "amap_mcp",
                }
            )
        return normalized

    def _extract_geocode_location(self, result: Any) -> str:
        if isinstance(result, dict):
            geocodes = result.get("geocodes")
            if isinstance(geocodes, list) and geocodes:
                first = geocodes[0]
                if isinstance(first, dict):
                    location = first.get("location")
                    if location:
                        return str(location)
            results = result.get("results")
            if isinstance(results, list) and results:
                first = results[0]
                if isinstance(first, dict):
                    location = first.get("location")
                    if location:
                        return str(location)
        locations = self._extract_list(result, ("locations", "data"))
        for item in locations:
            if isinstance(item, dict) and item.get("location"):
                return str(item["location"])
        if isinstance(result, dict) and result.get("location"):
            return str(result["location"])
        return ""

    def _extract_regeocode_address(self, result: Any) -> str:
        if isinstance(result, dict):
            regeocode = result.get("regeocode")
            if isinstance(regeocode, dict):
                formatted = regeocode.get("formatted_address")
                if formatted:
                    return str(formatted)
            if result.get("formatted_address"):
                return str(result["formatted_address"])
        return ""

    def _extract_schema_uri(self, result: Any) -> str:
        def _find_uri(text: str) -> str:
            match = re.search(r"((?:amapuri|amap|https?)://\S+)", text)
            if match:
                return match.group(1)
            return ""

        if isinstance(result, dict):
            text_value = result.get("text")
            if isinstance(text_value, str):
                found = _find_uri(text_value)
                if found:
                    return found
            for key in ("uri", "url", "link"):
                value = result.get(key)
                if isinstance(value, str) and value:
                    return value
            content = result.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        for key in ("text", "uri", "url"):
                            value = item.get(key)
                            if isinstance(value, str) and value:
                                return value
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    for key in ("uri", "url", "link", "text"):
                        value = item.get(key)
                        if isinstance(value, str) and value:
                            found = _find_uri(value)
                            return found or value
                elif isinstance(item, str) and item:
                    found = _find_uri(item)
                    return found or item
        if isinstance(result, str):
            found = _find_uri(result)
            return found or result
        text = self._normalize_mcp_result(result)
        if isinstance(text, dict):
            for key in ("uri", "url", "link", "text"):
                value = text.get(key)
                if isinstance(value, str) and value:
                    found = _find_uri(value)
                    return found or value
        if isinstance(text, str):
            found = _find_uri(text)
            return found or text
        return ""

    def _split_location(self, location: str) -> tuple[str, str]:
        parts = [part.strip() for part in str(location).split(",")]
        if len(parts) >= 2 and parts[0] and parts[1]:
            return parts[0], parts[1]
        return "", ""

    def _normalize_mcp_result(self, result: Any) -> Any:
        if result is None:
            return {}
        if isinstance(result, dict):
            content = result.get("content")
        else:
            content = getattr(result, "content", None)

        if not content:
            return result

        fragments: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)
            if text:
                fragments.append(str(text))

        if not fragments:
            return result

        text_payload = "\n".join(fragments).strip()
        try:
            return json.loads(text_payload)
        except json.JSONDecodeError:
            return {"text": text_payload}

    def _extract_list(self, result: Any, keys: tuple[str, ...]) -> list:
        if isinstance(result, list):
            return result
        if not isinstance(result, dict):
            return []
        for key in keys:
            value = result.get(key)
            if isinstance(value, list):
                return value
        return []

    def _extract_city(self, query: str) -> str:
        match = re.search(r"([\u4e00-\u9fa5]{2,8})(?:天气|气温|温度)", query)
        if match:
            return match.group(1)
        return query.replace("天气", "").strip() or "杭州"

    def _to_int(self, value: Any) -> int | None:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _to_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def is_available(self) -> bool:
        availability_check = getattr(self.client, "is_available", None)
        if availability_check is None:
            return True
        return bool(availability_check())
