from __future__ import annotations

import json
import math
import sys
import types

import pytest
from typer.testing import CliRunner

import aegis.embeddings.cli as embeddings_cli
from aegis.embeddings import EmbeddingRegistry, EmbeddingRequest, EmbeddingRuntime
from aegis.embeddings.errors import EmbeddingDimensionError, EmbeddingValidationError
from aegis.installer.catalog import ManifestRegistry
from aegis.providers.bge_m3 import BGEM3Config, BGEM3Provider


def _config_file(tmp_path, section=None):
    path = tmp_path / "services.yaml"
    payload = {
        "schema_version": 1,
        "server": {"host": "127.0.0.1", "scheme": "http"},
        "services": {
            "ollama": {"port": 11434, "base_url": None},
            "unlimited_ocr": {"port": 8190, "base_url": None},
            "comfyui": {"port": 8188, "base_url": None},
        },
        "paths": {},
        "embeddings": {"providers": {"bge-m3": section or {}}},
    }
    import yaml

    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def _install_fake(monkeypatch, *, vectors=None, fail_gpu=False):
    instances = []

    class Model:
        def __init__(self, name, **kwargs):
            if fail_gpu and kwargs["devices"] == "cuda":
                raise RuntimeError("CUDA mismatch")
            self.name = name
            self.kwargs = kwargs
            self.calls = []
            instances.append(self)

        def encode(self, texts, **kwargs):
            self.calls.append((list(texts), kwargs))
            result = vectors[:len(texts)] if vectors else [[1.0, 0.0] for _ in texts]
            return {"dense_vecs": result}

    monkeypatch.setitem(sys.modules, "FlagEmbedding", types.SimpleNamespace(BGEM3FlagModel=Model))
    monkeypatch.setattr(
        "aegis.providers.bge_m3.provider.importlib.util.find_spec",
        lambda name: object() if name == "FlagEmbedding" else None,
    )
    return instances


def test_config_defaults_and_relative_cache(tmp_path):
    assert BGEM3Config.load(_config_file(tmp_path)) == BGEM3Config()
    config = BGEM3Config.load(_config_file(tmp_path, {"cache_dir": "models", "device": "cpu"}))
    assert config.cache_dir == str((tmp_path / "models").resolve())
    assert config.device == "cpu"


def test_registry_default_and_validation():
    provider = BGEM3Provider(BGEM3Config(enabled=False))
    runtime = EmbeddingRuntime(EmbeddingRegistry([provider]), max_texts_per_request=2)
    assert runtime.registry.resolve() is provider
    for value in ([], "  ", ["ok", 3]):
        with pytest.raises(EmbeddingValidationError):
            runtime.embed(EmbeddingRequest(value))
    with pytest.raises(EmbeddingValidationError):
        runtime.embed(["a", "b", "c"])


def test_lazy_import_model_reuse_batch_order_and_plain_vectors(monkeypatch):
    vectors = [[0.6, 0.8], [0.0, 1.0]]
    instances = _install_fake(monkeypatch, vectors=vectors)
    provider = BGEM3Provider(BGEM3Config(device="cpu", batch_size=2))
    assert instances == []

    first = EmbeddingRuntime(EmbeddingRegistry([provider])).embed(["first", "second"])
    second = EmbeddingRuntime(EmbeddingRegistry([provider])).embed("again")

    assert len(instances) == 1
    assert [item.text for item in first.vectors] == ["first", "second"]
    assert first.vectors[0].vector == [0.6, 0.8]
    assert math.isclose(first.vectors[0].norm, 1.0)
    assert first.dimensions == 2
    assert second.device == "cpu"
    assert instances[0].calls[0][1]["return_sparse"] is False
    assert instances[0].calls[0][1]["return_colbert_vecs"] is False


def test_gpu_initialization_falls_back_once(monkeypatch):
    instances = _install_fake(monkeypatch, fail_gpu=True)
    monkeypatch.setattr(BGEM3Provider, "_gpu_runtime_available", staticmethod(lambda: True))
    provider = BGEM3Provider(BGEM3Config(device="gpu"))

    result = provider.embed(EmbeddingRequest("text"))
    again = provider.embed(EmbeddingRequest("other"))

    assert len(instances) == 1
    assert result.device == again.device == "cpu"
    assert result.metadata["fallback"]["from"] == "gpu"


def test_dimension_and_normalization_are_verified(monkeypatch):
    _install_fake(monkeypatch, vectors=[[2.0, 0.0]])
    provider = BGEM3Provider(BGEM3Config(device="cpu", normalize_embeddings=True))
    with pytest.raises(EmbeddingDimensionError, match="non-normalized"):
        provider.embed(EmbeddingRequest("text"))

    _install_fake(monkeypatch, vectors=[[1.0, 0.0], [1.0]])
    provider = BGEM3Provider(BGEM3Config(device="cpu"))
    with pytest.raises(EmbeddingDimensionError, match="different dimensions"):
        provider.embed(EmbeddingRequest(["one", "two"]))


def test_missing_package_health_and_cli_json(monkeypatch):
    monkeypatch.setattr("aegis.providers.bge_m3.provider.importlib.util.find_spec", lambda name: None)
    provider = BGEM3Provider(BGEM3Config())
    runtime = EmbeddingRuntime(EmbeddingRegistry([provider]))
    monkeypatch.setattr(embeddings_cli, "_runtime", lambda: runtime)

    health = provider.health()
    output = CliRunner().invoke(embeddings_cli.app, ["providers", "--json"])
    doctor = CliRunner().invoke(embeddings_cli.app, ["doctor", "bge-m3", "--json"])

    assert health.status == "package missing"
    assert "aegis install bge-m3" in health.message
    assert json.loads(output.stdout)["providers"][0]["available"] is False
    assert json.loads(doctor.stdout)["selected_provider"]["model_loaded"] is False


def test_cli_embedding_json_is_plain_and_finite(monkeypatch):
    _install_fake(monkeypatch)
    runtime = EmbeddingRuntime(EmbeddingRegistry([BGEM3Provider(BGEM3Config(device="cpu"))]))
    monkeypatch.setattr(embeddings_cli, "_runtime", lambda: runtime)

    output = CliRunner().invoke(embeddings_cli.app, ["embed", "example", "--json"])
    payload = json.loads(output.stdout)

    assert output.exit_code == 0
    assert "[bold]" not in output.stdout
    assert payload["vectors"][0]["vector"] == [1.0, 0.0]


def test_manifest_uses_optional_official_package():
    manifest = ManifestRegistry(__import__("pathlib").Path("aegis/installer/manifests")).get("bge-m3")
    assert manifest.type == "provider"
    assert manifest.providers == ["bge-m3"]
    assert manifest.install[0].command == ["${python}", "-m", "pip", "install", "FlagEmbedding"]
    assert "torch" not in manifest.install[0].command
