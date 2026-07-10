"""ComfyUI image generation provider."""

from __future__ import annotations

import json
import ipaddress
import platform
import socket
import subprocess
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx
from PIL import Image

from aegis.image_generation.models import (
    ImageGenerationRequest,
    ImageGenerationResult,
)

CONFIG_PATH = Path(r"F:\AI_WORKSPACE\image_generation\comfyui.json")
DEFAULT_BASE_URL = "http://192.168.1.7:8188"
DEFAULT_WORKFLOW_PATH = Path(r"F:\AI_WORKSPACE\image_generation\workflows\default.json")
DEFAULT_OUTPUT_DIR = Path(r"F:\AI_WORKSPACE\images\generated")
DEFAULT_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 0.5

EventPublisher = Callable[[str, dict[str, Any]], None]


def create_comfyui_http_client(base_url: str, timeout: float = 10.0) -> httpx.Client:
    """Create an HTTP client with proxy environment disabled only for local/LAN ComfyUI."""
    return httpx.Client(timeout=timeout, trust_env=not _is_local_or_lan_url(base_url))


def _is_local_or_lan_url(base_url: str) -> bool:
    host = urlparse(base_url).hostname or ""
    if host.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


@dataclass
class DoctorCheck:
    name: str
    status: str
    detail: str = ""
    elapsed_ms: float | None = None
    error_type: str = ""
    status_code: int | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class DoctorReport:
    base_url: str
    backend_url: str = ""
    proxy: str = "unknown"
    comfyui_version: str = "unknown"
    checks: list[DoctorCheck] = field(default_factory=list)
    reason: str = ""
    overall_status: str = "NOT READY"


