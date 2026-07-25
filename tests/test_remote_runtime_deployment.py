from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
DEPLOY = ROOT / "deploy" / "remote-runtime"


def test_remote_runtime_deployment_is_safe_and_lazy():
    dockerfile = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")
    compose_text = (DEPLOY / "docker-compose.yml").read_text(encoding="utf-8")
    compose = yaml.safe_load(compose_text)
    service = compose["services"]["aegis-remote-runtime"]
    assert "pytorch/pytorch:" in dockerfile
    assert "huggingface.co" not in dockerfile and "BAAI/bge-m3" not in dockerfile
    assert "healthcheck" in service
    assert service["gpus"] == "all"
    assert service.get("privileged") is not True
    assert "/var/run/docker.sock" not in compose_text
    assert "huggingface-cache:/var/cache/huggingface" in service["volumes"]
    assert "replace-with" not in compose_text


def test_server_route_uses_embedding_runtime_and_remote_provider_is_transport_only():
    route = (ROOT / "aegis" / "remote" / "server" / "app.py").read_text(encoding="utf-8")
    provider = (ROOT / "aegis" / "providers" / "remote_bge_m3.py").read_text(encoding="utf-8")
    assert "EmbeddingRuntime" in route
    assert "BGEM3FlagModel" not in route
    assert "import FlagEmbedding" not in provider
    assert "import torch" not in provider
