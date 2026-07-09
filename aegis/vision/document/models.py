"""Document Intelligence data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class DocumentExtraction:
    id: str = field(default_factory=lambda: f"document_extraction_{uuid4().hex}")
    path: str = ""
    type: str = ""
    text: str = ""
    supported: bool = True
    provider: str = "stub"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
