from __future__ import annotations

from typer.testing import CliRunner

import aegis.cli.config as config_cli


CONFIG = """schema_version: 1
server: {scheme: http, host: 127.0.0.1}
services:
  ollama: {port: 11434, base_url: null}
  unlimited_ocr: {port: 8190, base_url: null}
  comfyui: {port: 8188, base_url: null}
paths:
  comfyui_models: 'C:\\models'
"""


def test_config_show_reports_effective_values_and_sources(tmp_path, monkeypatch):
    path = tmp_path / "services.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(path))

    result = CliRunner().invoke(config_cli.app, ["show"])

    assert result.exit_code == 0
    assert "http://127.0.0.1:11434" in result.output
    assert "Unlimited OCR" in result.output
    assert "yaml" in result.output


def test_config_doctor_checks_all_services_when_one_fails(tmp_path, monkeypatch):
    path = tmp_path / "services.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("AEGIS_SERVICES_CONFIG", str(path))
    requested: list[str] = []

    monkeypatch.setattr(config_cli.socket, "getaddrinfo", lambda *args: [(None,)])

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(config_cli.socket, "create_connection", lambda *args, **kwargs: Connection())

    def fake_get(url, **kwargs):
        requested.append(url)

        class Response:
            status_code = 503 if "11434" in url else 200

        return Response()

    monkeypatch.setattr(config_cli.httpx, "get", fake_get)
    result = CliRunner().invoke(config_cli.app, ["doctor"])

    assert result.exit_code == 1
    assert len(requested) == 3
    assert "HTTP 503" in result.output
    assert "HTTP 200" in result.output
