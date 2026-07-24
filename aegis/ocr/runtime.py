"""OCR Runtime foundation."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from time import monotonic
from typing import Any

from PIL import Image

from aegis.capabilities import CapabilityDescriptor
from aegis.compute import GPUServiceHandoff
from aegis.greenboost import GreenBoostRuntime
from aegis.document import (
    DOCUMENT_ARTIFACT_TYPE,
    StructuredDocumentBuilder,
    StructuredDocumentSerializer,
    StructuredDocumentValidator,
    create_document_artifact,
    document_artifact_metadata,
)
from aegis.serialization import to_json, to_plain

from .doctor import OCRDoctor
from .events import OCR_EVENTS
from .models import OCRResult
from .validation import validate_recognition
from .registry import OCRRegistry, provider_name
from .providers.unlimited import DEFAULT_OUTPUT_DIR


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
        self.document_builder = StructuredDocumentBuilder()
        self.document_serializer = StructuredDocumentSerializer()
        self.document_validator = StructuredDocumentValidator()

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

    def doctor(
        self,
        verbose: bool = False,
        provider: str | None = None,
    ) -> dict[str, Any]:
        return OCRDoctor(self.registry).report(verbose=verbose, provider=provider)

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
        metadata: dict[str, Any] | None = None,
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
            metadata=metadata or {
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
        self._publish(
            OCR_EVENTS["artifact_saved"],
            {"artifact": plain_artifact, "result": self._result_summary(result)},
        )
        return plain_artifact

    def register_capabilities(self) -> None:
        capability_runtime = getattr(self.core, "capability_runtime", None)
        if capability_runtime is None:
            return
        specs = (
            ("ocr.providers", "List OCR Providers", "providers", ["ocr.providers"]),
            ("ocr.doctor", "Run OCR Doctor", "doctor", ["ocr.doctor"]),
            ("ocr.capabilities", "Show OCR Capabilities", "capabilities", ["ocr.capabilities"]),
            ("ocr.recognize_image", "Recognize Image Text", "recognize_image", ["ocr.recognize"]),
            ("ocr.recognize_pdf", "Recognize PDF Text", "recognize_pdf", ["ocr.recognize"]),
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
        selected = self._select_provider_for_recognition(provider)
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
        handoff_report = None
        try:
            use_greenboost = (
                selected_name == "unlimited"
                and source_type == "image"
                and selected.__class__.__module__ == "aegis.ocr.providers.unlimited"
                and (options or {}).get("greenboost") is not False
            )
            if use_greenboost:
                greenboost = GreenBoostRuntime()
                session = greenboost.begin_ocr(source)
                result = None
                try:
                    for index, attempt in enumerate(greenboost.attempts(session.selected_profile), 1):
                        if index > 1:
                            greenboost.reset_between_attempts(session, session.fallback_reason or "previous attempt failed")
                        attempt_options = dict(options or {})
                        attempt_options.pop("greenboost", None)
                        attempt_options["max_image_side"] = int(attempt["max_image_side"])
                        if str(attempt["name"]) == "emergency":
                            attempt_options["tile_ocr"] = True
                            attempt_options["focus_crop"] = True
                        result = selected.recognize_image(source, language=language, options=attempt_options)
                        self._apply_semantic_validation(result)
                        entry = {"number": index, "mode": attempt["name"], "max_image_side": attempt["max_image_side"], "success": not result.errors}
                        session.attempts.append(entry)
                        with Image.open(source) as image:
                            scale = min(1.0, int(attempt["max_image_side"]) / max(image.size))
                            session.effective_image_size = [max(1, int(image.width * scale)), max(1, int(image.height * scale))]
                        if not result.errors:
                            break
                        error_text = " ".join(result.errors).lower()
                        if not (
                            "out of memory" in error_text
                            or "cuda" in error_text and "memory" in error_text
                            or result.metadata.get("error_type") == "ocr.recognition.invalid"
                        ):
                            break
                        session.fallback_reason = "cuda_oom"
                finally:
                    greenboost.finish(session)
                if result is None:
                    raise RuntimeError("GreenBoost retry policy produced no OCR attempt")
                result.metadata.update(session.metadata())
            else:
                if selected_name == "unlimited":
                    handoff_report = self._prepare_gpu_service("ocr.recognize")
                if source_type == "image":
                    result = selected.recognize_image(source, language=language, options=options)
                elif source_type == "document":
                    result = selected.recognize_document(source, language=language, options=options)
                elif source_type == "pdf":
                    result = selected.recognize_pdf(source, language=language, options=options)
                else:
                    result = selected.recognize_directory(source, language=language, options=options)
            self._apply_semantic_validation(result)
            result.processing_time = result.processing_time or (monotonic() - started_at)
            if options and options.get("output_dir"):
                result.metadata["output_dir"] = str(options["output_dir"])
            if handoff_report is not None:
                result.metadata["gpu_service_handoff"] = to_plain(handoff_report)
        except Exception as exc:
            result = OCRResult(
                provider=selected_name,
                language=language or "unknown",
                processing_time=monotonic() - started_at,
                source=str(source),
                errors=[str(exc)],
                metadata={"source_type": source_type},
            )

        if result.errors and selected_name == "unlimited":
            self._publish_unlimited_failure(result, source=source, source_type=source_type)
        if not result.errors:
            self._persist_result_artifacts(result, source)

        event_type = OCR_EVENTS["failed"] if result.errors else OCR_EVENTS["completed"]
        self._publish(event_type, {"provider": selected_name, "result": self._result_summary(result)})
        return result

    def _apply_semantic_validation(self, result: OCRResult) -> None:
        validation = validate_recognition(result.text)
        result.metadata.update(validation.metadata())
        result.metadata["raw_output_available"] = bool(
            result.metadata.get("raw_output_available")
            or result.metadata.get("raw_text_before_normalization") is not None
        )
        if not validation.valid and not result.errors:
            result.metadata["error_type"] = "ocr.recognition.invalid"
            result.errors.append(f"OCR recognition is not semantically valid: {validation.reason}")

    def _prepare_gpu_service(self, task_type: str):
        handoff = None
        registry = getattr(self.core, "registry", None)
        get_service = getattr(registry, "get", None)
        if callable(get_service):
            handoff = get_service("gpu_service_handoff")
        if handoff is None:
            handoff = GPUServiceHandoff()
        prepare = getattr(handoff, "prepare_for_task", None)
        if not callable(prepare):
            return None
        return prepare(task_type)

    def _select_provider_for_recognition(self, provider: str | None):
        if provider:
            return self.registry.provider(provider)
        selected = self.registry.provider()
        if provider_name(selected) == "stub" and self.registry.has("unlimited"):
            return self.registry.provider("unlimited")
        return selected

    def _publish_unlimited_failure(
        self,
        result: OCRResult,
        *,
        source: str | Path,
        source_type: str,
    ) -> None:
        error_type = str(result.metadata.get("error_type") or self._classify_unlimited_failure(result))
        event_key = {
            "ocr.model.load_failed": "model_load_failed",
            "ocr.inference.failed": "inference_failed",
            "ocr.resource.exhausted": "resource_exhausted",
        }.get(error_type, "service_unavailable")
        self._publish(
            OCR_EVENTS[event_key],
            {
                "provider": result.provider,
                "source": str(source),
                "source_type": source_type,
                "errors": list(result.errors),
                "error_type": error_type,
            },
        )

    def _classify_unlimited_failure(self, result: OCRResult) -> str:
        text = " ".join(str(error) for error in result.errors).lower()
        if "out of memory" in text or "cuda oom" in text or ("cuda" in text and "memory" in text):
            return "ocr.resource.exhausted"
        if "load" in text and "failed" in text:
            return "ocr.model.load_failed"
        if "unavailable" in text or "connection" in text or "timed out" in text:
            return "ocr.service.unavailable"
        return "ocr.inference.failed"

    def _persist_result_artifacts(self, result: OCRResult, source: str | Path) -> None:
        output_dir = Path(str(result.metadata.get("output_dir") or DEFAULT_OUTPUT_DIR))
        output_dir.mkdir(parents=True, exist_ok=True)
        source_path = Path(source)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        stem = source_path.stem or "ocr"
        provider = result.provider or "ocr"
        text_path = output_dir / f"{stamp}-{stem}-{provider}.txt"
        json_path = output_dir / f"{stamp}-{stem}-{provider}.json"
        text_path.write_text(result.text or "", encoding="utf-8")
        json_payload = to_plain(result) | self._artifact_metadata(result, source_path)
        json_path.write_text(to_json(json_payload), encoding="utf-8")
        self._add_file_artifact(result, text_path, "text/plain")
        self._add_file_artifact(result, json_path, "application/json")
        self._persist_structured_document_artifacts(result, output_dir)

    def _persist_structured_document_artifacts(self, result: OCRResult, output_dir: Path) -> None:
        document = self.document_builder.from_ocr_result(result)
        self._publish(
            OCR_EVENTS["document_created"],
            {"document": self._document_summary(document)},
        )

        validation = self.document_validator.validate(document)
        document.metadata["validation"] = to_plain(validation)
        self._publish(
            OCR_EVENTS["document_validated"],
            {
                "document": self._document_summary(document),
                "validation": to_plain(validation),
            },
        )

        document_json_path = output_dir / "document.json"
        document_text_path = output_dir / "text.txt"
        document.artifacts.append(create_document_artifact(document, document_json_path))
        document.artifacts.append(
            create_document_artifact(
                document,
                document_text_path,
                content_type="text/plain",
            )
        )
        self.document_serializer.write_json(document, document_json_path)
        self.document_serializer.write_plain_text(document, document_text_path)

        self._add_document_file_artifact(result, document, document_json_path, "application/json")
        self._add_document_file_artifact(result, document, document_text_path, "text/plain")
        self._publish(
            OCR_EVENTS["document_saved"],
            {
                "document": self._document_summary(document),
                "artifacts": [
                    {"path": str(document_json_path), "content_type": "application/json"},
                    {"path": str(document_text_path), "content_type": "text/plain"},
                ],
            },
        )

    def _artifact_metadata(self, result: OCRResult, source: Path) -> dict[str, Any]:
        return {
            "artifact_metadata": {
                "provider": result.provider,
                "source_path": str(source),
                "language": result.language,
                "page_count": len(result.pages),
                "block_count": len(result.blocks),
                "processing_time": result.processing_time,
                "service_url": result.metadata.get("service_url"),
                "model_id": result.metadata.get("model_id") or result.metadata.get("model_version"),
            }
        }

    def _add_file_artifact(self, result: OCRResult, path: Path, content_type: str) -> None:
        artifact = {
            "type": "ocr.result",
            "path": str(path),
            "content_type": content_type,
            "provider": result.provider,
        }
        if artifact not in result.artifacts:
            result.artifacts.append(artifact)
        self.register_artifact(result, path=path, artifact_type="ocr.result")
        self._publish(
            OCR_EVENTS["artifact_saved"],
            {"artifact": artifact, "result": self._result_summary(result)},
        )

    def _add_document_file_artifact(
        self,
        result: OCRResult,
        document,
        path: Path,
        content_type: str,
    ) -> None:
        artifact = create_document_artifact(document, path, content_type=content_type)
        if artifact not in result.artifacts:
            result.artifacts.append(artifact)
        self.register_artifact(
            result,
            path=path,
            artifact_type=DOCUMENT_ARTIFACT_TYPE,
            metadata=artifact["metadata"],
        )
        self._publish(
            OCR_EVENTS["artifact_saved"],
            {"artifact": artifact, "result": self._result_summary(result)},
        )

    def _result_summary(self, result: OCRResult) -> dict[str, Any]:
        return {
            "provider": result.provider,
            "language": result.language,
            "source": result.source,
            "page_count": len(result.pages),
            "block_count": len(result.blocks),
            "table_count": len(result.tables),
            "text_length": len(result.text or ""),
            "processing_time": result.processing_time,
            "artifact_paths": [
                artifact.get("path")
                for artifact in result.artifacts
                if isinstance(artifact, dict) and artifact.get("path")
            ],
            "warnings": list(result.warnings),
            "errors": list(result.errors),
            "metadata": {
                "service_url": result.metadata.get("service_url"),
                "model_id": result.metadata.get("model_id") or result.metadata.get("model_version"),
            },
        }

    def _document_summary(self, document) -> dict[str, Any]:
        return {
            "id": document.id,
            "provider": document.provider,
            "source": document.source,
            "language": document.language,
            **document_artifact_metadata(document),
        }

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        events = getattr(self.core, "events", None)
        publish = getattr(events, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, source="ocr_runtime", payload=to_plain(payload))
        except Exception:
            return
