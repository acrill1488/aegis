"""Filesystem source for project knowledge files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegis.knowledge.parser import parse_document

from .base import KnowledgeSource


class FilesystemSource(KnowledgeSource):
    SUPPORTED_SUFFIXES = {".md", ".txt", ".json"}

    def scan(self) -> list[Path]:
        if self.path.is_file():
            return [self.path] if self._supported(self.path) else []
        if not self.path.exists():
            return []
        files = [
            path
            for path in self.path.rglob("*")
            if path.is_file() and self._supported(path)
        ]
        return sorted(files, key=lambda item: str(item).lower())

    def parse(self, path: str | Path | None = None) -> dict[str, Any]:
        target = Path(path) if path is not None else self.path
        return parse_document(target, self.load(target))

    def _supported(self, path: Path) -> bool:
        name = path.name.upper()
        return (
            path.suffix.lower() in self.SUPPORTED_SUFFIXES
            or name.startswith("README")
            or name.startswith("RFC")
        )
