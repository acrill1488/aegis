"""OCR Runtime exceptions."""

from __future__ import annotations


class OCRRuntimeError(RuntimeError):
    """Base error for OCR Runtime failures."""


class OCRProviderNotFound(OCRRuntimeError):
    """Raised when a requested OCR provider is not registered."""


class OCRNotImplemented(OCRRuntimeError):
    """Raised when OCR recognition is intentionally not implemented yet."""
