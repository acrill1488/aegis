"""Base interface for local knowledge sources."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class KnowledgeSource:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def scan(self) -> list[Path]:
        raise NotImplementedError

    def load(self, path: str | Path | None = None) -> str:
        target = Path(path) if path is not None else self.path
        return target.read_text(encoding="utf-8", errors="replace")

    def parse(self, path: str | Path | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def metadata(self, path: str | Path | None = None) -> dict[str, Any]:
        target = Path(path) if path is not None else self.path
        stat = target.stat()
        return {
            "path": str(target),
            "name": target.name,
            "suffix": target.suffix.lower(),
            "size": stat.st_size,
            "modified_at": stat.st_mtime,
        }
