# Unlimited-OCR Provider Acceptance

Status: PASS (GreenBoost resource and OCR semantic acceptance, 2026-07-23)

## GreenBoost v1 provenance

- Upstream: `https://gitlab.com/IsolatedOctopi/greenboost.git`
- Branch: `main`
- Pinned commit: `e390fd027180ed36738971251efcb031ff401e36`
- License observed at the pinned commit: GPL-2.0-only with a separate commercial option.
- Integration boundary: the independent `aegis.greenboost` adapter; no upstream files were modified or copied into the OCR service.

## Rejected structural run

Input: `C:\Users\MK\Downloads\IMG_4728_1024.png` (576x1024).

- Pages: 1
- Blocks: 1
- Text length: 18
- Errors: 0 at the old structural gate, but semantic validation: FAIL
- Final attempt: `emergency`, `max_image_side=640`, effective size 360x640
- Initial/preflight free VRAM: 1295/7639 MiB
- Peak VRAM: 6476 MiB
- Attempts: normal 1024 (OOM), memory_saver 768 (OOM), emergency 640 (resource PASS, semantic FAIL)
- Result artifact: `F:\AI_WORKSPACE\ocr\results\20260723-195604-IMG_4728_1024-unlimited.json`
- VRAM stages and GreenBoost metadata are embedded in the result artifact.

The synthetic 640x220 image remains a separate smoke test and is not production acceptance.
The output `![](images/0.jpg)` is a Markdown image reference, not recognized text, and must never satisfy acceptance.

## Semantic production acceptance

Input: `C:\Users\MK\Downloads\IMG_4728_1024.png` (576x1024).

- Pages: 1
- Blocks: 1
- Text length: 673
- Visible text length: 565
- Errors: 0
- `recognition_valid`: true (`visible_text_present`)
- Markdown image count: 0
- Raw output: available, type `tuple`, bounded repr and pre-normalization text recorded
- Generated tokens: 768 across three focus crops; finish reason: `length`
- Final mode: emergency 640 with sequential native-resolution focus crops
- Peak VRAM: 6654 MiB
- Permanent result: `F:\AI_WORKSPACE\ocr\results\20260723-201806-IMG_4728_1024-unlimited.json`

Recognized evidence includes `просроченная задолженность`, `ООО "МАЙРЕСТ"`,
`3 000 000`, `1 799 206,90`, and `256 033,01`.

### Root cause and correction

The pinned upstream `infer(save_results=True)` decoded generation internally and
then replaced detected image regions with Markdown links while writing `result.md`;
it returned no raw value. AEGIS had therefore read only the post-processed file.
The service adapter now uses `eval_mode=True` and `save_results=False`, captures
raw generation before parsing, uses the upstream plain-text `Free OCR.` prompt,
and normalizes grounding tags only after debug metadata is recorded. Whole-page
640 was not readable, so the bounded emergency attempt processes three central
crops sequentially at native pixel scale.

## Scope

This acceptance covers the current OCR Platform sprint only: connecting `UnlimitedOCRProvider` to the existing OCR Runtime through an Ubuntu/Docker service. It does not cover PaddleOCR, Tesseract, Vision, Knowledge, Memory, Companion, or System Intelligence.

## PASS Criteria

- Docker service is healthy on port 8190.
- `aegis ocr providers` lists `stub` and `unlimited`.
- `aegis ocr doctor --verbose` reports service reachability, model readiness, GPU status when available, supported formats, output directory writability, and recognition readiness.
- A real image is recognized through `aegis ocr recognize-image PATH --provider unlimited`.
- The returned object is a valid `OCRResult`.
- `.txt` and `.json` OCR artifacts are created.
- OCR lifecycle events are published without full recognized text in event payloads.
- `python -m compileall aegis` and `python -m pytest` pass.

## External Acceptance

Run only when the Ubuntu service is deployed:

```powershell
$env:AEGIS_RUN_UNLIMITED_OCR_ACCEPTANCE='1'
python -m pytest tests/test_unlimited_ocr_acceptance.py
```

## Model Notes

