"""HTTPX transport for GBIP with bounded retries and sanitized errors."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import httpx

from .errors import (
    AuthenticationError,
    ConnectionError,
    NodeUnavailable,
    ProtocolError,
    ReservationDenied,
    TimeoutError,
)

SAFE_RETRY_METHODS = frozenset({"GET"})


def _status_error(response: httpx.Response) -> Exception:
    detail = f"GreenBoost returned HTTP {response.status_code}"
    if response.status_code in {401, 403}:
        return AuthenticationError(detail)
    if response.status_code in {409, 422}:
        return ReservationDenied(detail)
    if response.status_code in {404, 410, 503}:
        return NodeUnavailable(detail)
    return ProtocolError(detail)


def _payload(response: httpx.Response) -> Any:
    if response.status_code >= 400:
        raise _status_error(response)
    try:
        return response.json()
    except ValueError as exc:
        raise ProtocolError("GreenBoost returned invalid JSON") from exc


class HTTPTransport:
    """Synchronous HTTP transport; policy decisions stay in its caller."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        timeout: httpx.Timeout,
        retries: int = 0,
        client: httpx.Client | None = None,
    ) -> None:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
            trust_env=False,
        )
        self._owns_client = client is None
        self._retries = retries

    def request(
        self, method: str, path: str, *, json: Mapping[str, Any] | None = None
    ) -> Any:
        attempts = self._retries + 1 if method.upper() in SAFE_RETRY_METHODS else 1
        for attempt in range(attempts):
            cause: httpx.RequestError
            try:
                return _payload(self._client.request(method, path, json=json))
            except httpx.TimeoutException as exc:
                error: Exception = TimeoutError("GreenBoost request timed out")
                cause = exc
            except httpx.RequestError as exc:
                error = ConnectionError("GreenBoost connection failed")
                cause = exc
            if attempt + 1 == attempts:
                raise error from cause
            time.sleep(min(0.1 * (2**attempt), 1.0))
        raise AssertionError("unreachable")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class AsyncHTTPTransport:
    """Asynchronous equivalent of :class:`HTTPTransport`."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        timeout: httpx.Timeout,
        retries: int = 0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
            trust_env=False,
        )
        self._owns_client = client is None
        self._retries = retries

    async def request(
        self, method: str, path: str, *, json: Mapping[str, Any] | None = None
    ) -> Any:
        import asyncio

        attempts = self._retries + 1 if method.upper() in SAFE_RETRY_METHODS else 1
        for attempt in range(attempts):
            cause: httpx.RequestError
            try:
                return _payload(await self._client.request(method, path, json=json))
            except httpx.TimeoutException as exc:
                error: Exception = TimeoutError("GreenBoost request timed out")
                cause = exc
            except httpx.RequestError as exc:
                error = ConnectionError("GreenBoost connection failed")
                cause = exc
            if attempt + 1 == attempts:
                raise error from cause
            await asyncio.sleep(min(0.1 * (2**attempt), 1.0))
        raise AssertionError("unreachable")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
