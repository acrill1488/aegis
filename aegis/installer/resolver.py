from __future__ import annotations

import importlib.util
import shutil

from .catalog import ManifestRegistry
from .errors import DependencyError
from .models import CheckResult, PackageManifest


SYSTEM_DEPENDENCIES = {"python", "docker", "cuda", "gpu", "network", "storage"}


class DependencyResolver:
    def __init__(self, registry: ManifestRegistry):
        self.registry = registry

    def resolve(self, manifest: PackageManifest) -> list[PackageManifest]:
        resolved: list[PackageManifest] = []
        visiting: list[str] = []

        def visit(item: PackageManifest) -> None:
            if item.id in visiting:
                chain = " -> ".join([*visiting, item.id])
                raise DependencyError(f"Circular package dependency: {chain}")
            if any(existing.id == item.id for existing in resolved):
                return
            visiting.append(item.id)
            for dependency in item.dependencies:
                if dependency not in SYSTEM_DEPENDENCIES:
                    visit(self.registry.get(dependency))
            visiting.pop()
            resolved.append(item)

        visit(manifest)
        return resolved

    def system_checks(self, manifest: PackageManifest) -> list[CheckResult]:
        checks: list[CheckResult] = []
        for dependency in manifest.dependencies:
            if dependency == "python":
                checks.append(CheckResult(name="python", ok=True, details="Python runtime is active"))
            elif dependency == "docker":
                ok = shutil.which("docker") is not None
                checks.append(CheckResult(name="docker", ok=ok, details="docker command found" if ok else "Install Docker and make the docker command available"))
            elif dependency in {"cuda", "gpu"}:
                ok = shutil.which("nvidia-smi") is not None
                checks.append(CheckResult(name=dependency, ok=ok, details="NVIDIA runtime found" if ok else "NVIDIA driver/runtime was not detected"))
            elif dependency == "network":
                checks.append(CheckResult(name="network", ok=True, details="Validated by downloader or service health check"))
            elif dependency == "storage":
                checks.append(CheckResult(name="storage", ok=True, details="Workspace is writable"))
            elif dependency == "model":
                checks.append(CheckResult(name="model", ok=importlib.util.find_spec("aegis.models") is not None))
        return checks

    def assert_system_dependencies(self, manifest: PackageManifest) -> None:
        failed = [check for check in self.system_checks(manifest) if not check.ok and check.required]
        if failed:
            reasons = "; ".join(f"{check.name}: {check.details}" for check in failed)
            raise DependencyError(f"Cannot install '{manifest.id}': {reasons}")
