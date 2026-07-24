from __future__ import annotations

import json
import sys
import types

from PIL import Image
from typer.testing import CliRunner

import aegis.ocr.cli as ocr_cli
from aegis.installer.catalog import ManifestRegistry
from aegis.ocr import OCRRegistry, OCRRuntime
from aegis.ocr.provider import StubOCRProvider
from aegis.providers.paddleocr import PaddleOCRConfig, PaddleOCRProvider


def _config_file(tmp_path, paddle_section=None):
    path = tmp_path / "services.yaml"
    paddle = paddle_section or {}
    path.write_text(
        "schema_version: 1\nserver: {host: 127.0.0.1, scheme: http}\n"
        "services:\n  ollama: {port: 11434, base_url: null}\n"
        "  unlimited_ocr: {port: 8190, base_url: null}\n"
        "  comfyui: {port: 8188, base_url: null}\npaths: {}\n"
        f"ocr:\n  providers:\n    paddleocr: {json.dumps(paddle)}\n",
        encoding="utf-8",
    )
    return path


def _install_fake_sdk(monkeypatch, *, fail_gpu=False, native=None):
    engines = []

    class Engine:
        def __init__(self, **kwargs):
            if fail_gpu and kwargs.get("use_gpu"):
                raise RuntimeError("CUDA runtime mismatch")
            self.kwargs = kwargs
            engines.append(self)

        def ocr(self, source, cls=True):
            return native if native is not None else [[
                [[[1, 2], [30, 2], [30, 12], [1, 12]], ("kept", 0.91)],
                [[[1, 20], [30, 20], [30, 30], [1, 30]], ("filtered", 0.2)],
            ]]

    paddleocr = types.SimpleNamespace(PaddleOCR=Engine)
    paddle = types.SimpleNamespace(
        is_compiled_with_cuda=lambda: True,
        device=types.SimpleNamespace(cuda=types.SimpleNamespace(device_count=lambda: 1)),
    )
    monkeypatch.setitem(sys.modules, "paddleocr", paddleocr)
    monkeypatch.setitem(sys.modules, "paddle", paddle)
    original = __import__("importlib").util.find_spec
    monkeypatch.setattr(
        "aegis.providers.paddleocr.provider.importlib.util.find_spec",
        lambda name: object() if name == "paddleocr" else original(name),
    )
    return engines


def test_paddleocr_config_defaults_and_overrides(tmp_path):
    defaults = PaddleOCRConfig.load(_config_file(tmp_path))
    custom = PaddleOCRConfig.load(_config_file(tmp_path, {"device": "cpu", "confidence_threshold": 0.75}))

    assert defaults == PaddleOCRConfig()
    assert custom.device == "cpu"
    assert custom.confidence_threshold == 0.75
    assert custom.max_image_size == 4096


def test_registry_registers_paddleocr_without_changing_explicit_default(tmp_path):
    registry = OCRRegistry(providers=[PaddleOCRProvider(PaddleOCRConfig(enabled=False))], default_provider="paddleocr")

    assert registry.has("paddleocr")
    assert registry.default() == "paddleocr"


def test_registry_preserves_unlimited_id_and_accepts_documented_alias():
    class Unlimited(StubOCRProvider):
        name = "unlimited"

    registry = OCRRegistry(providers=[Unlimited()], default_provider="unlimited")

    assert registry.provider("unlimited-ocr") is registry.provider("unlimited")
    assert registry.default() == "unlimited"


def test_missing_dependency_is_controlled(monkeypatch, tmp_path):
    monkeypatch.setattr("aegis.providers.paddleocr.provider.importlib.util.find_spec", lambda name: None)
    provider = PaddleOCRProvider(PaddleOCRConfig())

    health = provider.health()
    result = provider.recognize_image(tmp_path / "missing.png")

    assert health["status"] == "package missing"
    assert "aegis install paddleocr" in health["message"]
    assert result.errors == ["image file not found"]
    assert result.metadata["device"] is None


def test_valid_input_reports_missing_package_separately_from_input_errors(monkeypatch, tmp_path):
    monkeypatch.setattr("aegis.providers.paddleocr.provider.importlib.util.find_spec", lambda name: None)
    image = tmp_path / "valid.png"
    Image.new("RGB", (10, 10), "white").save(image)

    result = PaddleOCRProvider(PaddleOCRConfig()).recognize_image(image)

    assert result.errors == [
        "PaddleOCR package is not installed. Install the component with: aegis install paddleocr"
    ]
    assert result.metadata["device"] is None


def test_cpu_normalization_confidence_filter_and_engine_reuse(monkeypatch, tmp_path):
    engines = _install_fake_sdk(monkeypatch)
    image = tmp_path / "sample.png"
    Image.new("RGB", (80, 40), "white").save(image)
    provider = PaddleOCRProvider(PaddleOCRConfig(device="cpu", confidence_threshold=0.5))

    first = provider.recognize_image(image)
    second = provider.recognize_image(image)

    assert len(engines) == 1
    assert first.text == "kept"
    assert first.confidence == 0.91
    assert first.blocks[0].metadata["bounding_box"] == [[1.0, 2.0], [30.0, 2.0], [30.0, 12.0], [1.0, 12.0]]
    assert second.text == "kept"
    assert first.metadata["device"] == "cpu"


