"""Response Protocol v1 contracts."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class ResponseContract:
    """Structured model response extracted from protocol output."""

    thought: Optional[str]
    tool_calls: list
    final_answer: str
    citations: list
    metadata: dict[str, Any] = field(default_factory=dict)
