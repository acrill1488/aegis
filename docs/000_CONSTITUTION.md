# AEGIS Constitution

## Active Vertical

OCR Platform -> PaddleOCR Provider v1 -> ACTIVE

## Active Sprint

Document Pipeline

## Completed Verticals

### Image Generation

- Status: Production Ready
- Acceptance: Passed
- Completed: 2026-07-12
- Main backend: ComfyUI
- Compute location: Ubuntu/Docker
- Client/orchestration: Windows AEGIS
- Output: real PNG + artifact

## Lessons Learned

- Green Gate is more important than isolated unit tests.
- Provider availability must verify the real LAN endpoint.
- Private LAN addresses must not blindly trust the proxy environment.
- Diagnostics before fix helped identify the 503 source.
- Stub must not mask a production provider failure.
- Workflow metadata and model catalog must stay separated, but linked.
- A vertical closes only after a real user-visible result exists.

## Current OCR Boundary

The One Active Vertical principle remains mandatory. The active implementation boundary is OCR Platform -> Document Pipeline only.

Allowed scope:

- Windows AEGIS remains the OCR client and orchestrator.
- Ubuntu/Docker hosts the Unlimited-OCR service and model inference.
- Stub OCR remains only a foundation and diagnostics fallback.
- OCR output may be normalized into StructuredDocument.
- StructuredDocument may be saved as document.json and text.txt artifacts.

Not started:

- Tesseract
- Vision Language Models
- Qwen-VL
- BGE
- Vector Search
- Knowledge ingestion
- UI Graph
- Memory
- Companion
- System Intelligence
