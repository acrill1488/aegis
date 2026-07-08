"""Plain-data serialization helpers.

This module is intentionally dependency-light so CLI, daemon, agents, events,
dashboard, and live context code can share one stable serialization boundary.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID


def to_plain(value: Any) -> Any:
    """Convert supported Python objects to JSON-friendly plain values."""
    if value is None or isinstance(value, (int, float, str, bool)):
        return value

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Enum):
        return to_plain(value.value)

    if isinstance(value, (Path, UUID)):
        return str(value)

    if is_dataclass(value) and not isinstance(value, type):
        return to_plain(asdict(value))

    if isinstance(value, dict):
        return {to_plain(key): to_plain(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_plain(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return to_plain(model_dump())
        except Exception:
            pass

    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        try:
            return to_plain(dict_method())
        except Exception:
            pass

    return str(value)


def to_json(value: Any, indent: int | None = 2) -> str:
    """Serialize a value to JSON after converting it to plain data."""
    return json.dumps(to_plain(value), ensure_ascii=False, indent=indent)
