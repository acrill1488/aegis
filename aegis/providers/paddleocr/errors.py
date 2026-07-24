"""Controlled PaddleOCR provider errors."""


class PaddleOCRProviderError(RuntimeError):
    """Base error safe to present through the OCR CLI."""


class PaddleOCRUnavailableError(PaddleOCRProviderError):
    """The optional PaddleOCR package is not installed or is disabled."""


class PaddleOCRInitializationError(PaddleOCRProviderError):
    """The PaddleOCR engine could not be initialized."""

