from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from aegis.config.services import GreenBoostConfig
from aegis.greenboost.contracts import NodeReference, NodeScope, ResourceSnapshot
from aegis.greenboost.server.app import create_app


def _config() -> GreenBoostConfig:
    return GreenBoostConfig(
        enabled=True,
        server={
            "enabled": True,
            "node_id": "ubuntu-primary",
            "host": "192.0.2.10",
            "port": 8091,
            "token_env": "TEST_GBIP_TOKEN",
        },
    )


def _snapshot() -> ResourceSnapshot:
    return ResourceSnapshot(
        timestamp=datetime(2026, 7, 29, tzinfo=timezone.utc),
        node=NodeReference(id="ubuntu-primary", scope=NodeScope.remote),
    )


def test_server_requires_bearer_and_exposes_only_read_endpoints(monkeypatch):
    monkeypatch.setenv("TEST_GBIP_TOKEN", "secret")
    client = TestClient(create_app(_config(), snapshot_factory=_snapshot))
    assert client.get("/v1/health").status_code == 401
    headers = {"Authorization": "Bearer secret"}
    assert client.get("/v1/health", headers=headers).status_code == 200
    assert (
        client.get("/v1/snapshot", headers=headers).json()["node"]["id"]
        == "ubuntu-primary"
    )
    assert client.get("/v1/discover", headers=headers).json() == {
        "nodes": [{"id": "ubuntu-primary", "scope": "remote"}]
    }
    assert client.post("/v1/reservations", headers=headers).status_code == 404


def test_server_refuses_to_operate_without_configured_secret(monkeypatch):
    monkeypatch.delenv("TEST_GBIP_TOKEN", raising=False)
    client = TestClient(create_app(_config(), snapshot_factory=_snapshot))
    assert (
        client.get("/v1/health", headers={"Authorization": "Bearer x"}).status_code
        == 503
    )
