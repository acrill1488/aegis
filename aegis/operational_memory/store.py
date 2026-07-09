from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import OperationalExperience


class OperationalMemoryStore:
    """Durable JSON storage for operational execution experience."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> list[OperationalExperience]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        records: list[OperationalExperience] = []
        for item in data:
            if isinstance(item, dict):
                try:
                    records.append(OperationalExperience.from_dict(item))
                except (TypeError, ValueError):
                    continue
        return records

    def save(self, experiences: list[OperationalExperience]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(to_plain(experiences), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append(self, experience: OperationalExperience) -> OperationalExperience:
        experiences = self.load()
        experiences.append(experience)
        self.save(experiences)
        return experience

    def replace(self, experiences: list[OperationalExperience]) -> None:
        self.save(experiences)
