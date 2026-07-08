from datetime import datetime

from typer.testing import CliRunner

from aegis.cli.live import app
from aegis.live.models import ContextEntry


runner = CliRunner()


class FakeContextStore:
    last_set: dict | None = None

    def set(self, **kwargs):
        self.__class__.last_set = kwargs
        return ContextEntry(
            key=kwargs["key"],
            value=kwargs["value"],
            source=kwargs["source"],
            updated_at=datetime(2026, 1, 1),
            ttl_seconds=kwargs["ttl_seconds"],
            metadata=kwargs["metadata"],
        )


class FakeAegisCore:
    def __init__(self):
        self.live_context = FakeContextStore()


def test_live_set_reads_value_and_metadata_files(monkeypatch, tmp_path):
    value_file = tmp_path / "value.json"
    metadata_file = tmp_path / "metadata.json"
    value_file.write_text('{"status": "active"}', encoding="utf-8")
    metadata_file.write_text('{"source_type": "test"}', encoding="utf-8")
    monkeypatch.setattr("aegis.cli.live.AegisCore", FakeAegisCore)

    result = runner.invoke(
        app,
        [
            "set",
            "workspace.state",
            "--value-json",
            '{"ignored": true}',
            "--value-file",
            str(value_file),
            "--metadata-json",
            '{"ignored": true}',
            "--metadata-file",
            str(metadata_file),
            "--source",
            "test",
        ],
    )

    assert result.exit_code == 0
    assert FakeContextStore.last_set["value"] == {"status": "active"}
    assert FakeContextStore.last_set["metadata"] == {"source_type": "test"}


def test_live_set_reads_bom_encoded_json_files(monkeypatch, tmp_path):
    value_file = tmp_path / "value.json"
    metadata_file = tmp_path / "metadata.json"
    value_file.write_text('{"status": "active"}', encoding="utf-8-sig")
    metadata_file.write_text('{"source_type": "powershell"}', encoding="utf-8-sig")
    monkeypatch.setattr("aegis.cli.live.AegisCore", FakeAegisCore)

    result = runner.invoke(
        app,
        [
            "set",
            "workspace.state",
            "--value-file",
            str(value_file),
            "--metadata-file",
            str(metadata_file),
            "--source",
            "test",
        ],
    )

    assert result.exit_code == 0
    assert FakeContextStore.last_set["value"] == {"status": "active"}
    assert FakeContextStore.last_set["metadata"] == {"source_type": "powershell"}


def test_live_set_keeps_json_alias(monkeypatch):
    monkeypatch.setattr("aegis.cli.live.AegisCore", FakeAegisCore)

    result = runner.invoke(
        app,
        [
            "set",
            "workspace.state",
            "--json",
            '{"status": "active"}',
            "--source",
            "test",
        ],
    )

    assert result.exit_code == 0
    assert FakeContextStore.last_set["value"] == {"status": "active"}
    assert FakeContextStore.last_set["metadata"] == {}


def test_live_set_reports_invalid_value_file_json(monkeypatch, tmp_path):
    value_file = tmp_path / "value.json"
    value_file.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr("aegis.cli.live.AegisCore", FakeAegisCore)

    result = runner.invoke(
        app,
        [
            "set",
            "workspace.state",
            "--value-file",
            str(value_file),
            "--source",
            "test",
        ],
    )

    assert result.exit_code == 1
    assert "Invalid --value-file" in result.output
