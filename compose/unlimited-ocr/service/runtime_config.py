from __future__ import annotations

import os
import math
from dataclasses import dataclass

DEFAULT_MODEL_ID = "baidu/Unlimited-OCR"
DEFAULT_MODEL_REVISION = "ee63731b6461c8afcdcc7b15352e7d2ffecc2ead"


@dataclass(frozen=True)
class LoadProfile:
    name: str
    dtype: str
    gpu_memory_limit_gb: float | None
    offload: bool
    max_image_side: int
    max_length: int
    use_cache: bool


SUPPORTED_DEVICES = {"auto", "cuda", "cpu"}
SUPPORTED_DTYPES = {"auto", "float16", "bfloat16", "float32"}


LOAD_PROFILES = {
    "balanced": LoadProfile("balanced", "auto", None, True, 1024, 1024, False),
    "low_vram": LoadProfile("low_vram", "bfloat16", 6.5, True, 1024, 256, False),
    "cpu": LoadProfile("cpu", "float32", None, False, 1024, 256, False),
}


def resolve_load_profile(name: str | None = None) -> LoadProfile:
    requested = (name or os.getenv("AEGIS_UNLIMITED_OCR_LOAD_PROFILE") or "low_vram").lower()
    return LOAD_PROFILES.get(requested, LOAD_PROFILES["low_vram"])


def resolve_gpu_memory_limit_gb(profile: LoadProfile) -> float | None:
    raw = os.getenv("AEGIS_OCR_GPU_MEMORY_LIMIT_GB")
    if raw is not None:
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError("AEGIS_OCR_GPU_MEMORY_LIMIT_GB must be a number") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("AEGIS_OCR_GPU_MEMORY_LIMIT_GB must be greater than zero")
        return value

    # Retain the old service-specific setting as a compatibility alias.
    legacy = os.getenv("AEGIS_UNLIMITED_OCR_MAX_GPU_MEMORY")
    if legacy is not None:
        normalized = legacy.strip()
        if normalized.lower().endswith("gib"):
            normalized = normalized[:-3]
        try:
            value = float(normalized)
        except ValueError as exc:
            raise ValueError("AEGIS_UNLIMITED_OCR_MAX_GPU_MEMORY must be expressed in GiB") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("AEGIS_UNLIMITED_OCR_MAX_GPU_MEMORY must be greater than zero")
        return value
    return profile.gpu_memory_limit_gb


def safe_cpu_memory_limit_gb(available_ram_bytes: int) -> float:
    """Leave 15% of currently available RAM outside the Transformers budget."""
    available_gib = max(0.0, available_ram_bytes / 1024**3)
    safe_gib = math.floor(available_gib * 0.85 * 10) / 10
    if safe_gib <= 0:
        raise RuntimeError("Insufficient available RAM for CPU offload")
    return safe_gib


def format_gib(value: float) -> str:
    return f"{value:g}GiB"


def resolve_max_memory(
    profile: LoadProfile,
    *,
    cuda_available: bool,
    cpu_offload: bool,
    available_ram_bytes: int,
) -> dict[int | str, str] | None:
    if not cuda_available or profile.name == "cpu" or not cpu_offload:
        return None
    gpu_limit = resolve_gpu_memory_limit_gb(profile)
    if gpu_limit is None:
        return None
    memory: dict[int | str, str] = {0: format_gib(gpu_limit)}
    legacy_cpu = os.getenv("AEGIS_UNLIMITED_OCR_MAX_CPU_MEMORY")
    memory["cpu"] = legacy_cpu or format_gib(safe_cpu_memory_limit_gb(available_ram_bytes))
    return memory


def resolve_model_placement(
    profile: LoadProfile,
    *,
    device: str,
    cuda_available: bool,
    cpu_offload: bool,
    available_ram_bytes: int,
) -> dict[str, object]:
    if device == "cpu":
        return {"device_map": {"": "cpu"}}
    if not cpu_offload:
        return {"device_map": {"": 0}}
    placement: dict[str, object] = {
        "device_map": "auto",
        "low_cpu_mem_usage": True,
        "offload_state_dict": True,
    }
    max_memory = resolve_max_memory(
        profile,
        cuda_available=cuda_available,
        cpu_offload=True,
        available_ram_bytes=available_ram_bytes,
    )
    if max_memory is not None:
        placement["max_memory"] = max_memory
    return placement


def normalize_generation_kwargs(kwargs: dict[str, object], *, use_cache: bool) -> dict[str, object]:
    """Apply memory-safe flags without imposing a generation limit of our own."""
    normalized = dict(kwargs)
    max_length = normalized.pop("max_length", None)
    if max_length is not None and "max_new_tokens" not in normalized:
        normalized["max_new_tokens"] = max_length
    normalized["use_cache"] = use_cache
    normalized["output_attentions"] = False
    normalized["output_hidden_states"] = False
    normalized["output_scores"] = False
    normalized["return_dict_in_generate"] = False
    return normalized


def env_value(name: str, legacy_name: str | None, default: str) -> str:
    """Read the public OCR setting, retaining the service-specific alias."""
    value = os.getenv(name)
    if value is None and legacy_name:
        value = os.getenv(legacy_name)
    return default if value is None else value


def env_bool(name: str, legacy_name: str | None, default: bool) -> bool:
    value = env_value(name, legacy_name, "1" if default else "0")
    return value.strip().lower() not in {"0", "false", "no", "off"}


def resolve_device(*, cuda_available: bool, profile: LoadProfile) -> str:
    default = "cpu" if profile.name == "cpu" else "auto"
    requested = env_value("AEGIS_OCR_DEVICE", None, default).strip().lower()
    if requested not in SUPPORTED_DEVICES:
        raise ValueError(f"Unsupported AEGIS_OCR_DEVICE={requested!r}")
    if requested == "cuda" and not cuda_available:
        raise RuntimeError("AEGIS_OCR_DEVICE=cuda requested, but CUDA is unavailable")
    if requested == "auto":
        return "cuda" if cuda_available and profile.name != "cpu" else "cpu"
    return requested


def resolve_dtype(profile: LoadProfile, *, device: str) -> str:
    default = "float32" if device == "cpu" else profile.dtype
    requested = env_value("AEGIS_OCR_DTYPE", None, default).strip().lower()
    if requested not in SUPPORTED_DTYPES:
        raise ValueError(f"Unsupported AEGIS_OCR_DTYPE={requested!r}")
    if device == "cpu" and requested == "float16":
        raise ValueError("AEGIS_OCR_DTYPE=float16 is not supported with AEGIS_OCR_DEVICE=cpu")
    return requested


def resolve_max_image_side(profile: LoadProfile) -> int:
    raw = env_value(
        "AEGIS_OCR_MAX_IMAGE_SIDE",
        "AEGIS_UNLIMITED_OCR_MAX_IMAGE_SIDE",
        str(profile.max_image_side),
    )
    value = int(raw)
    if value <= 0:
        raise ValueError("AEGIS_OCR_MAX_IMAGE_SIDE must be greater than zero")
    return value
