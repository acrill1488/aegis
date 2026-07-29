from __future__ import annotations

import httpx
import pytest

from aegis.runtime.kimi import DEFAULT_BASE_URL, DEFAULT_MODEL, KimiRuntime


def response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "https://test"))


def test_configuration_defaults_and_environment(monkeypatch):
    monkeypatch.setenv("AEGIS_KIMI_API_KEY", "secret")
    monkeypatch.setenv("AEGIS_KIMI_BASE_URL", "https://kimi.example/v1/")
    monkeypatch.setenv("AEGIS_KIMI_MODEL", "kimi-test")
    monkeypatch.setenv("AEGIS_KIMI_REASONING_EFFORT", "high")

    runtime = KimiRuntime()

    assert runtime.api_key == "secret"
    assert runtime.base_url == "https://kimi.example/v1"
    assert runtime.default_model == "kimi-test"
    assert runtime.reasoning_effort == "high"

    monkeypatch.delenv("AEGIS_KIMI_BASE_URL")
    monkeypatch.delenv("AEGIS_KIMI_MODEL")
    assert KimiRuntime().base_url == DEFAULT_BASE_URL
    assert KimiRuntime().default_model == DEFAULT_MODEL


def test_health_success_and_models(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return response(200, {"data": [{"id": "kimi-k3"}, {"id": "kimi-k2"}]})

    monkeypatch.setattr("aegis.runtime.kimi.httpx.get", fake_get)
    runtime = KimiRuntime(api_key="secret")

    assert runtime.health() == {
        "configured": True,
        "reachable": True,
        "authenticated": True,
        "available": True,
        "quota": True,
        "rate_limited": False,
        "overloaded": False,
    }
    assert runtime.list_models() == ["kimi-k3", "kimi-k2"]
    assert calls[0][1]["headers"]["Authorization"] == "Bearer secret"


@pytest.mark.parametrize("status", [401, 403])
def test_health_authentication_failure(monkeypatch, status):
    monkeypatch.setattr(
        "aegis.runtime.kimi.httpx.get",
        lambda *args, **kwargs: response(status, {"error": {"message": "invalid key"}}),
    )

    health = KimiRuntime(api_key="bad").health()

    assert health["reachable"] is True
    assert health["authenticated"] is False
    assert health["available"] is False


def test_health_rate_limit_and_quota(monkeypatch):
    runtime = KimiRuntime(api_key="secret")
    replies = iter(
        [
            response(429, {"error": {"code": "rate_limit_exceeded"}}),
            response(429, {"error": {"code": "insufficient_quota"}}),
        ]
    )
    monkeypatch.setattr("aegis.runtime.kimi.httpx.get", lambda *args, **kwargs: next(replies))

    limited = runtime.health()
    quota = runtime.health()

    assert limited["rate_limited"] is True
    assert limited["quota"] is None
    assert quota["rate_limited"] is False
    assert quota["quota"] is False


def test_health_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr("aegis.runtime.kimi.httpx.get", timeout)

    health = KimiRuntime(api_key="secret").health()

    assert health["configured"] is True
    assert health["reachable"] is False
    assert health["available"] is False


def test_chat_uses_openai_compatible_request(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(200, {"choices": [{"message": {"content": "hello"}}]})

    monkeypatch.setattr("aegis.runtime.kimi.httpx.post", fake_post)
    runtime = KimiRuntime(api_key="secret", reasoning_effort="medium")

    result = runtime.chat("Hi", temperature=0.0, max_tokens=64)

    assert result == "hello"
    assert captured["url"] == f"{DEFAULT_BASE_URL}/chat/completions"
    assert captured["json"] == {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": False,
        "temperature": 0.0,
        "max_tokens": 64,
        "reasoning_effort": "medium",
    }


def test_stream_chat_reuses_chat_payload_and_yields_deltas(monkeypatch):
    captured = {}

    class StreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"hel"}}]}'
            yield "event: ignored"
            yield 'data: {"choices":[{"delta":{"content":"lo"}}]}'
            yield "data: [DONE]"

    def fake_stream(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return StreamResponse()

    monkeypatch.setattr("aegis.runtime.kimi.httpx.stream", fake_stream)

    chunks = list(KimiRuntime(api_key="secret").stream_chat(messages=[{"role": "user", "content": "Hi"}]))

    assert chunks == ["hel", "lo"]
    assert captured["json"]["stream"] is True


def test_chat_propagates_authentication_failure(monkeypatch):
    monkeypatch.setattr(
        "aegis.runtime.kimi.httpx.post",
        lambda *args, **kwargs: response(401, {"error": {"message": "invalid key"}}),
    )

    with pytest.raises(httpx.HTTPStatusError):
        KimiRuntime(api_key="bad").chat("Hi")


def test_chat_propagates_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr("aegis.runtime.kimi.httpx.post", timeout)

    with pytest.raises(httpx.ReadTimeout):
        KimiRuntime(api_key="secret").chat("Hi")


def test_unconfigured_runtime_makes_no_health_request(monkeypatch):
    monkeypatch.delenv("AEGIS_KIMI_API_KEY", raising=False)
    monkeypatch.setattr(
        "aegis.runtime.kimi.httpx.get",
        lambda *args, **kwargs: pytest.fail("health must not call HTTP without configuration"),
    )

    health = KimiRuntime().health()

    assert health["configured"] is False
    assert health["available"] is False