def test_empty_result_and_gpu_initialization_fallback(monkeypatch, tmp_path):
    engines = _install_fake_sdk(monkeypatch, fail_gpu=True, native=[])
    image = tmp_path / "empty.png"
    Image.new("RGB", (20, 20), "white").save(image)
    provider = PaddleOCRProvider(PaddleOCRConfig(device="auto"))

    result = provider.recognize_image(image)

    assert len(engines) == 1
    assert result.text == ""
    assert result.blocks == []
    assert result.metadata["device"] == "cpu"
    assert result.metadata["fallback"]["from"] == "gpu"
    assert provider.health()["status"] == "healthy"


def test_max_image_size_and_human_readable_error(tmp_path):
    image = tmp_path / "large.png"
    Image.new("RGB", (21, 10), "white").save(image)
    result = PaddleOCRProvider(PaddleOCRConfig(device="cpu", max_image_size=20)).recognize_image(image)

    assert result.errors == ["image exceeds max_image_size (20px)"]


def test_cli_json_has_valid_unstyled_payload(monkeypatch, tmp_path):
    image = tmp_path / "sample.png"
    Image.new("RGB", (10, 10), "white").save(image)

    class EmptyProvider(PaddleOCRProvider):
        def recognize_image(self, source, *, language=None, options=None):
            from aegis.ocr.models import OCRBlock, OCRResult
            return OCRResult(
                provider="paddleocr",
                language="en",
                pages=[{"page": 1}],
                text="recognized",
                blocks=[OCRBlock(text="recognized")],
                source=str(source),
                metadata={"device": "cpu"},
            )

        def available(self):
            return True

    runtime = OCRRuntime(registry=OCRRegistry(providers=[EmptyProvider(PaddleOCRConfig(device="cpu"))], default_provider="paddleocr"))
    monkeypatch.setattr(ocr_cli, "_runtime", lambda: runtime)

    output = CliRunner().invoke(ocr_cli.app, ["recognize", str(image), "--provider", "paddleocr", "--json"])

    assert output.exit_code == 0
    assert json.loads(output.stdout)["provider"] == "paddleocr"


def test_providers_json_is_valid_plain_json(monkeypatch):
    runtime = OCRRuntime(
        registry=OCRRegistry(
            providers=[PaddleOCRProvider(PaddleOCRConfig(enabled=False))],
            default_provider="paddleocr",
        )
    )
    monkeypatch.setattr(ocr_cli, "_runtime", lambda: runtime)

    output = CliRunner().invoke(ocr_cli.app, ["providers", "--json"])
    payload = json.loads(output.stdout)

    assert output.exit_code == 0
    assert "[bold]" not in output.stdout
    assert payload == {
        "providers": [
            {
                "id": "paddleocr",
                "available": False,
                "default": True,
                "device": "unavailable",
                "status": "disabled",
                "reason": "PaddleOCR provider is disabled",
            }
        ]
    }


def test_provider_specific_doctor_separates_platform_and_paddle_status(monkeypatch):
    class ProductionUnlimited(StubOCRProvider):
        name = "unlimited"

        def health(self):
            return {"status": "healthy", "service_alive": True}

        def doctor(self, verbose=False):
            return {
                "states": {
                    "service_alive": True,
                    "provider_available": True,
                    "model_loaded": True,
                    "model_ready": True,
                    "recognition_ready": True,
                }
            }

    monkeypatch.setattr("aegis.providers.paddleocr.provider.importlib.util.find_spec", lambda name: None)
    runtime = OCRRuntime(
        registry=OCRRegistry(
            providers=[ProductionUnlimited(), PaddleOCRProvider(PaddleOCRConfig())],
            default_provider="unlimited",
        )
    )
    monkeypatch.setattr(ocr_cli, "_runtime", lambda: runtime)

    output = CliRunner().invoke(ocr_cli.app, ["doctor", "paddleocr"])
    json_output = CliRunner().invoke(ocr_cli.app, ["doctor", "paddleocr", "--json"])
    payload = json.loads(json_output.stdout)

    assert output.exit_code == 0
    assert "Platform Status" in output.stdout
    assert "Platform Overall: PRODUCTION READY" in output.stdout
    assert "Selected Provider Status" in output.stdout
    assert "Selected Provider: paddleocr" in output.stdout
    assert "Selected Provider Overall: NOT READY" in output.stdout
    assert "Available: false" in output.stdout
    assert "Device: unavailable" in output.stdout
    assert "Reason: package missing" in output.stdout
    assert "provider_available=True" not in output.stdout
    assert "model_loaded=True" not in output.stdout
    assert "model_ready=True" not in output.stdout
    assert "recognition_ready=True" not in output.stdout
    assert payload["overall"] == "PRODUCTION READY"
    assert payload["selected_provider"]["overall"] == "NOT READY"
    assert payload["selected_provider"]["states"]["package_installed"] is False
    assert "model_ready" not in payload["selected_provider"]["states"]


def test_package_manager_manifest_is_valid():
    manifest = ManifestRegistry(__import__("pathlib").Path("aegis/installer/manifests")).get("paddleocr")

    assert manifest.type == "provider"
    assert manifest.providers == ["paddleocr"]
    assert manifest.healthcheck.type == "provider"
    assert manifest.python_requires == ">=3.12,<3.14"
    assert manifest.python_recommended == "3.12"
    assert manifest.install[0].command[:3] == ["${python}", "-m", "pip"]
