from __future__ import annotations

from typer.testing import CliRunner

import aegis.ocr.cli as ocr_cli
from aegis.ocr import OCRRegistry, OCRResult, OCRRuntime
from aegis.ocr.events import OCR_ARTIFACT_SAVED, OCR_FAILED, OCR_PROVIDER_SELECTED, OCR_STARTED
from aegis.ocr.provider import StubOCRProvider
from aegis.ocr.registry import OCRProviderRegistry


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
            "id": "artifact_1",
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


def test_ocr_registry_defaults_to_stub_provider():
    registry = OCRRegistry()

    provider = registry.provider()

    assert isinstance(provider, StubOCRProvider)
    assert registry.default() == "stub"
    assert [str(item.name) for item in registry.providers()] == ["stub"]
    assert [str(item.name) for item in registry.available()] == ["stub"]


def test_ocr_registry_accepts_future_provider_without_runtime_change():
    class FutureOCRProvider(StubOCRProvider):
        name = "future"

    registry = OCRProviderRegistry()
    registry.register(FutureOCRProvider())
    registry.set_default_provider("future")
    runtime = OCRRuntime(FakeCore(), registry=registry)

    assert runtime.default_provider() == "future"
    assert runtime.capabilities()["mode"] == "stub"
    assert {provider["name"] for provider in runtime.providers()} == {"stub", "future"}


def test_ocr_provider_contract_exposes_directory_and_callable_name(tmp_path):
    provider = StubOCRProvider()

    result = provider.recognize_directory(tmp_path, language="en")

    assert provider.name() == "stub"
    assert result.provider == "stub"
    assert result.metadata["source_type"] == "directory"
    assert result.figures == []


def test_ocr_runtime_doctor_reports_foundation_stub():
    runtime = OCRRuntime(FakeCore())

    report = runtime.doctor()

    assert report["default_provider"] == "stub"
    assert report["models_checked"] is False
    assert report["available"] == ["stub"]
    assert "pdf" in report["supported_formats"]["stub"]


def test_ocr_runtime_recognize_uses_stub_and_emits_failed_event(tmp_path):
    core = FakeCore()
    runtime = OCRRuntime(core)
    source = tmp_path / "sample.png"
    source.write_bytes(b"")

    result = runtime.recognize_image(source, language="en")

    assert result.provider == "stub"
    assert result.language == "en"
    assert result.errors
    assert [event["type"] for event in core.events.events] == [
        OCR_PROVIDER_SELECTED,
        OCR_STARTED,
        OCR_FAILED,
    ]


def test_ocr_runtime_registers_result_as_project_artifact(tmp_path):
    core = FakeCore()
    runtime = OCRRuntime(core)
    result = OCRResult(provider="stub", text="hello", source=str(tmp_path / "source.png"))

    artifact = runtime.register_artifact(result)

    assert artifact is not None
    assert artifact["type"] == "ocr.result"
    assert result.artifacts == [artifact]
    assert core.events.events[-1]["type"] == OCR_ARTIFACT_SAVED


def test_ocr_cli_foundation_commands(monkeypatch):
    runtime = OCRRuntime(FakeCore())
    monkeypatch.setattr(ocr_cli, "_runtime", lambda: runtime)
    runner = CliRunner()

    providers = runner.invoke(ocr_cli.app, ["providers"])
    doctor = runner.invoke(ocr_cli.app, ["doctor"])
    capabilities = runner.invoke(ocr_cli.app, ["capabilities"])

    assert providers.exit_code == 0
    assert "stub" in providers.output
    assert doctor.exit_code == 0
    assert "Default Provider" in doctor.output
    assert "FOUNDATION READY" in doctor.output
    assert capabilities.exit_code == 0
    assert "requires_model" in capabilities.output
