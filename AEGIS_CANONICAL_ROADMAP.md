# AEGIS Canonical Roadmap

## Near-Term Order

1. Image Generation finalization - completed
2. OCR Platform - active

No later vertical is active.

Service endpoints are resolved through the centralized AEGIS services configuration at
`F:\AI_WORKSPACE\config\services.yaml` by default.

## Image Generation

Status: COMPLETED / PRODUCTION READY

Completed scope:

- ImageGenerationRuntime.
- Provider API.
- Stub Provider for non-production and test flows.
- ComfyUI Provider for production txt2img.
- LAN HTTP client handling with `trust_env=False`.
- Workflow Library catalog, listing, selection, and validation.
- Image Model Catalog with installed-state tracking.
- API-format workflow loading.
- prompt, negative prompt, seed, size, and output-prefix injection.
- `POST /prompt` submission.
- history polling.
- PNG download through `/view`.
- output persistence under `F:\AI_WORKSPACE\images\generated`.
- artifact registration when an active project is available.
- lifecycle events.
- `aegis image doctor --verbose`.
- `aegis workflow validate`.
- acceptance documentation and external-gated acceptance test.

Planned future expansion:

- AnyLoRA installation.
- DreamShaper XL installation.
- img2img.
- inpainting.
- ControlNet.
- IP-Adapter.
- upscale.
- tattoo workflow presets.
- model/workflow installer.

Catalog note: AnyLoRA and DreamShaper XL are catalog roadmap entries. The current catalog shows them as `installed=false`, so they are not counted as completed installed models.

## OCR Platform

Status: ACTIVE

Current sprint: Unlimited-OCR Provider

Completed foundation scope:

- OCR Runtime package.
- Provider API.
- Provider Registry.
- Stub Provider only.
- Provider-neutral `OCRResult`.
- OCR lifecycle events.
- Artifact registration through the existing project artifact API.
- CLI diagnostics: providers, doctor, capabilities.

Active provider scope:

- `UnlimitedOCRProvider` as an HTTP client for Ubuntu/Docker inference.
- `baidu/Unlimited-OCR` service wrapper on port 8190.
- Stable OCR service contract: `/health`, `/info`, `/ocr/image`, `/ocr/pdf`.
- Windows config at `F:\AI_WORKSPACE\ocr\unlimited_ocr.json`.
- Real `aegis ocr recognize-image PATH --provider unlimited` path.
- OCR text and JSON artifacts under `F:\AI_WORKSPACE\ocr\results`.
- No hidden stub fallback for recognition.

Explicit non-scope:

- PaddleOCRProvider implementation.
- TesseractProvider implementation.
- Vision Language Models.
- Qwen-VL.
- UI Graph.
- Memory.
- Companion.
