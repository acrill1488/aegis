"""OCR provider implementations."""

from .unlimited import UnlimitedOCRProvider
from aegis.providers.paddleocr import PaddleOCRProvider

__all__ = ["PaddleOCRProvider", "UnlimitedOCRProvider"]
