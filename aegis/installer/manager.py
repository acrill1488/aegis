from __future__ import annotations

import logging
import uuid
from typing import Any

import yaml

from .catalog import ManifestRegistry
from .errors import InstallerError, OperationError
from .executor import ActionExecutor
from .health import HealthChecker
from .models import (
    DiagnosticReport,
    InstallReport,
    InstalledPackage,
    PackageRef,
    RemoveReport,
    RollbackRecord,
    UpdateReport,
)
from .paths import InstallerPaths
from .resolver import DependencyResolver
from .state import InstalledState, RollbackStore


class PackageManager:
    """Public manifest-driven lifecycle API described by RFC-017 / RFC-004."""

    def __init__(self, *, paths: InstallerPaths | None = None, executor: ActionExecutor | None = None):
        self.paths = paths or InstallerPaths.resolve()
        self.registry = ManifestRegistry(self.paths.manifests)
        self.state = InstalledState(self.paths.installed)
        self.rollbacks = RollbackStore(self.paths.rollbacks)
        self.resolver = DependencyResolver(self.registry)
        self.executor = executor or ActionExecutor(self.paths)
        self.health = HealthChecker(self.registry, self.state, self.resolver)
        self._configure_logging()
        self.logger = logging.getLogger("aegis.installer")

    def install(self, package_ref: PackageRef | str, options: dict[str, Any] | None = None) -> InstallReport:
        ref = package_ref if isinstance(package_ref, PackageRef) else PackageRef(name=package_ref)
        manifest = self.registry.get(ref.name)
        if ref.version and ref.version != manifest.version:
            raise InstallerError(f"Requested {ref.name} {ref.version}, but registry provides {manifest.version}.")
        existing = self.state.get(manifest.id)
        digest = self.registry.digest(manifest)
        if existing and existing.version == manifest.version and existing.manifest_digest == digest:
            diagnostics = self.health.package(manifest)
            return InstallReport(success=diagnostics.ok, package_id=manifest.id, version=manifest.version, changed=False, diagnostics=diagnostics)

        self.logger.info("Install started: %s %s", manifest.id, manifest.version)
        completed_packages: list[str] = []
        try:
            for dependency_manifest in self.resolver.resolve(manifest):
                if dependency_manifest.id != manifest.id and self.state.get(dependency_manifest.id):
                    continue
                self._install_one(dependency_manifest)
                completed_packages.append(dependency_manifest.id)
            diagnostics = self.health.package(manifest)
            if not diagnostics.ok:
                raise OperationError(self._diagnostic_failure(manifest.id, diagnostics))
            installed = self.state.get(manifest.id)
            if installed:
                installed.health = "healthy"
                self.state.put(installed)
            self.logger.info("Install completed: %s", manifest.id)
            return InstallReport(
                success=True,
                package_id=manifest.id,
                version=manifest.version,
                changed=True,
                installed_items=completed_packages,
                registrations=[*[f"provider:{item}" for item in manifest.providers], *[f"model:{item}" for item in manifest.models], *[f"workflow:{item}" for item in manifest.workflows]],
                diagnostics=diagnostics,
            )
        except Exception as exc:
            self.logger.error("Install failed: %s: %s", manifest.id, exc)
            for component_id in reversed(completed_packages):
                self._rollback_install(component_id)
            if isinstance(exc, InstallerError):
                raise
            raise OperationError(f"Installation failed and was rolled back: {exc}") from exc

    def remove(self, package_id: str, options: dict[str, Any] | None = None) -> RemoveReport:
        installed = self.state.get(package_id)
        if installed is None:
            return RemoveReport(success=True, package_id=package_id, changed=False, diagnostics=self.diagnose())
        dependants = [item.component for item in self.state.list() if package_id in item.dependencies]
        if dependants:
            raise InstallerError(f"Cannot remove '{package_id}'; it is used by: {', '.join(dependants)}")
        manifest = self.registry.get(package_id)
        record = RollbackRecord(operation_id=uuid.uuid4().hex, package_id=package_id, previous_state=installed)
        completed = []
        try:
            for action in manifest.remove:
                self.executor.execute(action)
                completed.append(action)
            record.completed_actions = completed
            self.rollbacks.save(record)
            self.state.remove(package_id)
        except Exception as exc:
            for action in reversed(completed):
                self.executor.compensate(action)
            raise OperationError(f"Removal failed and was rolled back: {exc}") from exc
        return RemoveReport(success=True, package_id=package_id, changed=True, diagnostics=self.diagnose())

    def update(self, package_id: str | None = None, options: dict[str, Any] | None = None) -> UpdateReport:
        options = options or {}
        if not options.get("confirmed", False):
            raise InstallerError("Update requires explicit confirmation; no silent updates are allowed.")
        installed = self.state.list()
        if package_id:
            installed = [item for item in installed if item.component == package_id]
            if not installed:
                raise InstallerError(f"Component '{package_id}' is not installed.")
        report = UpdateReport(success=True)
        for current in installed:
            manifest = self.registry.get(current.component)
            digest = self.registry.digest(manifest)
            if current.version == manifest.version and current.manifest_digest == digest:
                report.unchanged.append(current.component)
                continue
            try:
                result = self.install(PackageRef(name=current.component))
                (report.updated if result.success else report.failed).append(current.component)
            except InstallerError:
                report.failed.append(current.component)
        report.success = not report.failed
        return report

    def list(self, filter: str | None = None) -> list[InstalledPackage]:
        items = self.state.list()
        if filter:
            needle = filter.casefold()
            items = [item for item in items if needle in item.component.casefold() or needle in item.status.casefold()]
        return items

    def diagnose(self, package_id: str | None = None) -> DiagnosticReport:
        return self.health.package(self.registry.get(package_id)) if package_id else self.health.system()

    def bootstrap(self) -> DiagnosticReport:
        self.paths.ensure()
        if not self.paths.services_config.exists():
            self.paths.services_config.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": 1,
                "server": {"host": "127.0.0.1", "scheme": "http"},
                "services": {
                    "ollama": {"port": 11434, "base_url": None},
                    "unlimited_ocr": {"port": 8190, "base_url": None},
                    "comfyui": {"port": 8188, "base_url": None},
                },
                "paths": {},
            }
            self.paths.services_config.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        if not self.paths.installed.exists():
            self.state._save([])
        return self.diagnose()

    def rollback(self, package_id: str | None = None) -> bool:
        latest = self.rollbacks.latest(package_id)
        if latest is None:
            raise InstallerError("No rollback record is available.")
        path, record = latest
        for action in reversed(record.completed_actions):
            self.executor.compensate(action)
        if record.previous_state:
            self.state.put(record.previous_state)
        else:
            self.state.remove(record.package_id)
        path.rename(path.with_suffix(".rolled-back.json"))
        return True

    def _install_one(self, manifest) -> None:
        self.resolver.assert_system_dependencies(manifest)
        previous = self.state.get(manifest.id)
        record = RollbackRecord(operation_id=uuid.uuid4().hex, package_id=manifest.id, previous_state=previous)
        completed = []
        try:
            for action in manifest.install:
                self.executor.execute(action)
                completed.append(action)
            record.completed_actions = completed
            self.rollbacks.save(record)
            self.state.put(InstalledPackage(
                component=manifest.id,
                version=manifest.version,
                source=manifest.source,
                status="installed",
                health="pending",
                dependencies=list(manifest.dependencies),
                manifest_digest=self.registry.digest(manifest),
            ))
        except Exception:
            for action in reversed(completed):
                self.executor.compensate(action)
            if previous:
                self.state.put(previous)
            else:
                self.state.remove(manifest.id)
            raise

    def _rollback_install(self, package_id: str) -> None:
        latest = self.rollbacks.latest(package_id)
        if latest:
            _, record = latest
            for action in reversed(record.completed_actions):
                try:
                    self.executor.compensate(action)
                except Exception as exc:
                    self.logger.error("Rollback action failed for %s: %s", package_id, exc)
            if record.previous_state:
                self.state.put(record.previous_state)
            else:
                self.state.remove(package_id)

    def _configure_logging(self) -> None:
        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger("aegis.installer")
        logger.setLevel(logging.INFO)
        target = str(self.paths.log.resolve())
        if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == target for handler in logger.handlers):
            logger.addHandler(logging.FileHandler(self.paths.log, encoding="utf-8"))

    @staticmethod
    def _diagnostic_failure(package_id: str, diagnostics: DiagnosticReport) -> str:
        details = "; ".join(f"{item.name}: {item.details}" for item in diagnostics.checks if not item.ok)
        return f"Health check failed for '{package_id}': {details}"
