# PaddleOCR Provider v1

## Status

Active.

## Purpose

Add fast local recognition of printed text in documents, screenshots, interfaces, and images as a second OCR provider. Unlimited-OCR remains unchanged and remains the production default.

## Architecture

`PaddleOCRProvider` is an optional in-process adapter under `aegis.providers.paddleocr`. It registers with the existing `OCRRegistry`, returns the existing provider-neutral `OCRResult`, and does not create a second OCR runtime. Native SDK values are first normalized into provider-local line/result models and never cross the provider boundary.

## Public API

- `is_available() -> bool` (compatibility alias)
- `available() -> bool` (OCR Runtime contract)
- `health() -> dict`
- `provider_health() -> ProviderHealth`
- `recognize(request) -> OCRResult`
- Existing `recognize_image`, `recognize_document`, `recognize_pdf`, and `recognize_directory` contract methods

Provider id: `paddleocr`.

## Configuration

Configuration is read through the central Configuration Layer:

```yaml
ocr:
  providers:
    paddleocr:
      enabled: true
      device: auto
      language: en
      use_angle_cls: true
      confidence_threshold: 0.5
      timeout_seconds: 120
      max_image_size: 4096
```

The section is optional; safe built-in defaults apply without rewriting user configuration.

## Provider lifecycle

Importing AEGIS does not import PaddleOCR or load a model. The SDK and model engine are loaded on the first recognition request and the engine is reused. A missing optional package leaves AEGIS operational and reports `aegis install paddleocr` as the remediation.

## Device selection

`cpu` forces CPU. `gpu` and `auto` use GPU only when PaddlePaddle itself reports a CUDA-capable build and a CUDA device. GPU initialization failure permits one controlled CPU initialization attempt. The fallback reason and effective device are exposed in result metadata and health diagnostics.

An NVIDIA device alone is not considered proof that a Paddle GPU runtime is installed. Defaults do not reserve or fill the RTX 3050 8 GB VRAM.

## Failure modes

Diagnostics distinguish package missing, disabled, CPU runtime available, GPU runtime available, GPU requested but unavailable, model initialization failed, and healthy. Missing/invalid files, unsupported formats, oversized images, timeouts, initialization failures, and inference failures produce concise normalized errors. CLI commands do not expose tracebacks.

## CLI

- `aegis ocr recognize IMAGE --provider paddleocr`
- `--language`, `--device`, `--confidence`, and `--json`
- `aegis ocr providers`
- `aegis ocr doctor paddleocr`

JSON mode writes plain valid JSON without Rich markup.
`aegis ocr providers --json` returns a `providers` array with provider id,
availability, default flag, effective device, status, and an optional reason.
Provider-specific doctor output keeps platform readiness (derived from the
production Unlimited-OCR provider) separate from the selected provider status.

The existing canonical Unlimited-OCR provider id remains `unlimited`; `unlimited-ocr` is accepted as a lookup/CLI alias for compatibility with package naming. The default is not changed.

## Package manifest

The built-in `paddleocr` provider manifest installs `paddleocr` and CPU `paddlepaddle` as a separate Package Manager operation. PaddleOCR is not a base AEGIS dependency. GPU runtime selection remains an explicit environment-specific operation rather than a generic package dependency.

The package supports Python `>=3.12,<3.14` and recommends the project's Python
3.12 runtime. Package Manager checks this constraint before executing install
actions and uses `sys.executable -m pip`; it neither selects a global Python from
`PATH` nor replaces the system interpreter.

## Acceptance criteria

- Optional dependency and lazy model loading
- Stable registration without changing the default provider
- CPU operation and controlled GPU-to-CPU fallback
- Normalized text, confidence, line bounding boxes, timing, language, provider, effective device, and metadata
- Confidence filtering and valid empty results
- Human-readable CLI failures and valid JSON
- Mocked tests that download no model and require no GPU, Docker, or Ubuntu server
- Existing Unlimited-OCR behavior remains covered by the full test suite

## Out of scope

Remote Ubuntu execution, distributed runtime, document-type auto-routing, ensemble OCR, model training, UI, REST API, PDF support in PaddleOCR v1, and changes to Unlimited-OCR.
