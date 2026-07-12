# AEGIS Constitution

## Active Vertical

OCR Platform -> ACTIVE

## Active Sprint

Foundation

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

## Next Active Vertical

No later vertical is active.

The One Active Vertical principle remains mandatory. The active implementation boundary is OCR Platform Foundation only.
