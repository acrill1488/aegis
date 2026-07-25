"""HTTPX client for the versioned AEGIS remote runtime protocol."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from . import PROTOCOL_VERSION
from .config import RemoteNodeConfig


class RemoteRuntimeClient:
    def __init__(self, node: RemoteNodeConfig, *, connect_timeout: float = 5, read_timeout: float = 300):
        self.node = node
        self.timeout = httpx.Timeout(read_timeout, connect=connect_timeout)

    def _headers(self) -> dict[str, str]:
        if not self.node.token:
            raise RuntimeError(f"Remote token environment variable is not set: {self.node.token_env}")
        return {"Authorization": f"Bearer {self.node.token}"}

    def health(self) -> dict[str, Any]:
        response = httpx.get(f"{self.node.base_url}/v1/health", timeout=self.timeout, trust_env=False)
        response.raise_for_status()
        return response.json()

    def providers(self) -> dict[str, Any]:
        response = httpx.get(
            f"{self.node.base_url}/v1/providers", headers=self._headers(),
            timeout=self.timeout, trust_env=False,
        )
        response.raise_for_status()
        return response.json()

    def embed(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        response = httpx.post(
            f"{self.node.base_url}/v1/embeddings", headers=self._headers(), timeout=self.timeout,
            trust_env=False, json={"protocol_version": PROTOCOL_VERSION, "request_id": request_id,
                                   "operation": "embeddings.embed", "payload": payload, "metadata": {}},
        )
        response.raise_for_status()
        body = response.json()
        if body.get("protocol_version") != PROTOCOL_VERSION or body.get("request_id") != request_id:
            raise RuntimeError("Remote runtime returned an invalid protocol response")
        return body

