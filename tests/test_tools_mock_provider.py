import pytest

from app.tools import MockProvider


@pytest.mark.asyncio
async def test_mock_provider_returns_transport_options():
    provider = MockProvider()
    options = await provider.search_transport({"origin": "上海", "destination": "杭州"})

    assert len(options) > 0
    assert options[0]["mode"] in {"flight", "train", "bus"}

