# GreenBoost Runtime

## Status

Final.

RFC-054 was explicitly accepted by the owner. Its inclusion in `docs/rfc/INDEX.md` makes it canonical under current repository practice. This records the disposition of this RFC and does not introduce a repository-wide RFC status framework.

Acceptance of this architecture RFC does not complete Stage 7. Stage 7 implementation remains incomplete until the runtime is implemented, tested, accepted on the real Windows and Ubuntu environment, and separately approved by the owner.

## Purpose

GreenBoost Runtime is the provider-neutral resource coordination and lifecycle policy layer for resource-intensive AEGIS capabilities. It makes CPU, RAM, GPU, VRAM, disk, network, providers, models, services, and execution slots observable and manageable through one canonical orchestration path.

Independent provider-level resource management is insufficient because each provider sees only its own process and cannot safely account for competing workloads, retained models, remote capacity, queue priority, or system-wide lifecycle decisions. On the baseline NVIDIA RTX 3050 8 GB, assuming that individually valid workloads are safe together can produce VRAM exhaustion, unstable services, and unpredictable latency. Admission, reservation, scheduling, and release must therefore be explicit.

GreenBoost is infrastructure for future Vision, Voice, AIRI and Game Companion, Desktop and Office Co-worker, and Jarvis stages. It coordinates execution resources; it does not implement those capabilities or plan their work.

## Scope

GreenBoost Runtime covers:

- resource observation and accounting;
- resource admission control and task scheduling;
- provider, service, and model lifecycle;
- GPU ownership and VRAM pressure handling;
- execution queues and resource profiles;
- diagnostics, recovery, and audit events;
- local and remote-node awareness;
- compatibility with a future multi-node runtime without changing public request semantics.

## Non-Goals

This RFC does not define or authorize:

- Qwen3-VL, Voice, AIRI, Game Companion, Desktop/UI automation, or Office Co-worker implementation;
- distributed inference or a complex distributed scheduler;
- merging two GPUs into one logical GPU;
- game-performance modification;
- OS-level overclocking;
- automatic driver installation or CUDA upgrades;
- installation, download, import, or direct integration of external `gitlab.com/IsolatedOctopi/greenboost`;
- replacement of `ExecutionOrchestratorRuntime` or provider registries;
- business-task reasoning or planning;
- autonomous model downloads.

## Architectural Position

```text
Mission / CLI / Capability
        ↓
ExecutionOrchestratorRuntime
        ↓
GreenBoost policy and resource coordination
        ↓
Provider / Remote Runtime / Service
        ↓
CPU / RAM / GPU / VRAM / Disk / Network
```

`ExecutionOrchestratorRuntime` remains the only canonical execution orchestrator. GreenBoost is its policy, coordination, accounting, scheduling, and lifecycle subsystem; it must not become a second independent orchestrator. Providers must not bypass the orchestrator for production resource-intensive execution.

GreenBoost does not reason, plan missions, or choose the business capability to invoke. Provider registries remain responsible for provider registration and selection. Once an execution and provider have been accepted, GreenBoost decides whether and when that execution can start and which declared, policy-permitted resource scope it may use.

The existing internal GreenBoost adapter and resource-aware OCR execution are migration inputs. They do not implement the complete contract in this RFC and do not constitute Stage 7 completion.

## Core Components

### ResourceCoordinator

`ResourceCoordinator` is the facade used by `ExecutionOrchestratorRuntime`. It:

- maintains current local and remote resource state;
- evaluates execution requests;
- reserves resources and releases reservations;
- rejects impossible work or queues temporarily unsafe work;
- exposes resource snapshots;
- publishes resource events;
- keeps resource scopes explicitly associated with nodes.

It coordinates the components below but does not replace the execution orchestrator.

### ResourceProbe

`ResourceProbe` observes CPU usage, total and available RAM, GPU identity, total/used/reserved/free VRAM, GPU utilization, temperature when available, disk availability, remote service reachability, and relevant network latency.

Probe failures are explicit. Unknown or unavailable measurements are represented as unknown with a warning or error; they must never be reported as zero. Probe freshness is part of the observation.

