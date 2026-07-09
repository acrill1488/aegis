"""Vision Runtime v1."""

from __future__ import annotations

from typing import Any

from aegis.capabilities import CapabilityDescriptor
from aegis.serialization import to_plain

from .models import VisionSnapshot
from .ocr.providers.unlimited import UnlimitedOCRProvider
from .providers.screenshot import ScreenshotProvider
from .providers.stub_ocr import StubOCRProvider


class VisionRuntime:
    """Provider-neutral facade for screenshots and OCR observations."""

    def __init__(self, core: Any):
        self.core = core
        self.capture_providers = {"desktop": ScreenshotProvider(core)}
        stub_provider = StubOCRProvider()
        unlimited_provider = UnlimitedOCRProvider()
        self.ocr_providers = {
            "unlimited": unlimited_provider,
            "stub": stub_provider,
        }
        self.default_ocr_provider = (
            "unlimited" if unlimited_provider.available() else "stub"
        )

    def capture(self, source: str | dict = "desktop") -> dict:
        resolved_source = self._source(source)
        provider = self.capture_providers.get(resolved_source)
        if provider is None:
            raise ValueError(f"Vision capture provider not found: {resolved_source}")
        output = provider.capture()
        output = {
            "source": resolved_source,
            "image_path": output.get("path") or output.get("image_path") or "",
            "width": int(output.get("width") or 0),
            "height": int(output.get("height") or 0),
            "metadata": {
                key: value
                for key, value in output.items()
                if key not in {"path", "image_path", "width", "height"}
            },
        }
        self._publish("vision.capture.created", output)
        return output

    def analyze(
        self,
        image_path: str | dict | None = None,
        provider: str = "stub",
    ) -> VisionSnapshot:
        payload = image_path if isinstance(image_path, dict) else {}
        requested_provider = str(payload.get("provider") or provider)
        resolved_provider = (
            self.default_ocr_provider if requested_provider == "stub" else requested_provider
        )
        resolved_image_path = payload.get("image_path") or payload.get("path")
        if resolved_image_path is None and not isinstance(image_path, dict):
            resolved_image_path = image_path
        if not resolved_image_path:
            raise ValueError("image_path is required for vision analysis")

        ocr_provider = self.ocr_providers.get(resolved_provider)
        if ocr_provider is None:
            raise ValueError(f"OCR provider not found: {resolved_provider}")
        fallback_metadata = {}
        try:
            if not ocr_provider.available():
                raise RuntimeError(f"OCR provider unavailable: {resolved_provider}")
            elements = ocr_provider.recognize(str(resolved_image_path))
        except Exception as exc:
            if resolved_provider == "stub":
                raise
            fallback_metadata = {
                "fallback_from": resolved_provider,
                "fallback_reason": str(exc),
            }
            resolved_provider = "stub"
            ocr_provider = self.ocr_providers[resolved_provider]
            elements = ocr_provider.recognize(str(resolved_image_path))
        provider_metadata = dict(getattr(ocr_provider, "last_metadata", {}) or {})
        snapshot = VisionSnapshot(
            source="image",
            image_path=str(resolved_image_path),
            elements=elements,
            metadata={
                "provider": resolved_provider,
                **fallback_metadata,
                **provider_metadata,
            },
        )
        self._publish("vision.analysis.completed", {"snapshot": snapshot})
        return snapshot

    def snapshot(self, source: str | dict = "desktop") -> VisionSnapshot:
        capture = self.capture(source)
        snapshot = self.analyze(capture["image_path"])
        snapshot.source = capture["source"]
        snapshot.width = capture["width"]
        snapshot.height = capture["height"]
        snapshot.metadata = {
            **snapshot.metadata,
            "capture": capture.get("metadata", {}),
        }
        self._publish("vision.snapshot.created", {"snapshot": snapshot})
        return snapshot

    def find(
        self,
        query: str | dict,
        image_path: str | None = None,
    ) -> dict:
        if isinstance(query, dict):
            payload = query
            resolved_query = str(payload.get("query") or "")
            resolved_image_path = payload.get("image_path") or payload.get("image")
        else:
            resolved_query = query
            resolved_image_path = image_path
        if not resolved_query:
            raise ValueError("query is required")
        snapshot = (
            self.analyze(str(resolved_image_path))
            if resolved_image_path
            else self.snapshot("desktop")
        )
        needle = resolved_query.casefold()
        matches = [
            element
            for element in snapshot.elements
            if needle in (element.text or "").casefold()
        ]
        return {
            "query": resolved_query,
            "snapshot": snapshot,
            "matches": matches,
            "count": len(matches),
        }

    def register_capabilities(self) -> None:
        capability_runtime = getattr(self.core, "capability_runtime", None)
        if capability_runtime is None:
            return
        specs = (
            ("vision.capture", "Capture Vision Image", "capture", ["vision.capture"]),
            ("vision.analyze", "Analyze Vision Image", "analyze", ["vision.analyze"]),
            ("vision.snapshot", "Create Vision Snapshot", "snapshot", ["vision.capture", "vision.analyze"]),
            ("vision.find", "Find Text In Vision Snapshot", "find", ["vision.analyze"]),
        )
        for capability_id, name, method, permissions in specs:
            descriptor = CapabilityDescriptor(
                id=capability_id,
                name=name,
                version="1",
                owner_agent="vision",
                machine_scope="local",
                permissions=permissions,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                tags=["vision", "runtime"],
                metadata={
                    "provider_type": "runtime",
                    "description": name,
                },
            )
            capability_runtime.unregister(descriptor.id)
            capability_runtime.register(
                descriptor,
                {"type": "runtime", "runtime": "vision", "method": method},
            )

    def _source(self, source: str | dict) -> str:
        if isinstance(source, dict):
            return str(source.get("source") or "desktop")
        return str(source or "desktop")

    def _publish(self, event_type: str, payload: dict) -> None:
        events = getattr(self.core, "events", None)
        publish = getattr(events, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, source="vision_runtime", payload=to_plain(payload))
        except Exception:
            return
