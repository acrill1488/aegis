"""Document provider interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from aegis.vision.document.models import DocumentExtraction


class DocumentProvider(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def supported_types(self) -> list[str]:
        ...

    def extract(self, path: str | Path) -> DocumentExtraction:
        ...
