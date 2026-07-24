"""Structured Document artifact helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import StructuredDocument


DOCUMENT_ARTIFACT_TYPE = "document.structured"


def document_artifact_metadata(document: StructuredDocument) -> dict[str, Any]:
    """Return stable metadata for a Structured Document artifact."""
    return {
        "provider": document.provider,
        "page_count": document.statistics.get("page_count", len(document.pages)),
        "block_count": document.statistics.get("block_count", 0),
        "table_count": document.statistics.get("table_count", 0),
        "language": document.language,
    }


def create_document_artifact(
    document: StructuredDocument,
    path: str | Path,
    *,
    content_type: str = "application/json",
) -> dict[str, Any]:
    """Create a plain artifact record for a Structured Document file."""
    return {
        "type": DOCUMENT_ARTIFACT_TYPE,
        "path": str(path),
        "content_type": content_type,
        "metadata": document_artifact_metadata(document),
    }