### ResourceLedger

`ResourceLedger` records active reservations, actual and historical execution usage, provider/model/service ownership, suspected resource leaks, reservation timestamps, and execution correlation identifiers.

The ledger distinguishes:

- **observed usage:** usage measured by a probe at a stated time;
- **estimated usage:** a measured, benchmark-derived, configured, or unknown prediction for a request;
- **reserved usage:** capacity promised to admitted work and unavailable to conflicting work;
- **actual usage:** usage attributed to an execution during or after execution when attribution is available.

These values are not interchangeable. A reservation is a policy commitment, not proof of consumption; observed system usage may include unrelated processes.

### AdmissionController

`AdmissionController` determines whether a request may start. It compares minimum and preferred requirements with current capacity and reservations, applies the active profile, accounts for higher-priority work, rejects impossible requests, and queues temporarily blocked requests. It never silently degrades provider, model, device, or quality without explicit policy permission.

### ExecutionScheduler

`ExecutionScheduler` controls queued execution order, priority, fairness, cancellation, queue and execution timeouts, starvation prevention, maximum concurrency, GPU-exclusive work, and CPU-compatible parallel work. Stage 7 requires a bounded single-node/primary-remote-node scheduler, not a complex distributed scheduler.

### LifecycleManager

`LifecycleManager` starts services, verifies health, warms models, marks readiness, applies idle timeouts, unloads models, stops services, and performs bounded recovery. It prevents shutdown or unload while relevant reservations exist.

Conceptual lifecycle states are `stopped`, `starting`, `healthy`, `warming`, `ready`, `busy`, `idle`, `draining`, `unloading`, `failed`, and `recovering`. Implementations may add substates but must preserve explicit transitions and terminal failures.

### PolicyEngine

`PolicyEngine` resolves the active resource profile, concurrency, fallback and eviction rules, idle timeouts, GPU exclusivity, CPU fallback permission, remote preference, and failure behavior. Policy is configuration-driven and its effective source must be diagnosable.

### ResourceDiagnostics

`ResourceDiagnostics` provides human-readable and machine-readable JSON output for readiness, snapshots, active reservations, queues, loaded models, services, pressure reasons, probe warnings, and recent recovery actions.

## Resource Model

A provider-neutral `ResourceRequest` conceptually includes:

- `execution_id`, `capability`, `provider`, `service`, `model`, `node`, and `priority`;
- `cpu_cores_min`, `cpu_cores_preferred`, `ram_mb_min`, and `ram_mb_preferred`;
- `vram_mb_min`, `vram_mb_preferred`, `disk_mb`, `gpu_required`, and `gpu_exclusive`;
- `cpu_fallback_allowed`, `remote_allowed`, `preemptible`;
- `estimated_duration`, `queue_timeout`, and `execution_timeout`;
- validated `metadata`.

A `ResourceReservation` conceptually includes `reservation_id`, `execution_id`, `node`, `resources`, `state`, `created_at`, `expires_at`, `lease_expires_at`, `last_heartbeat_at`, `lease_owner`, `released_at`, `owner`, and `reason`.

An active execution periodically renews its reservation lease through a heartbeat attributable to `lease_owner`. Failure to renew by `lease_expires_at` moves the reservation to `suspected_stale`; expiration alone does not immediately free capacity when execution may still be active. Reconciliation checks execution ownership, provider state, service state, node reachability, and configured grace periods before releasing capacity.

The target node is authoritative for reservations against its resources. Duplicate release is idempotent. Process or runtime restart reconciliation is conservative and observable: it must avoid double-admitting unsafe work while eventually releasing reservations proven abandoned after terminal cleanup and configured grace periods.

A `ResourceSnapshot` conceptually includes `timestamp`, `node`, CPU, RAM, GPU, VRAM, disk, services, models, reservations, queue depth, pressure state, and probe warnings.

Providers are not required to know exact VRAM consumption. Estimates may be measured, benchmark-derived, configured, or unknown, and their source and confidence should be retained. Unknown estimates are subject to conservative policy rather than being treated as zero.

