"""Thin, lazy adapter over the official FlagEmbedding BGE-M3 API."""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import math
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from threading import Lock
from typing import Any

from aegis.embeddings.models import EmbeddingRequest, EmbeddingResult, EmbeddingVector
from aegis.embeddings.errors import EmbeddingError

from .config import BGEM3Config
from .errors import (
    EmbeddingDimensionError,
    EmbeddingInitializationError,
    EmbeddingProviderDisabledError,
    EmbeddingProviderMissingError,
    EmbeddingTimeoutError,
)
from .health import ProviderHealth

INSTALL_MESSAGE = "BGE-M3 provider is not installed. Run: aegis install bge-m3"


class BGEM3Provider:
    """Lifecycle and normalization boundary around ``FlagEmbedding.BGEM3FlagModel``."""

    id = "bge-m3"

    def __init__(self, config: BGEM3Config | None = None, *, config_path: str | Path | None = None):
        self.config = config or BGEM3Config.load(config_path)
        self._models: dict[tuple[str, bool], Any] = {}
        self._initialization_error: str | None = None
        self._fallback: dict[str, str] | None = None
        self._lock = Lock()

    def is_available(self) -> bool:
        return self.config.enabled and importlib.util.find_spec("FlagEmbedding") is not None

    def health(self) -> ProviderHealth:
        cached = self._model_cached()
        if not self.config.enabled:
            return ProviderHealth(status="disabled", message="BGE-M3 provider is disabled", model_cached=cached)
        if importlib.util.find_spec("FlagEmbedding") is None:
            return ProviderHealth(message=INSTALL_MESSAGE, model_cached=cached)
        device = self._select_device(self.config.device)
        if self._initialization_error:
            return ProviderHealth(
                status="initialization failed", device=device, message=self._initialization_error,
                model_cached=cached, metadata=self._metadata(),
            )
        status = "GPU runtime available" if device == "gpu" else "CPU runtime available"
        if self.config.device == "gpu" and device != "gpu":
            status = "GPU requested but unavailable"
        if self._models:
            status = "healthy"
        return ProviderHealth(
            status=status, available=True, device=device, model_cached=cached,
            model_loaded=bool(self._models), metadata=self._metadata(),
        )

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        if not self.config.enabled:
            raise EmbeddingProviderDisabledError("BGE-M3 provider is disabled")
        if importlib.util.find_spec("FlagEmbedding") is None:
            raise EmbeddingProviderMissingError(INSTALL_MESSAGE)
        texts = request.texts if isinstance(request.texts, list) else [request.texts]
        config = self.config.with_overrides(
            device=request.device, batch_size=request.batch_size,
            normalize_embeddings=request.normalize,
        )
        requested_device = self._select_device(config.device)
        if config.device == "gpu" and requested_device == "cpu" and self._fallback is None:
            self._fallback = {
                "from": "gpu", "to": "cpu",
                "reason": "the installed PyTorch runtime does not report an available CUDA device",
            }
        model, effective_device = self._get_model(config, requested_device)
        started = time.monotonic()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bge-m3")
        future = executor.submit(
            model.encode, texts, batch_size=config.batch_size, max_length=config.max_length,
            return_dense=True, return_sparse=False, return_colbert_vecs=False,
        )
        try:
            native = future.result(timeout=config.timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise EmbeddingTimeoutError(
                f"BGE-M3 embedding timed out after {config.timeout_seconds:g} seconds"
            ) from exc
        except Exception as exc:
            raise EmbeddingError(f"BGE-M3 embedding failed: {exc}") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        vectors = self._normalize_output(native, texts, config.normalize_embeddings)
        duration_ms = (time.monotonic() - started) * 1000
        dimensions = vectors[0].dimensions
        warnings: list[str] = []
        if self._fallback:
            warnings.append(f"GPU unavailable; used CPU: {self._fallback['reason']}")
        if any(len(text) > config.max_length for text in texts):
            warnings.append("Input may have been truncated by FlagEmbedding at the configured token max_length")
        return EmbeddingResult(
            provider=self.id, model=config.model_name, vectors=vectors, dimensions=dimensions,
            normalized=config.normalize_embeddings, device=effective_device, duration_ms=duration_ms,
            metadata={**dict(request.metadata), "batch_size": config.batch_size,
                      "max_length": config.max_length, "fallback": self._fallback,
                      "backend": "FlagEmbedding"}, warnings=warnings,
        )

    def _get_model(self, config: BGEM3Config, device: str) -> tuple[Any, str]:
        key = (device, config.normalize_embeddings)
        with self._lock:
            if key in self._models:
                return self._models[key], device
            try:
                model = self._create_model(config, device)
            except Exception as exc:
                if device != "gpu":
                    self._initialization_error = f"BGE-M3 model initialization failed: {exc}"
                    raise EmbeddingInitializationError(self._initialization_error) from exc
                self._fallback = {"from": "gpu", "to": "cpu", "reason": str(exc)}
                try:
                    device = "cpu"
                    key = (device, config.normalize_embeddings)
                    model = self._models.get(key) or self._create_model(config, device)
                except Exception as cpu_exc:
                    self._initialization_error = f"BGE-M3 initialization failed on GPU and CPU fallback: {cpu_exc}"
                    raise EmbeddingInitializationError(self._initialization_error) from cpu_exc
            self._models[key] = model
            return model, device

    @staticmethod
    def _create_model(config: BGEM3Config, device: str) -> Any:
        module = importlib.import_module("FlagEmbedding")
        return module.BGEM3FlagModel(
            config.model_name, normalize_embeddings=config.normalize_embeddings,
            use_fp16=config.use_fp16 and device == "gpu", devices="cuda" if device == "gpu" else "cpu",
            trust_remote_code=config.trust_remote_code, cache_dir=config.cache_dir,
        )

    @staticmethod
    def _gpu_runtime_available() -> bool:
        try:
            torch = importlib.import_module("torch")
            return bool(torch.cuda.is_available() and torch.cuda.device_count() > 0)
        except Exception:
            return False

    def _select_device(self, requested: str) -> str:
        if requested == "cpu":
            return "cpu"
        return "gpu" if self._gpu_runtime_available() else "cpu"

    def _normalize_output(self, native: Any, texts: list[str], normalized: bool) -> list[EmbeddingVector]:
        if not isinstance(native, dict) or "dense_vecs" not in native:
            raise EmbeddingDimensionError("FlagEmbedding response did not contain dense_vecs")
        dense = native["dense_vecs"]
        if hasattr(dense, "detach"):
            dense = dense.detach().cpu()
        if hasattr(dense, "tolist"):
            dense = dense.tolist()
        if len(texts) == 1 and dense and isinstance(dense[0], (int, float)):
            dense = [dense]
        if not isinstance(dense, list) or len(dense) != len(texts):
            raise EmbeddingDimensionError("FlagEmbedding returned a vector count that differs from the input")
        result: list[EmbeddingVector] = []
        dimensions: int | None = None
        for index, (text, value) in enumerate(zip(texts, dense, strict=True)):
            try:
                vector = [float(item) for item in value]
            except (TypeError, ValueError) as exc:
                raise EmbeddingDimensionError("FlagEmbedding returned an invalid dense vector") from exc
            if not vector or any(not math.isfinite(item) for item in vector):
                raise EmbeddingDimensionError("FlagEmbedding returned an empty or non-finite dense vector")
            if dimensions is None:
                dimensions = len(vector)
            elif len(vector) != dimensions:
                raise EmbeddingDimensionError("FlagEmbedding returned vectors with different dimensions")
            norm = math.sqrt(math.fsum(item * item for item in vector))
            if normalized and not math.isclose(norm, 1.0, rel_tol=1e-3, abs_tol=1e-3):
                raise EmbeddingDimensionError(
                    f"FlagEmbedding returned a non-normalized vector (norm={norm:.6g})"
                )
            result.append(EmbeddingVector(index=index, text=text, vector=vector, dimensions=len(vector), norm=norm))
        return result

    def _model_cached(self) -> bool | None:
        if self.config.cache_dir:
            root = Path(self.config.cache_dir)
        else:
            root = Path.home() / ".cache" / "huggingface" / "hub"
        model_dir = root / f"models--{self.config.model_name.replace('/', '--')}"
        if not root.exists():
            return False
        if not model_dir.exists():
            return False
        refs = model_dir / "refs" / "main"
        snapshots = model_dir / "snapshots"
        return refs.is_file() and snapshots.is_dir() and any(snapshots.iterdir())

    def _metadata(self) -> dict[str, Any]:
        try:
            version = importlib.metadata.version("FlagEmbedding")
        except importlib.metadata.PackageNotFoundError:
            version = None
        return {"package_version": version, "fallback": self._fallback}
