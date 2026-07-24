# OCR Platform

## Purpose

OCR Platform is the provider-neutral text extraction layer for AEGIS. It gives the system one stable architecture for extracting text and document structure from images, documents, PDFs, and directories before any production OCR provider is connected.

The Foundation sprint defined the runtime boundary. The current sprint connects the first production provider, `UnlimitedOCRProvider`, through a stable HTTP service boundary.

## Responsibilities

- Select an OCR provider through a registry.
- Expose a stable Provider API for images, documents, and PDFs.
- Normalize provider output into `OCRResult`.
- Publish OCR lifecycle events.
- Register OCR output as an artifact through the existing project and mission artifact path.
- Preserve source references, warnings, errors, metadata, and provider provenance.
- Provide CLI diagnostics for provider availability, capabilities, supported formats, and the default provider.

## Non-Responsibilities

OCR Platform does not perform:

- image analysis
- reasoning
- scene description
- Vision Language Model behavior
- UI Graph construction
- text generation
- embedding
- visual planning
- Qwen-VL integration
- model download, installation, or health checks

It is responsible only for extracting text and document structure.

## Provider API

Providers implement `OCRProvider`:

- `name() -> str`
- `available() -> bool`
- `health() -> dict`
- `capabilities() -> dict`
- `supported_formats() -> list[str]`
- `recognize_image(source, language=None, options=None) -> OCRResult`
- `recognize_document(source, language=None, options=None) -> OCRResult`
- `recognize_pdf(source, language=None, options=None) -> OCRResult`
- `recognize_directory(source, language=None, options=None) -> OCRResult`

The registry registers `StubOCRProvider`, `UnlimitedOCRProvider`, and `PaddleOCRProvider`. TesseractProvider may be added later through the registry without changing Runtime or the public Provider API.

## OCRResult

`OCRResult` is provider-neutral and includes:

- `provider`
- `language`
- `pages`
- `text`
- `blocks`
- `tables`
- `figures`
- `confidence`
- `processing_time`
- `artifacts`
- `metadata`
- `warnings`
- `errors`

The model is intentionally not tied to any concrete OCR engine. Providers may enrich `pages`, `blocks`, and `tables`, but callers must tolerate empty structures and warnings.

## Events

OCR Runtime publishes:

- `ocr.started`
- `ocr.completed`
- `ocr.failed`
- `ocr.artifact.saved`
- `ocr.provider.selected`

Events carry provider name, source metadata, and normalized result data when available.

Recognition events must not include the full recognized text. Event payloads carry summaries, counts, warnings, errors, and artifact paths.

## Artifact

OCR Runtime can register an `OCRResult` as an artifact with type `ocr.result` by using the existing active project artifact API. This keeps OCR aligned with Mission and Project artifact handling without introducing a new artifact store in the foundation sprint.

## Mission Interaction

Mission nodes may invoke OCR capabilities after they are registered in `CapabilityRuntime`. OCR Runtime does not plan mission graphs and does not reason over extracted text. It returns structured extraction output that mission skills may consume.

When an active project exists, OCR artifacts can be associated with the project workspace that contains mission work.

## Knowledge Interaction

OCR Runtime does not index content into Knowledge directly. A later Knowledge integration may ingest `OCRResult.text`, blocks, tables, and artifact references through the existing Knowledge Runtime. This separation keeps extraction independent from retrieval and memory.

## Registry

`OCRRegistry` owns provider registration, lookup, default provider selection, and provider listing.

Required registry methods:

- `register()`
- `default()`
- `providers()`
- `provider(name)`
- `available()`

Current state:

- default provider: `unlimited` when the service is available and healthy, otherwise `stub` for diagnostics.
- registered providers: `StubOCRProvider`, `UnlimitedOCRProvider`, `PaddleOCRProvider`
- production providers: `UnlimitedOCRProvider`, with optional local `PaddleOCRProvider`

Recognition commands must not silently return a stub result when Unlimited-OCR is unavailable. They return an explicit provider/service error instead.

Future registry targets:

- `TesseractProvider`

## CLI

Commands:

- `aegis ocr providers`
- `aegis ocr doctor --verbose`
- `aegis ocr capabilities`
- `aegis ocr recognize`
- `aegis ocr recognize-image PATH --provider unlimited`
- `aegis ocr recognize-pdf PATH --provider unlimited`

Recognition commands return normalized `OCRResult` data and save `.txt` plus `.json` artifacts after success.

## Diagnostics

OCR Doctor reports:

- Providers
- Available
- Capabilities
- Supported Formats
- Default Provider
- Unlimited-OCR config
- TCP reachability
- `/health`
- `/info`
- model loaded or lazy
- GPU detected when reported by the service
- output directory writability
- recognition readiness

Stub availability is not counted as production readiness.

## Constraints

- Do not add TesseractProvider in the PaddleOCR Provider v1 slice.
- Do not add Vision, Qwen-VL, UI Graph, Memory, or Companion changes.
- Do not break the Provider API once production providers depend on it.
