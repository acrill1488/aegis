from __future__ import annotations

from pathlib import Path

import pytest

from aegis.config.services import (
    ServicesConfigError,
    get_configured_path,
    get_greenboost_config,
    get_service_base_url,
    load_services_config,
    resolve_service_base_url,
)


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _valid(host: str = "comfy.test", ocr_url: str = "null") -> str:
    return f"""schema_version: 1
server: {{scheme: http, host: {host}}}
services:
  ollama: {{port: 11434, base_url: null}}
  unlimited_ocr: {{port: 8190, base_url: {ocr_url}}}
  comfyui: {{port: 8188, base_url: null}}
paths:
  comfyui_models: '\\\\comfy.test\\models'
"""


def test_loads_yaml_and_builds_urls(tmp_path, monkeypatch):
    path = _write(tmp_path / "services.yaml", _valid())
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(path))
    config = load_services_config()
    assert config.configuration_source == "yaml"
    assert get_service_base_url("ollama") == "http://comfy.test:11434"
    assert get_configured_path("comfyui_models") == r"\\comfy.test\models"


def test_missing_yaml_uses_explicit_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(tmp_path / "missing.yaml"))
    resolved = resolve_service_base_url("comfyui")
    assert resolved.value == "http://127.0.0.1:8188"
    assert resolved.source == "fallback"


@pytest.mark.parametrize(
    "body, message",
    [
        ("server: [", "YAML could not be loaded"),
        (_valid().replace("8190", "70000"), "integer between 1 and 65535"),
    ],
)
def test_invalid_yaml_is_not_silently_ignored(tmp_path, monkeypatch, body, message):
    path = _write(tmp_path / "bad.yaml", body)
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(path))
    with pytest.raises(ServicesConfigError, match=message):
        load_services_config()


def test_base_url_and_environment_precedence(tmp_path, monkeypatch):
    path = _write(tmp_path / "services.yaml", _valid(ocr_url="https://ocr.test/api"))
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(path))
    assert get_service_base_url("unlimited_ocr") == "https://ocr.test/api"
    monkeypatch.setenv("AEGIS_UNLIMITED_OCR_BASE_URL", "http://10.0.0.5:9000/")
    assert get_service_base_url("unlimited_ocr") == "http://10.0.0.5:9000"
    assert (
        get_service_base_url("unlimited_ocr", "http://127.0.0.1:1")
        == "http://127.0.0.1:1"
    )


def test_unknown_service_is_rejected(tmp_path, monkeypatch):
    path = _write(tmp_path / "services.yaml", _valid())
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(path))
    with pytest.raises(KeyError, match="Unknown AEGIS service"):
        get_service_base_url("missing")


def test_common_server_environment_overrides_yaml(tmp_path, monkeypatch):
    path = _write(tmp_path / "services.yaml", _valid())
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(path))
    monkeypatch.setenv("AEGIS_SERVER_HOST", "10.0.0.5")
    monkeypatch.setenv("AEGIS_SERVER_SCHEME", "https")
    assert get_service_base_url("comfyui") == "https://10.0.0.5:8188"


def test_greenboost_uses_central_configuration(tmp_path, monkeypatch):
    body = (
        _valid()
        + """
greenboost:
  enabled: true
  base_url: https://greenboost.test/api
  connect_timeout: 2
  read_timeout: 9
  write_timeout: 4
  retries: 2
"""
    )
    path = _write(tmp_path / "services.yaml", body)
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(path))
    config = get_greenboost_config()
    assert config.enabled is True
    assert str(config.base_url) == "https://greenboost.test/api"
    assert config.retries == 2
