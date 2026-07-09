"""OCR provider interface."""

from __future__ import annotations

from typing import Protocol

from aegis.vision.models import VisionElement


class OCRProvider(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def languages(self) -> list[str]:
        ...

    def recognize(
        self,
        image_path: str,
        region: dict | None = None,
    ) -> list[VisionElement]:
        ...

    def recognize_region(
        self,
        image_path: str,
        region: dict,
    ) -> list[VisionElement]:
        ...
