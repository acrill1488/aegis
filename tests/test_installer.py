from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegis.installer.errors import InstallerError, OperationError
from aegis.installer.manager import PackageManager
from aegis.installer.models import Action
from aegis.installer.paths import InstallerPaths


class FakeExecutor:
    def __init__(self, fail_on: str | None = None):
        self.fail_on = fail_on
        self.executed: list[Action] = []
        self.compensated: list[Action] = []

    def execute(self, action: Action) -> None:
        if self.fail_on is not None and action.operation == self.fail_on:
            raise OperationError("simulated operation failure")
        self.executed.append(action)

    def compensate(self, action: Action) -> None:
        self.compensated.append(action)


def make_paths(tmp_path: Path) -> InstallerPaths:
    workspace = tmp_path / "workspace"
    state = tmp_path / "state"
    return InstallerPaths(
        workspace=workspace,
        state_dir=state,
        manifests=tmp_path / "manifests",
        installed=state / "installed.json",
        rollbacks=state / "rollbacks",
        log=state / "installer.log",
        services_config=workspace / "config" / "services.yaml",
    )


def write_manifest(paths: InstallerPaths, component_id: str, *, dependencies=None, install=None, remove=None) -> None:
    paths.manifests.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "id": component_id,
        "name": component_id.title(),
        "type": "service",
        "version": "1.0.0",
        "dependencies": dependencies or [],
        "healthcheck": {"type": "none"},
        "install": install or [{"type": "noop"}],
        "remove": remove or [{"type": "noop"}],
        "source": "test",
        "permissions": [],
    }
    (paths.manifests / f"{component_id}.yaml").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_install_is_idempotent_and_resolves_package_dependencies(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    write_manifest(paths, "base")
    write_manifest(paths, "feature", dependencies=["base"])
    executor = FakeExecutor()
    manager = PackageManager(paths=paths, executor=executor)  # type: ignore[arg-type]

    first = manager.install("feature")
    second = manager.install("feature")

    assert first.success and first.changed
    assert first.installed_items == ["base", "feature"]
    assert second.success and not second.changed
    assert [item.component for item in manager.list()] == ["base", "feature"]
    assert len(executor.executed) == 2


def test_failed_install_rolls_back_all_completed_dependencies(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    write_manifest(paths, "base")
    write_manifest(paths, "feature", dependencies=["base"], install=[{"type": "noop", "operation": "fail"}])
    executor = FakeExecutor(fail_on="fail")
    manager = PackageManager(paths=paths, executor=executor)  # type: ignore[arg-type]

    with pytest.raises(OperationError, match="simulated operation failure"):
        manager.install("feature")

    assert manager.list() == []
    assert len(executor.compensated) == 1


def test_remove_protects_shared_dependencies(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    write_manifest(paths, "base")
    write_manifest(paths, "feature", dependencies=["base"])
    manager = PackageManager(paths=paths, executor=FakeExecutor())  # type: ignore[arg-type]
    manager.install("feature")

    with pytest.raises(InstallerError, match="used by: feature"):
        manager.remove("base")


def test_update_requires_explicit_confirmation(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    write_manifest(paths, "feature")
    manager = PackageManager(paths=paths, executor=FakeExecutor())  # type: ignore[arg-type]
    manager.install("feature")

    with pytest.raises(InstallerError, match="explicit confirmation"):
        manager.update()


def test_bootstrap_creates_valid_configuration_and_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = make_paths(tmp_path)
    paths.manifests.mkdir(parents=True)
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(paths.services_config))
    manager = PackageManager(paths=paths, executor=FakeExecutor())  # type: ignore[arg-type]

    report = manager.bootstrap()

    assert report.ok
    assert paths.services_config.exists()
    assert paths.installed.exists()
