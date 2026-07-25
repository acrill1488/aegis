"""FastAPI application for the AEGIS remote embedding runtime."""

from __future__ import annotations

import hmac
import os
import platform
import socket
import sys
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from aegis.embeddings import EmbeddingRequest, EmbeddingRuntime
from aegis.remote import PROTOCOL_VERSION

_STARTED = time.monotonic()


class EmbeddingPayload(BaseModel):
    texts: str | list[str]
    provider: str | None = None
    normalize: bool | None = None
    batch_size: int | None = Field(default=None, gt=0)
    device: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RemoteRequest(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    operation: str = "embeddings.embed"
    payload: EmbeddingPayload
    metadata: dict[str, Any] = Field(default_factory=dict)


def _authenticate(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("AEGIS_REMOTE_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail={"type": "remote.auth.unconfigured"})
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"type": "remote.auth.missing"})
    if not hmac.compare_digest(authorization[7:], expected):
        raise HTTPException(status_code=401, detail={"type": "remote.auth.invalid"})


def _runtime() -> EmbeddingRuntime:
    return EmbeddingRuntime()


def create_app() -> FastAPI:
    application = FastAPI(title="AEGIS Remote Runtime", version="1")

    @application.get("/v1/health")
    def health() -> dict[str, Any]:
        # Deliberately does not construct EmbeddingRuntime: health must never load a model.
        return {
            "service": "aegis-remote-runtime",
            "protocol_version": PROTOCOL_VERSION,
            "status": "healthy",
            "node_id": os.environ.get("AEGIS_REMOTE_NODE_ID", "ubuntu-primary"),
            "hostname": socket.gethostname(),
            "platform": platform.system().lower(),
            "python_version": sys.version.split()[0],
            "uptime_seconds": round(time.monotonic() - _STARTED, 3),
            "providers": ["bge-m3"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @application.get("/v1/version")
    def version() -> dict[str, str]:
        return {"service": "aegis-remote-runtime", "protocol_version": PROTOCOL_VERSION}

    @application.get("/v1/node", dependencies=[Depends(_authenticate)])
    def node() -> dict[str, Any]:
        return {"id": os.environ.get("AEGIS_REMOTE_NODE_ID", "ubuntu-primary"),
                "service": "aegis-remote-runtime", "protocol_version": PROTOCOL_VERSION}

    @application.get("/v1/providers", dependencies=[Depends(_authenticate)])
    def providers(runtime: EmbeddingRuntime = Depends(_runtime)) -> dict[str, Any]:
        return {"providers": runtime.providers()}

    @application.post("/v1/embeddings", dependencies=[Depends(_authenticate)])
    def embeddings(request: RemoteRequest, runtime: EmbeddingRuntime = Depends(_runtime)) -> dict[str, Any]:
        if request.protocol_version != PROTOCOL_VERSION:
            raise HTTPException(status_code=409, detail={"type": "remote.protocol.mismatch"})
        payload = request.payload
        result = runtime.embed(EmbeddingRequest(**payload.model_dump(), execution="local"))
        return {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": request.request_id,
            "success": True,
            "result": asdict(result),
            "errors": [],
            "warnings": result.warnings,
            "metadata": {"node_id": os.environ.get("AEGIS_REMOTE_NODE_ID", "ubuntu-primary")},
        }

    return application


app = create_app()
