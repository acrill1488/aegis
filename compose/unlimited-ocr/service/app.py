from __future__ import annotations

import os
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", os.environ["PYTORCH_ALLOC_CONF"])

import gc
import json
import re
import shutil
import tempfile
import time
from contextlib import nullcontext
from pathlib import Path
from threading import Lock
from typing import Any

import psutil
import torch
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
from runtime_config import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    LoadProfile,
    env_bool,
    env_value,
    normalize_generation_kwargs,
    resolve_device,
    resolve_dtype,
    resolve_load_profile,
    resolve_gpu_memory_limit_gb,
    resolve_max_image_side,
    resolve_model_placement,
)

MODEL_ID = os.getenv("AEGIS_UNLIMITED_OCR_MODEL_ID", DEFAULT_MODEL_ID)
MODEL_REVISION = os.getenv(
    "AEGIS_UNLIMITED_OCR_MODEL_REVISION",
    DEFAULT_MODEL_REVISION,
)
OUTPUT_DIR = Path(os.getenv("AEGIS_UNLIMITED_OCR_OUTPUT_DIR", "/output"))
LAZY_LOAD = os.getenv("AEGIS_UNLIMITED_OCR_LAZY_LOAD", "1").lower() not in {"0", "false", "no"}
LOAD_PROFILE = os.getenv("AEGIS_UNLIMITED_OCR_LOAD_PROFILE", "low_vram").lower()
OFFLOAD_FOLDER = Path(os.getenv("AEGIS_UNLIMITED_OCR_OFFLOAD_FOLDER", "/cache/offload"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OFFLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AEGIS Unlimited-OCR Service")
_state: dict[str, Any] = {
    "model": None,
    "tokenizer": None,
    "model_loaded": False,
    "load_time": None,
    "load_error": None,
    "load_profile": LOAD_PROFILE,
    "warmup_success": False,
    "inference_verified": False,
    "last_inference_ok": False,
    "last_inference_error": None,
    "last_inference_error_type": None,
    "last_inference_peak_vram_mb": None,
    "model_device_map": {},
    "model_structure": {},
    "device": None,
    "dtype": None,
    "vram_stages": {},
    "last_generation_debug": {},
    "last_recognition_debug": {},
}
_inference_lock = Lock()


@app.get("/health")
def health() -> dict[str, Any]:
    inference_ready = bool(_state["model_loaded"] and _state["load_error"] is None)
    return _status_payload() | {
        "status": "ok",
        "provider": "unlimited",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "service_alive": True,
        "model_loaded": _state["model_loaded"],
        "model_ready": _state["model_loaded"],
        "warmup_success": _state["warmup_success"],
        "inference_ready": inference_ready,
        "inference_verified": _state["inference_verified"],
        "gpu_detected": torch.cuda.is_available(),
        "recognition_ready": bool(_state["inference_verified"]),
        "load_error": _state["load_error"],
        "last_inference_ok": _state["last_inference_ok"],
        "last_inference_error": _state["last_inference_error"],
        "last_inference_error_type": _state["last_inference_error_type"],
    }


@app.get("/info")
def info() -> dict[str, Any]:
    return _status_payload() | {
        "provider": "unlimited",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_loaded": _state["model_loaded"],
        "inference_ready": bool(_state["model_loaded"] and _state["load_error"] is None),
        "inference_verified": _state["inference_verified"],
        "warmup_success": _state["warmup_success"],
        "load_time": _state["load_time"],
        "supported_formats": ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "pdf"],
        "languages": ["auto"],
        "gpu_detected": torch.cuda.is_available(),
    }


@app.post("/warmup")
def warmup() -> JSONResponse:
    started_at = time.monotonic()
    try:
        _, model = _load_model()
        structure = _inspect_loaded_model(model)
        if structure["meta_parameter_count"]:
            raise RuntimeError(
                f"Unlimited-OCR has {structure['meta_parameter_count']} parameters on the meta device"
            )
        _state["model_structure"] = structure
        _state["warmup_success"] = True
        return JSONResponse(
            content={
                "success": True,
                "provider": "unlimited",
                "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION,
                "model_loaded": _state["model_loaded"],
                "inference_ready": True,
                "inference_verified": _state["inference_verified"],
                "recognition_ready": _state["inference_verified"],
                "processing_time": time.monotonic() - started_at,
                "warnings": ["Inference is loaded but not smoke-test verified."],
                "errors": [],
                "metadata": {"model_id": MODEL_ID, "model_revision": MODEL_REVISION} | _status_payload(),
            }
        )
    except Exception as exc:
        error_type = "ocr.model.load_failed"
        _reset_model_state(
            load_error=str(exc),
            last_inference_error=str(exc),
            last_inference_error_type=error_type,
            last_inference_peak_vram_mb=_peak_vram_mb(),
        )
        _clear_cuda_cache()
        return _ocr_error_response(
            exc,
            language="auto",
            started_at=started_at,
            status_code=507 if _is_oom(exc) else 500,
            error_type="ocr.resource.exhausted" if _is_oom(exc) else error_type,
        )


@app.post("/unload")
def unload() -> dict[str, Any]:
    _reset_model_state()
    _clear_cuda_cache()
    return {
        "success": True,
        "provider": "unlimited",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_loaded": False,
        "inference_ready": False,
        "inference_verified": False,
        "warmup_success": False,
        "metadata": _status_payload(),
    }


@app.post("/ocr/image")
def ocr_image(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    options: str = Form("{}"),
) -> JSONResponse:
    return _run_uploaded_file(file, language=language, options=options, is_pdf=False)


@app.post("/ocr/pdf")
def ocr_pdf(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    options: str = Form("{}"),
) -> JSONResponse:
    return _run_uploaded_file(file, language=language, options=options, is_pdf=True)


def _run_uploaded_file(file: UploadFile, *, language: str, options: str, is_pdf: bool) -> JSONResponse:
    if not _inference_lock.acquire(blocking=False):
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "provider": "unlimited",
                "language": language,
                "pages": [],
                "text": "",
                "blocks": [],
                "tables": [],
                "confidence": None,
                "processing_time": 0.0,
                "warnings": [],
                "metadata": {"model_id": MODEL_ID},
                "errors": ["Unlimited-OCR is already processing another request."],
            },
        )
    started_at = time.monotonic()
    tmp_dir = Path(tempfile.mkdtemp(prefix="aegis_unlimited_ocr_"))
    text = None
    try:
        suffix = Path(file.filename or ("input.pdf" if is_pdf else "input.png")).suffix
        source_path = tmp_dir / f"source{suffix}"
        with source_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        request_options = _parse_options(options)
        _prepare_inference_memory()
        _record_vram_stage("before_inference")
        text, recognition_debug = _infer(source_path, is_pdf=is_pdf, options=request_options)
        _state["last_recognition_debug"] = recognition_debug
        validation = _validate_recognition(text)
        recognition_debug.update(validation)
        if not validation["recognition_valid"]:
            raise RuntimeError(
                "Unlimited-OCR returned semantically invalid text: "
                + str(validation["recognition_validation_reason"])
            )
        _state["inference_verified"] = True
        _state["last_inference_ok"] = True
        _state["last_inference_error"] = None
        _state["last_inference_error_type"] = None
        _state["last_inference_peak_vram_mb"] = _peak_vram_mb()
        _record_vram_stage("peak", peak=True)
        del request_options
        _cleanup_after_request()
        _record_vram_stage("after_request")
        processing_time = time.monotonic() - started_at
        return JSONResponse(
            content={
                "success": True,
                "provider": "unlimited",
                "language": language,
                "pages": [{"page": 1, "text": text}] if text else [],
                "text": text,
                "blocks": [{"page": 1, "role": "text", "text": text}] if text else [],
                "tables": [],
                "confidence": None,
                "processing_time": processing_time,
                "warnings": [],
                "metadata": {
                    "model_id": MODEL_ID,
                    "model_revision": MODEL_REVISION,
                    "load_time": _state["load_time"],
                    "gpu_detected": torch.cuda.is_available(),
                    **recognition_debug,
                    **_status_payload(),
                },
            }
        )
    except Exception as exc:
        error_type = _classify_error(exc)
        peak_vram_mb = _peak_vram_mb()
        _reset_model_state(
            last_inference_error=str(exc),
            last_inference_error_type=error_type,
            last_inference_peak_vram_mb=peak_vram_mb,
        )
        _clear_cuda_cache()
        return _ocr_error_response(
            exc,
            language=language,
            started_at=started_at,
            status_code=507 if error_type == "ocr.resource.exhausted" else 500,
            error_type=error_type,
        )
    finally:
        del text
        _cleanup_after_request()
        _inference_lock.release()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _load_model() -> tuple[Any, Any]:
    if _state["model_loaded"]:
        return _state["tokenizer"], _state["model"]
    started_at = time.monotonic()
    try:
        from transformers import AutoModel, AutoTokenizer

        profile = _load_profile()
        device = resolve_device(cuda_available=torch.cuda.is_available(), profile=profile)
        dtype_name = resolve_dtype(profile, device=device)
        _state["device"] = device
        _state["dtype"] = dtype_name
        _record_vram_stage("before_model_load")
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            revision=MODEL_REVISION,
        )
        load_kwargs: dict[str, Any] = {
            "trust_remote_code": True,
            "revision": MODEL_REVISION,
            "use_safetensors": True,
            "low_cpu_mem_usage": True,
        }
        dtype = _torch_dtype(dtype_name)
        if dtype is not None:
            load_kwargs["torch_dtype"] = dtype
        load_kwargs.update(_model_placement_config(profile=profile, device=device))
        if _cpu_offload_enabled() and device == "cuda":
            load_kwargs["offload_folder"] = str(OFFLOAD_FOLDER)
            load_kwargs["offload_state_dict"] = True
        model = AutoModel.from_pretrained(MODEL_ID, **load_kwargs)
        model = model.eval()
        if hasattr(model, "config"):
            model.config.use_cache = profile.use_cache
            model.config.output_attentions = False
            model.config.output_hidden_states = False
        _install_memory_safe_generate(model, use_cache=profile.use_cache)
        _record_vram_stage("after_model_load")
        _state.update(
            {
                "tokenizer": tokenizer,
                "model": model,
                "model_loaded": True,
                "load_time": time.monotonic() - started_at,
                "load_error": None,
                "load_profile": profile.name,
                "model_device_map": _summarize_device_map(getattr(model, "hf_device_map", None)),
                "model_structure": _inspect_loaded_model(model),
            }
        )
        return tokenizer, model
    except Exception as exc:
        _reset_model_state(load_error=str(exc))
        _clear_cuda_cache()
        raise