## Resource Pressure States

- **normal:** capacity is comfortably within configured limits; normal admission policy applies.
- **elevated:** capacity is tightening; preserve headroom and avoid speculative concurrency.
- **high:** admit only work whose requirements and compatibility are known safe; prefer queueing and controlled idle eviction.
- **critical:** do not admit new optional GPU work; preserve active non-preemptible execution; permit controlled eviction of idle workloads; emit explicit diagnostics.
- **unknown:** one or more required probes are missing, stale, or invalid; admission follows the configured conservative unknown-capacity policy.

At critical pressure GreenBoost never kills unrelated processes, terminates user applications on Windows, or reboots a node automatically. Recovery is limited to allowlisted AEGIS-managed workloads and lifecycle actions.

## Scheduling Semantics

Priority classes, highest first, are `critical`, `interactive`, `normal`, `background`, and `maintenance`. Callers may request a priority, but `ExecutionOrchestratorRuntime` validates and normalizes it before scheduling. Provider metadata cannot elevate priority. `critical` is limited to allowlisted trusted system capabilities or explicit administrative policy; unauthorized elevation is rejected or downgraded according to explicit policy and is audited.

FIFO ordering applies within equal priority. Bounded aging prevents starvation without promoting work into `critical` or allowing any priority to bypass hard resource-safety constraints.

Every queued request has a queue timeout; every admitted execution has an execution timeout and cancellation path. Active inference is non-preemptible by default. Preemption is permitted only for work explicitly marked preemptible and known safe to interrupt. One GPU-exclusive workload per GPU is the default, while CPU concurrency is configurable.

The scheduler obtains a reservation before provider invocation and releases it in success, failure, cancellation, timeout, and defensive `finally` paths. A voice request normally outranks background embedding ingestion, but an active image-generation job is not killed merely because voice arrives. OCR and embeddings may run concurrently only when policy and measured capacity allow it. ComfyUI and a large Ollama model are not presumed safe together on 8 GB VRAM.

## Profiles

Profiles are configuration-driven and do not authorize unsafe overcommit.

### performance

Prioritizes latency and warm services, retains idle resources longer, and permits measured-safe concurrency.

### balanced

The initial default profile. It uses moderate idle timeouts, conservative GPU concurrency, and normal queue behavior.

### eco

Uses aggressive idle unloading, keeps fewer services warm, prefers CPU only for explicitly CPU-safe lightweight work, and lowers background concurrency.

### emergency

Applies when pressure is critical or when manually selected. It rejects nonessential background work, unloads idle models and services, and preserves active non-preemptible tasks. It performs no destructive OS action and makes no silent provider substitution.

## Provider Contract

Before execution:

1. Build or resolve a `ResourceRequest`.
2. Submit it through `ExecutionOrchestratorRuntime`.
3. Obtain a confirmed reservation.
4. Ensure the selected provider, service, and model are ready.
5. Execute.

After execution:

1. Record the outcome.
2. Update actual usage when available.
3. Release the reservation.
4. Apply lifecycle policy.
5. Publish events.

Providers must not allocate production GPU work without a reservation; silently switch provider, model, GPU to CPU, or quality; bypass queue policy; or hide resource errors. A fallback is allowed only when explicit policy and the request permit it, and the result metadata records the original choice, fallback, and reason.

## Service and Model Lifecycle

Lifecycle policy covers Ollama, ComfyUI, Unlimited OCR, PaddleOCR, the BGE-M3 embedding service, and future Qwen3-VL, `faster-whisper`, and TTS services. Each integration must distinguish:

- service process lifecycle;
- provider readiness;
- model loaded state;
- model warm state;
- execution reservation.

Service health does not imply that a model is loaded or warm. Likewise, a loaded model does not imply that an execution owns the GPU. Lifecycle operations must be allowlisted, observable, idempotent where practical, and blocked while conflicting reservations exist.

## Remote Runtime Integration

Windows may submit resource-intensive work to the Ubuntu AI server. Each node has a stable validated identifier and an explicit `local` or `remote` scope. Ubuntu reports timestamped snapshots; Windows must display their age because remote snapshots can become stale.

