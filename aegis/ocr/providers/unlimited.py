"""Unlimited-OCR HTTP provider for the OCR Runtime."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from aegis.serialization import to_plain
from aegis.config.services import ResolvedValue, resolve_service_base_url

from ..models import OCRResult
from ..provider import ProviderName

CONFIG_PATH = Path(r"F:\AI_WORKSPACE\ocr\unlimited_ocr.json")
DEFAULT_OUTPUT_DIR = Path(r"F:\AI_WORKSPACE\ocr\results")
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_POLL_INTERVAL_MS = 500
DEFAULT_LANGUAGE = "auto"
MODEL_ID = "baidu/Unlimited-OCR"


@dataclass
class UnlimitedOCRConfig:
    base_url: str = "http://127.0.0.1:8190"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS
    default_language: str = DEFAULT_LANGUAGE
    trust_env: bool = False


def create_unlimited_ocr_http_client(
    base_url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    trust_env: bool | None = None,
) -> httpx.Client:
    """Create an HTTP client with proxy environment disabled for local/LAN endpoints."""
    use_trust_env = trust_env if trust_env is not None else not _is_local_or_lan_url(base_url)
    return httpx.Client(timeout=timeout, trust_env=use_trust_env)


def _is_local_or_lan_url(base_url: str) -> bool:
    host = urlparse(base_url).hostname or ""
    if host.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private


class UnlimitedOCRProvider:
    """Production OCR provider backed by an Ubuntu Unlimited-OCR service."""

    name = ProviderName("unlimited")

    def __init__(self, config_path: str | Path = CONFIG_PATH, base_url: str | None = None):
        self.config_path = Path(config_path)
        self._base_url_override = base_url
        self._resolved_source = "fallback"

    def available(self) -> bool:
        health = self.health()
        return bool(health.get("service_alive", health.get("service_reachable"))) and health.get("status") in {
            "ok",
            "ready",
            "healthy",
        }

    def health(self) -> dict[str, Any]:
        config = self._load_config()
        started_at = time.monotonic()
        try:
            with create_unlimited_ocr_http_client(
                config.base_url,
                timeout=min(float(config.timeout_seconds), 2.0),
                trust_env=config.trust_env,
            ) as client:
                response = client.get(self._url("/health"))
                elapsed_ms = round((time.monotonic() - started_at) * 1000, 2)
                payload = self._safe_json(response)
                status = str(payload.get("status") or ("ok" if response.status_code == 200 else "error"))
                return {
                    "provider": str(self.name),
                    "status": status,
                    "service_alive": response.status_code == 200,
                    "service_reachable": response.status_code == 200,
                    "status_code": response.status_code,
                    "latency_ms": elapsed_ms,
                    "base_url": config.base_url,
                    "model_id": payload.get("model_id") or MODEL_ID,
                    "model_loaded": payload.get("model_loaded", payload.get("model_ready")),
                    "inference_verified": bool(payload.get("inference_verified", False)),
                    "inference_ready": bool(payload.get("inference_ready", False)),
                    "gpu_detected": payload.get("gpu_detected"),
                    "recognition_ready": bool(payload.get("recognition_ready", False)),
                    "details": payload,
                }
        except Exception as exc:
            return {
                "provider": str(self.name),
                "status": "unavailable",
                "service_alive": False,
                "service_reachable": False,
                "base_url": config.base_url,
                "model_id": MODEL_ID,
                "error": str(exc),
            }

    def info(self) -> dict[str, Any]:
        config = self._load_config()
        try:
            with create_unlimited_ocr_http_client(
                config.base_url,
                timeout=min(float(config.timeout_seconds), 2.0),
                trust_env=config.trust_env,
            ) as client:
                response = client.get(self._url("/info"))
                return self._safe_json(response) if response.status_code == 200 else {}
        except Exception:
            return {}

    def capabilities(self) -> dict[str, Any]:
        config = self._load_config()
        info = self.info()
        return {
            "mode": "http-service",
            "requires_model": True,
            "recognition": True,
            "images": True,
            "documents": True,
            "pdf": True,
            "tables": True,
            "layout": True,
            "languages": info.get("languages") or ["auto"],
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "poll_interval_ms": config.poll_interval_ms,
            "model_id": info.get("model_id") or MODEL_ID,
        }

    def warmup(self) -> dict[str, Any]:
        return self._post_control("/warmup")

    def unload(self) -> dict[str, Any]:
        return self._post_control("/unload")

    def supported_formats(self) -> list[str]:
        info = self.info()
        formats = info.get("supported_formats")
        if isinstance(formats, list) and formats:
            return [str(item).lstrip(".").lower() for item in formats]
        return ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "pdf"]

    def recognize_image(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        path = Path(source)
        if not path.exists() or not path.is_file():
            return self._error_result(path, language, "image file not found")
        if path.suffix.lower().lstrip(".") not in {"png", "jpg", "jpeg", "webp", "bmp", "tiff"}:
            return self._error_result(path, language, f"unsupported image format: {path.suffix}")
        return self._submit_file("/ocr/image", path, language=language, options=options)

    def recognize_pdf(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        path = Path(source)
        if not path.exists() or not path.is_file():
            return self._error_result(path, language, "PDF file not found")
        if path.suffix.lower() != ".pdf":
            return self._error_result(path, language, f"unsupported PDF format: {path.suffix}")
        return self._submit_file("/ocr/pdf", path, language=language, options=options)

    def recognize_document(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        path = Path(source)
        if path.suffix.lower() == ".pdf":
            return self.recognize_pdf(path, language=language, options=options)
        return self.recognize_image(path, language=language, options=options)

    def recognize_directory(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        return self._error_result(source, language, "directory OCR is not supported by this sprint")

    def doctor(self, verbose: bool = False) -> dict[str, Any]:
        config = self._load_config()
        parsed = urlparse(config.base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        checks = {
            "config_exists": self.config_path.exists(),
            "tcp": self._tcp_check(host, port),
            "health": self.health(),
            "info": self.info(),
            "output_directory_writable": self._output_directory_writable(),
            "trust_env": config.trust_env,
        }
        health = checks["health"]
        info = checks["info"]
        service_alive = bool(health.get("service_alive", health.get("service_reachable")))
        model_loaded = bool(health.get("model_loaded") or info.get("model_loaded"))
        inference_verified = bool(health.get("inference_verified") or info.get("inference_verified"))
        inference_ready = bool(health.get("inference_ready") or info.get("inference_ready"))
        recognition_ready = service_alive and (inference_verified or (model_loaded and inference_ready))
        states = {
            "service_alive": service_alive,
            "service_reachable": service_alive,
            "model_loaded": model_loaded,
            "model_ready": model_loaded,
            "inference_verified": inference_verified,
            "inference_ready": inference_ready,
            "provider_available": self.available(),
            "recognition_ready": recognition_ready,
        }
        if verbose:
            states["gpu_detected"] = bool(health.get("gpu_detected") or info.get("gpu_detected"))
        return {
            "provider": str(self.name),
            "base_url": config.base_url,
            "configuration_source": self._configuration_source(),
            "model_id": info.get("model_id") or health.get("model_id") or MODEL_ID,
            "checks": checks,
            "states": states,
            "overall": "READY" if states["provider_available"] and states["recognition_ready"] else "NOT READY",
        }

    def _submit_file(
        self,
        endpoint: str,
        path: Path,
        *,
        language: str | None,
        options: dict[str, Any] | None,
    ) -> OCRResult:
        config = self._load_config()
        resolved_language = language or config.default_language
        started_at = time.monotonic()
        try:
            with create_unlimited_ocr_http_client(
                config.base_url,
                timeout=float(config.timeout_seconds),
                trust_env=config.trust_env,
            ) as client:
                with path.open("rb") as file_obj:
                    response = client.post(
                        self._url(endpoint),
                        files={"file": (path.name, file_obj, self._content_type(path))},
                        data={
                            "language": resolved_language,
                            "options": json.dumps(options or {}, ensure_ascii=False),
                        },
                    )
                if response.status_code == 202:
                    payload = self._poll_job(client, response.json(), config)
                else:
                    payload = self._response_payload_or_error(response)
            return self._map_response(
                payload,
                source=path,
                language=resolved_language,
                processing_time=time.monotonic() - started_at,
            )
        except Exception as exc:
            error = f"Unlimited-OCR service unavailable or failed: {exc}"
            return self._error_result(
                path,
                resolved_language,
                error,
                processing_time=time.monotonic() - started_at,
                error_type=self._classify_error(error),
            )

    def _poll_job(
        self,
        client: httpx.Client,
        payload: dict[str, Any],
        config: UnlimitedOCRConfig,
    ) -> dict[str, Any]:
        job_id = payload.get("job_id") or payload.get("id")
        if not job_id:
            return payload
        deadline = time.monotonic() + float(config.timeout_seconds)
        while time.monotonic() < deadline:
            response = client.get(self._url(f"/jobs/{job_id}"))
            data = self._response_payload_or_error(response)
            status = str(data.get("status") or "").lower()
            if status in {"completed", "complete", "succeeded", "success"}:
                return data.get("result") if isinstance(data.get("result"), dict) else data
            if status in {"failed", "error"}:
                raise RuntimeError(data.get("error") or f"job failed: {job_id}")
            time.sleep(max(config.poll_interval_ms, 100) / 1000)
        raise TimeoutError(f"Unlimited-OCR job timed out: {job_id}")

    def _map_response(
        self,
        payload: dict[str, Any],
        *,
        source: Path,
        language: str,
        processing_time: float,
    ) -> OCRResult:
        success = bool(payload.get("success", True))
        errors = list(payload.get("errors") or ([] if success else [payload.get("error") or "OCR failed"]))
        warnings = list(payload.get("warnings") or [])
        error_type = payload.get("error_type") or dict(payload.get("metadata") or {}).get("error_type")
        if not error_type and errors:
            error_type = self._classify_error(" ".join(str(error) for error in errors))
        return OCRResult(
            provider=str(payload.get("provider") or self.name),
            language=str(payload.get("language") or language),
            pages=list(payload.get("pages") or []),
            text=str(payload.get("text") or ""),
            blocks=list(payload.get("blocks") or []),
            tables=list(payload.get("tables") or []),
            figures=list(payload.get("figures") or []),
            confidence=payload.get("confidence"),
            processing_time=float(payload.get("processing_time") or processing_time),
            artifacts=list(payload.get("artifacts") or []),
            metadata={
                "service_url": self._load_config().base_url,
                "model_id": payload.get("model_id") or payload.get("model") or MODEL_ID,
                "error_type": error_type,
                **dict(payload.get("metadata") or {}),
            },
            warnings=warnings,
            errors=[str(error) for error in errors if error],
            source=str(source),
        )

    def _response_payload_or_error(self, response: httpx.Response) -> dict[str, Any]:
        payload = self._safe_json(response)
        if response.status_code < 400:
            return payload
        if self._looks_like_ocr_contract(payload):
            metadata = dict(payload.get("metadata") or {})
            metadata["status_code"] = response.status_code
            payload["metadata"] = metadata
            payload.setdefault("success", False)
            return payload
        response.raise_for_status()
        return payload

    def _post_control(self, endpoint: str) -> dict[str, Any]:
        config = self._load_config()
        try:
            with create_unlimited_ocr_http_client(
                config.base_url,
                timeout=float(config.timeout_seconds),
                trust_env=config.trust_env,
            ) as client:
                response = client.post(self._url(endpoint))
                return self._response_payload_or_error(response)
        except Exception as exc:
            return {
                "success": False,
                "provider": str(self.name),
                "model_id": MODEL_ID,
                "errors": [f"Unlimited-OCR service unavailable or failed: {exc}"],
                "metadata": {
                    "service_url": config.base_url,
                    "model_id": MODEL_ID,
                    "error_type": "ocr.service.unavailable",
                },
            }

    def _looks_like_ocr_contract(self, payload: dict[str, Any]) -> bool:
        if not payload:
            return False
        contract_keys = {
            "success",
            "provider",
            "language",
            "pages",
            "text",
            "blocks",
            "tables",
            "figures",
            "confidence",
            "processing_time",
            "artifacts",
            "metadata",
            "warnings",
            "errors",
        }
        return bool(contract_keys.intersection(payload)) and (
            isinstance(payload.get("errors"), list)
            or isinstance(payload.get("warnings"), list)
            or payload.get("success") is False
        )

    def _load_config(self) -> UnlimitedOCRConfig:
        data: dict[str, Any] = {}
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                data = {}
        legacy_url = data.get("base_url")
        if self._base_url_override:
            resolved = resolve_service_base_url("unlimited_ocr", explicit=self._base_url_override)
        elif os.environ.get("AEGIS_UNLIMITED_OCR_BASE_URL"):
            resolved = resolve_service_base_url("unlimited_ocr")
        elif legacy_url:
            resolved = ResolvedValue(str(legacy_url).rstrip("/"), "legacy OCR config")
        else:
            resolved = resolve_service_base_url("unlimited_ocr")
        self._resolved_source = resolved.source
        return UnlimitedOCRConfig(
            base_url=resolved.value,
            timeout_seconds=float(data.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
            poll_interval_ms=int(data.get("poll_interval_ms") or DEFAULT_POLL_INTERVAL_MS),
            default_language=str(data.get("default_language") or DEFAULT_LANGUAGE),
            trust_env=bool(data.get("trust_env", False)),
        )

    def _configuration_source(self) -> str:
        self._load_config()
        return self._resolved_source

    def _url(self, path: str) -> str:
        config = self._load_config()
        return f"{config.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _safe_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _error_result(
        self,
        source: str | Path,
        language: str | None,
        error: str,
        *,
        processing_time: float = 0.0,
        error_type: str | None = None,
    ) -> OCRResult:
        return OCRResult(
            provider=str(self.name),
            language=language or self._load_config().default_language,
            source=str(source),
            processing_time=processing_time,
            errors=[error],
            metadata={
                "service_url": self._load_config().base_url,
                "model_id": MODEL_ID,
                "error_type": error_type or self._classify_error(error),
            },
        )

    def _classify_error(self, error: str) -> str:
        text = str(error).lower()
        if "out of memory" in text or "cuda oom" in text or ("cuda" in text and "memory" in text):
            return "ocr.resource.exhausted"
        if "load" in text and "failed" in text:
            return "ocr.model.load_failed"
        if "unavailable" in text or "connection" in text or "timed out" in text:
            return "ocr.service.unavailable"
        return "ocr.inference.failed"

    def _tcp_check(self, host: str, port: int) -> dict[str, Any]:
        started_at = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=3.0):
                return {
                    "ok": True,
                    "host": host,
                    "port": port,
                    "latency_ms": round((time.monotonic() - started_at) * 1000, 2),
                }
        except OSError as exc:
            return {"ok": False, "host": host, "port": port, "error": str(exc)}

    def _output_directory_writable(self) -> bool:
        try:
            DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            probe = DEFAULT_OUTPUT_DIR / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def _content_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".pdf":
            return "application/pdf"
        if suffix == ".webp":
            return "image/webp"
        if suffix in {".tif", ".tiff"}:
            return "image/tiff"
        return "image/png"

    def to_plain_response(self, result: OCRResult) -> dict[str, Any]:
        return to_plain(result)
