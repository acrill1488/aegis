"""Structured Document validation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import StructuredDocument


@dataclass
class DocumentValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class StructuredDocumentValidator:
    """Validate the internal document contract before downstream use."""

    REQUIRED_FIELDS = ("id", "source", "provider", "created_at", "language")

    def validate(self, document: StructuredDocument) -> DocumentValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        for field_name in self.REQUIRED_FIELDS:
            if getattr(document, field_name, None) in (None, ""):
                errors.append(f"missing required field: {field_name}")

        if not isinstance(document.pages, list) or not document.pages:
            errors.append("document must contain at least one page")

        seen_block_ids: set[str] = set()
        for page in document.pages:
            if page.number < 1:
                errors.append(f"page number must be positive: {page.number}")

            page_block_ids: set[str] = set()
            for block in page.blocks:
                if not block.id:
                    errors.append(f"page {page.number} contains a block without id")
                    continue
                if block.id in seen_block_ids:
                    errors.append(f"duplicate block id: {block.id}")
                seen_block_ids.add(block.id)
                page_block_ids.add(block.id)

            if not page.reading_order:
                warnings.append(f"page {page.number} has empty reading_order")
            for block_id in page.reading_order:
                if block_id not in page_block_ids:
                    errors.append(
                        f"page {page.number} reading_order references missing block: {block_id}"
                    )

        return DocumentValidationResult(valid=not errors, errors=errors, warnings=warnings)
