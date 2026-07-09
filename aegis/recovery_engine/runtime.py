from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from aegis.serialization import to_plain

from .models import RecoveryAttempt, RecoveryDecision
from .strategies import (
    browser_relocate,
    browser_wait_reload,
    daemon_restart,
    no_recovery,
)


DEFAULT_HISTORY_PATH = Path("F:/AI_WORKSPACE/recovery/history.json")


class RecoveryEngineRuntime:
    """Chooses and records one simple recovery action for failed operations."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        history_path: Path | str = DEFAULT_HISTORY_PATH,
    ):
        self.core = core
        self.history_path = Path(history_path)
        self._strategies = (
            daemon_restart,
            browser_relocate,
            browser_wait_reload,
        )

    def decide(
        self,
        action: str,
        payload: dict[str, Any],
        error: Exception | str,
        context: dict[str, Any] | None = None,
    ) -> RecoveryDecision:
        context = self._context(context)
        error_text = str(error)
        for strategy in self._strategies:
            decision = strategy(action, payload, error_text, context)
            if decision is not None:
                return decision
        return no_recovery(action, payload, error_text, context)

    def recover(
        self,
        action: str,
        payload: dict[str, Any],
        error: Exception | str,
        context: dict[str, Any] | None = None,
    ) -> RecoveryDecision:
        context = self._context(context)
        started_at = self._now()
        decision = self.decide(action, payload, error, context)
        completed_at = self._now()
        self.record_attempt(
            source=str(context.get("source") or action),
            error=str(error),
            strategy=decision.strategy,
            success=decision.should_retry,
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "action": action,
                "reason": decision.reason,
                "decision": to_plain(decision),
                **dict(context.get("attempt_metadata") or {}),
            },
        )
        return decision

    def record_attempt(
        self,
        *,
        source: str,
        error: str,
        strategy: str,
        success: bool,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RecoveryAttempt:
        attempt = RecoveryAttempt(
            id=f"recovery_{uuid4().hex}",
            source=source,
            error=error,
            strategy=strategy,
            success=success,
            started_at=started_at or self._now(),
            completed_at=completed_at or self._now(),
            metadata=metadata or {},
        )
        self._append_history(attempt)
        return attempt

    def history(self) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def status(self) -> dict[str, Any]:
        history = self.history()
        successful = [item for item in history if item.get("success")]
        latest = history[-1] if history else None
        return {
            "history_path": str(self.history_path),
            "attempt_count": len(history),
            "successful_attempt_count": len(successful),
            "failed_attempt_count": len(history) - len(successful),
            "latest": latest,
        }

    def _context(self, context: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(context or {})
        if "action_dispatcher" not in merged and self.core is not None:
            dispatcher = getattr(self.core, "scenario_runtime", None)
            if dispatcher is not None:
                merged["action_dispatcher"] = dispatcher
        return merged

    def _append_history(self, attempt: RecoveryAttempt) -> None:
        history = self.history()
        history.append(to_plain(attempt))
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
