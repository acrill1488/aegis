"""OCR provider interface and foundation stub provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .exceptions import OCRNotImplemented
from .models import OCRResult


class ProviderName(str):
    """String provider id that also supports the foundation `name()` API."""

    def __call__(self) -> str:
        return str(self)


class OCRProvider(Protocol):
    """Provider contract for text and document-structure extraction."""

    def name(self) -> str:
        ...

    def available(self) -> bool:
        ...

    def health(self) -> dict[str, Any]:
        ...

    def recognize_image(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        ...

    def recognize_document(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        ...

    def recognize_pdf(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        ...

    def recognize_directory(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        ...

    def supported_formats(self) -> list[str]:
        ...

    def capabilities(self) -> dict[str, Any]:
        ...


class StubOCRProvider:
    """Dependency-free provider used to expose the OCR Runtime contract."""

    name = ProviderName("stub")

    def available(self) -> bool:
        return True

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "provider": self.name,
            "mode": "stub",
            "models_checked": False,
        }

    def recognize_image(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        return self._not_implemented_result(source, language, "image", options)

    def recognize_document(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        return self._not_implemented_result(source, language, "document", options)

    def recognize_pdf(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        return self._not_implemented_result(source, language, "pdf", options)

    def recognize_directory(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        return self._not_implemented_result(source, language, "directory", options)

    def supported_formats(self) -> list[str]:
        return ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "pdf"]

    def capabilities(self) -> dict[str, Any]:
        return {
            "mode": "stub",
            "requires_model": False,
            "recognition": False,
            "images": True,
            "documents": True,
            "pdf": True,
            "tables": False,
            "layout": False,
            "languages": [],
        }

    def _not_implemented_result(
        self,
        source: str | Path,
        language: str | None,
        source_type: str,
        options: dict[str, Any] | None,
    ) -> OCRResult:
        error = (
            "OCR recognition is not implemented in the foundation stub. "
            "Register a production provider in a later sprint."
        )
        return OCRResult(
            provider=self.name,
            language=language or "unknown",
            source=str(source),
            metadata={"source_type": source_type, "options": dict(options or {})},
            warnings=["StubOCRProvider exposes the OCR API but does not run OCR models."],
            errors=[error],
        )

    def raise_not_implemented(self) -> None:
        raise OCRNotImplemented("StubOCRProvider does not perform OCR recognition.")
