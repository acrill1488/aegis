from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class IPCRequest:
    id: str
    target: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        target: str,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> "IPCRequest":
        return cls(
            id=str(uuid4()),
            target=target,
            action=action,
            payload=payload or {},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IPCRequest":
        return cls(
            id=str(data.get("id") or uuid4()),
            target=str(data.get("target") or ""),
            action=str(data.get("action") or ""),
            payload=dict(data.get("payload") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target": self.target,
            "action": self.action,
            "payload": self.payload,
        }


@dataclass(slots=True)
class IPCResponse:
    id: str
    success: bool
    output: dict[str, Any] | list[Any] | str | int | float | bool | None = None
    error: str | None = None

    @classmethod
    def ok(cls, request_id: str, output: Any = None) -> "IPCResponse":
        return cls(id=request_id, success=True, output=output, error=None)

    @classmethod
    def fail(cls, request_id: str, error: str) -> "IPCResponse":
        return cls(id=request_id, success=False, output=None, error=error)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IPCResponse":
        return cls(
            id=str(data.get("id") or ""),
            success=bool(data.get("success")),
            output=data.get("output"),
            error=data.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
        }
