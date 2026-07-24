"""Structured Document contract package."""

from .artifacts import DOCUMENT_ARTIFACT_TYPE, create_document_artifact, document_artifact_metadata
from .builder import StructuredDocumentBuilder
from .models import (
    DocumentBlock,
    DocumentFigure,
    DocumentPage,
    DocumentTable,
    StructuredDocument,
)
from .serializer import StructuredDocumentSerializer, to_plain_document
from .validator import DocumentValidationResult, StructuredDocumentValidator

__all__ = [
    "DOCUMENT_ARTIFACT_TYPE",
    "DocumentBlock",
    "DocumentFigure",
    "DocumentPage",
    "DocumentTable",
    "DocumentValidationResult",
    "StructuredDocument",
    "StructuredDocumentBuilder",
    "StructuredDocumentSerializer",
    "StructuredDocumentValidator",
    "create_document_artifact",
    "document_artifact_metadata",
    "to_plain_document",
]