- Model id: `baidu/Unlimited-OCR`
- Hugging Face lists the model as 3B parameters with BF16 tensors.
- The upstream model card shows Transformers, vLLM, and SGLang paths and tested Transformers requirements on Python 3.12.3 plus CUDA 12.9.
- RTX 3050 8 GB may require `device_map="auto"` and CPU offload. GPU-only operation is not guaranteed.
- AEGIS pins the service default revision to `ee63731b6461c8afcdcc7b15352e7d2ffecc2ead` instead of loading remote code from floating `main`.
- The default Docker profile for RTX 3050 8 GB is `low_vram`: bfloat16 weights, `device_map="auto"`, GPU `max_memory=6.5GiB`, a safe dynamic CPU budget based on currently available RAM, `/cache/offload`, `offload_state_dict=True`, `low_cpu_mem_usage=True`, `use_cache=False`, a 256-new-token generation budget, and one in-flight request. BF16 matches the pinned upstream preprocessing path; FP16 fails with mixed Half/Float tensors during real inference.
- Public runtime controls are `AEGIS_OCR_DEVICE`, `AEGIS_OCR_DTYPE`, `AEGIS_OCR_MAX_IMAGE_SIDE`, `AEGIS_OCR_CPU_OFFLOAD`, `AEGIS_OCR_GPU_MEMORY_LIMIT_GB`, and `AEGIS_OCR_EMPTY_CACHE_AFTER_REQUEST`. `AEGIS_OCR_GPU_MEMORY_LIMIT_GB` is a numeric GiB value; only the RTX 3050 `low_vram` profile supplies a default (6.5). Other profiles leave GPU memory uncapped unless configured. Older service-specific memory, offload, and image-side variables remain aliases for compatibility.
- The pinned upstream `infer()` implementation constructs BF16 preprocessing tensors and contains its own BF16 CUDA autocast. `AEGIS_OCR_DTYPE=float16` therefore controls loaded weights, but does not claim that every inference tensor is FP16. The service generation adapter overrides the upstream hard-coded `use_cache=True`, disables attentions, hidden states, scores, and dictionary generation outputs, and converts an upstream `max_length` into `max_new_tokens`. It does not add a generation limit when upstream supplies neither setting. With caching disabled, it pads the upstream image-token mask as the causal input grows so the remote model can recompute the complete sequence safely.
- The service records `before_model_load`, `after_model_load`, `before_inference`, `after_preprocessing`, `peak`, and `after_request` CUDA telemetry. `after_preprocessing` is sampled at the `generate()` boundary, after the upstream preprocessing tensors have been moved to CUDA.
- `/health` and `/info` report profile, RAM/VRAM telemetry, offload status, summarized device map, last peak VRAM, and last inference error. `recognition_ready` is true only after a verified OCR inference, not after load-only warmup.
- `POST /warmup` loads the model without claiming production recognition readiness. `POST /unload` releases model state and clears CUDA cache.
- Warmup inspects `named_modules()` and `named_parameters()` from the actually loaded remote-code model. It rejects unresolved `meta` parameters and reports only a bounded structure summary; no guessed module names are used in a manual device map.
- CUDA OOM is classified as `ocr.resource.exhausted`; load failures and inference failures use separate error codes.

## GPU Service Handoff

The host `gpu_services.json` entry for Unlimited-OCR must include its unload endpoint so image tasks release OCR allocations before the container is stopped:

```json
{
  "services": {
    "unlimited-ocr": {
      "unload_url": "http://127.0.0.1:8190/unload"
    }
  }
}
```

## Experiment Order

Run these as separate container starts, always recording `/warmup`, the OCR response, and `/info` after inference:

| Case | Profile/config | Purpose |
|---|---|---|
| A | official `pipeline`, `dtype=auto` | upstream baseline outside the production service |
| B | `balanced`, override GPU `6GiB`, CPU `22GiB` | AutoModel/offload baseline |
| C | `low_vram` | FP16, cache disabled, generation limited to 256 |
| D | `low_vram`, override GPU `5.5GiB` | larger activation reserve |
| E | `cpu` | correctness control, not a production fallback |

For every case record whether load succeeded, RAM/VRAM from telemetry, load and inference time, non-empty text, warnings, and full errors. A case passes only after a real non-empty inference; load-only warmup is not recognition readiness.

## Measurements

Fill after running on Ubuntu:

- VRAM usage: TBD
- RAM usage: TBD
- model load time: TBD
- first recognition time: TBD
- RTX 3050 8 GB limitations: TBD