Admission accounts for snapshot age, and the target node must atomically confirm a reservation against its current state. A network failure, stale snapshot, or rejected confirmation produces an explicit state. Remote fallback never occurs silently.

Stage 7 supports one primary remote AI node. The request, snapshot, reservation, and node contracts remain compatible with future multi-node selection, but multi-node scheduling and distributed inference are not implemented by this stage.

## Configuration

Policy must be configuration-driven. The following example is non-binding; exact key names may be adjusted during implementation through compatibility-aware design:

```yaml
greenboost:
  mode: observe
  profile: balanced

  scheduler:
    max_queue_size: 100
    default_queue_timeout_seconds: 300
    default_execution_timeout_seconds: 3600
    starvation_threshold_seconds: 900

  gpu:
    exclusive_by_default: true
    minimum_free_vram_mb: 512
    critical_free_vram_mb: 256
    allow_unknown_vram: false

  lifecycle:
    ollama_idle_timeout_seconds: 900
    comfyui_idle_timeout_seconds: 600
    embedding_idle_timeout_seconds: 900
    ocr_idle_timeout_seconds: 600

  fallback:
    allow_cpu: false
    allow_remote: true
    allow_provider_substitution: false
    allow_quality_reduction: false

  diagnostics:
    history_limit: 200
    expose_process_details: false
```

GreenBoost has three canonical operating modes:

- **disabled:** GreenBoost enforcement and observation are disabled. This is an explicit legacy compatibility path until a future RFC removes it. Diagnostics expose that legacy execution behavior is active, and no partial GreenBoost policies may remain silently enabled.
- **observe:** GreenBoost collects snapshots, estimates decisions, produces diagnostics, and records what would have been admitted, queued, or rejected, but does not change execution behavior. This is the initial migration and installation default.
- **enforce:** admission control, reservations, queueing, lifecycle policy, and explicit rejection are active.

Transition to `enforce` requires completed acceptance and owner approval. The active mode is visible in diagnostics and events, and every mode change is audited. This RFC does not modify `config/services.yaml` or any other configuration file.

## Events

The event contract includes:

- `resource.snapshot.created`, `resource.pressure.changed`, `resource.requested`, `resource.queued`, `resource.admitted`, `resource.rejected`, `resource.reserved`, `resource.released`, `resource.leak.detected`;
- `scheduler.execution.started`, `scheduler.execution.completed`, `scheduler.execution.failed`, `scheduler.execution.cancelled`, `scheduler.execution.timed_out`;
- `lifecycle.service.starting`, `lifecycle.service.ready`, `lifecycle.service.stopped`, `lifecycle.service.failed`;
- `lifecycle.model.loading`, `lifecycle.model.loaded`, `lifecycle.model.unloaded`;
- `greenboost.mode.changed`, `greenboost.profile.changed`, `greenboost.recovery.started`, `greenboost.recovery.completed`, `greenboost.recovery.failed`.

Payloads carry identifiers, state transitions, timestamps, resource summaries, and sanitized reasons. They must not expose secrets, tokens, full prompts, full OCR text, private document contents, or arbitrary environment variables.

## CLI

Future diagnostic and administrative commands are:

- `aegis resources status`
- `aegis resources status --json`
- `aegis resources watch`
- `aegis resources queue`
- `aegis resources reservations`
- `aegis resources services`
- `aegis resources models`
- `aegis resources profile`
- `aegis resources profile set balanced`
- `aegis resources release RESERVATION_ID`
- `aegis doctor resources`
- `aegis doctor gpu`
- `aegis doctor services`
- `aegis doctor scheduler`
- `aegis greenboost doctor`

Manual release, eviction, stop, unload, or comparable dangerous operations require explicit confirmation where appropriate and must create audit events. These commands are contracts for later implementation; this RFC does not implement them.

## Failure and Recovery

GreenBoost handles stale reservations, provider and service crashes, probe failures, remote disconnects, timeouts, cancellation, model-load failures, insufficient VRAM, inaccurate resource estimates, failed unloads, and partial lifecycle transitions.

