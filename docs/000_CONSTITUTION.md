# AEGIS Constitution

## Active Vertical

Embedding Platform -> BGE-M3 Provider v1 -> ACTIVE

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

## Current Embedding Boundary

The One Active Vertical principle remains mandatory. PaddleOCR Provider v1 is complete. The active implementation boundary is Embedding Platform -> BGE-M3 dense embeddings only.

Allowed scope:

- Windows AEGIS remains the OCR client and orchestrator.
- Ubuntu/Docker hosts the Unlimited-OCR service and model inference.
- Stub OCR remains only a foundation and diagnostics fallback.
- The official FlagEmbedding API remains the model, tokenizer, batching, and normalization backend.
- AEGIS owns only configuration, lifecycle, registry, diagnostics, normalized public models, installer, and CLI integration.

Not started:

- Tesseract
- Vision Language Models
- Qwen-VL
- Vector Search
- Knowledge ingestion
- UI Graph
- Memory
- Companion
- System Intelligence

Embedding foundation does not complete the Memory vertical and does not add retrieval, indexing, RAG, sparse vectors, or ColBERT vectors.
