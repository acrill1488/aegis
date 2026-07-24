# BGE-M3 Embedding Provider v1

## Status

Active.

## Purpose

Add the first provider-neutral dense embedding path to AEGIS. This is an embedding foundation, not a Memory, indexing, retrieval, or RAG implementation.

## Architecture

`CLI -> EmbeddingRuntime -> EmbeddingRegistry -> BGEM3Provider -> FlagEmbedding`.

AEGIS does not implement BGE-M3, tokenization, batching, pooling, or vector normalization. `BGEM3Provider` is a thin adapter over the official `FlagEmbedding.BGEM3FlagModel` API.

## Public API and models

- `EmbeddingRuntime.embed(EmbeddingRequest) -> EmbeddingResult`
- `EmbeddingRegistry.register/get/list/resolve`
- `BGEM3Provider.is_available/health/embed`
- `EmbeddingRequest`, `EmbeddingVector`, and `EmbeddingResult`

Only plain `list[float]` vectors cross the provider boundary. Native NumPy, PyTorch, FlagEmbedding, and SDK response objects do not.

## Configuration

The optional `embeddings` section selects default provider `bge-m3`, limits a request to 256 texts, and configures model name, device, batch size, backend normalization, maximum token length, precision, timeout, cache, and remote-code trust. Built-in defaults apply without rewriting a user's `services.yaml`. Relative cache paths resolve beside the selected configuration file.

## Provider lifecycle and lazy loading

Importing AEGIS neither imports FlagEmbedding nor loads or downloads a model. The SDK and `BGEM3FlagModel` are loaded on the first valid embed call and reused. Provider diagnostics inspect package, CUDA, cache, and loaded state without model initialization or network access.

## Device selection

`cpu` selects CPU. `auto` and `gpu` select CUDA only when the installed PyTorch runtime reports CUDA availability and a device. A GPU initialization error allows one controlled CPU initialization attempt; the reason appears in warnings and metadata. Input/inference errors do not trigger fallback.

## Normalization

The provider passes `normalize_embeddings` to FlagEmbedding. AEGIS calculates the norm only for diagnostics and validates normalized backend output within tolerance; it never performs a second normalization pass. Dimensions are detected from output and must agree across the result.

## Health model

Health distinguishes disabled, package missing, CPU/GPU runtime available, GPU requested but unavailable, cache state, model loaded, healthy, and initialization failure. A cache is considered present only when the Hugging Face model directory contains refs and snapshots, not merely because a parent directory exists.

## CLI

`aegis embeddings providers`, `doctor [bge-m3]`, `embed TEXT`, and `embed-file PATH` are supported. Embed accepts provider, device, batch size, normalization, JSON, and vector-display options. File ingestion is limited to UTF-8 `.txt` and `.md`. Normal table output omits vectors; JSON contains plain finite numbers.

## Package manifest

`aegis install bge-m3` installs only the official FlagEmbedding Python package and dependencies through the current interpreter. It does not download the model or treat a GPU as an installable package. FlagEmbedding and torch are not base AEGIS dependencies.

## Failure modes

Stable errors cover validation, missing/disabled provider, provider failure, initialization failure, timeout, and dimension mismatch. The CLI returns concise structured JSON or plain messages without tracebacks.

FlagEmbedding exposes a synchronous inference call without a cooperative cancellation contract. The adapter can return a timeout to the caller, but an already-running native call may finish in its worker before process shutdown; forcefully terminating it in-process would risk corrupting shared CUDA/model state.

## Security considerations

`trust_remote_code` defaults to false. No automatic install or model download occurs during diagnostics. Cache paths are configuration-resolved, and public JSON rejects non-finite vector values.

## Acceptance criteria

The optional dependency remains lazy; mocked tests cover configuration, registry, input validation, model reuse, dense output conversion, order, CPU/GPU selection and fallback, normalization verification, dimensions, diagnostics, CLI JSON, manifest registration, and compatibility with the existing OCR suite. Compile, full pytest, Ruff, CLI smoke checks, and whitespace checks must pass without installing FlagEmbedding or downloading BGE-M3.

## Out of scope

Sparse vectors, ColBERT vectors, hybrid retrieval, reranking, Qdrant, FAISS persistence, chunking, crawling, automatic indexing, Memory Engine, RAG, REST, UI, remote execution, and model download commands.