There is no silent fallback and no infinite retry. Recovery attempts are bounded, observable, and end in an explicit terminal failure when exhausted. The audit trail is preserved. Reservations are released after every terminal execution state, and duplicate release is idempotent.

An expired lease enters `suspected_stale` rather than immediately returning capacity. Conservative reconciliation checks execution ownership, provider and service state, node reachability, and configured grace periods. Network partitions and runtime restarts retain uncertain reservations until reconciliation provides sufficient evidence to release them. Terminal cleanup must eventually release abandoned reservations without double-admitting unsafe work. Active user workloads are never killed automatically.

A failed lifecycle transition records the last confirmed state and uncertainty rather than inventing a successful state. Estimate errors feed later diagnostics and tuning without retroactively falsifying the reservation record.

## Security

GreenBoost requires least privilege, authenticated remote control, validated node identity, allowlists for controllable services and critical-priority capabilities, bounded queues, rate limiting where appropriate, and protection against reservation exhaustion. Provider metadata is schema-validated, bounded, and treated as untrusted; it cannot elevate scheduling priority.

`ExecutionOrchestratorRuntime` validates and normalizes caller-requested priority. Unauthorized `critical` requests are rejected or downgraded only according to explicit policy, and the decision is audited. Critical priority never bypasses hard resource-safety constraints.

Untrusted requests cannot cause arbitrary process termination, arbitrary Docker control, or unvalidated shell execution. Secrets are excluded from events and diagnostics. External `gitlab.com/IsolatedOctopi/greenboost` remains isolated and **EXPERIMENTAL**; audit, benchmark, rollback planning, a separate RFC, and owner acceptance are prerequisites to any future production integration.

## Observability

The runtime exposes structured logs and machine-readable diagnostics with execution correlation IDs, reservation IDs, provider and node attribution, queue wait and execution duration, lifecycle transition duration, estimated versus observed usage, pressure transitions, probe freshness and warnings, and recovery actions. Human-readable output must explain why work is queued, rejected, degraded under explicit policy, or recovering.

## Compatibility

Implementation must preserve existing OCR, image, embedding, mission, project, and remote-runtime behavior. Existing direct APIs may remain temporarily available during an explicit migration, while production resource-intensive execution progressively moves through `ExecutionOrchestratorRuntime`.

No provider public API may break without a separate RFC and migration plan. The contract supports Windows and Ubuntu, the RTX 3050 8 GB baseline, future higher-memory GPUs, and future multi-node execution without changing public request semantics.

## Migration Strategy

### Phase 1: Observe

- Introduce resource models, probes, snapshots, and diagnostics.
- Make `observe` the initial migration and installation mode.
- Record admission decisions without enforcement or execution behavior changes.

### Phase 2: Coordinate

- Add reservations, admission, and a bounded queue.
- Integrate the coordinator beneath `ExecutionOrchestratorRuntime`.

### Phase 3: Integrate Providers

- Integrate OCR, BGE-M3 embeddings, and image generation.
- Add lifecycle accounting and explicit resource failures while preserving public APIs.

### Phase 4: Manage Lifecycle

- Add service/model lifecycle, profiles, idle policy, and bounded recovery.

### Phase 5: Enforce and Accept

- Add target-node reservation confirmation and stale-snapshot rules.
- Run acceptance benchmarks and manual Windows/Ubuntu validation.
- Transition to `enforce` only after completed acceptance and owner approval.

Global enforcement must not be enabled before observation-only data and estimates have been validated against the target environment.

## Testing Strategy

Testing includes unit tests, integration tests, concurrency tests, failure injection, remote-disconnect and stale-snapshot tests, reservation-leak and queue-timeout tests, lifecycle-transition tests, backward-compatibility tests, and security tests. It verifies heartbeat renewal, expired leases entering `suspected_stale`, network partitions, idempotent duplicate release, conservative restart reconciliation, eventual abandoned-reservation cleanup, and rejection or policy-controlled downgrade of unauthorized critical-priority requests. Real GPU access is not required unless a test is explicitly marked as integration/hardware.

