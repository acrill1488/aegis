"""Transport-only BGE-M3 provider for Windows and other client nodes.

This module intentionally has no imports from FlagEmbedding, torch, or transformers.
"""

from __future__ import annotations

from dataclasses import replace

from aegis.embeddings.models import EmbeddingRequest, EmbeddingResult, EmbeddingVector
from aegis.providers.bge_m3.health import ProviderHealth
from aegis.remote.client import RemoteRuntimeClient
from aegis.remote.config import RemoteNodeConfig


class RemoteBGEM3Provider:
    id = "remote-bge-m3"

    def __init__(self, node: RemoteNodeConfig, *, connect_timeout: float = 5, read_timeout: float = 300):
        self.node = node
        self.client = RemoteRuntimeClient(node, connect_timeout=connect_timeout, read_timeout=read_timeout)

    def is_available(self) -> bool:
        return self.node.enabled and bool(self.node.token)

    def health(self) -> ProviderHealth:
        if not self.node.enabled:
            return ProviderHealth(status="disabled", message=f"Remote node {self.node.id} is disabled")
        if not self.node.token:
            return ProviderHealth(status="token missing", message=f"Set {self.node.token_env}")
        try:
            data = self.client.health()
            ready = data.get("status") == "healthy"
            return ProviderHealth(status="healthy" if ready else "not ready", available=ready,
                                  device="remote", metadata={"node_id": self.node.id})
        except Exception as exc:
            return ProviderHealth(status="unreachable", device="remote", message=str(exc),
                                  metadata={"node_id": self.node.id})

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        body = self.client.embed({
            "texts": request.texts, "provider": "bge-m3", "normalize": request.normalize,
            "batch_size": request.batch_size, "device": request.device, "metadata": request.metadata,
        })
        data = body["result"]
        vectors = [EmbeddingVector(**item) for item in data["vectors"]]
        result = EmbeddingResult(**{**data, "vectors": vectors})
        return replace(result, metadata={**result.metadata, "execution": "remote",
                                         "node_id": self.node.id, "request_id": body["request_id"]})
