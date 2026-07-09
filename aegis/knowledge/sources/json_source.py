"""JSON knowledge source."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegis.knowledge.parser import parse_json

from .base import KnowledgeSource


class JsonSource(KnowledgeSource):
    def scan(self) -> list[Path]:
        return [self.path] if self.path.is_file() else []

    def parse(self, path: str | Path | None = None) -> dict[str, Any]:
        target = Path(path) if path is not None else self.path
        return parse_json(self.load(target), fallback_title=target.stem)
