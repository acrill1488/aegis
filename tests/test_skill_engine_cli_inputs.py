import pytest
import typer

from aegis.cli.skill_engine import _load_inputs


def test_skill_cli_load_inputs_supports_query_option():
    inputs = _load_inputs("{}", None, query="RTX 3090")

    assert inputs == {"query": "RTX 3090"}


def test_skill_cli_load_inputs_supports_key_value_arguments():
    inputs = _load_inputs("{}", None, extra_inputs=["query=AEGIS", "limit=5"])

    assert inputs == {"query": "AEGIS", "limit": "5"}


def test_skill_cli_load_inputs_keeps_input_file_and_overrides_query(tmp_path):
    input_file = tmp_path / "inputs.json"
    input_file.write_text('{"query": "old", "lang": "en"}', encoding="utf-8")

    inputs = _load_inputs("{}", input_file, query="new")

    assert inputs == {"query": "new", "lang": "en"}


def test_skill_cli_load_inputs_rejects_invalid_key_value_argument():
    with pytest.raises(typer.Exit):
        _load_inputs("{}", None, extra_inputs=["broken"])
