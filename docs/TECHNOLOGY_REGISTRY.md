# AEGIS Technology Registry

## Statuses

- **ACTIVE** — Already used and accepted.
- **LOCKED_PLANNED** — Locked for future implementation but not yet in production.
- **CANDIDATE** — May be researched but is not selected before benchmark and acceptance.
- **EXPERIMENTAL** — A high-risk or low-level dependency requiring a separate RFC and isolated test.
- **OPTIONAL** — Not a mandatory part of AEGIS Core.

## Model Registry

### LLM / Coding

**ACTIVE:** Ollama model `qwen3-coder:latest`. The `latest` tag is allowed only
in the current development environment; production must pin an exact tag or
digest.

**LOCKED_PLANNED:** Qwen3-Coder family; upstream `QwenLM/Qwen3-Coder`. Its
purposes are coding, repository reasoning, refactoring, testing, and code review.

### Embeddings

**ACTIVE:** `BAAI/bge-m3`, using the FlagEmbedding runtime. Its purposes are
multilingual embeddings, local search, RAG, document retrieval, repository
retrieval, and project memory.

### Vision / UI Understanding

**LOCKED_PLANNED — primary 8 GB profile:** `Qwen/Qwen3-VL-4B-Instruct`, for UI
understanding, visual grounding, screenshots, OCR fusion, UI Graph, and screen
reasoning.

**LOCKED_PLANNED — upgrade profile:** `Qwen/Qwen3-VL-8B-Instruct`. Use only
after the Resource Coordinator exists and a GreenBoost benchmark passes.

**FALLBACK / REFERENCE ONLY:** Qwen2.5-VL family. Do not make it the primary new
choice without a technical reason.

### Speech-to-Text

**LOCKED_PLANNED:** `openai/whisper-large-v3-turbo`, using
`SYSTRAN/faster-whisper`. The baseline RTX 3050 target is
`compute_type=int8_float16`; moving to `int8` requires a benchmark.

### Voice Activity Detection

**LOCKED_PLANNED:** Silero VAD; upstream `snakers4/silero-vad`. The selected
version must be compatible with the pinned voice runtime.

### Text-to-Speech

**LOCKED_PLANNED FAMILY:** Qwen3-TTS family. Select a checkpoint only in the
Voice RFC after benchmarking Russian quality, English quality, latency, VRAM,
streaming, voice-cloning requirements, and license.

**Runtime integration:** Project AIRI `unspeech` may serve as a unified ASR/TTS
proxy or adapter if its benchmark demonstrates suitability.

**Mandatory fallback:** Provide a lightweight CPU TTS provider for times when
the GPU is occupied by OCR, Vision, or ComfyUI. Select its model in the Voice RFC.

### OCR

**ACTIVE — completed platform:** PaddleOCR provider and Unlimited OCR provider.
Both are integrated through the provider-neutral OCR Runtime and have production
acceptance evidence. Qwen3-VL does not replace the specialized OCR Provider.

### Image Generation

**ACTIVE — completed txt2img platform:** ComfyUI, integrated through the
provider-neutral Image Generation Runtime with remote execution, PNG and
artifact retrieval, diagnostics, explicit error handling, automated coverage,
and real-PNG acceptance. Stable Diffusion and Flux checkpoints are not globally
locked; pin each checkpoint at workflow level after benchmarking. Image-to-image,
inpainting, ControlNet, IP-Adapter, and upscale remain later expansions rather
than accepted capabilities of the completed txt2img boundary.

### GreenBoost Runtime

**ACTIVE — current vertical, incomplete:** The repository already contains an
internal GreenBoost adapter and resource-aware OCR execution, but the complete
Stage 7 Resource Coordinator, scheduling, lifecycle, accounting, compatibility,
and acceptance contract is not yet complete. Existing pieces must be extended
under the canonical `ExecutionOrchestratorRuntime`, not treated as a second
orchestrator or as completion of Stage 7.

The external `IsolatedOctopi/greenboost` project remains **EXPERIMENTAL** and is
governed separately from the internal GreenBoost policy.

## Repository Registry

### Authoritative Repository

- `github.com/acrill1488/aegis` — **ACTIVE**; the sole authoritative AEGIS repository.

### AI and Runtime Upstreams

An upstream is **ACTIVE** when already used; otherwise it is **LOCKED_PLANNED**.

- `github.com/ollama/ollama`
- `github.com/QwenLM/Qwen3-Coder`
- `github.com/QwenLM/Qwen3-VL`
- `github.com/FlagOpen/FlagEmbedding`
- `github.com/PaddlePaddle/PaddleOCR`
- `github.com/ComfyUI/ComfyUI`
- `github.com/SYSTRAN/faster-whisper`
- `github.com/snakers4/silero-vad`

### Companion / Voice

- `github.com/moeru-ai/airi` — **LOCKED_PLANNED**

Allowed integration directions are companion UI, Live2D / VRM, realtime voice,
unspeech, game integrations, memory hooks, and desktop presentation. AIRI and
AEGIS Core must not be mixed directly. Integrate through an API, adapter,
plugin, or separate frontend/runtime. AIRI remains a companion and presentation
layer, not a replacement for AEGIS Core.

### GreenBoost

- `gitlab.com/IsolatedOctopi/greenboost` — **EXPERIMENTAL**

It requires an audit, no automatic installation or updates, an isolated
benchmark, CUDA/NVIDIA and Docker compatibility tests, rollback, a separate RFC,
and no production integration before acceptance.

### Automation

- `github.com/n8n-io/n8n` — **OPTIONAL**

Use only at stage 17. It must not become a mandatory AEGIS Core dependency.

## Version Pinning Policy

Production dependencies must not target `latest`, `main`, `master`, or an
unbounded Git dependency. After integration acceptance, record the Git commit
SHA, Docker image digest, Hugging Face revision, Python package version, CUDA
compatibility, license, and checksum where appropriate.

```yaml
models:
  embeddings:
    id: BAAI/bge-m3
    revision: "<verified-revision>"
    status: active

  vision:
    id: Qwen/Qwen3-VL-4B-Instruct
    revision: "<verified-revision>"
    status: locked_planned

  asr:
    id: openai/whisper-large-v3-turbo
    revision: "<verified-revision>"
    runtime: faster-whisper
    status: locked_planned
```
