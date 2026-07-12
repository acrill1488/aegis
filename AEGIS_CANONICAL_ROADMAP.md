# AEGIS Canonical Roadmap

## Near-Term Order

1. Image Generation finalization - completed
2. Unlimited-OCR - next planned

No later vertical is active.

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

## Unlimited-OCR

Status: PLANNED / NOT STARTED

Unlimited-OCR is the next planned vertical after Image Generation closure. It has not been activated in code by this roadmap update.
