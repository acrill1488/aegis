"""Data models for knowledge retrieval and local project knowledge."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class KnowledgeSource:
    """Legacy provider source used by KnowledgeEngine."""

    type: str
    title: str
    content: str
    url: str | None = None
    score: float = 1.0
    valid: bool = True
    error: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class KnowledgeBundle:
    query: str
    sources: list[KnowledgeSource]
    summary: str = ""
    gaps: list[str] = field(default_factory=list)


@dataclass
class KnowledgeDocument:
    id: str
    path: str
    title: str
    type: str
    checksum: str
    modified_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "KnowledgeDocument":
        return cls(
            id=str(item["id"]),
            path=str(item["path"]),
            title=str(item.get("title") or ""),
            type=str(item.get("type") or ""),
            checksum=str(item.get("checksum") or ""),
            modified_at=_parse_datetime(item.get("modified_at")),
            metadata=dict(item.get("metadata") or {}),
        )


@dataclass
class KnowledgeChunk:
    id: str
    document_id: str
    text: str
    index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "KnowledgeChunk":
        return cls(
            id=str(item["id"]),
            document_id=str(item["document_id"]),
            text=str(item.get("text") or ""),
            index=int(item.get("index") or 0),
            metadata=dict(item.get("metadata") or {}),
        )


@dataclass
class KnowledgeEntity:
    id: str
    name: str
    type: str
    document_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "KnowledgeEntity":
        return cls(
            id=str(item["id"]),
            name=str(item.get("name") or ""),
            type=str(item.get("type") or ""),
            document_id=str(item.get("document_id") or ""),
            metadata=dict(item.get("metadata") or {}),
        )


@dataclass
class KnowledgeContext:
    goal: str
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    documents: list[KnowledgeDocument] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return utc_now()
