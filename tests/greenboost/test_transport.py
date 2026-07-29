from __future__ import annotations

import httpx
import pytest

from aegis.greenboost.errors import (
    AuthenticationError,
    ConnectionError,
    ProtocolError,
    ReservationDenied,
    TimeoutError,
)
from aegis.greenboost.transport import HTTPTransport


def _transport(handler, *, retries=0):
    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://greenboost.test"
    )
    return HTTPTransport(
        base_url="http://greenboost.test",
        api_key=None,
        timeout=httpx.Timeout(1),
        retries=retries,
        client=client,
    )


def test_success_and_safe_retry():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, json={"ok": True})

    assert _transport(handler, retries=1).request("GET", "/v1/health") == {"ok": True}
    assert calls == 2


def test_mutating_request_is_never_retried():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(ConnectionError):
        _transport(handler, retries=5).request("POST", "/v1/reservations", json={})
    assert calls == 1


@pytest.mark.parametrize(
    "status,error",
    [(401, AuthenticationError), (409, ReservationDenied), (500, ProtocolError)],
)
def test_status_mapping(status, error):
    with pytest.raises(error):
        _transport(lambda request: httpx.Response(status, json={})).request("GET", "/")


def test_timeout_mapping():
    def handler(request):
        raise httpx.ReadTimeout("late", request=request)

    with pytest.raises(TimeoutError):
        _transport(handler).request("GET", "/")


def test_invalid_json_is_protocol_error():
    with pytest.raises(ProtocolError):
        _transport(lambda request: httpx.Response(200, text="not-json")).request(
            "GET", "/"
        )
