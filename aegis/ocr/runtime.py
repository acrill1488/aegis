"""OCR Runtime foundation."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any

from aegis.capabilities import CapabilityDescriptor
from aegis.serialization import to_plain

from .doctor import OCRDoctor
from .events import OCR_EVENTS
from .models import OCRResult
from .registry import OCRRegistry, provider_name


class OCRRuntime:
    """Provider-neutral facade for OCR text and document-structure extraction."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        registry: OCRRegistry | None = None,
    ):
        self.core = core
        self.registry = registry or OCRRegistry()

    def providers(self, payload: dict | None = None) -> list[dict[str, Any]]:
        default_provider = self.default_provider()
        return [
            {
                "name": provider_name(provider),
                "available": provider.available(),
                "default": provider_name(provider) == default_provider,
                "health": provider.health(),
                "capabilities": provider.capabilities(),
                "supported_formats": provider.supported_formats(),
            }
            for provider in self.registry.providers()
        ]

    def doctor(self) -> dict[str, Any]:
        return OCRDoctor(self.registry).report()

    def capabilities(self, provider: str | None = None) -> dict[str, Any]:
        selected = self.registry.provider(provider)
        self._publish(
            OCR_EVENTS["provider_selected"],
            {"provider": provider_name(selected), "reason": "capabilities"},
        )
        return selected.capabilities()

    def supported_formats(self, provider: str | None = None) -> list[str]:
        return self.registry.provider(provider).supported_formats()

    def default_provider(self) -> str:
        return self.registry.default()

    def recognize_image(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        provider: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        return self._recognize("image", source, language=language, provider=provider, options=options)

    def recognize_document(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        provider: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        return self._recognize("document", source, language=language, provider=provider, options=options)

    def recognize_pdf(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        provider: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        return self._recognize("pdf", source, language=language, provider=provider, options=options)

    def recognize_directory(
        self,
        source: str | Path,
        *,
        language: str | None = None,
        provider: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OCRResult:
        return self._recognize("directory", source, language=language, provider=provider, options=options)

    def register_artifact(
        self,
        result: OCRResult,
        *,
        path: str | Path | None = None,
        artifact_type: str = "ocr.result",
    ) -> dict[str, Any] | None:
        project_runtime = getattr(self.core, "project_runtime", None)
        get_active = getattr(project_runtime, "get_active", None)
        add_artifact = getattr(project_runtime, "add_artifact", None)
        if not callable(get_active) or not callable(add_artifact):
            return None
        active_project = get_active()
        if active_project is None:
            return None

        artifact_path = str(path or result.source or "")
        artifact = add_artifact(
            active_project.id,
            artifact_type,
            artifact_path,
            metadata={
                "provider": result.provider,
                "language": result.language,
                "confidence": result.confidence,
                "processing_time": result.processing_time,
                "source": result.source,
                "metadata": to_plain(result.metadata),
                "warnings": list(result.warnings),
                "errors": list(result.errors),
            },
        )
        plain_artifact = to_plain(artifact)
        if plain_artifact not in result.artifacts:
            result.artifacts.append(plain_artifact)
        self._publish(OCR_EVENTS["artifact_saved"], {"artifact": plain_artifact, "result": result})
        return plain_artifact

    def register_capabilities(self) -> None:
        capability_runtime = getattr(self.core, "capability_runtime", None)
        if capability_runtime is None:
            return
        specs = (
            ("ocr.providers", "List OCR Providers", "providers", ["ocr.providers"]),
            ("ocr.doctor", "Run OCR Doctor", "doctor", ["ocr.doctor"]),
            ("ocr.capabilities", "Show OCR Capabilities", "capabilities", ["ocr.capabilities"]),
        )
        for capability_id, name, method, permissions in specs:
            descriptor = CapabilityDescriptor(
                id=capability_id,
                name=name,
                version="1",
                owner_agent="ocr_runtime",
                machine_scope="local",
                permissions=permissions,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                tags=["ocr", "runtime"],
                metadata={
                    "provider_type": "runtime",
                    "description": name,
                },
            )
            capability_runtime.unregister(descriptor.id)
            capability_runtime.register(
                descriptor,
                {"type": "runtime", "runtime": "ocr", "method": method},
            )

    def _recognize(
        self,
        source_type: str,
        source: str | Path,
        *,
        language: str | None,
        provider: str | None,
        options: dict[str, Any] | None,
    ) -> OCRResult:
        selected = self.registry.provider(provider)
        selected_name = provider_name(selected)
        self._publish(
            OCR_EVENTS["provider_selected"],
            {"provider": selected_name, "reason": "recognize", "source_type": source_type},
        )
        self._publish(
            OCR_EVENTS["started"],
            {"provider": selected_name, "source": str(source), "source_type": source_type},
        )
        started_at = monotonic()
        try:
            if source_type == "image":
                result = selected.recognize_image(source, language=language, options=options)
            elif source_type == "document":
                result = selected.recognize_document(source, language=language, options=options)
            elif source_type == "pdf":
                result = selected.recognize_pdf(source, language=language, options=options)
            else:
                result = selected.recognize_directory(source, language=language, options=options)
            result.processing_time = result.processing_time or (monotonic() - started_at)
        except Exception as exc:
            result = OCRResult(
                provider=selected_name,
                language=language or "unknown",
                processing_time=monotonic() - started_at,
                source=str(source),
                errors=[str(exc)],
                metadata={"source_type": source_type},
            )

        event_type = OCR_EVENTS["failed"] if result.errors else OCR_EVENTS["completed"]
        self._publish(event_type, {"provider": selected_name, "result": result})
        return result

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        events = getattr(self.core, "events", None)
        publish = getattr(events, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, source="ocr_runtime", payload=to_plain(payload))
        except Exception:
            return
