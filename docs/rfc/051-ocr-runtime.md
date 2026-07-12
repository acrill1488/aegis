# OCR Platform

## Purpose

OCR Platform is the provider-neutral text extraction layer for AEGIS. It gives the system one stable architecture for extracting text and document structure from images, documents, PDFs, and directories before any production OCR provider is connected.

Production providers are expected in later sprints. This RFC defines the runtime boundary only.

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

The foundation sprint registers only `StubOCRProvider`. `UnlimitedOCRProvider`, `PaddleOCRProvider`, and `TesseractProvider` must be added later through the registry without changing Runtime or the public Provider API.

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

Foundation state:

- default provider: `stub`
- registered providers: `StubOCRProvider`
- production providers: none

Future registry targets:

- `UnlimitedOCRProvider`
- `PaddleOCRProvider`
- `TesseractProvider`

## CLI

Foundation commands:

- `aegis ocr providers`
- `aegis ocr doctor`
- `aegis ocr capabilities`
- `aegis ocr recognize`

`recognize` is a placeholder and returns `NotImplemented` until a production provider exists.

## Diagnostics

OCR Doctor reports:

- Providers
- Available
- Capabilities
- Supported Formats
- Default Provider

OCR Doctor does not check models in this sprint.

## Constraints

- Do not integrate OCR models in the foundation sprint.
- Do not add Docker or model downloads.
- Do not add UnlimitedOCRProvider yet.
- Do not add PaddleOCRProvider or TesseractProvider.
- Do not add Vision, Qwen-VL, UI Graph, Memory, or Companion changes.
- Do not break the Provider API once production providers depend on it.
