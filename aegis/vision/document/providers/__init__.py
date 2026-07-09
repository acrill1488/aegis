"""Document Intelligence providers."""

from .base import DocumentProvider
from .stub import StubDocumentProvider

__all__ = ["DocumentProvider", "StubDocumentProvider"]
