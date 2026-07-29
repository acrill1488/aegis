"""Authenticated, one-shot GBIP service for an Ubuntu AEGIS node."""

from __future__ import annotations

import hmac
import os
from collections.abc import Callable

from fastapi import Depends, FastAPI, Header, HTTPException

from aegis.config.services import GreenBoostConfig, get_greenboost_config
from aegis.greenboost.contracts import NodeReference, NodeScope, ResourceSnapshot
from aegis.greenboost.probes import (
    ComfyUIProbe,
    DockerProbe,
    EmbeddingProbe,
    HostProbe,
    NvidiaGpuProbe,
    OCRProbe,
    OllamaModelProbe,
    OllamaProbe,
    ResourceProbe,
)

SnapshotFactory = Callable[[], ResourceSnapshot]


def _authenticate(config: GreenBoostConfig, authorization: str | None) -> None:
    expected = os.environ.get(config.server.token_env)
    if not expected:
        raise HTTPException(status_code=503, detail={"type": "gbip.auth.unconfigured"})
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not supplied:
        raise HTTPException(status_code=401, detail={"type": "gbip.auth.missing"})
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail={"type": "gbip.auth.invalid"})


def _snapshot_factory(config: GreenBoostConfig) -> SnapshotFactory:
    node = NodeReference(id=config.server.node_id, scope=NodeScope.remote)

    def collect() -> ResourceSnapshot:
        # Deliberately one-shot: no polling, cache, reservation, or scheduler state.
        return ResourceProbe(
            (
                HostProbe(),
                NvidiaGpuProbe(),
                DockerProbe(),
                OllamaProbe(),
                OllamaModelProbe(),
                OCRProbe(),
                ComfyUIProbe(),
                EmbeddingProbe(),
            ),
            node=node,
        ).collect()

    return collect


def create_app(
    config: GreenBoostConfig | None = None,
    *,
    snapshot_factory: SnapshotFactory | None = None,
) -> FastAPI:
    settings = config or get_greenboost_config()
    collect = snapshot_factory or _snapshot_factory(settings)
    application = FastAPI(title="AEGIS GBIP Service", version="1")

    def auth(authorization: str | None = Header(default=None)) -> None:
        _authenticate(settings, authorization)

    @application.get("/v1/health", dependencies=[Depends(auth)])
    def health() -> ResourceSnapshot:
        return collect()

    @application.get("/v1/discover", dependencies=[Depends(auth)])
    def discover() -> dict[str, list[NodeReference]]:
        return {
            "nodes": [NodeReference(id=settings.server.node_id, scope=NodeScope.remote)]
        }

    @application.get("/v1/snapshot", dependencies=[Depends(auth)])
    def snapshot() -> ResourceSnapshot:
        return collect()

    return application


app = create_app()