def _model_placement_config(*, profile: LoadProfile, device: str) -> dict[str, object]:
    return resolve_model_placement(
        profile,
        device=device,
        cuda_available=torch.cuda.is_available(),
        cpu_offload=_cpu_offload_enabled(),
        available_ram_bytes=psutil.virtual_memory().available,
    )


def _reset_model_state(
    load_error: str | None = None,
    last_inference_error: str | None = None,
    last_inference_error_type: str | None = None,
    last_inference_peak_vram_mb: int | None = None,
) -> None:
    _state.update(
        {
            "model": None,
            "tokenizer": None,
            "model_loaded": False,
            "load_time": None,
            "load_error": load_error,
            "warmup_success": False,
            "inference_verified": False,
            "last_inference_ok": False,
            "last_inference_error": last_inference_error,
            "last_inference_error_type": last_inference_error_type,
            "last_inference_peak_vram_mb": last_inference_peak_vram_mb,
            "model_device_map": {},
            "model_structure": {},
        }
    )


def _clear_cuda_cache() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass


def _prepare_inference_memory() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.reset_peak_memory_stats()
        except Exception:
            pass


def _cleanup_after_request() -> None:
    gc.collect()
    if _empty_cache_after_request() and torch.cuda.is_available():
        torch.cuda.empty_cache()


