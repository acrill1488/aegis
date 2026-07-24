from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .errors import InstallerError
from .models import InstalledPackage, RollbackRecord


class InstalledState:
    """Installed-state journal; it is not a provider or capability registry."""

    def __init__(self, path: Path):
        self.path = path

    def list(self) -> list[InstalledPackage]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
            return [InstalledPackage.model_validate(item) for item in payload.get("packages", [])]
        except (OSError, ValueError, TypeError) as exc:
            raise InstallerError(f"Installed-state database is invalid: {self.path}: {exc}") from exc

    def get(self, component_id: str) -> InstalledPackage | None:
        return next((item for item in self.list() if item.component == component_id), None)

    def put(self, package: InstalledPackage) -> None:
        packages = {item.component: item for item in self.list()}
        packages[package.component] = package
        self._save(list(packages.values()))

    def remove(self, component_id: str) -> None:
        self._save([item for item in self.list() if item.component != component_id])

    def _save(self, packages: list[InstalledPackage]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "packages": [item.model_dump() for item in sorted(packages, key=lambda x: x.component)]}
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix="installed-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


class RollbackStore:
    def __init__(self, root: Path):
        self.root = root

    def save(self, record: RollbackRecord) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{record.operation_id}.json"
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return path

    def latest(self, package_id: str | None = None) -> tuple[Path, RollbackRecord] | None:
        candidates = sorted(self.root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in candidates:
            record = RollbackRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if package_id is None or record.package_id == package_id:
                return path, record
        return None
