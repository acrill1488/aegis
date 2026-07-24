"""Lazy, optional PaddleOCR adapter for the provider-neutral OCR Runtime."""

from __future__ import annotations

import importlib
import importlib.util
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from threading import Lock
from typing import Any

from PIL import Image

from aegis.ocr.models import OCRBlock, OCRResult
from aegis.ocr.provider import ProviderName

from .config import PaddleOCRConfig
from .errors import PaddleOCRInitializationError, PaddleOCRUnavailableError
from .health import ProviderHealth
from .models import PaddleOCRLine, PaddleOCRResult


INSTALL_HINT = "Install the component with: aegis install paddleocr"


class PaddleOCRProvider:
    """In-process PaddleOCR provider; the SDK and model are loaded on first OCR call."""

    name = ProviderName("paddleocr")

    def __init__(self, config: PaddleOCRConfig | None = None, *, config_path: str | Path | None = None):
        self.config = config or PaddleOCRConfig.load(config_path)
        self._engine: Any | None = None
        self._device: str | None = None
        self._fallback: dict[str, Any] | None = None
        self._initialization_error: str | None = None
        self._lock = Lock()

    def is_available(self) -> bool:
        return self.available()

    def available(self) -> bool:
        return self.config.enabled and importlib.util.find_spec("paddleocr") is not None

    def health(self) -> dict[str, Any]:
        return self.provider_health().as_dict()

    def provider_health(self) -> ProviderHealth:
        if not self.config.enabled:
            return ProviderHealth(status="disabled", message="PaddleOCR provider is disabled")
        if importlib.util.find_spec("paddleocr") is None:
            return ProviderHealth(message=f"PaddleOCR package is not installed. {INSTALL_HINT}")
        if self._initialization_error:
            return ProviderHealth(status="model initialization failed", available=False, device=self._device or "unavailable", message=self._initialization_error)
        device = self._device or self._select_device()
        status = "GPU runtime available" if device == "gpu" else "CPU runtime available"
        if self.config.device == "gpu" and device != "gpu":
            status = "GPU requested but unavailable"
        if self._engine is not None:
            status = "healthy"
        return ProviderHealth(status=status, available=True, device=device, metadata={"fallback": self._fallback})

    def capabilities(self) -> dict[str, Any]:
        return {"mode": "in-process", "requires_model": True, "recognition": True, "images": True, "documents": True, "pdf": False, "tables": False, "layout": False, "languages": [self.config.language]}

    def supported_formats(self) -> list[str]:
        return ["png", "jpg", "jpeg", "webp", "bmp", "tiff"]

    def doctor(self, verbose: bool = False) -> dict[str, Any]:
        health = self.health()
        return {"provider": str(self.name), "health": health, "states": {"package_installed": importlib.util.find_spec("paddleocr") is not None, "provider_enabled": self.config.enabled, "gpu_runtime_available": self._gpu_runtime_available(), "model_initialized": self._engine is not None, "fallback_active": self._fallback is not None}}

    def recognize(self, request: Any) -> OCRResult:
        source = getattr(request, "source", request)
        language = getattr(request, "language", None)
        options = getattr(request, "options", None)
        return self.recognize_image(source, language=language, options=options)

    def recognize_image(self, source: str | Path, *, language: str | None = None, options: dict[str, Any] | None = None) -> OCRResult:
        path = Path(source)
        effective = self.config.with_overrides(language=language, device=(options or {}).get("device"), confidence_threshold=(options or {}).get("confidence_threshold"))
        if not path.is_file():
            return self._error(path, effective, "image file not found")
        if path.suffix.lower().lstrip(".") not in self.supported_formats():
            return self._error(path, effective, f"unsupported image format: {path.suffix}")
        try:
            with Image.open(path) as image:
                if max(image.size) > effective.max_image_size:
                    return self._error(path, effective, f"image exceeds max_image_size ({effective.max_image_size}px)")
                image.verify()
            started = time.monotonic()
            engine = self._get_engine(effective)
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paddleocr")
            future = executor.submit(engine.ocr, str(path), cls=effective.use_angle_cls)
            try:
                native = future.result(timeout=effective.timeout_seconds)
            except FutureTimeoutError:
                future.cancel()
                return self._error(path, effective, f"PaddleOCR recognition timed out after {effective.timeout_seconds:g} seconds")
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            normalized = self._normalize(native, effective, (time.monotonic() - started) * 1000)
            return self._to_ocr_result(normalized, path)
        except (PaddleOCRUnavailableError, PaddleOCRInitializationError) as exc:
            return self._error(path, effective, str(exc))
        except Exception as exc:
            return self._error(path, effective, f"PaddleOCR recognition failed: {exc}")

    def recognize_document(self, source: str | Path, *, language: str | None = None, options: dict[str, Any] | None = None) -> OCRResult:
        return self.recognize_image(source, language=language, options=options)

    def recognize_pdf(self, source: str | Path, *, language: str | None = None, options: dict[str, Any] | None = None) -> OCRResult:
        return self._error(source, self.config.with_overrides(language=language), "PDF OCR is not supported by PaddleOCR Provider v1")

    def recognize_directory(self, source: str | Path, *, language: str | None = None, options: dict[str, Any] | None = None) -> OCRResult:
        return self._error(source, self.config.with_overrides(language=language), "directory OCR is not supported by PaddleOCR Provider v1")

    def _get_engine(self, config: PaddleOCRConfig) -> Any:
        if not config.enabled:
            raise PaddleOCRUnavailableError("PaddleOCR provider is disabled")
        if importlib.util.find_spec("paddleocr") is None:
            raise PaddleOCRUnavailableError(f"PaddleOCR package is not installed. {INSTALL_HINT}")
        with self._lock:
            if self._engine is not None:
                return self._engine
            requested = self._select_device(config.device)
            try:
                self._engine = self._create_engine(config, requested)
                self._device = requested
            except Exception as exc:
                if requested != "gpu":
                    self._initialization_error = f"PaddleOCR model initialization failed: {exc}"
                    raise PaddleOCRInitializationError(self._initialization_error) from exc
                self._fallback = {"from": "gpu", "to": "cpu", "reason": str(exc)}
                try:
                    self._engine = self._create_engine(config, "cpu")
                    self._device = "cpu"
                except Exception as cpu_exc:
                    self._initialization_error = f"PaddleOCR model initialization failed on GPU and CPU fallback: {cpu_exc}"
                    raise PaddleOCRInitializationError(self._initialization_error) from cpu_exc
            return self._engine

    def _create_engine(self, config: PaddleOCRConfig, device: str) -> Any:
        module = importlib.import_module("paddleocr")
        try:
            return module.PaddleOCR(lang=config.language, use_angle_cls=config.use_angle_cls, use_gpu=device == "gpu", show_log=False)
        except TypeError:
            return module.PaddleOCR(lang=config.language, device=device, use_textline_orientation=config.use_angle_cls)

    def _select_device(self, requested: str | None = None) -> str:
        requested = requested or self.config.device
        if requested == "cpu":
            return "cpu"
        return "gpu" if self._gpu_runtime_available() else "cpu"

    @staticmethod
    def _gpu_runtime_available() -> bool:
        try:
            paddle = importlib.import_module("paddle")
            return bool(paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0)
        except Exception:
            return False

    def _normalize(self, native: Any, config: PaddleOCRConfig, duration_ms: float) -> PaddleOCRResult:
        lines: list[PaddleOCRLine] = []
        for page in native or []:
            for entry in page or []:
                if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                    continue
                box, value = entry[0], entry[1]
                if not isinstance(value, (list, tuple)) or len(value) < 2:
                    continue
                text, confidence = str(value[0]), float(value[1])
                if confidence < config.confidence_threshold:
                    continue
                lines.append(PaddleOCRLine(text=text, confidence=confidence, bounding_box=[[float(x), float(y)] for x, y in (box or [])]))
        confidence = sum(line.confidence for line in lines) / len(lines) if lines else None
        return PaddleOCRResult(text="\n".join(line.text for line in lines), lines=lines, confidence=confidence, language=config.language, provider=str(self.name), duration_ms=duration_ms, device=self._device or self._select_device(config.device), metadata={"fallback": self._fallback, "native_line_count": sum(len(page or []) for page in native or [])})

    @staticmethod
    def _to_ocr_result(result: PaddleOCRResult, source: Path) -> OCRResult:
        blocks = [OCRBlock(text=line.text, confidence=line.confidence, bbox=[coordinate for point in line.bounding_box for coordinate in point], metadata={"bounding_box": line.bounding_box}) for line in result.lines]
        pages = [{"page": 1, "text": result.text, "blocks": len(blocks)}] if blocks else []
        return OCRResult(provider=result.provider, language=result.language, pages=pages, text=result.text, blocks=blocks, confidence=result.confidence, processing_time=result.duration_ms / 1000, source=str(source), metadata={**result.metadata, "device": result.device, "duration_ms": result.duration_ms})

    def _error(self, source: str | Path, config: PaddleOCRConfig, message: str) -> OCRResult:
        return OCRResult(provider=str(self.name), language=config.language, source=str(source), errors=[message], metadata={"device": self._device, "fallback": self._fallback, "error_type": "ocr.provider.failed"})
