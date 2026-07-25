"""Provider-neutral embedding orchestration."""

from __future__ import annotations

from .errors import EmbeddingValidationError
from .models import EmbeddingRequest, EmbeddingResult
from .registry import EmbeddingRegistry


class EmbeddingRuntime:
    def __init__(self, registry: EmbeddingRegistry | None = None, *, max_texts_per_request: int | None = None):
        self.registry = registry or EmbeddingRegistry()
        if max_texts_per_request is None:
            from aegis.providers.bge_m3.config import load_embedding_settings

            max_texts_per_request = load_embedding_settings()[1]
        self.max_texts_per_request = max_texts_per_request

    def embed(self, request: EmbeddingRequest | str | list[str]) -> EmbeddingResult:
        if not isinstance(request, EmbeddingRequest):
            request = EmbeddingRequest(texts=request)
        texts = self._validate_texts(request.texts)
        normalized = EmbeddingRequest(
            texts=texts,
            provider=request.provider,
            normalize=request.normalize,
            batch_size=request.batch_size,
            device=request.device,
            metadata=dict(request.metadata),
            execution=request.execution,
            node=request.node,
        )
        from aegis.remote.config import load_embedding_execution

        configured_execution, configured_node = load_embedding_execution()
        execution = request.execution or configured_execution
        node = request.node or configured_node
        if execution == "local":
            return self.registry.resolve(request.provider).embed(normalized)
        if execution == "remote":
            return self.registry.remote(node).embed(normalized)
        if execution != "auto":
            raise EmbeddingValidationError("execution must be one of: local, remote, auto")
        try:
            remote = self.registry.remote(node)
            remote_health = remote.health()
            if remote_health.available and remote_health.status == "healthy":
                return remote.embed(normalized)
            reason = remote_health.message or remote_health.status
        except Exception as exc:
            reason = str(exc)
        local = self.registry.resolve(request.provider)
        local_health = local.health()
        if not local_health.available:
            raise EmbeddingValidationError(
                f"remote node is unavailable ({reason}) and local provider is not ready"
            )
        result = local.embed(normalized)
        from dataclasses import replace

        return replace(result, warnings=[*result.warnings, f"Remote fallback to local: {reason}"],
                       metadata={**result.metadata, "execution": "local", "fallback_reason": reason})

    def providers(self) -> list[dict]:
        return [
            {
                "id": provider.id,
                "available": provider.is_available(),
                "default": provider.id == self.registry.default_provider,
                **provider.health().as_dict(),
            }
            for provider in self.registry.list()
        ]

    def _validate_texts(self, value: str | list[str]) -> list[str]:
        texts = [value] if isinstance(value, str) else value
        if not isinstance(texts, list) or not texts:
            raise EmbeddingValidationError("texts must contain at least one string")
        if len(texts) > self.max_texts_per_request:
            raise EmbeddingValidationError(
                f"texts exceeds max_texts_per_request ({self.max_texts_per_request})"
            )
        if any(not isinstance(text, str) for text in texts):
            raise EmbeddingValidationError("every text must be a string")
        if any(not text.strip() for text in texts):
            raise EmbeddingValidationError("texts must not contain empty or whitespace-only strings")
        return list(texts)