class ComfyUIProvider:
    """Provider adapter for ComfyUI's HTTP API.

    The adapter treats the ComfyUI workflow as the model-specific boundary:
    AEGIS only patches common generation inputs and never hard-codes a model,
    checkpoint, sampler, or custom node.
    """

    name = "comfyui"

    def __init__(
        self,
        config_path: Path | str = CONFIG_PATH,
        event_publisher: EventPublisher | None = None,
    ):
        self.config_path = Path(config_path)
        self._event_publisher = event_publisher

    def available(self) -> bool:
        config = self._load_config()
        workflow_path = Path(config["workflow_path"])
        if not workflow_path.exists():
            return False
        try:
            with create_comfyui_http_client(config["base_url"], timeout=5.0) as client:
                response = client.get(f"{config['base_url'].rstrip('/')}/system_stats")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    def configured(self) -> bool:
        config = self._load_config()
        return Path(config["workflow_path"]).exists()

    def capabilities(self) -> dict:
        config = self._load_config()
        workflow_path = Path(config["workflow_path"])
        return {
            "mode": "comfyui",
            "requires_model": True,
            "formats": ["png"],
            "base_url": config["base_url"],
            "workflow_path": str(workflow_path),
            "workflow_exists": workflow_path.exists(),
            "default_output_dir": config["output_dir"],
            "timeout_seconds": config["timeout_seconds"],
        }

    def doctor(self, verbose: bool = False) -> DoctorReport:
        """Run connectivity and backend diagnostics for the configured ComfyUI API."""
        config = self._load_config()
        base_url = config["base_url"]
        parsed = urlparse(base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        report = DoctorReport(base_url=base_url)

        report.checks.append(self._tcp_check(host, port))
        report.checks.append(self._http_environment_check(base_url))
        endpoint_checks: dict[str, DoctorCheck] = {}
        for name, path, acceptable in (
            ("System Stats", "/system_stats", {200}),
            ("Object Info", "/object_info", {200}),
            ("Queue", "/queue", {200}),
            ("History", "/history", {200}),
            ("View API", "/view", {200, 400, 404}),
            ("Prompt API", "/prompt", {200, 400, 405}),
        ):
            check = self._http_check(base_url, path, acceptable)
            check.name = name
            endpoint_checks[path] = check
            report.checks.append(check)

        system_data = self._json_payload(endpoint_checks.get("/system_stats"))
        if isinstance(system_data, dict):
            system = system_data.get("system")
            if isinstance(system, dict):
                report.comfyui_version = str(system.get("comfyui_version") or "unknown")
                report.backend_url = self._backend_url_from_argv(base_url, system.get("argv"))

        first_headers = next((check.headers for check in endpoint_checks.values() if check.headers), {})
        report.proxy = self._detect_proxy(first_headers)
        report.checks.append(self._reverse_proxy_check(report.proxy, report.backend_url, endpoint_checks))
        report.checks.append(self._backend_check(report.backend_url, endpoint_checks))
        report.checks.append(self._localhost_check(base_url))
        report.checks.extend(self._docker_checks(verbose))
        report.checks.extend(self._process_checks(host, port))
        report.checks.append(self._workflow_check(config))
        report.checks.append(self._output_dir_check(config))

        report.reason = self._doctor_reason(report, endpoint_checks)
        report.overall_status = "READY" if not report.reason else "NOT READY"
        return report

    def generate(
        self,
        request: ImageGenerationRequest,
    ) -> ImageGenerationResult:
        started_at = time.monotonic()
        config = self._load_config()
        workflow_path = Path(str(request.metadata.get("workflow_path") or config["workflow_path"]))
        if not workflow_path.exists():
            result = self._failure(request, "ComfyUI workflow not found")
            self._publish("image.generation.failed", {"request": request, "result": result})
            return result

        try:
            self._check_available(config)
            workflow_metadata = self._load_workflow_metadata(workflow_path)
            self._apply_workflow_metadata(request, workflow_metadata)
            workflow = self._load_workflow(workflow_path)
            api_workflow = self._to_api_workflow(workflow)
            node_map = self._detect_nodes(api_workflow)
            patch_report = self._patch_workflow(api_workflow, request, node_map)
            prompt_id = self._submit_prompt(config, api_workflow)
            self._publish(
                "image.generation.progress",
                {
                    "provider": self.name,
                    "workflow": request.workflow,
                    "prompt_id": prompt_id,
                    "progress": 0.05,
                    "elapsed": round(time.monotonic() - started_at, 3),
                    "message": "ComfyUI prompt submitted",
                },
            )
            history = self._wait_for_history(config, prompt_id, started_at)
            image_paths = self._download_images(config, history, request, prompt_id)
            if not image_paths:
                raise RuntimeError("ComfyUI completed without image outputs")
            generation_time = time.monotonic() - started_at
            artifacts = [
                self._artifact_metadata(
                    request,
                    path,
                    generation_time=generation_time,
                    workflow_path=workflow_path,
                    workflow_metadata=workflow_metadata,
                )
                for path in image_paths
            ]
            result = ImageGenerationResult(
                success=True,
                image_paths=image_paths,
                provider=self.name,
                workflow=request.workflow,
                model_family=request.model_family,
                prompt=request.prompt,
                seed=request.seed,
                images=list(image_paths),
                artifacts=artifacts,
                generation_time=generation_time,
                metadata={
                    "prompt_id": prompt_id,
                    "workflow_id": request.metadata.get("workflow_id", ""),
                    "workflow_path": str(workflow_path),
                    "workflow_metadata": workflow_metadata,
                    "base_url": config["base_url"],
                    "patch_report": patch_report,
                    "output_dir": self._output_dir(config, request),
                },
            )
            for artifact in artifacts:
                self._publish("image.artifact.saved", {"artifact": artifact, "request": request})
            self._publish("image.generation.completed", {"request": request, "result": result})
            return result
        except Exception as exc:
            result = self._failure(request, str(exc))
            result.generation_time = time.monotonic() - started_at
            self._publish("image.generation.failed", {"request": request, "result": result})
            return result

    def _load_config(self) -> dict[str, Any]:
        config = {
            "base_url": DEFAULT_BASE_URL,
            "workflow_path": str(DEFAULT_WORKFLOW_PATH),
            "output_dir": str(DEFAULT_OUTPUT_DIR),
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        }
        if self.config_path.exists():
            data = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                config.update({key: value for key, value in data.items() if value not in (None, "")})
        config["base_url"] = str(config["base_url"]).rstrip("/")
        config["workflow_path"] = str(config["workflow_path"])
        config["output_dir"] = str(config["output_dir"])
        config["timeout_seconds"] = int(config["timeout_seconds"] or DEFAULT_TIMEOUT_SECONDS)
        return config

    def _load_workflow(self, workflow_path: Path) -> dict[str, Any]:
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("ComfyUI workflow must be a JSON object")
        return data

    def _check_available(self, config: dict[str, Any]) -> None:
        with create_comfyui_http_client(config["base_url"], timeout=10.0) as client:
            response = client.get(f"{config['base_url']}/system_stats")
            if response.status_code >= 500:
                proxy = self._detect_proxy(dict(response.headers))
                if response.status_code == 503 and proxy == "Caddy":
                    raise RuntimeError("Reverse Proxy cannot reach backend (Caddy returned 503)")
                if response.status_code == 503:
                    raise RuntimeError(f"Backend unavailable ({proxy} returned 503)")
            response.raise_for_status()

    def _tcp_check(self, host: str, port: int) -> DoctorCheck:
        started = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=3.0):
                return DoctorCheck("Network", "OK", f"TCP {host}:{port}", (time.monotonic() - started) * 1000)
        except OSError as exc:
            return DoctorCheck("Network", "FAIL", f"TCP {host}:{port}: {exc}", (time.monotonic() - started) * 1000, type(exc).__name__)

    def _http_check(self, base_url: str, path: str, acceptable: set[int]) -> DoctorCheck:
        started = time.monotonic()
        try:
            with create_comfyui_http_client(base_url, timeout=10.0) as client:
                response = client.get(f"{base_url.rstrip('/')}{path}")
            elapsed = (time.monotonic() - started) * 1000
            status = "OK" if response.status_code in acceptable else "FAIL"
            detail = f"HTTP {response.status_code}"
            if response.status_code == 503:
                detail = f"{detail}; returned by {self._detect_503_source(response)}"
            check = DoctorCheck(path, status, detail, elapsed, "", response.status_code, dict(response.headers))
            check.headers["_body_preview"] = response.text[:1000]
            return check
        except Exception as exc:
            return DoctorCheck(path, "FAIL", str(exc), (time.monotonic() - started) * 1000, type(exc).__name__)

    def _http_environment_check(self, base_url: str) -> DoctorCheck:
        started = time.monotonic()
        try:
            with httpx.Client(timeout=10.0, trust_env=True) as client:
                response = client.get(f"{base_url.rstrip('/')}/system_stats")
            status = "OK" if response.status_code < 500 else "WARN"
            detail = f"trust_env=True HTTP {response.status_code}"
            if response.status_code == 503:
                source = self._detect_503_source(response)
                detail = f"{detail}; returned by {source}; direct LAN mode uses trust_env=False"
            check = DoctorCheck("HTTP Environment", status, detail, (time.monotonic() - started) * 1000, "", response.status_code, dict(response.headers))
            check.headers["_body_preview"] = response.text[:1000]
            return check
        except Exception as exc:
            return DoctorCheck("HTTP Environment", "WARN", str(exc), (time.monotonic() - started) * 1000, type(exc).__name__)

    def _json_payload(self, check: DoctorCheck | None) -> Any:
        if check is None:
            return None
        try:
            return json.loads(check.headers.get("_body_preview", ""))
        except json.JSONDecodeError:
            return None

    def _detect_proxy(self, headers: dict[str, str]) -> str:
        server = headers.get("server") or headers.get("Server") or ""
        lower = server.lower()
        if "caddy" in lower:
            return "Caddy"
        if "nginx" in lower:
            return "nginx"
        if "docker" in lower:
            return "Docker"
        if "aiohttp" in lower or "python" in lower:
            return "ComfyUI"
        return "unknown"

    def _detect_503_source(self, response: httpx.Response) -> str:
        proxy = self._detect_proxy(dict(response.headers))
        if proxy != "unknown":
            return proxy
        body = response.text.lower()
        if "caddy" in body:
            return "Caddy"
        if "nginx" in body:
            return "nginx"
        if not response.headers.get("server") and not body.strip():
            return "other proxy / HTTP client environment"
        return "unknown proxy/backend"

    def _backend_url_from_argv(self, base_url: str, argv: Any) -> str:
        args = [str(item) for item in argv] if isinstance(argv, list) else []
        port = ""
        for index, item in enumerate(args):
            if item == "--port" and index + 1 < len(args):
                port = args[index + 1]
                break
        if not port:
            return ""
        parsed = urlparse(base_url)
        return urlunparse((parsed.scheme or "http", f"{parsed.hostname}:{port}", "", "", "", ""))

    def _reverse_proxy_check(self, proxy: str, backend_url: str, endpoint_checks: dict[str, DoctorCheck]) -> DoctorCheck:
        failed_503 = [check for check in endpoint_checks.values() if check.status_code == 503]
        if proxy == "Caddy":
            detail = "Caddy detected"
            if backend_url:
                detail = f"{detail}; upstream {backend_url}; timeout/health unknown from client"
            if failed_503:
                return DoctorCheck("Reverse Proxy", "FAIL", f"{detail}; Caddy returned 503")
            return DoctorCheck("Reverse Proxy", "OK", detail)
        if failed_503:
            return DoctorCheck("Reverse Proxy", "FAIL", f"{self._detect_proxy(failed_503[0].headers)} returned 503")
        if proxy in {"nginx", "Docker"}:
            return DoctorCheck("Reverse Proxy", "OK", f"{proxy} detected")
        return DoctorCheck("Reverse Proxy", "WARN", "No reverse proxy identified")

    def _backend_check(self, backend_url: str, endpoint_checks: dict[str, DoctorCheck]) -> DoctorCheck:
        if not backend_url:
            return DoctorCheck("Backend", "WARN", "Backend URL not discovered")
        check = self._http_check(backend_url, "/system_stats", {200})
        check.name = "Backend"
        if check.status == "FAIL" and check.error_type:
            proxy_reaches_backend = all(
                endpoint.status == "OK"
                for path, endpoint in endpoint_checks.items()
                if path in {"/system_stats", "/object_info", "/queue", "/history"}
            )
            if proxy_reaches_backend:
                check.status = "WARN"
                check.detail = f"Backend is not externally reachable at {backend_url}; proxy path is healthy"
            else:
                check.detail = f"Proxy cannot reach backend candidate {backend_url}: {check.detail}"
        return check

    def _localhost_check(self, base_url: str) -> DoctorCheck:
        parsed = urlparse(base_url)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} and _is_windows():
            return DoctorCheck(
                "Localhost",
                "SKIP",
                f"Remote ComfyUI host {parsed.hostname}; localhost check is not applicable on this Windows client",
            )
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        local_url = urlunparse((parsed.scheme or "http", f"127.0.0.1:{port}", "", "", "", ""))
        check = self._http_check(local_url, "/system_stats", {200})
        check.name = "Localhost"
        if check.status == "OK" and parsed.hostname not in {"127.0.0.1", "localhost"}:
            check.detail = f"{check.detail}; localhost works while {parsed.hostname} is configured"
        return check

    def _docker_checks(self, verbose: bool) -> list[DoctorCheck]:
        if _is_windows():
            return [DoctorCheck("Docker", "INFO", "Remote backend checks unavailable from this Windows client")]
        docker = self._run_command(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"])
        if docker is None:
            return [DoctorCheck("Docker", "WARN", "Docker CLI unavailable")]
        if docker.returncode != 0:
            return [DoctorCheck("Docker", "WARN", docker.stderr.strip() or "Docker not reachable")]
        lines = [line for line in docker.stdout.splitlines() if "comfy" in line.lower()]
        if not lines:
            return [DoctorCheck("Docker", "OK", "No ComfyUI container found")]
        checks = [DoctorCheck("Docker", "OK" if "Up" in lines[0] else "FAIL", lines[0])]
        if verbose:
            name = lines[0].split("\t", 1)[0]
            inspect = self._run_command(["docker", "inspect", name, "--format", "state={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} restarts={{.RestartCount}}"])
            if inspect is not None:
                checks.append(DoctorCheck("Docker Health", "OK" if inspect.returncode == 0 else "WARN", inspect.stdout.strip() or inspect.stderr.strip()))
            logs = self._run_command(["docker", "logs", "--tail", "20", name])
            if logs is not None:
                text = (logs.stderr + "\n" + logs.stdout).strip()
                status = "FAIL" if any(word in text.lower() for word in ("cuda error", "out of memory", "traceback")) else "OK"
                checks.append(DoctorCheck("Docker Logs", status, text[-500:] if text else "No recent logs"))
        return checks

    def _process_checks(self, host: str, port: int) -> list[DoctorCheck]:
        if _is_windows() and host not in {"127.0.0.1", "localhost", "::1"}:
            return [
                DoctorCheck("Port", "INFO", f"Remote port ownership unavailable from this Windows client for {host}:{port}"),
                DoctorCheck("Process", "INFO", "Remote ComfyUI process check unavailable from this Windows client"),
                DoctorCheck("systemd", "INFO", "Remote systemd check unavailable from this Windows client"),
            ]
        try:
            import psutil
        except Exception:
            return [DoctorCheck("Process", "WARN", "psutil unavailable")]
        listeners = []
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port in {port, 18188}:
                listeners.append(f"{conn.laddr.ip}:{conn.laddr.port} pid={conn.pid}")
        checks = [DoctorCheck("Port", "OK" if listeners else "WARN", "; ".join(listeners) or f"No local listener for {host}:{port}")]
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline") or [])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if "comfy" in cmdline.lower():
                processes.append(f"pid={proc.info['pid']} {proc.info.get('name')}")
        checks.append(DoctorCheck("Process", "OK" if processes else "WARN", "; ".join(processes) or "No local ComfyUI process found"))
        checks.append(DoctorCheck("systemd", "WARN", "systemd check skipped on this host"))
        return checks

    def _workflow_check(self, config: dict[str, Any]) -> DoctorCheck:
        path = Path(config["workflow_path"])
        return DoctorCheck("Workflow", "OK" if path.exists() else "FAIL", str(path))

    def _output_dir_check(self, config: dict[str, Any]) -> DoctorCheck:
        path = Path(config["output_dir"])
        try:
            path.mkdir(parents=True, exist_ok=True)
            return DoctorCheck("Output directory", "OK", str(path))
        except OSError as exc:
            return DoctorCheck("Output directory", "FAIL", f"{path}: {exc}", error_type=type(exc).__name__)

    def _run_command(self, command: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError):
            return None

    def _doctor_reason(self, report: DoctorReport, endpoint_checks: dict[str, DoctorCheck]) -> str:
        if any(check.name == "Network" and check.status == "FAIL" for check in report.checks):
            return "TCP connection failed"
        if any(check.status_code == 503 for check in endpoint_checks.values()):
            return "Reverse Proxy cannot reach backend" if report.proxy == "Caddy" else "Backend returned 503"
        backend = next((check for check in report.checks if check.name == "Backend"), None)
        if backend is not None and backend.status == "FAIL" and report.proxy in {"Caddy", "nginx"}:
            return "Proxy cannot reach backend"
        required = {"System Stats", "Object Info", "Queue", "History", "Prompt API", "View API", "Workflow", "Output directory"}
        failing = [check.name for check in report.checks if check.name in required and check.status == "FAIL"]
        if failing:
            return f"Failed checks: {', '.join(failing)}"
        return ""

    def _load_workflow_metadata(self, workflow_path: Path) -> dict[str, Any]:
        candidates = [
            workflow_path.with_name(f"{workflow_path.stem}.meta.json"),
            workflow_path.with_name("default.meta.json"),
        ]
        for path in candidates:
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
        return {}

    def _apply_workflow_metadata(
        self,
        request: ImageGenerationRequest,
        metadata: dict[str, Any],
    ) -> None:
        if not request.model_family:
            request.model_family = str(metadata.get("model_family") or "unknown")
        request.task_type = request.task_type or str(metadata.get("task_type") or "txt2img")
        if request.width <= 0:
            request.width = int(metadata.get("default_width") or 1024)
        if request.height <= 0:
            request.height = int(metadata.get("default_height") or 1024)

    def _to_api_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        nodes = workflow.get("nodes")
        links = workflow.get("links")
        if not isinstance(nodes, list) or not isinstance(links, list):
            return workflow

        link_map: dict[int, list[Any]] = {}
        for link in links:
            if isinstance(link, list) and len(link) >= 6:
                link_map[int(link[0])] = link

        api_workflow: dict[str, Any] = {}
        for node in nodes:
            if not isinstance(node, dict) or "id" not in node:
                continue
            node_id = str(node["id"])
            class_type = str(node.get("type") or node.get("class_type") or "")
            if not class_type:
                continue
            api_inputs = self._ui_widget_inputs(class_type, node.get("widgets_values", []))
            for input_item in node.get("inputs", []):
                if not isinstance(input_item, dict) or input_item.get("link") is None:
                    continue
                link = link_map.get(int(input_item["link"]))
                if not link:
                    continue
                api_inputs[str(input_item.get("name"))] = [str(link[1]), int(link[2])]
            api_workflow[node_id] = {
                "class_type": class_type,
                "inputs": api_inputs,
            }
            if isinstance(node.get("_meta"), dict):
                api_workflow[node_id]["_meta"] = node["_meta"]
            elif isinstance(node.get("properties"), dict):
                title = node["properties"].get("Node name for S&R")
                if title:
                    api_workflow[node_id]["_meta"] = {"title": str(title)}
        return api_workflow

    def _ui_widget_inputs(self, class_type: str, widgets: Any) -> dict[str, Any]:
        values = list(widgets) if isinstance(widgets, list) else []
        if class_type == "CLIPTextEncode":
            return {"text": str(values[0]) if values else ""}
        if class_type == "EmptyLatentImage":
            return {
                "width": int(values[0]) if len(values) > 0 else 1024,
                "height": int(values[1]) if len(values) > 1 else 1024,
                "batch_size": int(values[2]) if len(values) > 2 else 1,
            }
        if class_type == "KSampler":
            return {
                "seed": int(values[0]) if len(values) > 0 else 0,
                "steps": int(values[2]) if len(values) > 2 else 20,
                "cfg": values[3] if len(values) > 3 else 7,
                "sampler_name": values[4] if len(values) > 4 else "euler",
                "scheduler": values[5] if len(values) > 5 else "normal",
                "denoise": values[6] if len(values) > 6 else 1,
            }
        if class_type == "CheckpointLoaderSimple":
            return {"ckpt_name": str(values[0]) if values else ""}
        if class_type == "SaveImage":
            return {"filename_prefix": str(values[0]) if values else "AEGIS"}
        return {}

    def _detect_nodes(self, workflow: dict[str, Any]) -> dict[str, str]:
        class_nodes = self._nodes_by_class(workflow)
        sampler_id = self._require_one(class_nodes, "KSampler")
        latent_id = self._require_one(class_nodes, "EmptyLatentImage")
        save_id = self._require_one(class_nodes, "SaveImage")
        clip_nodes = class_nodes.get("CLIPTextEncode", [])
        if not clip_nodes:
            raise ValueError("ComfyUI workflow is missing CLIPTextEncode node")

        sampler_inputs = workflow[sampler_id].get("inputs", {})
        positive_id = self._linked_node_id(sampler_inputs.get("positive"))
        negative_id = self._linked_node_id(sampler_inputs.get("negative"))
        if positive_id not in clip_nodes:
            raise ValueError("ComfyUI workflow has no positive CLIPTextEncode connected to KSampler")
        if negative_id not in clip_nodes:
            raise ValueError("ComfyUI workflow has no negative CLIPTextEncode connected to KSampler")
        if self._linked_node_id(sampler_inputs.get("latent_image")) != latent_id:
            raise ValueError("ComfyUI workflow has no EmptyLatentImage connected to KSampler")
        return {
            "sampler": sampler_id,
            "latent": latent_id,
            "save": save_id,
            "positive": positive_id,
            "negative": negative_id,
        }

    def _nodes_by_class(self, workflow: dict[str, Any]) -> dict[str, list[str]]:
        nodes: dict[str, list[str]] = {}
        for node_id, node in workflow.items():
            if isinstance(node, dict):
                nodes.setdefault(str(node.get("class_type", "")), []).append(str(node_id))
        return nodes

    def _require_one(self, nodes: dict[str, list[str]], class_type: str) -> str:
        matches = nodes.get(class_type, [])
        if not matches:
            raise ValueError(f"ComfyUI workflow is missing {class_type} node")
        return matches[0]

    def _linked_node_id(self, value: Any) -> str:
        if isinstance(value, list) and value:
            return str(value[0])
        if isinstance(value, tuple) and value:
            return str(value[0])
        return ""

    def _patch_workflow(
        self,
        workflow: dict[str, Any],
        request: ImageGenerationRequest,
        node_map: dict[str, str],
    ) -> dict[str, int]:
        report = {
            "prompt_nodes": 0,
            "negative_prompt_nodes": 0,
            "seed_nodes": 0,
            "steps_nodes": 0,
            "size_nodes": 0,
            "save_nodes": 0,
        }
        seed = request.seed if request.seed is not None else int(time.time_ns() % 2_147_483_647)
        request.seed = seed

        positive_inputs = workflow[node_map["positive"]]["inputs"]
        negative_inputs = workflow[node_map["negative"]]["inputs"]
        sampler_inputs = workflow[node_map["sampler"]]["inputs"]
        latent_inputs = workflow[node_map["latent"]]["inputs"]
        save_inputs = workflow[node_map["save"]]["inputs"]

        positive_inputs["text"] = request.prompt
        negative_inputs["text"] = request.negative_prompt
        sampler_inputs["seed"] = int(seed)
        sampler_inputs["steps"] = int(request.steps)
        latent_inputs["width"] = int(request.width)
        latent_inputs["height"] = int(request.height)
        save_inputs["filename_prefix"] = "AEGIS"

        report["prompt_nodes"] = 1
        report["negative_prompt_nodes"] = 1
        report["seed_nodes"] = 1
        report["steps_nodes"] = 1
        report["size_nodes"] = 1
        report["save_nodes"] = 1

        if report["prompt_nodes"] == 0:
            raise ValueError("ComfyUI workflow has no prompt text input")
        return report

    def _submit_prompt(self, config: dict[str, Any], workflow: dict[str, Any]) -> str:
        timeout = float(config["timeout_seconds"])
        payload = {"prompt": workflow, "client_id": f"aegis-{uuid4().hex}"}
        with create_comfyui_http_client(config["base_url"], timeout=timeout) as client:
            response = client.post(f"{config['base_url']}/prompt", json=payload)
            response.raise_for_status()
            data = response.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return prompt_id")
        return str(prompt_id)

    def _wait_for_history(
        self,
        config: dict[str, Any],
        prompt_id: str,
        started_at: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + float(config["timeout_seconds"])
        with create_comfyui_http_client(config["base_url"], timeout=10.0) as client:
            while time.monotonic() < deadline:
                try:
                    response = client.get(f"{config['base_url']}/history/{prompt_id}")
                    response.raise_for_status()
                    data = response.json()
                except (httpx.HTTPError, json.JSONDecodeError) as exc:
                    self._publish(
                        "image.generation.progress",
                        {
                            "provider": self.name,
                            "prompt_id": prompt_id,
                            "progress": self._elapsed_progress(started_at, config),
                            "elapsed": round(time.monotonic() - started_at, 3),
                            "message": f"Waiting for ComfyUI history: {exc}",
                        },
                    )
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue
                history = data.get(prompt_id) if isinstance(data, dict) else None
                if isinstance(history, dict):
                    status = history.get("status", {})
                    if isinstance(status, dict) and status.get("status_str") == "error":
                        messages = status.get("messages") or []
                        raise RuntimeError(f"ComfyUI generation failed: {messages}")
                    outputs = history.get("outputs")
                    if isinstance(outputs, dict) and outputs:
                        return history
                self._publish(
                    "image.generation.progress",
                    {
                        "provider": self.name,
                        "prompt_id": prompt_id,
                        "progress": self._elapsed_progress(started_at, config),
                        "elapsed": round(time.monotonic() - started_at, 3),
                        "message": "ComfyUI generation running",
                    },
                )
                time.sleep(POLL_INTERVAL_SECONDS)
        raise TimeoutError("ComfyUI generation timed out")

    def _download_images(
        self,
        config: dict[str, Any],
        history: dict[str, Any],
        request: ImageGenerationRequest,
        prompt_id: str,
    ) -> list[str]:
        output_dir = Path(self._output_dir(config, request))
        output_dir.mkdir(parents=True, exist_ok=True)
        image_paths: list[str] = []
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        outputs = history.get("outputs", {})
        with create_comfyui_http_client(config["base_url"], timeout=float(config["timeout_seconds"])) as client:
            for node_output in outputs.values():
                if not isinstance(node_output, dict):
                    continue
                for image in node_output.get("images", []):
                    if not isinstance(image, dict):
                        continue
                    params = {
                        "filename": image.get("filename", ""),
                        "subfolder": image.get("subfolder", ""),
                        "type": image.get("type", "output"),
                    }
                    response = client.get(f"{config['base_url']}/view?{urlencode(params)}")
                    response.raise_for_status()
                    path = output_dir / f"{timestamp}-{prompt_id}-{len(image_paths)}.png"
                    with Image.open(BytesIO(response.content)) as generated_image:
                        generated_image.save(path, format="PNG")
                    image_paths.append(str(path))
        return image_paths

    def _elapsed_progress(self, started_at: float, config: dict[str, Any]) -> float:
        timeout = max(1.0, float(config["timeout_seconds"]))
        return min(0.95, max(0.05, (time.monotonic() - started_at) / timeout))

    def _artifact_metadata(
        self,
        request: ImageGenerationRequest,
        output_path: str,
        *,
        generation_time: float,
        workflow_path: Path,
        workflow_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": "image.generated",
            "provider": self.name,
            "workflow": request.workflow or request.metadata.get("workflow_id") or workflow_path.stem,
            "model_family": request.model_family or workflow_metadata.get("model_family", "unknown"),
            "seed": request.seed,
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "generation_time": generation_time,
            "output_path": output_path,
            "category": workflow_metadata.get("category", "general"),
            "task_type": request.task_type or workflow_metadata.get("task_type", "txt2img"),
        }

    def _output_dir(self, config: dict[str, Any], request: ImageGenerationRequest) -> str:
        return request.output_dir or str(config["output_dir"])

    def _failure(self, request: ImageGenerationRequest, error: str) -> ImageGenerationResult:
        return ImageGenerationResult(
            success=False,
            provider=self.name,
            prompt=request.prompt,
            seed=request.seed,
            error=error,
        )

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_publisher is None:
            return
        self._event_publisher(event_type, payload)
