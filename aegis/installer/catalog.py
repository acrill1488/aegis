from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import ValidationError

from .errors import ManifestError
from .models import PackageManifest


class ManifestRegistry:
    """Read-only package catalog backed by validated YAML manifests."""

    def __init__(self, root: Path):
        self.root = root

    def list(self) -> list[PackageManifest]:
        manifests: list[PackageManifest] = []
        if not self.root.exists():
            return manifests
        for path in sorted((*self.root.glob("*.yaml"), *self.root.glob("*.yml"))):
            manifests.append(self._load(path))
        ids = [item.id for item in manifests]
        duplicate = next((item for item in ids if ids.count(item) > 1), None)
        if duplicate:
            raise ManifestError(f"Duplicate component id in registry: {duplicate}")
        return manifests

    def get(self, component_id: str) -> PackageManifest:
        manifest = next((item for item in self.list() if item.id == component_id), None)
        if manifest is None:
            raise ManifestError(f"Component '{component_id}' was not found in the package registry.")
        return manifest

    def search(self, query: str = "") -> list[PackageManifest]:
        needle = query.casefold().strip()
        return [
            item for item in self.list()
            if not needle or needle in f"{item.id} {item.name} {item.description} {item.type}".casefold()
        ]

    @staticmethod
    def digest(manifest: PackageManifest) -> str:
        return hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()

    def _load(self, path: Path) -> PackageManifest:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
            return PackageManifest.model_validate(data)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise ManifestError(f"Invalid manifest '{path.name}': {exc}") from exc
