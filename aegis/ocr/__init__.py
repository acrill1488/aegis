"""OCR Runtime public API."""

from .models import OCRBlock, OCRResult, OCRTable
from .provider import OCRProvider, StubOCRProvider
from .registry import OCRProviderRegistry, OCRRegistry
from .runtime import OCRRuntime

__all__ = [
    "OCRBlock",
    "OCRProvider",
    "OCRProviderRegistry",
    "OCRRegistry",
    "OCRResult",
    "OCRRuntime",
    "OCRTable",
    "StubOCRProvider",
]
