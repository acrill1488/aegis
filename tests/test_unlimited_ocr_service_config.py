from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_runtime_config():
    module_path = Path(__file__).resolve().parents[1] / "compose" / "unlimited-ocr" / "service" / "runtime_config.py"
    spec = importlib.util.spec_from_file_location("unlimited_ocr_runtime_config", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_low_vram_profile_uses_rtx_3050_memory_budget(monkeypatch):
    config = _load_runtime_config()
    monkeypatch.delenv("AEGIS_UNLIMITED_OCR_MAX_GPU_MEMORY", raising=False)
    monkeypatch.delenv("AEGIS_UNLIMITED_OCR_MAX_CPU_MEMORY", raising=False)
    monkeypatch.delenv("AEGIS_OCR_GPU_MEMORY_LIMIT_GB", raising=False)

    profile = config.resolve_load_profile("low_vram")

    assert profile.dtype == "bfloat16"
    assert profile.max_length == 256
    assert profile.use_cache is False
    assert config.resolve_gpu_memory_limit_gb(profile) == 6.5
    assert config.resolve_max_memory(
        profile, cuda_available=True, cpu_offload=True, available_ram_bytes=32 * 1024**3
    ) == {0: "6.5GiB", "cpu": "27.2GiB"}


def test_other_profiles_have_no_implicit_gpu_limit(monkeypatch):
    config = _load_runtime_config()
    monkeypatch.delenv("AEGIS_UNLIMITED_OCR_MAX_GPU_MEMORY", raising=False)
    monkeypatch.delenv("AEGIS_UNLIMITED_OCR_MAX_CPU_MEMORY", raising=False)

    monkeypatch.delenv("AEGIS_OCR_GPU_MEMORY_LIMIT_GB", raising=False)
    profile = config.resolve_load_profile("balanced")

    assert config.resolve_gpu_memory_limit_gb(profile) is None
    assert config.resolve_max_memory(
        profile, cuda_available=True, cpu_offload=True, available_ram_bytes=16 * 1024**3
    ) is None


def test_unknown_profile_falls_back_to_low_vram():
    config = _load_runtime_config()

    profile = config.resolve_load_profile("surprise")

    assert profile.name == "low_vram"
    assert profile.gpu_memory_limit_gb == 6.5


def test_public_gpu_limit_overrides_profile_and_legacy(monkeypatch):
    config = _load_runtime_config()
    profile = config.resolve_load_profile("low_vram")
    monkeypatch.setenv("AEGIS_OCR_GPU_MEMORY_LIMIT_GB", "5.75")
    monkeypatch.setenv("AEGIS_UNLIMITED_OCR_MAX_GPU_MEMORY", "6GiB")

    assert config.resolve_gpu_memory_limit_gb(profile) == 5.75
    assert config.resolve_max_memory(
        profile, cuda_available=True, cpu_offload=True, available_ram_bytes=8 * 1024**3
    ) == {0: "5.75GiB", "cpu": "6.8GiB"}


def test_max_memory_is_only_used_for_cuda_cpu_offload(monkeypatch):
    config = _load_runtime_config()
    profile = config.resolve_load_profile("low_vram")
    monkeypatch.delenv("AEGIS_OCR_GPU_MEMORY_LIMIT_GB", raising=False)
    monkeypatch.delenv("AEGIS_UNLIMITED_OCR_MAX_GPU_MEMORY", raising=False)

    assert config.resolve_max_memory(
        profile, cuda_available=True, cpu_offload=False, available_ram_bytes=8 * 1024**3
    ) is None
    assert config.resolve_max_memory(
        profile, cuda_available=False, cpu_offload=True, available_ram_bytes=8 * 1024**3
    ) is None


def test_cpu_offload_preserves_transformers_loading_flags(monkeypatch):
    config = _load_runtime_config()
    monkeypatch.delenv("AEGIS_OCR_GPU_MEMORY_LIMIT_GB", raising=False)
    monkeypatch.delenv("AEGIS_UNLIMITED_OCR_MAX_GPU_MEMORY", raising=False)

    placement = config.resolve_model_placement(
        config.resolve_load_profile("low_vram"),
        device="cuda",
        cuda_available=True,
        cpu_offload=True,
        available_ram_bytes=20 * 1024**3,
    )

    assert placement == {
        "device_map": "auto",
        "low_cpu_mem_usage": True,
        "offload_state_dict": True,
        "max_memory": {0: "6.5GiB", "cpu": "17GiB"},
    }


def test_generation_wrapper_converts_total_length_to_new_token_budget():
    config = _load_runtime_config()

    normalized = config.normalize_generation_kwargs(
        {"max_length": 256, "temperature": None}, use_cache=False
    )

    assert "max_length" not in normalized
    assert normalized["max_new_tokens"] == 256
    assert normalized["use_cache"] is False
    assert normalized["output_hidden_states"] is False
    assert normalized["output_attentions"] is False
    assert normalized["output_scores"] is False
    assert normalized["return_dict_in_generate"] is False


def test_generation_wrapper_does_not_add_limit_when_upstream_has_none():
    config = _load_runtime_config()

    normalized = config.normalize_generation_kwargs({"temperature": None}, use_cache=False)

    assert "max_length" not in normalized
    assert "max_new_tokens" not in normalized


def test_generation_wrapper_preserves_explicit_max_new_tokens():
    config = _load_runtime_config()

    normalized = config.normalize_generation_kwargs(
        {"max_length": 256, "max_new_tokens": 64}, use_cache=False
    )

    assert "max_length" not in normalized
    assert normalized["max_new_tokens"] == 64


def test_invalid_gpu_memory_limit_is_rejected(monkeypatch):
    config = _load_runtime_config()
    monkeypatch.setenv("AEGIS_OCR_GPU_MEMORY_LIMIT_GB", "unlimited")

    try:
        config.resolve_gpu_memory_limit_gb(config.resolve_load_profile("low_vram"))
    except ValueError as exc:
        assert "must be a number" in str(exc)
    else:
        raise AssertionError("invalid GPU memory limit must be rejected")


def test_public_ocr_environment_overrides_legacy_service_setting(monkeypatch):
    config = _load_runtime_config()
    profile = config.resolve_load_profile("low_vram")
    monkeypatch.setenv("AEGIS_OCR_MAX_IMAGE_SIDE", "896")
    monkeypatch.setenv("AEGIS_UNLIMITED_OCR_MAX_IMAGE_SIDE", "1024")
    monkeypatch.setenv("AEGIS_OCR_DTYPE", "bfloat16")
    monkeypatch.setenv("AEGIS_OCR_DEVICE", "cuda")

    assert config.resolve_max_image_side(profile) == 896
    assert config.resolve_device(cuda_available=True, profile=profile) == "cuda"
    assert config.resolve_dtype(profile, device="cuda") == "bfloat16"


def test_device_auto_falls_back_to_cpu_without_cuda(monkeypatch):
    config = _load_runtime_config()
    profile = config.resolve_load_profile("low_vram")
    monkeypatch.setenv("AEGIS_OCR_DEVICE", "auto")
    monkeypatch.delenv("AEGIS_OCR_DTYPE", raising=False)

    device = config.resolve_device(cuda_available=False, profile=profile)

    assert device == "cpu"
    assert config.resolve_dtype(profile, device=device) == "float32"


def test_invalid_public_ocr_configuration_is_rejected(monkeypatch):
    config = _load_runtime_config()
    profile = config.resolve_load_profile("low_vram")
    monkeypatch.setenv("AEGIS_OCR_MAX_IMAGE_SIDE", "0")

    try:
        config.resolve_max_image_side(profile)
    except ValueError as exc:
        assert "greater than zero" in str(exc)
    else:
        raise AssertionError("invalid max image side must be rejected")
