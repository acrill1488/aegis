"""Vision provider interfaces."""

from __future__ import annotations

from typing import Protocol

from aegis.vision.models import VisionSnapshot


class VisionProvider(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def capabilities(self) -> list[str]:
        ...

    def capture(self) -> dict:
        ...

    def analyze(self, image_path: str | None = None) -> VisionSnapshot:
        ...
