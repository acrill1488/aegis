# AEGIS Project Charter

## 1. Project Purpose

AEGIS is a personal AI operating system, AI co-worker, desktop automation
platform, remote AI runtime, long-term knowledge and memory system, and
companion platform.

AEGIS is built exclusively for its owner and sole user. It is not a mass-market
open-source framework, SaaS offering, or universal product, and it is not
required to support arbitrary user environments. Its architecture is optimized
for the owner's infrastructure and workflows.

## 2. Target Infrastructure

```text
Windows Workstation
        <-> LAN / secured remote connection
Ubuntu AI Server
```

The Windows workstation (Ryzen 5 7400F, RTX 3050 8 GB, 32 GB RAM) owns user
interaction, local files, office software, the desktop runtime, browser and UI
automation, screen capture, and final artifact handling.

The Ubuntu AI server (Intel i5-9600KF, RTX 3050 8 GB, 32 GB RAM) owns Ollama,
CUDA inference, OCR, embeddings, ComfyUI, voice inference, containerized AI
services, and the remote runtime. Windows is the interface and automation tier;
Ubuntu performs heavyweight AI computation.

## 3. Core Development Principles

### One Active Vertical

Only one feature vertical may be developed at a time. The mandatory progression
is:

```text
RFC -> implementation -> automated tests -> manual acceptance
    -> owner approval -> commit -> next vertical
```

No roadmap stage may be skipped or started before the current stage is accepted
by the owner. The only exceptions are a data-loss bug, critical security
vulnerability, environment-breaking regression, or infrastructure blocker.

### RFC-Driven Development

Every major capability begins with an RFC. The RFC must define the goal, scope,
non-goals, architecture, configuration, CLI, observability, security, errors,
tests, manual acceptance procedure, and completion criteria.

### Acceptance Before Commit

A capability is complete only after manual verification and explicit owner
approval. A final commit must not be made before acceptance unless the owner has
separately authorized that commit in advance.

### Production First

Do not substitute demo-only or throwaway implementations for production-quality
architecture.

### Infrastructure Before Features

Establish configuration, provider abstraction, runtime, lifecycle, health,
logging, tests, and security before implementing the user-facing capability.

### Provider Architecture

The primary provider interfaces are `LLMProvider`, `OCRProvider`,
`EmbeddingProvider`, `VisionProvider`, `ASRProvider`, `TTSProvider`, and
`ImageProvider`. Business logic must not depend directly on a single concrete
engine.

### Config Over Hardcode

IP addresses, ports, model IDs, paths, timeouts, resource limits, and policies
must be supplied through configuration or environment variables.

### CLI First

Interfaces are introduced in this order:

```text
CLI -> internal Python API -> Remote API -> Desktop UI
    -> autonomous agent usage
```

### Observable System

Every subsystem must expose health, status, doctor diagnostics, structured
logs, the selected provider, execution mode, timeouts, metrics, and actionable
errors.

### No Silent Fallback

When `execution: remote` is selected, AEGIS must never execute the task locally
without notice. The result must be either successful remote execution or an
explicit error.

### Backward Compatibility

Accepted CLI commands, configuration formats, and public data contracts must
not be broken without a migration plan.

### Security by Default

AEGIS applies least privilege, keeps secrets outside Git, controls destructive
actions, prefers recoverable deletion, audits actions, isolates networks,
protects against prompt injection, and requires confirmation for dangerous
actions. Untrusted external content must never directly control the system.

## 4. GreenBoost Principle

### Internal GreenBoost Policy

GreenBoost is a cross-cutting AEGIS policy covering lazy loading, model
unloading after idle, VRAM and RAM awareness, a GPU job queue, prevention of
unsafe parallel workloads, queueing instead of OOM, service idle shutdown,
cache preservation, warm-resource reuse, CPU/GPU execution choice, graceful
degradation, and Performance, Balanced, Eco, and Emergency modes.

Every future RFC must account for GreenBoost.

### External GreenBoost Project

`gitlab.com/IsolatedOctopi/greenboost` is an **experimental external
dependency**. It must not be installed or updated automatically. Integration
requires audit first, an isolated benchmark, compatibility checks, a rollback
plan, a separate RFC, and acceptance before any production use.

## 5. Architecture Change Policy

Changes to the roadmap, models, or upstream repositories must follow:

```text
proposal -> technical comparison -> benchmark -> architecture impact
    -> migration plan -> owner approval
```

New models do not replace locked choices merely because they are newer.