Mode tests verify that `disabled` exposes legacy behavior with no partial policy, `observe` records decisions without changing execution, and `enforce` activates admission, reservations, queueing, lifecycle policy, and explicit rejection. They also verify mode visibility, audit events, and the acceptance gate for transition to `enforce`.

Hardware acceptance must exercise incompatible and compatible workload combinations on the RTX 3050 8 GB baseline and record the effective profile, measurements, decisions, reservations, and terminal outcomes.

## Acceptance Criteria

1. Every resource-intensive execution can be correlated to an execution ID.
2. GPU-bound production execution obtains a reservation before provider invocation.
3. Reservations release after success, failure, cancellation, and timeout, and duplicate release is idempotent.
4. Queue order follows priority and FIFO rules, subject to bounded starvation prevention.
5. No silent CPU, provider, model, or quality fallback occurs.
6. The RTX 3050 8 GB profile cannot admit clearly incompatible configured workloads concurrently.
7. OCR, BGE-M3, and ComfyUI remain backward compatible.
8. Remote resource state is visible with snapshot age.
9. Stale remote state cannot be treated as fresh capacity.
10. CLI diagnostics expose queue, reservations, services, models, node, and pressure.
11. Probe failure is shown as unknown/error, not zero usage.
12. Active user processes are never killed automatically.
13. Secrets and full content are absent from events.
14. Recovery attempts are bounded and observable.
15. Observation-only mode can run without changing execution behavior.
16. `disabled` mode exposes legacy compatibility behavior and leaves no observation or enforcement policy partially active.
17. Existing tests continue to pass.
18. New test coverage documents scheduler, reservation, recovery, and lifecycle behavior.
19. Manual acceptance is completed on the real Windows and Ubuntu environment.
20. Owner approval is recorded before final production enforcement.
21. `observe` is the initial migration and installation default, records would-admit/queue/reject decisions, and does not change execution behavior.
22. `enforce` activates admission control, reservations, queueing, lifecycle policy, and explicit rejection only after completed acceptance and owner approval.
23. Diagnostics and events expose the active mode, and mode changes are audited.
24. Active reservations renew leases by heartbeat; missed renewal produces `suspected_stale` rather than immediate capacity release.
25. Expired leases, network partitions, and process/runtime restarts reconcile conservatively against target-node ownership, provider/service state, reachability, and grace periods.
26. Terminal cleanup eventually releases abandoned reservations without double-admitting unsafe work.
27. The target node is authoritative for reservations against its resources.
28. Provider metadata cannot elevate priority, and unauthorized `critical` requests are rejected or explicitly downgraded and audited.
29. Priority aging never promotes work into `critical`, and critical work cannot bypass hard resource-safety constraints.

## Open Questions

- How should VRAM estimates be derived, versioned, and updated from observed data?
- Should Ollama model unloading use native APIs, service restart, or both?
- Which workloads are demonstrably safe to preempt?
- Should image generation be GPU-exclusive by default?
- Which diagnostics may expose process names?
- How long may remote snapshots remain valid for admission?
- What level of CPU fallback is acceptable for Voice?
- Should the first implementation persist the ledger or keep it in memory?
- How should stale reservations be reconciled after process restart?
- Which profile should be the installation default after observation and acceptance?

## Future Work

- Qwen3-VL integration;
- Voice Runtime;
- AIRI and Game Companion;
- Desktop and Office Co-worker;
- distributed runtime;
- multi-GPU and multi-node scheduling;
- predictive resource estimation;
- resource dashboard and historical telemetry;
- an optional separate RFC to audit external GreenBoost.

## Constraints

- This task and RFC are documentation only.
- External GreenBoost is not installed, downloaded, imported, or integrated.
- GreenBoost does not create a second orchestrator or replace `ExecutionOrchestratorRuntime`.
- This RFC contains no runtime implementation or provider rewrite.
- Existing RFCs are not renamed, deleted, or renumbered; the RFC-052 collision remains untouched.
- Untracked files are not changed.
- No commit or push occurs before explicit owner acceptance.
