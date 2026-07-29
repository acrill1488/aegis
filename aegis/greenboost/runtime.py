"""Resource orchestration adapter around the external GreenBoost project.

This module intentionally does not vendor or modify GreenBoost.  It translates
AEGIS task policy into service lifecycle actions and records GPU telemetry.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml
from PIL import Image

from aegis.config.services import get_greenboost_config

from .client import GreenBoostClient

DEFAULT_CONFIG = Path(r"F:\AI_WORKSPACE\compute\greenboost.yaml")
REPO_CONFIG = Path(__file__).resolve().parents[2] / "config" / "greenboost.yaml"


@dataclass
class GreenBoostSession:
    enabled: bool
    selected_profile: str
    attempts: list[dict[str, Any]] = field(default_factory=list)
    initial_free_vram_mb: int | None = None
    free_vram_before_inference_mb: int | None = None
    peak_vram_mb: int | None = None
    stopped_services: list[str] = field(default_factory=list)
    unloaded_models: list[str] = field(default_factory=list)
    original_image_size: list[int] | None = None
    effective_image_size: list[int] | None = None
    fallback_reason: str | None = None
    vram_stages: dict[str, Any] = field(default_factory=dict)
    _restore_services: list[str] = field(default_factory=list, repr=False)

    def metadata(self) -> dict[str, Any]:
        return {
            "greenboost_enabled": self.enabled,
            "selected_profile": self.selected_profile,
            "attempts": self.attempts,
            "initial_free_vram_mb": self.initial_free_vram_mb,
            "free_vram_before_inference_mb": self.free_vram_before_inference_mb,
            "peak_vram_mb": self.peak_vram_mb,
            "stopped_services": self.stopped_services,
            "unloaded_models": self.unloaded_models,
            "original_image_size": self.original_image_size,
            "effective_image_size": self.effective_image_size,
            "fallback_reason": self.fallback_reason,
            "vram_stages": self.vram_stages,
        }


class GreenBoostRuntime:
    """Apply a bounded AEGIS policy through external service interfaces."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        command_runner: Callable[[str, float], subprocess.CompletedProcess[str]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        configured = config_path or os.getenv("AEGIS_GREENBOOST_CONFIG")
        self.config_path = Path(configured) if configured else (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else REPO_CONFIG)
        self.config = self._load_config()
        self._run = command_runner or self._run_command
        self._sleep = sleep

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", False))

    def profile(self, name: str | None = None) -> dict[str, Any]:
        selected = name or str(self.config.get("default_profile", "ocr_rtx3050"))
        profiles = dict(self.config.get("profiles") or {})
        if selected not in profiles:
            raise KeyError(f"GreenBoost profile not found: {selected}")
        return {"name": selected, **dict(profiles[selected])}

    def snapshot(self) -> dict[str, Any]:
        gbip = get_greenboost_config()
        if gbip.enabled:
            with GreenBoostClient(gbip) as client:
                return client.snapshot().model_dump(mode="json")
        ssh_snapshot = self._snapshot_via_ssh()
        if ssh_snapshot:
            return ssh_snapshot
        command = str(self.config.get("gpu_snapshot_command") or "")
        if not command:
            return self._snapshot_from_ocr()
        result = self._run(command, float(self.config.get("command_timeout_seconds", 30)))
        if result.returncode != 0:
            fallback = self._snapshot_from_ocr()
            fallback["process_telemetry_error"] = result.stderr.strip() or result.stdout.strip()
            return fallback
        try:
            payload = json.loads(result.stdout.strip())
            return payload if isinstance(payload, dict) else {"available": False, "error": "invalid snapshot"}
        except json.JSONDecodeError:
            fallback = self._snapshot_from_ocr()
            fallback["process_telemetry_error"] = "GPU snapshot command did not return JSON"
            return fallback

    def _snapshot_via_ssh(self) -> dict[str, Any]:
        password = os.getenv("AEGIS_GREENBOOST_SSH_PASSWORD")
        server = dict(self.config.get("server") or {})
        if not password or not server.get("host"):
            return {}
        try:
            import paramiko

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                str(server["host"]),
                username=str(server.get("user") or "aegis"),
                password=password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
            gpu_cmd = "nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv,noheader,nounits | head -n1"
            _, stdout, _ = client.exec_command(gpu_cmd, timeout=15)
            gpu = [int(item.strip()) for item in stdout.read().decode().strip().split(",")]
            proc_cmd = "nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits 2>/dev/null || true"
            _, stdout, _ = client.exec_command(proc_cmd, timeout=15)
            processes = []
            for row in stdout.read().decode().splitlines():
                parts = [item.strip() for item in row.split(",")]
                if len(parts) >= 3:
                    processes.append({"pid": int(parts[0]), "name": parts[1], "used_vram_mb": int(parts[2])})
            _, stdout, _ = client.exec_command("git -C ~/greenboost rev-parse HEAD 2>/dev/null || true", timeout=15)
            sha = stdout.read().decode().strip()
            client.close()
            services: dict[str, int] = {}
            for process in processes:
                name = process["name"].lower()
                service = "unlimited-ocr" if "python" in name else "ollama" if "ollama" in name else "comfyui" if "comfy" in name else ""
                if service:
                    services[service] = services.get(service, 0) + process["used_vram_mb"]
            return {"available": True, "total_vram_mb": gpu[0], "used_vram_mb": gpu[1], "free_vram_mb": gpu[2], "cuda_processes": processes, "aegis_services": services, "greenboost_commit": sha}
        except Exception as exc:
            return {"available": False, "ssh_error": str(exc)}
    def doctor(self) -> dict[str, Any]:
        snap = self.snapshot()
        source = dict(self.config.get("upstream") or {})
        profile = self.profile()
        checks = {
            "config_exists": self.config_path.exists(),
            "upstream_pinned": bool(source.get("url") and source.get("commit")),
            "gpu_telemetry": bool(snap.get("available", snap.get("total_vram_mb") is not None)),
            "cuda_process_telemetry": not bool(snap.get("process_telemetry_error") or snap.get("ssh_error")),
            "upstream_commit_matches": not snap.get("greenboost_commit") or snap.get("greenboost_commit") == source.get("commit"),
            "profile_valid": all(key in profile for key in ("required_free_vram_mb", "gpu_memory_limit_gb", "max_image_side", "cpu_offload")),
        }
        return {"overall": "READY" if all(checks.values()) else "NOT READY", "checks": checks, "snapshot": snap, "profile": profile, "upstream": source}

    def plan(self, task: str) -> dict[str, Any]:
        if task != "ocr":
            raise ValueError(f"Unsupported GreenBoost task: {task}")
        p = self.profile()
        return {
            "task": task,
            "profile": p["name"],
            "required_free_vram_mb": p["required_free_vram_mb"],
            "gpu_memory_limit_gb": p["gpu_memory_limit_gb"],
            "cpu_offload": p["cpu_offload"],
            "attempts": list(p.get("retry_policy") or []),
            "stoppable_services": list(p.get("stoppable_services") or []),
            "unloadable_ollama_models": list(p.get("unloadable_ollama_models") or []),
        }

    def begin_ocr(self, source: str | Path, profile_name: str | None = None) -> GreenBoostSession:
        p = self.profile(profile_name)
        session = GreenBoostSession(enabled=True, selected_profile=p["name"])
        with Image.open(source) as image:
            session.original_image_size = [image.width, image.height]
        initial = self.snapshot()
        session.vram_stages["initial"] = initial
        session.initial_free_vram_mb = self._free(initial)
        try:
            self._unload_ocr_state()
            self._unload_allowed_ollama(p, session)
            for service in p.get("stoppable_services") or []:
                if self._free(self.snapshot()) >= int(p["required_free_vram_mb"]):
                    break
                if self._service_running(str(service)) and self._service_action(str(service), "stop"):
                    session.stopped_services.append(str(service))
                    session._restore_services.append(str(service))
            final = self._wait_for_free(int(p["required_free_vram_mb"]))
            session.vram_stages["preflight_complete"] = final
            session.free_vram_before_inference_mb = self._free(final)
            if session.free_vram_before_inference_mb < int(p["required_free_vram_mb"]):
                raise RuntimeError(
                    f"GreenBoost preflight requires {p['required_free_vram_mb']} MB free VRAM; "
                    f"only {session.free_vram_before_inference_mb} MB available"
                )
        except Exception:
            if bool(p.get("restore_stopped_services", True)):
                for service in reversed(session._restore_services):
                    self._service_action(service, "start")
            raise
        return session

    def attempts(self, profile_name: str | None = None) -> list[dict[str, Any]]:
        p = self.profile(profile_name)
        policy = list(p.get("retry_policy") or [])
        return policy or [{"name": "normal", "max_image_side": int(p["max_image_side"])}]

    def reset_between_attempts(self, session: GreenBoostSession, reason: str) -> None:
        session.fallback_reason = reason
        self._unload_ocr_state()
        snap = self._wait_for_free(int(self.profile(session.selected_profile)["required_free_vram_mb"]))
        session.vram_stages[f"before_attempt_{len(session.attempts) + 1}"] = snap

    def finish(self, session: GreenBoostSession) -> None:
        info = self._get_json(self._service_url("unlimited-ocr", "info_url"))
        if info:
            session.vram_stages["ocr_service"] = info.get("vram_stages", {})
            peak = info.get("last_inference_peak_vram_mb")
            session.peak_vram_mb = int(peak) if peak is not None else None
        session.vram_stages["final"] = self.snapshot()
        if bool(self.profile(session.selected_profile).get("restore_stopped_services", True)):
            for service in reversed(session._restore_services):
                self._service_action(service, "start")

    def _unload_allowed_ollama(self, profile: dict[str, Any], session: GreenBoostSession) -> None:
        base = str(self.config.get("ollama_base_url") or "").rstrip("/")
        if not base:
            return
        running = self._get_json(f"{base}/api/ps").get("models", [])
        allowed = set(str(x) for x in profile.get("unloadable_ollama_models") or [])
        for item in running:
            name = str(item.get("name") or item.get("model") or "")
            if name and ("*" in allowed or name in allowed):
                try:
                    with httpx.Client(timeout=30, trust_env=False) as client:
                        response = client.post(f"{base}/api/generate", json={"model": name, "keep_alive": 0})
                    if response.status_code < 400:
                        session.unloaded_models.append(name)
                except httpx.HTTPError:
                    pass

    def _unload_ocr_state(self) -> None:
        url = self._service_url("unlimited-ocr", "unload_url")
        if url:
            try:
                with httpx.Client(timeout=60, trust_env=False) as client:
                    client.post(url)
            except httpx.HTTPError:
                pass

    def _service_running(self, service: str) -> bool:
        url = self._service_url(service, "health_url")
        if not url:
            return False
        try:
            with httpx.Client(timeout=5, trust_env=False) as client:
                return client.get(url).status_code < 500
        except httpx.HTTPError:
            return False

    def _service_action(self, service: str, action: str) -> bool:
        cfg = dict((self.config.get("services") or {}).get(service) or {})
        command = str(cfg.get(f"{action}_command") or "")
        if not command:
            return False
        result = self._run(command, float(self.config.get("command_timeout_seconds", 60)))
        return result.returncode == 0

    def _service_url(self, service: str, key: str) -> str:
        return str(((self.config.get("services") or {}).get(service) or {}).get(key) or "")

    def _wait_for_free(self, required: int) -> dict[str, Any]:
        deadline = time.monotonic() + float(self.config.get("vram_wait_timeout_seconds", 90))
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.snapshot()
            if self._free(last) >= required:
                return last
            self._sleep(float(self.config.get("poll_interval_seconds", 2)))
        return last

    def _snapshot_from_ocr(self) -> dict[str, Any]:
        data = self._get_json(self._service_url("unlimited-ocr", "info_url"))
        return {
            "available": bool(data),
            "total_vram_mb": data.get("gpu_total_mb", 0),
            "used_vram_mb": max(0, int(data.get("gpu_total_mb", 0)) - int(data.get("gpu_free_mb", 0))),
            "free_vram_mb": data.get("gpu_free_mb", 0),
            "cuda_processes": [],
            "aegis_services": {},
        }

    @staticmethod
    def _free(snapshot: dict[str, Any]) -> int:
        return int(snapshot.get("free_vram_mb") or 0)

    @staticmethod
    def _get_json(url: str) -> dict[str, Any]:
        if not url:
            return {}
        try:
            with httpx.Client(timeout=10, trust_env=False) as client:
                response = client.get(url)
            return response.json() if response.status_code < 400 else {}
        except (httpx.HTTPError, ValueError):
            return {}

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _run_command(command: str, timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], capture_output=True, text=True, timeout=timeout, check=False)
