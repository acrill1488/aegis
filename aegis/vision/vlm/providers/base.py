"""Vision-language provider interface."""

from __future__ import annotations

from typing import Protocol


class VisionLanguageProvider(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def describe(self, image_path: str, prompt: str | None = None) -> dict:
        ...

    def locate(self, image_path: str, query: str) -> dict:
        ...

    def reason(self, image_path: str, question: str) -> dict:
        ...
