"""OCR provider registry."""

from __future__ import annotations

from collections.abc import Iterable

from .exceptions import OCRProviderNotFound
from .provider import OCRProvider, StubOCRProvider
from .providers import PaddleOCRProvider, UnlimitedOCRProvider


def provider_name(provider: OCRProvider) -> str:
    name = getattr(provider, "name")
    return str(name() if callable(name) else name)


class OCRRegistry:
    """Small provider registry for OCR Runtime providers."""

    def __init__(
        self,
        providers: Iterable[OCRProvider] | None = None,
        *,
        default_provider: str = "stub",
    ):
        self._providers: dict[str, OCRProvider] = {}
        default_providers = providers or [StubOCRProvider(), UnlimitedOCRProvider(), PaddleOCRProvider()]
        for provider in default_providers:
            self.register(provider)
        if providers is None and default_provider == "stub":
            unlimited = self._providers.get("unlimited")
            self._default_provider = "unlimited" if unlimited and unlimited.available() else "stub"
        else:
            self._default_provider = default_provider

    def register(self, provider: OCRProvider) -> OCRProvider:
        self._providers[provider_name(provider)] = provider
        return provider

    def provider(self, name: str | None = None) -> OCRProvider:
        provider_name = name or self._default_provider
        if provider_name == "unlimited-ocr":
            provider_name = "unlimited"
        provider = self._providers.get(provider_name)
        if provider is None:
            raise OCRProviderNotFound(f"OCR provider not found: {provider_name}")
        return provider

    def providers(self) -> list[OCRProvider]:
        return [self._providers[name] for name in sorted(self._providers)]

    def default(self) -> str:
        return self._default_provider

    def available(self) -> list[OCRProvider]:
        return [provider for provider in self.providers() if provider.available()]

    def has(self, name: str) -> bool:
        if name == "unlimited-ocr":
            name = "unlimited"
        return name in self._providers

    def set_default_provider(self, name: str) -> None:
        if name == "unlimited-ocr":
            name = "unlimited"
        if name not in self._providers:
            raise OCRProviderNotFound(f"OCR provider not found: {name}")
        self._default_provider = name

    def get(self, name: str | None = None) -> OCRProvider:
        return self.provider(name)

    def list(self) -> list[OCRProvider]:
        return self.providers()

    def default_provider(self) -> str:
        return self.default()


OCRProviderRegistry = OCRRegistry
