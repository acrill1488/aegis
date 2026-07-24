from __future__ import annotations

from typer.testing import CliRunner

import aegis.ocr.cli as ocr_cli
from aegis.ocr import OCRRegistry, OCRResult, OCRRuntime
from aegis.ocr.events import (
    OCR_ARTIFACT_SAVED,
    OCR_COMPLETED,
    OCR_FAILED,
    OCR_INFERENCE_FAILED,
    OCR_RESOURCE_EXHAUSTED,
    OCR_PROVIDER_SELECTED,
    OCR_SERVICE_UNAVAILABLE,
    OCR_STARTED,
)
from aegis.ocr.provider import ProviderName, StubOCRProvider
from aegis.ocr.providers.unlimited import (
    UnlimitedOCRProvider,
    create_unlimited_ocr_http_client,
)
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
    registry = OCRRegistry(providers=[StubOCRProvider()])

    provider = registry.provider()

    assert isinstance(provider, StubOCRProvider)
    assert registry.default() == "stub"
    assert [str(item.name) for item in registry.providers()] == ["stub"]
    assert [str(item.name) for item in registry.available()] == ["stub"]


def test_ocr_registry_accepts_future_provider_without_runtime_change():
    class FutureOCRProvider(StubOCRProvider):
        name = "future"

    registry = OCRProviderRegistry(providers=[StubOCRProvider()])
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
    runtime = OCRRuntime(FakeCore(), registry=OCRRegistry(providers=[StubOCRProvider()]))

    report = runtime.doctor()

    assert report["default_provider"] == "stub"
    assert report["models_checked"] is False
    assert report["available"] == ["stub"]
    assert "pdf" in report["supported_formats"]["stub"]


def test_ocr_runtime_recognize_uses_stub_and_emits_failed_event(tmp_path):
    core = FakeCore()
    runtime = OCRRuntime(core, registry=OCRRegistry(providers=[StubOCRProvider()]))
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
    runtime = OCRRuntime(FakeCore(), registry=OCRRegistry(providers=[StubOCRProvider()]))
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


def test_unlimited_config_loading(tmp_path):
    config_path = tmp_path / "unlimited_ocr.json"
    config_path.write_text(
        '{"base_url":"http://10.0.0.5:8190","timeout_seconds":12,'
        '"poll_interval_ms":250,"default_language":"auto","trust_env":false}',
        encoding="utf-8",
    )

    config = UnlimitedOCRProvider(config_path=config_path)._load_config()

    assert config.base_url == "http://10.0.0.5:8190"
    assert config.timeout_seconds == 12
    assert config.poll_interval_ms == 250


def test_unlimited_lan_http_client_disables_trust_env():
    client = create_unlimited_ocr_http_client("http://192.168.1.7:8190", timeout=1)

    try:
        assert client._trust_env is False
    finally:
        client.close()


def test_unlimited_health_parsing(tmp_path, monkeypatch):
    config_path = tmp_path / "unlimited_ocr.json"
    config_path.write_text('{"base_url":"http://127.0.0.1:8190","trust_env":false}', encoding="utf-8")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.trust_env = kwargs["trust_env"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            class Response:
                status_code = 200

                def json(self):
                    return {
                        "status": "ok",
                        "model_id": "baidu/Unlimited-OCR",
                        "model_loaded": True,
                        "gpu_detected": True,
                    }

            return Response()

    monkeypatch.setattr("aegis.ocr.providers.unlimited.httpx.Client", FakeClient)

    health = UnlimitedOCRProvider(config_path=config_path).health()

    assert health["service_reachable"] is True
    assert health["model_loaded"] is True
    assert health["model_id"] == "baidu/Unlimited-OCR"


def test_unlimited_ocr_response_maps_into_ocr_result(tmp_path, monkeypatch):
    config_path = tmp_path / "unlimited_ocr.json"
    config_path.write_text('{"base_url":"http://127.0.0.1:8190","trust_env":false}', encoding="utf-8")
    image = tmp_path / "sample.png"
    image.write_bytes(b"png")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, files=None, data=None):
            class Response:
                status_code = 200

                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "success": True,
                        "provider": "unlimited",
                        "language": "auto",
                        "pages": [{"page": 1}],
                        "text": "hello",
                        "blocks": [{"text": "hello", "page": 1}],
                        "tables": [],
                        "processing_time": 1.25,
                        "metadata": {"model_id": "baidu/Unlimited-OCR"},
                    }

            return Response()

    monkeypatch.setattr("aegis.ocr.providers.unlimited.httpx.Client", FakeClient)

    result = UnlimitedOCRProvider(config_path=config_path).recognize_image(image)

    assert result.provider == "unlimited"
    assert result.text == "hello"
    assert result.blocks == [{"text": "hello", "page": 1}]
    assert result.metadata["model_id"] == "baidu/Unlimited-OCR"