def _cpu_offload_enabled() -> bool:
    return env_bool("AEGIS_OCR_CPU_OFFLOAD", "AEGIS_UNLIMITED_OCR_CPU_OFFLOAD", True)


def _empty_cache_after_request() -> bool:
    return env_bool("AEGIS_OCR_EMPTY_CACHE_AFTER_REQUEST", None, True)


def _load_profile() -> LoadProfile:
    return resolve_load_profile(os.getenv("AEGIS_UNLIMITED_OCR_LOAD_PROFILE", LOAD_PROFILE))


def _torch_dtype(name: str) -> Any:
    if name == "auto":
        return "auto"
    if name == "float16":
        return torch.float16
    if name == "bfloat16":
        return torch.bfloat16
    if name == "float32":
        return torch.float32
    return None


def _parse_options(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _peak_vram_mb() -> int | None:
    if not torch.cuda.is_available():
        return None
    try:
        return int(torch.cuda.max_memory_allocated(0) / 1024**2)
    except Exception:
        return None


def _record_vram_stage(name: str, *, peak: bool = False) -> dict[str, Any]:
    memory = _gpu_memory_payload()
    if peak:
        memory["gpu_peak_allocated_mb"] = _peak_vram_mb()
    _state.setdefault("vram_stages", {})[name] = memory
    print(
        json.dumps(
            {
                "event": "ocr.vram",
                "stage": name,
                "device": _state.get("device"),
                "dtype": _state.get("dtype"),
                **memory,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return memory


def _gpu_memory_payload() -> dict[str, Any]:
    if not torch.cuda.is_available():
        return {
            "gpu_total_mb": None,
            "gpu_allocated_mb": None,
            "gpu_reserved_mb": None,
            "gpu_free_mb": None,
        }
    total = torch.cuda.get_device_properties(0).total_memory
    free = None
    try:
        free, total = torch.cuda.mem_get_info(0)
    except Exception:
        pass
    return {
        "gpu_total_mb": int(total / 1024**2),
        "gpu_allocated_mb": int(torch.cuda.memory_allocated(0) / 1024**2),
        "gpu_reserved_mb": int(torch.cuda.memory_reserved(0) / 1024**2),
        "gpu_free_mb": int(free / 1024**2) if free is not None else None,
    }


def _ram_payload() -> dict[str, int]:
    memory = psutil.virtual_memory()
    return {
        "ram_total_mb": int(memory.total / 1024**2),
        "ram_available_mb": int(memory.available / 1024**2),
    }


def _status_payload() -> dict[str, Any]:
    structure = _state.get("model_structure") or {}
    parameter_counts = structure.get("parameter_count_by_device") or {}
    module_counts = structure.get("module_count_by_device") or {}
    return {
        "load_profile": _load_profile().name,
        **_gpu_memory_payload(),
        **_ram_payload(),
        "model_device_map": _state.get("model_device_map") or {},
        "resolved_device_map": _state.get("model_device_map") or {},
        "model_structure": structure,
        "cuda_parameter_count": int(parameter_counts.get("cuda", 0)),
        "cpu_parameter_count": int(parameter_counts.get("cpu", 0)),
        "cuda_module_count": int(module_counts.get("cuda", 0)),
        "cpu_module_count": int(module_counts.get("cpu", 0)),
        "device": _state.get("device"),
        "dtype": _state.get("dtype"),
        "offload_enabled": bool(_cpu_offload_enabled()),
        "offload_active": bool(structure.get("offload_active", False)),
        "gpu_memory_limit_gb": resolve_gpu_memory_limit_gb(_load_profile()),
        "offload_folder": str(OFFLOAD_FOLDER),
        "last_inference_peak_vram_mb": _state.get("last_inference_peak_vram_mb"),
        "last_inference_error": _state.get("last_inference_error"),
        "vram_stages": _state.get("vram_stages") or {},
        **dict(_state.get("last_recognition_debug") or {}),
    }


def _install_memory_safe_generate(model: Any, *, use_cache: bool) -> None:
    """Override only generation flags that retain large CUDA outputs.

    The pinned remote model passes use_cache=True directly from infer(), so setting
    model.config alone is insufficient. Keeping this adapter at the service boundary
    avoids modifying the downloaded remote-code package or the public HTTP contract.
    """
    original_generate = model.generate
    original_prepare_inputs = getattr(model, "prepare_inputs_for_generation", None)

    if callable(original_prepare_inputs):
        def memory_safe_prepare_inputs(*args: Any, **kwargs: Any) -> Any:
            input_ids = kwargs.get("input_ids")
            if input_ids is None and args:
                input_ids = args[0]
            image_mask = kwargs.get("images_seq_mask")
            if (
                not use_cache
                and input_ids is not None
                and image_mask is not None
                and image_mask.shape[-1] < input_ids.shape[-1]
            ):
                padding = input_ids.shape[-1] - image_mask.shape[-1]
                kwargs["images_seq_mask"] = torch.nn.functional.pad(
                    image_mask, (0, padding), value=False
                )
            return original_prepare_inputs(*args, **kwargs)

        model.prepare_inputs_for_generation = memory_safe_prepare_inputs

    def memory_safe_generate(*args: Any, **kwargs: Any) -> Any:
        kwargs = normalize_generation_kwargs(kwargs, use_cache=use_cache)
        _record_vram_stage("after_preprocessing")
        input_ids = kwargs.get("input_ids")
        result = original_generate(*args, **kwargs)
        sequences = getattr(result, "sequences", result)
        input_count = int(input_ids.shape[-1]) if hasattr(input_ids, "shape") else 0
        output_count = int(sequences.shape[-1]) if hasattr(sequences, "shape") else input_count
        generated = max(0, output_count - input_count)
        finish_reason = "length" if generated >= int(kwargs.get("max_new_tokens") or generated + 1) else "stop"
        _state["last_generation_debug"] = {
            "generated_token_count": generated,
            "finish_reason": finish_reason,
        }
        return result

    model.generate = memory_safe_generate


def _summarize_device_map(device_map: Any) -> dict[str, Any]:
    if not isinstance(device_map, dict):
        return {}
    summary: dict[str, Any] = {"total_entries": len(device_map), "devices": {}}
    examples: list[str] = []
    for module_name, device in device_map.items():
        device_key = str(device)
        summary["devices"][device_key] = int(summary["devices"].get(device_key, 0)) + 1
        if len(examples) < 12:
            examples.append(f"{module_name}:{device_key}")
    summary["examples"] = examples
    return summary


def _inspect_loaded_model(model: Any) -> dict[str, Any]:
    """Summarize the real remote-code model tree without assuming module names."""
    module_names = [name for name, _ in model.named_modules()]
    parameters = list(model.named_parameters())
    meta_parameters = [name for name, value in parameters if value.device.type == "meta"]
    parameter_devices: dict[str, int] = {"cuda": 0, "cpu": 0}
    for _, value in parameters:
        if value.device.type in parameter_devices:
            parameter_devices[value.device.type] += value.numel()
    module_devices: dict[str, int] = {"cuda": 0, "cpu": 0}
    for _, module in model.named_modules():
        direct_devices = {value.device.type for value in module.parameters(recurse=False)}
        for device_type in direct_devices & module_devices.keys():
            module_devices[device_type] += 1
    return {
        "module_count": len(module_names),
        "top_level_modules": [name for name in module_names if name and "." not in name][:24],
        "meta_parameter_count": len(meta_parameters),
        "meta_parameter_examples": meta_parameters[:12],
        "parameter_count_by_device": parameter_devices,
        "module_count_by_device": module_devices,
        "offload_active": bool(parameter_devices["cuda"] and parameter_devices["cpu"]),
    }


def _resize_image_for_inference(source_path: Path, max_side: int) -> Path:
    if max_side <= 0:
        return source_path
    with Image.open(source_path) as image:
        width, height = image.size
        largest_side = max(width, height)
        if largest_side <= max_side:
            return source_path
        scale = max_side / float(largest_side)
        resized = image.resize((max(1, int(width * scale)), max(1, int(height * scale))))
        target = source_path.with_name(f"{source_path.stem}-max{max_side}.png")
        resized.save(target)
        return target


def _is_oom(exc: Exception) -> bool:
    text = str(exc).lower()
    return "out of memory" in text or "cuda oom" in text or "cuda error" in text and "memory" in text


def _classify_error(exc: Exception) -> str:
    if _is_oom(exc):
        return "ocr.resource.exhausted"
    if _state.get("load_error"):
        return "ocr.model.load_failed"
    if "semantically invalid" in str(exc).lower():
        return "ocr.recognition.invalid"
    return "ocr.inference.failed"


def _ocr_error_response(
    error: Exception | str,
    *,
    language: str,
    started_at: float,
    status_code: int,
    error_type: str | None = None,
) -> JSONResponse:
    message = str(error)
    error_type = error_type or (
        _classify_error(error) if isinstance(error, Exception) else "ocr.inference.failed"
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "provider": "unlimited",
            "language": language,
            "pages": [],
            "text": "",
            "blocks": [],
            "tables": [],
            "figures": [],
            "confidence": None,
            "processing_time": time.monotonic() - started_at,
            "warnings": ["model state reset"] if error_type == "ocr.resource.exhausted" else [],
            "metadata": {
                "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION,
                "error_type": error_type,
                **_status_payload(),
            },
            "errors": [message],
        },
    )


def _infer(source_path: Path, *, is_pdf: bool, options: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    tokenizer, model = _load_model()
    profile = _load_profile()
    options = options or {}
    output_path = OUTPUT_DIR / f"run-{int(time.time())}"
    output_path.mkdir(parents=True, exist_ok=True)
    max_length = int(options.get("max_length") or os.getenv("AEGIS_UNLIMITED_OCR_MAX_LENGTH", profile.max_length))
    configured_max_side = resolve_max_image_side(profile)
    requested_max_side = int(options.get("max_image_side") or configured_max_side)
    if requested_max_side <= 0:
        raise ValueError("max_image_side request option must be greater than zero")
    max_image_side = min(requested_max_side, configured_max_side)
    dtype_name = str(_state.get("dtype") or resolve_dtype(profile, device=_state.get("device") or "cpu"))
    autocast_dtype = _torch_dtype(dtype_name)
    autocast = (
        torch.autocast(device_type="cuda", dtype=autocast_dtype)
        if torch.cuda.is_available() and autocast_dtype in {torch.float16, torch.bfloat16}
        else nullcontext()
    )
    source_for_infer = source_path if is_pdf else _resize_image_for_inference(source_path, max_image_side)
    result = None
    image_files: list[Path] = []
    if is_pdf:
        image_files = _pdf_to_images(source_path, max_side=max_image_side)
        try:
            with torch.inference_mode(), autocast:
                result = model.infer_multi(
                    tokenizer,
                    prompt="<image>Multi page parsing.",
                    image_files=[str(path) for path in image_files],
                    output_path=str(output_path),
                    image_size=max_image_side,
                    max_length=max_length,
                    no_repeat_ngram_size=35,
                    ngram_window=1024,
                    save_results=True,
                )
        finally:
            if image_files:
                shutil.rmtree(image_files[0].parent, ignore_errors=True)
    else:
        image_size = min(max_image_side, int(options.get("image_size") or 640))
        sources = [source_for_infer]
        tile_dir = None
        if options.get("tile_ocr"):
            tile_dir = Path(tempfile.mkdtemp(prefix="ocr_tiles_"))
            sources = (
                _focus_crops(source_path, tile_dir)
                if options.get("focus_crop")
                else _vertical_tiles(source_path, tile_dir, tile_height=max_image_side)
            )
        raw_results: list[Any] = []
        token_count = 0
        finish_reasons: list[str] = []
        try:
            for item in sources:
                with torch.inference_mode(), autocast:
                    raw_results.append(model.infer(
                        tokenizer,
                        prompt=str(options.get("prompt") or "<image>Free OCR."),
                        image_file=str(item),
                        output_path=str(output_path),
                        base_size=max_image_side,
                        image_size=image_size,
                        crop_mode=not bool(options.get("tile_ocr")),
                        max_length=max_length,
                        no_repeat_ngram_size=35,
                        ngram_window=128,
                        save_results=False,
                        eval_mode=True,
                    ))
                generation = dict(_state.get("last_generation_debug") or {})
                token_count += int(generation.get("generated_token_count") or 0)
                if generation.get("finish_reason"):
                    finish_reasons.append(str(generation["finish_reason"]))
            result = raw_results[0] if len(raw_results) == 1 else tuple(raw_results)
            _state["last_generation_debug"] = {
                "generated_token_count": token_count,
                "finish_reason": "length" if "length" in finish_reasons else "stop",
            }
        finally:
            if tile_dir is not None:
                shutil.rmtree(tile_dir, ignore_errors=True)
    text, debug = _extract_text(result, output_path)
    debug.update(dict(_state.get("last_generation_debug") or {}))
    debug.update({
        "inference_prompt": str(options.get("prompt") or "<image>Free OCR."),
        "inference_mode": "focus_crop" if options.get("focus_crop") else ("tiles" if options.get("tile_ocr") else "single"),
        "max_new_tokens": max_length,
        "crop_mode": not bool(options.get("tile_ocr")),
    })
    text = _normalize_ocr_text(text)
    del result, image_files
    return text, debug


def _pdf_to_images(pdf_path: Path, dpi: int = 300, max_side: int = 1024) -> list[Path]:
    import fitz

    doc = fitz.open(pdf_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="pdf_ocr_"))
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    paths: list[Path] = []
    for index, page in enumerate(doc):
        output = tmp_dir / f"page_{index + 1:04d}.png"
        page.get_pixmap(matrix=matrix).save(output)
        paths.append(_resize_image_for_inference(output, max_side))
    doc.close()
    return paths


def _extract_text(result: Any, output_path: Path) -> tuple[str, dict[str, Any]]:
    debug = {
        "raw_output_type": type(result).__name__,
        "raw_output_repr": repr(result)[:4000],
        "raw_text_before_normalization": "",
        "raw_output_available": result is not None,
    }
    if isinstance(result, str):
        debug["raw_text_before_normalization"] = result[:16000]
        return result, debug
    if isinstance(result, tuple) and result and isinstance(result[0], str):
        raw = "\n".join(item for item in result if isinstance(item, str))
        debug["raw_text_before_normalization"] = raw[:16000]
        return raw, debug
    if isinstance(result, dict):
        for key in ("text", "result", "content"):
            value = result.get(key)
            if isinstance(value, str):
                debug["raw_text_before_normalization"] = value[:16000]
                return value, debug
    for path in sorted(output_path.rglob("*")):
        if path.suffix.lower() in {".txt", ".md"}:
            value = path.read_text(encoding="utf-8", errors="replace")
            debug["raw_text_before_normalization"] = value[:16000]
            return value, debug
    value = "" if result is None else str(result)
    debug["raw_text_before_normalization"] = value[:16000]
    return value, debug


def _validate_recognition(text: str) -> dict[str, Any]:
    markdown_images = len(re.findall(r"!\[[^\]]*\]\([^)]*\)", text, flags=re.I))
    visible = re.sub(r"<\|det\|>\s*(?:image|img|figure)\s*\[[^\]]*\]\s*<\|/det\|>", " ", text, flags=re.I)
    visible = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", visible, flags=re.I)
    visible = re.sub(r"<img\b[^>]*>", " ", visible, flags=re.I)
    visible = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", visible, flags=re.I)
    visible = re.sub(r"<\|[^|>]+\|>|\[(?:image|img|placeholder|unreadable)\]", " ", visible, flags=re.I)
    visible = re.sub(r"\[\s*\d+(?:\s*,\s*\d+){3}\s*\]", " ", visible)
    visible = re.sub(r"(?:^|\s)[\w./\\-]+\.(?:png|jpe?g|webp|bmp|tiff?)(?:\s|$)", " ", visible, flags=re.I)
    visible_length = len(re.sub(r"\s+", "", visible))
    reason = "visible_text_present" if visible_length else ("markdown_images_only" if markdown_images else "no_visible_text")
    return {
        "recognition_valid": visible_length > 0,
        "recognition_validation_reason": reason,
        "visible_text_length": visible_length,
        "markdown_image_count": markdown_images,
    }


def _vertical_tiles(source_path: Path, target_dir: Path, *, tile_height: int) -> list[Path]:
    with Image.open(source_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        tile_height = max(256, min(int(tile_height), height))
        overlap = min(96, tile_height // 5)
        step = max(1, tile_height - overlap)
        starts = list(range(0, max(1, height - tile_height + 1), step))
        final_start = max(0, height - tile_height)
        if not starts or starts[-1] != final_start:
            starts.append(final_start)
        paths: list[Path] = []
        for index, top in enumerate(starts):
            path = target_dir / f"tile-{index:02d}.png"
            image.crop((0, top, width, min(height, top + tile_height))).save(path)
            paths.append(path)
        return paths


def _focus_crops(source_path: Path, target_dir: Path) -> list[Path]:
    """Preserve native pixels for the central document/dialog region."""
    with Image.open(source_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        boxes = [
            (int(width * 0.10), int(height * 0.27), int(width * 0.90), int(height * 0.66)),
            (int(width * 0.08), int(height * 0.18), int(width * 0.92), int(height * 0.50)),
            (int(width * 0.08), int(height * 0.48), int(width * 0.92), int(height * 0.78)),
        ]
        paths = []
        for index, box in enumerate(boxes):
            path = target_dir / f"focus-{index:02d}.png"
            image.crop(box).save(path)
            paths.append(path)
        return paths


def _normalize_ocr_text(text: str) -> str:
    normalized = re.sub(r"<\|det\|>\s*(?:image|img|figure)\s*\[[^\]]*\]\s*<\|/det\|>", " ", text, flags=re.I)
    normalized = re.sub(r"<\|/?det\|>(?:[^\n<]*?\[[^\]]*\])?", "", normalized, flags=re.I)
    normalized = re.sub(r"\[(?:Unreadable|Image|Placeholder)\]", " ", normalized, flags=re.I)
    normalized = re.sub(r"<\|[^|>]+\|>", " ", normalized)
    normalized = "\n".join(line.strip() for line in normalized.splitlines() if line.strip())
    return normalized.strip()
