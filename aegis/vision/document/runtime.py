"""Document Intelligence Runtime v1."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from aegis.capabilities import CapabilityDescriptor
from aegis.serialization import to_plain

from .models import DocumentExtraction
from .providers.stub import StubDocumentProvider


class DocumentRuntime:
    """Provider-neutral facade for document extraction and indexing."""

    def __init__(self, core: Any):
        self.core = core
        self.providers = {"stub": StubDocumentProvider()}

    def extract(
        self,
        path: str | Path | dict,
        provider: str = "stub",
    ) -> DocumentExtraction:
        payload = path if isinstance(path, dict) else {}
        resolved_provider = str(payload.get("provider") or provider)
        resolved_path = payload.get("path") if isinstance(path, dict) else path
        if not resolved_path:
            raise ValueError("path is required")
        document_provider = self.providers.get(resolved_provider)
        if document_provider is None:
            raise ValueError(f"Document provider not found: {resolved_provider}")
        extraction = document_provider.extract(resolved_path)
        self._publish("document.extracted", {"extraction": extraction})
        return extraction

    def add_to_knowledge(self, path: str | Path | dict) -> dict:
        extraction = self.extract(path)
        if not extraction.supported:
            return {
                "added": False,
                "extraction": extraction,
                "error": extraction.metadata.get("warning", "Unsupported document type"),
            }
        target = self._write_extracted_text(extraction)
        knowledge = getattr(self.core, "knowledge", None)
        if knowledge is None:
            raise RuntimeError("KnowledgeRuntime is required to add extracted documents.")
        document = knowledge.add(target)
        output = {
            "added": True,
            "source_path": extraction.path,
            "extracted_path": str(target),
            "document": document,
        }
        self._publish("document.added_to_knowledge", output)
        return output

    def supported_types(self, payload: dict | None = None) -> dict:
        provider = str((payload or {}).get("provider") or "stub")
        document_provider = self.providers.get(provider)
        if document_provider is None:
            raise ValueError(f"Document provider not found: {provider}")
        return {"provider": provider, "types": document_provider.supported_types()}

    def register_capabilities(self) -> None:
        capability_runtime = getattr(self.core, "capability_runtime", None)
        if capability_runtime is None:
            return
        specs = (
            ("document.extract", "Extract Document Text", "extract", ["document.read"]),
            (
                "document.add_to_knowledge",
                "Add Extracted Document To Knowledge",
                "add_to_knowledge",
                ["document.read", "knowledge.write"],
            ),
        )
        for capability_id, name, method, permissions in specs:
            descriptor = CapabilityDescriptor(
                id=capability_id,
                name=name,
                version="1",
                owner_agent="document",
                machine_scope="local",
                permissions=permissions,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                tags=["document", "runtime"],
                metadata={
                    "provider_type": "runtime",
                    "description": name,
                },
            )
            capability_runtime.unregister(descriptor.id)
            capability_runtime.register(
                descriptor,
                {"type": "runtime", "runtime": "document", "method": method},
            )

    def _write_extracted_text(self, extraction: DocumentExtraction) -> Path:
        source = Path(extraction.path)
        suffix = ".md" if source.suffix.lower() == ".md" else ".txt"
        directory = Path(tempfile.gettempdir()) / "aegis-document-intelligence"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{source.stem}-{extraction.id}{suffix}"
        header = f"# Extracted document: {source.name}\n\n" if suffix == ".md" else ""
        target.write_text(header + extraction.text, encoding="utf-8")
        return target

    def _publish(self, event_type: str, payload: dict) -> None:
        events = getattr(self.core, "events", None)
        publish = getattr(events, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, source="document_runtime", payload=to_plain(payload))
        except Exception:
            return
