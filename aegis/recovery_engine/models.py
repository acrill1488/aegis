from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RecoveryAttempt:
    id: str
    source: str
    error: str
    strategy: str
    success: bool
    started_at: datetime
    completed_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryDecision:
    should_retry: bool
    strategy: str
    patched_payload: dict[str, Any]
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)
