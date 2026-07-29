from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import json

import httpx
import pytest

from aegis.config.services import GreenBoostConfig
from aegis.greenboost.client import AsyncGreenBoostClient, GreenBoostClient
from aegis.greenboost.contracts import (
    NodeReference,
    NodeScope,
    ResourceRequest,
    ResourceReservation,
    ResourceSnapshot,
)
from aegis.greenboost.errors import ProtocolError
from aegis.greenboost.transport import AsyncHTTPTransport, HTTPTransport


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
NODE = {"id": "node-1", "scope": "remote"}
SNAPSHOT = {"timestamp": NOW.isoformat(), "node": NODE}
RESERVATION = {
    "reservation_id": "r-1",
    "execution_id": "e-1",
    "node": NODE,
    "resources": {},
    "state": "active",
    "created_at": NOW.isoformat(),
    "owner": "aegis",
}


def _client(handler):
    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://greenboost.test"
    )
    transport = HTTPTransport(
        base_url="http://greenboost.test",
        api_key=None,
        timeout=httpx.Timeout(1),
        client=http,
    )
    return GreenBoostClient(
        GreenBoostConfig(base_url="http://greenboost.test"), transport=transport
    )


def test_discover_and_snapshot_are_typed():
    def handler(request):
        return httpx.Response(
            200,
            json={"nodes": [NODE]}
            if request.url.path.endswith("discover")
            else SNAPSHOT,
        )

    client = _client(handler)
    assert client.discover() == (NodeReference(id="node-1", scope=NodeScope.remote),)
    assert isinstance(client.snapshot(), ResourceSnapshot)


def test_reserve_serializes_existing_contract():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=RESERVATION)

    request = ResourceRequest(
        execution_id="e-1",
        capability="ocr",
        node=NodeReference(id="node-1", scope="remote"),
    )
    result = _client(handler).reserve(request)
    assert isinstance(result, ResourceReservation)
    assert seen["execution_id"] == "e-1"


def test_invalid_model_is_protocol_error():
    with pytest.raises(ProtocolError):
        _client(lambda request: httpx.Response(200, json={})).snapshot()


def test_async_client_uses_the_same_typed_contract():
    async def run():
        http = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=SNAPSHOT)
            ),
            base_url="http://greenboost.test",
        )
        transport = AsyncHTTPTransport(
            base_url="http://greenboost.test",
            api_key=None,
            timeout=httpx.Timeout(1),
            client=http,
        )
        client = AsyncGreenBoostClient(
            GreenBoostConfig(base_url="http://greenboost.test"), transport=transport
        )
        assert isinstance(await client.health(), ResourceSnapshot)
        await http.aclose()

    asyncio.run(run())
