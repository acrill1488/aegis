"""Registry dedicated to embedding providers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .errors import EmbeddingError


class EmbeddingRegistry:
    def __init__(self, providers: Iterable[Any] | None = None, *, default_provider: str | None = None):
        self._providers: dict[str, Any] = {}
        if providers is None:
            from aegis.providers.bge_m3 import BGEM3Provider

            providers = [BGEM3Provider()]
        for provider in providers:
            self.register(provider)
        if default_provider is None:
            from aegis.providers.bge_m3.config import load_embedding_settings

            default_provider = load_embedding_settings()[0]
        self._default = default_provider

    def register(self, provider: Any) -> Any:
        self._providers[str(provider.id)] = provider
        return provider

    def get(self, provider_id: str) -> Any:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise EmbeddingError(f"Embedding provider not found: {provider_id}") from exc

    def list(self) -> list[Any]:
        return [self._providers[key] for key in sorted(self._providers)]

    def resolve(self, provider_id: str | None = None) -> Any:
        return self.get(provider_id or self._default)

    @property
    def default_provider(self) -> str:
        return self._default
