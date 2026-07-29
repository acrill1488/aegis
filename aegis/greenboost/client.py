"""Single public integration point between AEGIS and GreenBoost."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import TypeAdapter, ValidationError

from aegis.config.services import GreenBoostConfig, get_greenboost_config

from .contracts import (
    NodeReference,
    ResourceRequest,
    ResourceReservation,
    ResourceSnapshot,
)
from .errors import ProtocolError
from .transport import AsyncHTTPTransport, HTTPTransport

_NODES = TypeAdapter(tuple[NodeReference, ...])


def _timeout(config: GreenBoostConfig) -> httpx.Timeout:
    return httpx.Timeout(
        connect=config.connect_timeout,
        read=config.read_timeout,
        write=config.write_timeout,
        pool=config.pool_timeout,
    )


def _model(model: type[Any], payload: Any) -> Any:
    try:
        return model.model_validate(payload)
    except (ValidationError, TypeError) as exc:
        raise ProtocolError(f"GreenBoost returned an invalid {model.__name__}") from exc


def _nodes(payload: Any) -> tuple[NodeReference, ...]:
    if isinstance(payload, Mapping) and "nodes" in payload:
        payload = payload["nodes"]
    try:
        return _NODES.validate_python(payload)
    except ValidationError as exc:
        raise ProtocolError("GreenBoost returned an invalid node list") from exc


class GreenBoostClient:
    """Typed synchronous GBIP facade with no planning or fallback behavior."""

    def __init__(
        self,
        config: GreenBoostConfig | None = None,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.config = config or get_greenboost_config()
        self.transport = transport or HTTPTransport(
            base_url=str(self.config.base_url),
            api_key=self.config.api_key,
            timeout=_timeout(self.config),
            retries=self.config.retries,
        )

    def discover(self) -> tuple[NodeReference, ...]:
        return _nodes(self.transport.request("GET", "/v1/nodes"))

    def snapshot(self, node_id: str | None = None) -> ResourceSnapshot:
        path = (
            f"/v1/nodes/{quote(node_id, safe='')}/snapshot"
            if node_id
            else "/v1/snapshot"
        )
        return _model(ResourceSnapshot, self.transport.request("GET", path))

    def reserve(self, request: ResourceRequest) -> ResourceReservation:
        payload = request.model_dump(mode="json")
        return _model(
            ResourceReservation,
            self.transport.request("POST", "/v1/reservations", json=payload),
        )

    def heartbeat(
        self, reservation_id: str, *, lease_owner: str
    ) -> ResourceReservation:
        identifier = quote(reservation_id, safe="")
        return _model(
            ResourceReservation,
            self.transport.request(
                "POST",
                f"/v1/reservations/{identifier}/heartbeat",
                json={"lease_owner": lease_owner},
            ),
        )

    def release(self, reservation_id: str) -> ResourceReservation:
        identifier = quote(reservation_id, safe="")
        return _model(
            ResourceReservation,
            self.transport.request("DELETE", f"/v1/reservations/{identifier}"),
        )

    def cancel(self, reservation_id: str) -> ResourceReservation:
        identifier = quote(reservation_id, safe="")
        return _model(
            ResourceReservation,
            self.transport.request("POST", f"/v1/reservations/{identifier}/cancel"),
        )

    def health(self) -> ResourceSnapshot:
        return _model(ResourceSnapshot, self.transport.request("GET", "/v1/health"))

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> "GreenBoostClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AsyncGreenBoostClient:
    """Typed asynchronous GBIP facade matching :class:`GreenBoostClient`."""

    def __init__(
        self,
        config: GreenBoostConfig | None = None,
        *,
        transport: AsyncHTTPTransport | None = None,
    ) -> None:
        self.config = config or get_greenboost_config()
        self.transport = transport or AsyncHTTPTransport(
            base_url=str(self.config.base_url),
            api_key=self.config.api_key,
            timeout=_timeout(self.config),
            retries=self.config.retries,
        )

    async def discover(self) -> tuple[NodeReference, ...]:
        return _nodes(await self.transport.request("GET", "/v1/nodes"))

    async def snapshot(self, node_id: str | None = None) -> ResourceSnapshot:
        path = (
            f"/v1/nodes/{quote(node_id, safe='')}/snapshot"
            if node_id
            else "/v1/snapshot"
        )
        return _model(ResourceSnapshot, await self.transport.request("GET", path))

    async def reserve(self, request: ResourceRequest) -> ResourceReservation:
        return _model(
            ResourceReservation,
            await self.transport.request(
                "POST", "/v1/reservations", json=request.model_dump(mode="json")
            ),
        )

    async def heartbeat(
        self, reservation_id: str, *, lease_owner: str
    ) -> ResourceReservation:
        identifier = quote(reservation_id, safe="")
        return _model(
            ResourceReservation,
            await self.transport.request(
                "POST",
                f"/v1/reservations/{identifier}/heartbeat",
                json={"lease_owner": lease_owner},
            ),
        )

    async def release(self, reservation_id: str) -> ResourceReservation:
        identifier = quote(reservation_id, safe="")
        return _model(
            ResourceReservation,
            await self.transport.request("DELETE", f"/v1/reservations/{identifier}"),
        )

    async def cancel(self, reservation_id: str) -> ResourceReservation:
        identifier = quote(reservation_id, safe="")
        return _model(
            ResourceReservation,
            await self.transport.request(
                "POST", f"/v1/reservations/{identifier}/cancel"
            ),
        )

    async def health(self) -> ResourceSnapshot:
        return _model(
            ResourceSnapshot, await self.transport.request("GET", "/v1/health")
        )

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self) -> "AsyncGreenBoostClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
