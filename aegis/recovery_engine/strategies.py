from __future__ import annotations

from copy import deepcopy
from typing import Any

from aegis.daemon.supervisor import DaemonSupervisor
from aegis.scenarios import ScenarioStep
from aegis.serialization import to_plain

from .models import RecoveryDecision


DAEMON_ERROR_MARKERS = ("daemon", "connection refused", "not running")
BROWSER_LOCATE_MARKERS = ("element not found", "timeout", "selector", "locator")
BROWSER_WAIT_MARKERS = ("navigation timeout", "timeout")
BROWSER_SELECTOR_ACTIONS = {"browser.fill", "browser.click"}


def daemon_restart(
    action: str,
    payload: dict[str, Any],
    error: str,
    context: dict[str, Any],
) -> RecoveryDecision | None:
    if not _contains_any(error, DAEMON_ERROR_MARKERS):
        return None
    result = DaemonSupervisor().ensure_running()
    return RecoveryDecision(
        should_retry=bool(result.get("running")),
        strategy="daemon_restart",
        patched_payload=deepcopy(payload),
        reason="Daemon looked unavailable; ensured the daemon is running.",
        metadata={"daemon": to_plain(result)},
    )


def browser_relocate(
    action: str,
    payload: dict[str, Any],
    error: str,
    context: dict[str, Any],
) -> RecoveryDecision | None:
    if action not in BROWSER_SELECTOR_ACTIONS:
        return None
    if not _contains_any(error, BROWSER_LOCATE_MARKERS):
        return None
    if not isinstance(payload.get("selector"), str):
        return None

    locate_payload = _locate_payload(payload, context)
    if not locate_payload.get("query"):
        return None

    dispatcher = context.get("action_dispatcher")
    run_step = getattr(dispatcher, "run_step", None)
    if not callable(run_step):
        return None

    locate_result = run_step(
        ScenarioStep(
            id="recovery-ui-locate",
            action="ui.locate",
            payload=locate_payload,
        )
    )
    if not locate_result.get("success"):
        return RecoveryDecision(
            should_retry=False,
            strategy="browser_relocate",
            patched_payload=deepcopy(payload),
            reason="UI relocation failed.",
            metadata={"locate_result": to_plain(locate_result)},
        )

    selector = _selector_from_locate(locate_result.get("output") or {})
    if not selector:
        return RecoveryDecision(
            should_retry=False,
            strategy="browser_relocate",
            patched_payload=deepcopy(payload),
            reason="UI relocation did not return a usable selector.",
            metadata={"locate_result": to_plain(locate_result)},
        )

    patched_payload = deepcopy(payload)
    patched_payload["selector"] = selector
    return RecoveryDecision(
        should_retry=True,
        strategy="browser_relocate",
        patched_payload=patched_payload,
        reason="Replaced the browser selector with a UI-located selector.",
        metadata={
            "locate_payload": to_plain(locate_payload),
            "locate_result": to_plain(locate_result),
        },
    )


def browser_wait_reload(
    action: str,
    payload: dict[str, Any],
    error: str,
    context: dict[str, Any],
) -> RecoveryDecision | None:
    if not action.startswith("browser."):
        return None
    if not _contains_any(error, BROWSER_WAIT_MARKERS):
        return None

    dispatcher = context.get("action_dispatcher")
    run_step = getattr(dispatcher, "run_step", None)
    if not callable(run_step):
        return None

    wait_result = run_step(
        ScenarioStep(
            id="recovery-browser-wait",
            action="browser.wait",
            payload={"timeout_ms": 1000},
        )
    )
    return RecoveryDecision(
        should_retry=bool(wait_result.get("success")),
        strategy="browser_wait_reload",
        patched_payload=deepcopy(payload),
        reason="Waited for the browser before retrying the action.",
        metadata={"wait_result": to_plain(wait_result)},
    )


def no_recovery(
    action: str,
    payload: dict[str, Any],
    error: str,
    context: dict[str, Any],
) -> RecoveryDecision:
    return RecoveryDecision(
        should_retry=False,
        strategy="no_recovery",
        patched_payload=deepcopy(payload),
        reason="No Recovery Engine v1 strategy matched this error.",
        metadata={},
    )


def _contains_any(error: str, markers: tuple[str, ...]) -> bool:
    lowered = str(error or "").casefold()
    return any(marker.casefold() in lowered for marker in markers)


def _locate_payload(
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    metadata = context.get("metadata") or {}
    locate_payload: dict[str, Any] = {}
    for source in (metadata, payload):
        query = source.get("query")
        if query not in (None, ""):
            locate_payload["query"] = str(query)
            break
    role = metadata.get("role") or payload.get("role")
    if role not in (None, ""):
        locate_payload["role"] = str(role)
    return locate_payload


def _selector_from_locate(output: Any) -> str | None:
    if not isinstance(output, dict):
        return None
    best_match = output.get("best_match")
    if isinstance(best_match, dict):
        selector = best_match.get("selector")
        if isinstance(selector, str) and selector.strip():
            return selector
    matches = output.get("matches")
    if isinstance(matches, list):
        for match in matches:
            if not isinstance(match, dict):
                continue
            selector = match.get("selector")
            if isinstance(selector, str) and selector.strip():
                return selector
    return None
