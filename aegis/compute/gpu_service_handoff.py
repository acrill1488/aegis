"""Minimal GPU service handoff for mutually exclusive OCR/image services."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

DEFAULT_GPU_SERVICES_CONFIG_PATH = Path(r"F:\AI_WORKSPACE\compute\gpu_services.json")
DEFAULT_TASK_MAPPING = {
    "ocr.": "unlimited-ocr",
    "image.": "comfyui",
}

CommandRunner = Callable[[str, float], subprocess.CompletedProcess[str]]


@dataclass
class GPUServiceHandoffReport:
    enabled: bool
    task_type: str
    target_service: str = ""
    stopped_services: list[str] = field(default_factory=list)
    started_service: str = ""
    health_url: str = ""
    health_ok: bool = False
    warmup_url: str = ""
    warmup_ok: bool = False
    unloaded_services: list[str] = field(default_factory=list)
    skipped_reason: str = ""
    errors: list[str] = field(default_factory=list)


def select_service_for_task_type(task_type: str, mapping: dict[str, str] | None = None) -> str:
    """Resolve obvious task types without an LLM or Brain-specific logic."""
    normalized = str(task_type or "").lower()
    rules = mapping or DEFAULT_TASK_MAPPING
    for prefix, service in rules.items():
        if normalized.startswith(str(prefix).lower()):
            return str(service)
    return ""


class GPUServiceHandoff:
    """Small utility that prepares the single shared GPU for one target service."""

    def __init__(
        self,
        config_path: str | Path = DEFAULT_GPU_SERVICES_CONFIG_PATH,
        *,
        command_runner: CommandRunner | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.config_path = Path(config_path)
        self._command_runner = command_runner or self._run_command
        self._sleep = sleep

    def prepare_for_task(self, task_type: str) -> GPUServiceHandoffReport:
        config = self._load_config()
        mapping = {
            str(key): str(value)
            for key, value in dict(config.get("task_mapping") or DEFAULT_TASK_MAPPING).items()
        }
        target = select_service_for_task_type(task_type, mapping)
        report = GPUServiceHandoffReport(
            enabled=bool(config.get("enabled", False)),
            task_type=task_type,
            target_service=target,
        )
        if not target:
            report.skipped_reason = "no mapped GPU service"
            return report
        if not report.enabled:
            report.skipped_reason = "gpu service handoff disabled"
            return report

        services = dict(config.get("services") or {})
        target_config = dict(services.get(target) or {})
        if not target_config:
            report.errors.append(f"GPU service config not found: {target}")
            return report

        for service in self._conflicting_services(config, target, target_config):
            service_config = dict(services.get(service) or {})
            unload_url = str(service_config.get("unload_url") or "")
            if unload_url and self._post_service_action(unload_url, config, report, action=f"unload {service}"):
                report.unloaded_services.append(service)
            stop_command = str(service_config.get("stop_command") or "")
            if stop_command:
                self._run_checked(stop_command, config, report, action=f"stop {service}")
                report.stopped_services.append(service)

        self._wait_for_vram(config, target_config, report)

        start_command = str(target_config.get("start_command") or "")
        if start_command:
            self._run_checked(start_command, config, report, action=f"start {target}")
            report.started_service = target

        health_url = str(target_config.get("health_url") or "")
        report.health_url = health_url
        if health_url:
            report.health_ok = self._wait_for_health(health_url, config, report)
        warmup_url = str(target_config.get("warmup_url") or "")
        report.warmup_url = warmup_url
        if warmup_url and target_config.get("warmup_on_start", False):
            report.warmup_ok = self._post_warmup(warmup_url, config, report)
        return report

    def prepare_for_ocr(self) -> GPUServiceHandoffReport:
        return self.prepare_for_task("ocr.recognize")

    def prepare_for_image(self) -> GPUServiceHandoffReport:
        return self.prepare_for_task("image.generate")

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {"enabled": False, "task_mapping": DEFAULT_TASK_MAPPING, "services": {}}
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return {"enabled": False, "task_mapping": DEFAULT_TASK_MAPPING, "services": {}}
        return data if isinstance(data, dict) else {}

    def _conflicting_services(
        self,
        config: dict[str, Any],
        target: str,
        target_config: dict[str, Any],
    ) -> list[str]:
        conflicts = target_config.get("conflicting_services")
        if isinstance(conflicts, list):
            return [str(service) for service in conflicts if str(service) != target]
        shared_conflicts = dict(config.get("conflicting_services") or {})
        return [str(service) for service in shared_conflicts.get(target, []) if str(service) != target]

    def _wait_for_vram(
        self,
        config: dict[str, Any],
        target_config: dict[str, Any],
        report: GPUServiceHandoffReport,
    ) -> None:
        check_command = str(config.get("vram_check_command") or "")
        if not check_command:
            return
        minimum_mb = int(target_config.get("minimum_free_vram_mb") or config.get("minimum_free_vram_mb") or 0)
        if minimum_mb <= 0:
            return
        deadline = time.monotonic() + float(config.get("vram_wait_timeout_seconds", 60))
        while time.monotonic() < deadline:
            result = self._command_runner(check_command, float(config.get("command_timeout_seconds", 30)))
            if result.returncode == 0:
                try:
                    free_mb = int(str(result.stdout).strip().splitlines()[-1])
                except (IndexError, ValueError):
                    free_mb = 0
                if free_mb >= minimum_mb:
                    return
            self._sleep(float(config.get("poll_interval_seconds", 2)))
        report.errors.append(f"Timed out waiting for {minimum_mb} MB free VRAM")

    def _wait_for_health(
        self,
        health_url: str,
        config: dict[str, Any],
        report: GPUServiceHandoffReport,
    ) -> bool:
        deadline = time.monotonic() + float(config.get("health_timeout_seconds", 90))
        while time.monotonic() < deadline:
            try:
                with httpx.Client(timeout=5.0, trust_env=False) as client:
                    response = client.get(health_url)
                if response.status_code == 200:
                    return True
            except httpx.HTTPError as exc:
                last_error = str(exc)
            else:
                last_error = f"HTTP {response.status_code}"
            self._sleep(float(config.get("poll_interval_seconds", 2)))
        report.errors.append(f"Health check failed for {health_url}: {last_error}")
        return False

    def _post_warmup(
        self,
        warmup_url: str,
        config: dict[str, Any],
        report: GPUServiceHandoffReport,
    ) -> bool:
        try:
            with httpx.Client(timeout=float(config.get("warmup_timeout_seconds", 600)), trust_env=False) as client:
                response = client.post(warmup_url)
            if response.status_code < 400:
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("success", True):
                    return True
                report.errors.extend(str(error) for error in payload.get("errors") or [])
                return False
            report.errors.append(f"Warmup failed for {warmup_url}: HTTP {response.status_code}")
            return False
        except Exception as exc:
            report.errors.append(f"Warmup failed for {warmup_url}: {exc}")
            return False

    def _post_service_action(
        self,
        url: str,
        config: dict[str, Any],
        report: GPUServiceHandoffReport,
        *,
        action: str,
    ) -> bool:
        try:
            with httpx.Client(timeout=float(config.get("service_action_timeout_seconds", 60)), trust_env=False) as client:
                response = client.post(url)
            if response.status_code < 400:
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("success", True):
                    return True
                report.errors.extend(str(error) for error in payload.get("errors") or [])
            else:
                report.errors.append(f"Failed to {action}: HTTP {response.status_code}")
        except Exception as exc:
            report.errors.append(f"Failed to {action}: {exc}")
        return False

    def _run_checked(
        self,
        command: str,
        config: dict[str, Any],
        report: GPUServiceHandoffReport,
        *,
        action: str,
    ) -> None:
        result = self._command_runner(command, float(config.get("command_timeout_seconds", 60)))
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            report.errors.append(f"Failed to {action}: {detail}")

    def _run_command(self, command: str, timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
