# AEGIS Canonical Roadmap

> This roadmap is canonical. AEGIS follows the One Active Vertical rule.
> No stage may be skipped or started before the current active stage passes manual acceptance and receives explicit owner approval.

## 0. Infrastructure Foundation — Completed

- Core
- Registry
- CLI
- Config
- Installer
- Package Manager
- Serialization
- Logging
- Tests

## 1. Provider Platform — Foundation Completed

- LLM Provider
- OCR Provider
- Embedding Provider
- Image Provider
- Remote execution contracts

## 2. Execution Engines — Foundation Completed

- Goal Engine
- Mission Engine
- Planner
- Skill Graph
- Reflection
- Recovery
- Knowledge
- Project Runtime
- Execution Orchestrator

The existing `ExecutionOrchestratorRuntime` is the canonical task and mission
orchestrator. It must be extended, never duplicated by a second orchestrator.

## 3. Remote AI Runtime — Foundation Completed

- Windows-to-Ubuntu execution
- Docker deployment
- Authentication
- Health
- Remote execution
- CUDA
- Service configuration

## 4. Embedding Platform — Completed

- BGE-M3
- FlagEmbedding
- Remote CUDA
- Lazy loading
- Persistent Hugging Face cache

## 5. OCR Platform — Completed

- PaddleOCR
- Unlimited OCR
- PDF/image pipeline
- Normalized OCR result
- Remote execution
- OOM recovery
- Production acceptance

Production acceptance is complete for both the PaddleOCR and Unlimited OCR
provider paths, including normalized results, remote execution, diagnostics,
artifact output, error handling, OOM recovery, automated tests, and real-image
acceptance on the target infrastructure.

## 6. Image Generation Platform — Completed

- ComfyUI
- Workflows
- Image-to-image
- Inpainting
- Progress
- Cancellation
- Artifacts
- Lifecycle
- Idle shutdown

The accepted production boundary is txt2img through the provider-neutral Image
Generation Runtime and the remote ComfyUI provider. The repository includes
remote workflow submission, progress polling, PNG retrieval, persisted and
project-linked artifacts, provider and endpoint diagnostics, explicit failure
reporting without a silent stub fallback, automated tests, and external
real-PNG acceptance. Image-to-image, inpainting, ControlNet, IP-Adapter, upscale,
and additional checkpoint workflows remain later expansions and do not reopen
the accepted txt2img vertical.

## 7. GreenBoost Runtime — Current Active Vertical

- Internal GreenBoost policy
- Resource Coordinator
- VRAM accounting
- RAM monitoring
- GPU reservation
- Service compatibility matrix
- Container lifecycle
- Model unloading
- Idle timeout
- OOM recovery
- External GreenBoost research RFC

```text
ExecutionOrchestratorRuntime
    +-- ResourceCoordinator
        +-- resource checks
        +-- service lifecycle
        +-- provider scheduling
        +-- health waiting
        +-- idle shutdown
```

The Resource Coordinator belongs beneath `ExecutionOrchestratorRuntime`; do not
create a second orchestrator.

Existing resource-aware OCR support and the external GreenBoost adapter are
inputs to this stage, not evidence that the full GreenBoost Runtime is complete.
Stage 7 must proceed through its own RFC, implementation, tests, manual
acceptance, and explicit owner approval.

## 8. Document Intelligence / Basic Desktop Foundation

- PDF, DOCX, XLSX, and PPTX parsing
- Layout understanding and OCR integration
- Chunking, indexing, and retrieval
- Source provenance and safe file access
- Foundation for the UI and office co-worker

## 9. Qwen-VL + UI Graph

The actual model foundation is Qwen3-VL.

- Screenshot understanding
- UI element detection and visual grounding
- Bounding boxes and OCR fusion
- UI Graph and Window Graph
- Multi-monitor awareness
- Visual verification after actions
- Visual prompt-injection protection

## 10. AIRI + Voice + Companion

- Project AIRI integration and personality
- Live2D / VRM
- STT, TTS, VAD, and realtime voice
- Memory hooks and emotional reactions
- Overlay and companion presentation layer

AIRI does not replace AEGIS Core. It is a presentation and companion layer.

## 11. Game Companion

- Game screen understanding and HUD recognition
- Voice reactions, session memory, and gameplay advice
- Safe game integrations
- No cheats or prohibited online-game automation

## 12. File and Office Co-worker

- Windows File Runtime and Explorer
- DOCX, PDF, PPTX, XLSX, Markdown, and archives
- File search and organization
- Office artifact creation and rollback
- Allowed directories and safe deletion

## 13. System Intelligence / Jarvis

- Window control, process intelligence, and installed applications
- Clipboard, notifications, keyboard, and mouse
- Windows UI Automation and PowerShell
- Browser runtime and screen understanding
- Automation policies and dangerous-action confirmation

## 14. Distributed Windows ↔ Ubuntu Runtime

- Distributed queues and bidirectional events
- Streaming and task cancellation
- Shared job state and synchronization
- Resource scheduling and distributed memory
- Reconnect and recovery
- LAN and secured remote operation

## 15. Repository Intelligence / Coding Co-worker

- Repository, symbol, and AST graphs
- Semantic code search and Git
- RFCs, issues, and diffs
- Tests, lint, and type checking
- Code review and refactoring
- Acceptance before commit

## 16. Security / Dashboard / Packaging

- Dashboard, metrics, audit, permissions, and secrets
- Backup, restore, updates, and rollback
- Packaging and installer hardening
- Disaster recovery and production security review

## 17. Gmail / Calendar / Optional n8n

- Gmail, Calendar, Contacts, reminders, and recurring workflows
- Optional n8n
- Sending actions require explicit policy or confirmation
- n8n is not part of the mandatory core

## Roadmap Governance

- One active vertical
- No stage skipping
- No parallel feature verticals
- Infrastructure fixes only when they block the current stage
- Owner approval is authoritative
- Roadmap changes require an explicit owner decision