def test_unlimited_non_2xx_ocr_contract_preserves_oom_error(tmp_path, monkeypatch):
    config_path = tmp_path / "unlimited_ocr.json"
    config_path.write_text('{"base_url":"http://127.0.0.1:8190","trust_env":false}', encoding="utf-8")
    image = tmp_path / "sample.png"
    image.write_bytes(b"png")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, files=None, data=None):
            class Response:
                status_code = 500

                def json(self):
                    return {
                        "success": False,
                        "provider": "unlimited",
                        "language": "auto",
                        "pages": [],
                        "text": "",
                        "blocks": [],
                        "tables": [],
                        "warnings": ["model state reset"],
                        "metadata": {"model_id": "baidu/Unlimited-OCR"},
                        "errors": ["CUDA out of memory while loading baidu/Unlimited-OCR"],
                    }

                def raise_for_status(self):
                    raise AssertionError("detailed OCR error should be used before HTTPStatusError")

            return Response()

    monkeypatch.setattr("aegis.ocr.providers.unlimited.httpx.Client", FakeClient)

    result = UnlimitedOCRProvider(config_path=config_path).recognize_image(image)

    assert result.errors == ["CUDA out of memory while loading baidu/Unlimited-OCR"]
    assert result.warnings == ["model state reset"]
    assert result.metadata["status_code"] == 500
    assert result.metadata["error_type"] == "ocr.resource.exhausted"


def test_unlimited_non_json_500_returns_controlled_error(tmp_path, monkeypatch):
    config_path = tmp_path / "unlimited_ocr.json"
    config_path.write_text('{"base_url":"http://127.0.0.1:8190","trust_env":false}', encoding="utf-8")
    image = tmp_path / "sample.png"
    image.write_bytes(b"png")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, files=None, data=None):
            class Response:
                status_code = 500

                def json(self):
                    raise ValueError("not json")

                def raise_for_status(self):
                    raise RuntimeError("HTTP 500 plain text failure")

            return Response()

    monkeypatch.setattr("aegis.ocr.providers.unlimited.httpx.Client", FakeClient)

    result = UnlimitedOCRProvider(config_path=config_path).recognize_image(image)

    assert result.provider == "unlimited"
    assert result.errors == [
        "Unlimited-OCR service unavailable or failed: HTTP 500 plain text failure"
    ]


def test_unlimited_service_unavailable_returns_controlled_error(tmp_path):
    provider = UnlimitedOCRProvider(config_path=tmp_path / "missing.json")

    result = provider.recognize_image(tmp_path / "missing.png")

    assert result.provider == "unlimited"
    assert result.errors == ["image file not found"]


def test_ocr_runtime_persists_successful_artifacts(tmp_path):
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
                language=language or "auto",
                text="recognized text",
                pages=[{"page": 1}],
                blocks=[{"text": "recognized text"}],
                source=str(source),
                metadata={"service_url": "http://127.0.0.1:8190", "model_id": "baidu/Unlimited-OCR"},
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

    artifact_paths = [
        artifact["path"]
        for artifact in result.artifacts
        if isinstance(artifact, dict) and artifact.get("path")
    ]
    assert result.errors == []
    assert any(path.endswith("-sample-unlimited.txt") for path in artifact_paths)
    assert any(path.endswith("-sample-unlimited.json") for path in artifact_paths)
    assert any(event["type"] == OCR_COMPLETED for event in core.events.events)


