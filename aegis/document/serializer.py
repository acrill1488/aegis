"""Structured Document serializers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aegis.serialization import to_json, to_plain

from .models import (
    DocumentBlock,
    DocumentFigure,
    DocumentPage,
    DocumentTable,
    StructuredDocument,
)


class StructuredDocumentSerializer:
    """Serialize and load StructuredDocument objects."""

    def to_json(self, document: StructuredDocument) -> str:
        return to_json(document)

    def to_markdown(self, document: StructuredDocument) -> str:
        parts = [f"# Document {document.id}", ""]
        if document.plain_text:
            parts.extend([document.plain_text.strip(), ""])
        for page in document.pages:
            parts.extend([f"## Page {page.number}", ""])
            block_by_id = {block.id: block for block in page.blocks}
            ordered_blocks = [
                block_by_id[block_id]
                for block_id in page.reading_order
                if block_id in block_by_id
            ]
            if not ordered_blocks:
                ordered_blocks = page.blocks
            for block in ordered_blocks:
                if block.text:
                    parts.extend([block.text.strip(), ""])
            for table in page.tables:
                parts.extend(self._table_to_markdown(table))
        return "\n".join(parts).rstrip() + "\n"

    def to_plain_text(self, document: StructuredDocument) -> str:
        if document.plain_text:
            return document.plain_text
        lines: list[str] = []
        for page in document.pages:
            block_by_id = {block.id: block for block in page.blocks}
            ordered_ids = page.reading_order or [block.id for block in page.blocks]
            for block_id in ordered_ids:
                block = block_by_id.get(block_id)
                if block and block.text:
                    lines.append(block.text)
        return "\n".join(lines)

    def from_json(self, value: str | Path | dict[str, Any]) -> StructuredDocument:
        if isinstance(value, Path):
            data = json.loads(value.read_text(encoding="utf-8"))
        elif isinstance(value, str):
            data = json.loads(value)
        else:
            data = value
        return self.from_plain(data)

    def from_plain(self, data: dict[str, Any]) -> StructuredDocument:
        pages = [
            DocumentPage(
                number=int(page.get("number", page.get("page", 1))),
                width=page.get("width"),
                height=page.get("height"),
                rotation=float(page.get("rotation") or 0.0),
                blocks=[
                    DocumentBlock(
                        id=str(block.get("id", "")),
                        bbox=list(block.get("bbox") or []),
                        text=str(block.get("text") or ""),
                        role=str(block.get("role") or "text"),
                        confidence=block.get("confidence"),
                        metadata=dict(block.get("metadata") or {}),
                    )
                    for block in page.get("blocks", [])
                    if isinstance(block, dict)
                ],
                tables=[
                    DocumentTable(
                        rows=list(table.get("rows") or []),
                        columns=list(table.get("columns") or []),
                        cells=list(table.get("cells") or []),
                        bbox=list(table.get("bbox") or []),
                        confidence=table.get("confidence"),
                    )
                    for table in page.get("tables", [])
                    if isinstance(table, dict)
                ],
                figures=[
                    DocumentFigure(
                        bbox=list(figure.get("bbox") or []),
                        caption=str(figure.get("caption") or ""),
                        metadata=dict(figure.get("metadata") or {}),
                    )
                    for figure in page.get("figures", [])
                    if isinstance(figure, dict)
                ],
                reading_order=list(page.get("reading_order") or []),
                metadata=dict(page.get("metadata") or {}),
            )
            for page in data.get("pages", [])
            if isinstance(page, dict)
        ]
        return StructuredDocument(
            id=str(data.get("id") or ""),
            source=data.get("source") or "",
            provider=str(data.get("provider") or ""),
            created_at=str(data.get("created_at") or ""),
            language=str(data.get("language") or "unknown"),
            metadata=dict(data.get("metadata") or {}),
            plain_text=str(data.get("plain_text") or ""),
            pages=pages,
            attachments=list(data.get("attachments") or []),
            statistics=dict(data.get("statistics") or {}),
            artifacts=list(data.get("artifacts") or []),
        )

    def write_json(self, document: StructuredDocument, path: str | Path) -> Path:
        target = Path(path)
        target.write_text(self.to_json(document), encoding="utf-8")
        return target

    def write_markdown(self, document: StructuredDocument, path: str | Path) -> Path:
        target = Path(path)
        target.write_text(self.to_markdown(document), encoding="utf-8")
        return target

    def write_plain_text(self, document: StructuredDocument, path: str | Path) -> Path:
        target = Path(path)
        target.write_text(self.to_plain_text(document), encoding="utf-8")
        return target

    def _table_to_markdown(self, table: DocumentTable) -> list[str]:
        rows = table.rows
        if not rows:
            return []
        header = table.columns or [str(item) for item in rows[0]]
        body = rows if table.columns else rows[1:]
        lines = [
            "| " + " | ".join(str(cell) for cell in header) + " |",
            "| " + " | ".join("---" for _ in header) + " |",
        ]
        for row in body:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        return lines + [""]


def to_plain_document(document: StructuredDocument) -> dict[str, Any]:
    """Return a JSON-friendly StructuredDocument payload."""
    return to_plain(document)
