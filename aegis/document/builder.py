"""Build StructuredDocument objects from OCR outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .models import (
    DocumentBlock,
    DocumentFigure,
    DocumentPage,
    DocumentTable,
    StructuredDocument,
)


class StructuredDocumentBuilder:
    """Convert OCR provider output into the official document contract."""

    def from_ocr_result(self, ocr_result: Any) -> StructuredDocument:
        pages = self._build_pages(ocr_result)
        statistics = self._statistics(ocr_result, pages)
        return StructuredDocument(
            id=f"doc_{uuid4().hex}",
            source=getattr(ocr_result, "source", ""),
            provider=str(getattr(ocr_result, "provider", "") or "unknown"),
            created_at=datetime.now(timezone.utc).isoformat(),
            language=str(getattr(ocr_result, "language", "") or "unknown"),
            metadata={
                "source_runtime": "ocr",
                "ocr_confidence": getattr(ocr_result, "confidence", None),
                "ocr_processing_time": getattr(ocr_result, "processing_time", 0.0),
                "ocr_metadata": dict(getattr(ocr_result, "metadata", {}) or {}),
                "warnings": list(getattr(ocr_result, "warnings", []) or []),
                "errors": list(getattr(ocr_result, "errors", []) or []),
            },
            plain_text=str(getattr(ocr_result, "text", "") or ""),
            pages=pages,
            attachments=[],
            statistics=statistics,
            artifacts=list(getattr(ocr_result, "artifacts", []) or []),
        )

    def _build_pages(self, ocr_result: Any) -> list[DocumentPage]:
        raw_pages = list(getattr(ocr_result, "pages", []) or [])
        page_numbers = self._page_numbers(ocr_result, raw_pages)
        pages = [self._page_from_raw(number, raw_pages) for number in page_numbers]

        page_by_number = {page.number: page for page in pages}
        used_block_ids: set[str] = set()
        for index, block in enumerate(getattr(ocr_result, "blocks", []) or [], start=1):
            page_number = int(self._field(block, "page", 1) or 1)
            page = page_by_number.setdefault(page_number, DocumentPage(number=page_number))
            block_id = str(self._field(block, "id", "") or f"p{page_number}-b{len(page.blocks) + 1}")
            if block_id in used_block_ids:
                block_id = f"{block_id}-{index}"
            used_block_ids.add(block_id)
            document_block = DocumentBlock(
                id=block_id,
                bbox=list(self._field(block, "bbox", []) or []),
                text=str(self._field(block, "text", "") or ""),
                role=str(self._field(block, "role", "text") or "text"),
                confidence=self._field(block, "confidence", None),
                metadata=dict(self._field(block, "metadata", {}) or {}),
            )
            page.blocks.append(document_block)
            page.reading_order.append(document_block.id)

        for table in getattr(ocr_result, "tables", []) or []:
            page_number = int(self._field(table, "page", 1) or 1)
            page = page_by_number.setdefault(page_number, DocumentPage(number=page_number))
            page.tables.append(
                DocumentTable(
                    rows=list(self._field(table, "rows", []) or []),
                    columns=list(self._field(table, "columns", []) or []),
                    cells=list(self._field(table, "cells", []) or []),
                    bbox=list(self._field(table, "bbox", []) or []),
                    confidence=self._field(table, "confidence", None),
                )
            )

        for figure in getattr(ocr_result, "figures", []) or []:
            page_number = int(self._field(figure, "page", 1) or 1)
            page = page_by_number.setdefault(page_number, DocumentPage(number=page_number))
            page.figures.append(
                DocumentFigure(
                    bbox=list(self._field(figure, "bbox", []) or []),
                    caption=str(self._field(figure, "caption", "") or ""),
                    metadata=dict(self._field(figure, "metadata", {}) or {}),
                )
            )

        if not any(page.blocks for page in page_by_number.values()):
            text = str(getattr(ocr_result, "text", "") or "")
            first_page = page_by_number.setdefault(1, DocumentPage(number=1))
            block = DocumentBlock(id="p1-b1", text=text, role="text")
            first_page.blocks.append(block)
            first_page.reading_order.append(block.id)

        return [page_by_number[number] for number in sorted(page_by_number)]

    def _page_from_raw(self, number: int, raw_pages: list[Any]) -> DocumentPage:
        raw = next(
            (
                item
                for item in raw_pages
                if int(self._field(item, "number", self._field(item, "page", number)) or number)
                == number
            ),
            {},
        )
        return DocumentPage(
            number=number,
            width=self._field(raw, "width", None),
            height=self._field(raw, "height", None),
            rotation=float(self._field(raw, "rotation", 0.0) or 0.0),
            metadata=dict(self._field(raw, "metadata", {}) or {}),
        )

    def _page_numbers(self, ocr_result: Any, raw_pages: list[Any]) -> list[int]:
        numbers = {
            int(self._field(page, "number", self._field(page, "page", 1)) or 1)
            for page in raw_pages
        }
        for block in getattr(ocr_result, "blocks", []) or []:
            numbers.add(int(self._field(block, "page", 1) or 1))
        for table in getattr(ocr_result, "tables", []) or []:
            numbers.add(int(self._field(table, "page", 1) or 1))
        for figure in getattr(ocr_result, "figures", []) or []:
            numbers.add(int(self._field(figure, "page", 1) or 1))
        return sorted(numbers or {1})

    def _statistics(self, ocr_result: Any, pages: list[DocumentPage]) -> dict[str, Any]:
        return {
            "page_count": len(pages),
            "block_count": sum(len(page.blocks) for page in pages),
            "table_count": sum(len(page.tables) for page in pages),
            "figure_count": sum(len(page.figures) for page in pages),
            "character_count": len(str(getattr(ocr_result, "text", "") or "")),
        }

    def _field(self, value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)
