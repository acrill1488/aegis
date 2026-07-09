"""Image generation provider interface."""

from __future__ import annotations

from typing import Protocol

from aegis.image_generation.models import (
    ImageGenerationRequest,
    ImageGenerationResult,
)


class ImageGenerationProvider(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def capabilities(self) -> dict:
        ...

    def generate(
        self,
        request: ImageGenerationRequest,
    ) -> ImageGenerationResult:
        ...
