from __future__ import annotations

from typer.testing import CliRunner

import aegis.cli.document as document_cli
from aegis.document import (
    StructuredDocumentBuilder,
    StructuredDocumentSerializer,
    StructuredDocumentValidator,
)
from aegis.ocr import OCRRegistry, OCRResult, OCRRuntime
from aegis.ocr.events import DOCUMENT_CREATED, DOCUMENT_SAVED, DOCUMENT_VALIDATED
from aegis.ocr.provider import ProviderName, StubOCRProvider


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


class FakeProject:
    id = "project_1"


class FakeProjectRuntime:
    def __init__(self):
        self.artifacts = []

    def get_active(self):
        return FakeProject()

    def add_artifact(self, project_id, type, path, metadata=None):
        artifact = {
            "id": f"artifact_{len(self.artifacts) + 1}",
            "project_id": project_id,
            "type": type,
            "path": path,
            "metadata": metadata or {},
        }
        self.artifacts.append(artifact)
        return artifact


class FakeCore:
    def __init__(self):
        self.events = FakeEvents()
        self.project_runtime = FakeProjectRuntime()


def test_structured_document_builder_validator_and_serializers():
    result = OCRResult(
        provider="unlimited",
        language="en",
        source="sample.png",
        text="Invoice\nTotal 10",
        pages=[{"page": 1, "width": 100, "height": 200}],
        blocks=[
            {"id": "title", "text": "Invoice", "page": 1, "role": "title"},
            {"id": "total", "text": "Total 10", "page": 1},
        ],
        tables=[{"page": 1, "rows": [["Item", "Price"], ["A", "10"]]}],
    )

    document = StructuredDocumentBuilder().from_ocr_result(result)
    validation = StructuredDocumentValidator().validate(document)
    serializer = StructuredDocumentSerializer()

    assert validation.valid is True
    assert document.provider == "unlimited"
    assert document.statistics["page_count"] == 1
    assert document.statistics["block_count"] == 2
    assert document.pages[0].reading_order == ["title", "total"]
    assert '"plain_text": "Invoice\\nTotal 10"' in serializer.to_json(document)
    assert "# Document " in serializer.to_markdown(document)
    assert serializer.to_plain_text(document) == "Invoice\nTotal 10"


def test_document_cli_validate_inspect_and_export(tmp_path):
    document = StructuredDocumentBuilder().from_ocr_result(
        OCRResult(
            provider="unlimited",
            language="en",
            source="sample.png",
            text="recognized text",
            pages=[{"page": 1}],
            blocks=[{"id": "p1-b1", "text": "recognized text", "page": 1}],
        )
    )
    path = tmp_path / "document.json"
    StructuredDocumentSerializer().write_json(document, path)

    runner = CliRunner()
    validate = runner.invoke(document_cli.app, ["validate", str(path)])
    inspect = runner.invoke(document_cli.app, ["inspect", str(path)])
    export = runner.invoke(document_cli.app, ["export", str(path), "--format", "text"])

    assert validate.exit_code == 0
    assert '"valid": true' in validate.output
    assert inspect.exit_code == 0
    assert "Structured Document" in inspect.output
    assert export.exit_code == 0
    assert "recognized text" in export.output


def test_ocr_runtime_creates_structured_document_artifacts_and_events(tmp_path):
    class SuccessProvider:
        name = ProviderName("unlimited")

        def available(self):
            return True

        def health(self):
            return {"status": "ok"}

        def capabilities(self):
            return {"mode": "test", "recognition": True}

        def supported_formats(self):
            return ["png"]

        def recognize_image(self, source, *, language=None, options=None):
            return OCRResult(
                provider="unlimited",
                language=language or "en",
                source=str(source),
                text="recognized text",
                pages=[{"page": 1}],
                blocks=[{"id": "p1-b1", "text": "recognized text", "page": 1}],
            )

        recognize_document = recognize_image
        recognize_pdf = recognize_image
        recognize_directory = recognize_image

    core = FakeCore()
    runtime = OCRRuntime(
        core,
        registry=OCRRegistry(providers=[StubOCRProvider(), SuccessProvider()], default_provider="unlimited"),
    )
    source = tmp_path / "sample.png"
    source.write_bytes(b"png")

    result = runtime.recognize_image(source, options={"output_dir": tmp_path})

    event_types = [event["type"] for event in core.events.events]
    document_artifacts = [
        artifact for artifact in result.artifacts if artifact.get("type") == "document.structured"
    ]
    project_document_artifacts = [
        artifact
        for artifact in core.project_runtime.artifacts
        if artifact["type"] == "document.structured"
    ]

    assert result.errors == []
    assert (tmp_path / "document.json").exists()
    assert (tmp_path / "text.txt").read_text(encoding="utf-8") == "recognized text"
    assert DOCUMENT_CREATED in event_types
    assert DOCUMENT_VALIDATED in event_types
    assert DOCUMENT_SAVED in event_types
    assert document_artifacts
    assert project_document_artifacts
    assert project_document_artifacts[0]["metadata"]["provider"] == "unlimited"
    assert project_document_artifacts[0]["metadata"]["page_count"] == 1
    assert project_document_artifacts[0]["metadata"]["block_count"] == 1
    assert project_document_artifacts[0]["metadata"]["table_count"] == 0
    assert project_document_artifacts[0]["metadata"]["language"] == "en"
