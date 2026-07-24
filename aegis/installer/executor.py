from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Callable

from .errors import OperationError
from .models import Action
from .paths import InstallerPaths


class ActionExecutor:
    def __init__(self, paths: InstallerPaths, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run):
        self.paths = paths
        self.runner = runner
        self.logger = logging.getLogger("aegis.installer")

    def execute(self, action: Action) -> None:
        self.logger.info("Action started: %s", action.type)
        if action.type == "noop":
            return
        if action.type == "directory":
            self._resolve(action.path).mkdir(parents=True, exist_ok=True)
            return
        if action.type == "docker_compose":
            compose = self._resolve(action.path)
            operation = action.operation or "up"
            command = ["docker", "compose", "-f", str(compose)]
            command += ["up", "-d"] if operation == "up" else [operation]
            self._run(command)
            return
        if action.type == "command":
            if not action.command:
                raise OperationError("Manifest command action must define command arguments.")
            self._run([self._expand(part) for part in action.command])
            return
        if action.type == "config":
            self._write_config(action)
            return
        raise OperationError(f"Unsupported action type: {action.type}")

    def compensate(self, action: Action) -> None:
        if action.type == "docker_compose" and (action.operation or "up") == "up":
            self.execute(action.model_copy(update={"operation": "down"}))
        elif action.type == "docker_compose" and action.operation == "down":
            self.execute(action.model_copy(update={"operation": "up"}))

    def _run(self, command: list[str]) -> None:
        try:
            result = self.runner(command, check=False, capture_output=True, text=True)
        except OSError as exc:
            raise OperationError(f"Could not run '{command[0]}': {exc}") from exc
        if result.returncode:
            details = (result.stderr or result.stdout or "unknown error").strip()
            raise OperationError(f"Command '{command[0]}' failed: {details}")

    def _write_config(self, action: Action) -> None:
        path = self._resolve(action.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return
        path.write_text(json.dumps(action.values, ensure_ascii=False, indent=2), encoding="utf-8")

    def _resolve(self, value: str | None) -> Path:
        if not value:
            raise OperationError("Manifest action requires a path.")
        expanded = Path(self._expand(value))
        return expanded if expanded.is_absolute() else Path.cwd() / expanded

    def _expand(self, value: str) -> str:
        replacements = {
            "${workspace}": str(self.paths.workspace),
            "${state_dir}": str(self.paths.state_dir),
            "${services_config}": str(self.paths.services_config),
            "${project_root}": str(Path(__file__).resolve().parents[2]),
        }
        for token, replacement in replacements.items():
            value = value.replace(token, replacement)
        if "${" in value:
            raise OperationError(f"Unknown path token in manifest: {value}")
        return value