def test_ocr_runtime_does_not_hidden_fallback_to_stub(tmp_path):
    class UnavailableUnlimited:
        name = ProviderName("unlimited")

        def available(self):
            return False

        def health(self):
            return {"status": "unavailable"}

        def capabilities(self):
            return {"mode": "http-service"}

        def supported_formats(self):
            return ["png"]

        def recognize_image(self, source, *, language=None, options=None):
            return OCRResult(
                provider="unlimited",
                language=language or "auto",
                source=str(source),
                errors=["Unlimited-OCR service unavailable"],
            )

        recognize_document = recognize_image
        recognize_pdf = recognize_image
        recognize_directory = recognize_image

    core = FakeCore()
    runtime = OCRRuntime(
        core,
        registry=OCRRegistry(providers=[StubOCRProvider(), UnavailableUnlimited()], default_provider="stub"),
    )
    source = tmp_path / "sample.png"
    source.write_bytes(b"png")

    result = runtime.recognize_image(source)

    assert result.provider == "unlimited"
    assert result.errors == ["Unlimited-OCR service unavailable"]
    assert OCR_SERVICE_UNAVAILABLE in [event["type"] for event in core.events.events]


def test_unlimited_oom_error_is_not_published_as_service_unavailable(tmp_path):
    class OOMUnlimited:
        name = ProviderName("unlimited")

        def available(self):
            return True

        def health(self):
            return {"status": "ok"}

        def capabilities(self):
            return {"mode": "http-service"}

        def supported_formats(self):
            return ["png"]

        def recognize_image(self, source, *, language=None, options=None):
            return OCRResult(
                provider="unlimited",
                language=language or "auto",
                source=str(source),
                errors=["CUDA out of memory while loading baidu/Unlimited-OCR"],
                metadata={"error_type": "ocr.resource.exhausted"},
            )

        recognize_document = recognize_image
        recognize_pdf = recognize_image
        recognize_directory = recognize_image

    core = FakeCore()
    runtime = OCRRuntime(
        core,
        registry=OCRRegistry(providers=[StubOCRProvider(), OOMUnlimited()], default_provider="unlimited"),
    )
    source = tmp_path / "sample.png"
    source.write_bytes(b"png")

    result = runtime.recognize_image(source)
    event_types = [event["type"] for event in core.events.events]

    assert result.errors == ["CUDA out of memory while loading baidu/Unlimited-OCR"]
    assert OCR_RESOURCE_EXHAUSTED in event_types
    assert OCR_SERVICE_UNAVAILABLE not in event_types


def test_unlimited_inference_error_uses_specific_event(tmp_path):
    class BrokenUnlimited:
        name = ProviderName("unlimited")

        def available(self):
            return True

        def health(self):
            return {"status": "ok"}

        def capabilities(self):
            return {"mode": "http-service"}

        def supported_formats(self):
            return ["png"]

        def recognize_image(self, source, *, language=None, options=None):
            return OCRResult(
                provider="unlimited",
                language=language or "auto",
                source=str(source),
                errors=["generation failed"],
                metadata={"error_type": "ocr.inference.failed"},
            )

        recognize_document = recognize_image
        recognize_pdf = recognize_image
        recognize_directory = recognize_image

    core = FakeCore()
    runtime = OCRRuntime(
        core,
        registry=OCRRegistry(providers=[StubOCRProvider(), BrokenUnlimited()], default_provider="unlimited"),
    )
    source = tmp_path / "sample.png"
    source.write_bytes(b"png")

    runtime.recognize_image(source)

    assert OCR_INFERENCE_FAILED in [event["type"] for event in core.events.events]
