from __future__ import annotations

import json

from aegis.vision.document.runtime import DocumentRuntime
from aegis.vision.runtime import VisionRuntime


class FakeEvents:
    def __init__(self):
        self.events = []

    def publish(self, event_type, source, payload=None, **context):
        self.events.append(
            {
                "type": event_type,
                "source": source,
                "payload": payload or {},
                "context": context,
            }
        )


class FakeDesktopRuntime:
    def __init__(self, path):
        self.path = path

    def screenshot(self, payload=None):
        return {
            "path": str(self.path),
            "width": 80,
            "height": 40,
            "created_at": "2026-07-10T00:00:00",
        }


class FakeKnowledgeRuntime:
    def __init__(self):
        self.added = []

    def add(self, path):
        self.added.append(path)
        return {"id": "doc_1", "path": str(path)}


class FakeCore:
    def __init__(self, screenshot_path=None):
        self.events = FakeEvents()
        self.desktop_runtime = (
            FakeDesktopRuntime(screenshot_path) if screenshot_path is not None else None
        )
        self.knowledge = FakeKnowledgeRuntime()


def test_vision_snapshot_uses_desktop_capture_and_stub_ocr(tmp_path):
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"not-a-real-image")
    core = FakeCore(image_path)
    runtime = VisionRuntime(core)

    snapshot = runtime.snapshot()

    assert snapshot.source == "desktop"
    assert snapshot.image_path == str(image_path)
    assert snapshot.width == 80
    assert snapshot.height == 40
    assert snapshot.elements == []
    assert snapshot.metadata["provider"] == "stub"
    assert [event["type"] for event in core.events.events] == [
        "vision.capture.created",
        "vision.analysis.completed",
        "vision.snapshot.created",
    ]


def test_vision_find_matches_stub_elements(tmp_path):
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"")
    runtime = VisionRuntime(FakeCore(image_path))

    result = runtime.find("anything", image_path=str(image_path))

    assert result["count"] == 0
    assert result["matches"] == []


def test_vision_analyze_falls_back_when_default_ocr_fails(tmp_path):
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"")
    runtime = VisionRuntime(FakeCore(image_path))

    class BrokenOCRProvider:
        name = "unlimited"
        last_metadata = {}

        def available(self):
            return True

        def recognize(self, image_path):
            raise RuntimeError("model unavailable")

    runtime.ocr_providers["unlimited"] = BrokenOCRProvider()
    runtime.default_ocr_provider = "unlimited"

    snapshot = runtime.analyze(str(image_path))

    assert snapshot.elements == []
    assert snapshot.metadata["provider"] == "stub"
    assert snapshot.metadata["fallback_from"] == "unlimited"
    assert "model unavailable" in snapshot.metadata["fallback_reason"]


def test_document_extract_supports_text_and_json(tmp_path):
    text_path = tmp_path / "note.txt"
    text_path.write_text("hello", encoding="utf-8")
    json_path = tmp_path / "payload.json"
    json_path.write_text(json.dumps({"b": 2}), encoding="utf-8")
    runtime = DocumentRuntime(FakeCore())

    text = runtime.extract(text_path)
    pretty_json = runtime.extract(json_path)

    assert text.supported is True
    assert text.text == "hello"
    assert pretty_json.supported is True
    assert '"b": 2' in pretty_json.text


def test_document_extract_reports_unsupported(tmp_path):
    binary_path = tmp_path / "file.bin"
    binary_path.write_bytes(b"\x00")
    runtime = DocumentRuntime(FakeCore())

    extraction = runtime.extract(binary_path)

    assert extraction.supported is False
    assert extraction.text == ""
    assert "Unsupported document type" in extraction.metadata["warning"]


def test_document_add_to_knowledge_writes_extracted_text(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# Title\n\nBody", encoding="utf-8")
    core = FakeCore()
    runtime = DocumentRuntime(core)

    result = runtime.add_to_knowledge(source)

    assert result["added"] is True
    assert core.knowledge.added
    extracted_path = core.knowledge.added[0]
    assert extracted_path.exists()
    assert "Body" in extracted_path.read_text(encoding="utf-8")
    assert "document.added_to_knowledge" in {
        event["type"] for event in core.events.events
    }
