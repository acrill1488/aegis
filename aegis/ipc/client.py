from __future__ import annotations

import json
import socket
from typing import Any

from aegis.serialization import to_plain

from .models import IPCRequest, IPCResponse


DEFAULT_IPC_HOST = "127.0.0.1"
DEFAULT_IPC_PORT = 8787


class IPCConnectionError(RuntimeError):
    pass


class IPCClient:
    def __init__(
        self,
        host: str = DEFAULT_IPC_HOST,
        port: int = DEFAULT_IPC_PORT,
        timeout: float = 60.0,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout

    def invoke(
        self,
        target: str,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> IPCResponse:
        request = IPCRequest.create(target=target, action=action, payload=payload)
        try:
            with socket.create_connection(
                (self.host, self.port),
                timeout=self.timeout,
            ) as connection:
                connection.settimeout(self.timeout)
                writer = connection.makefile("wb")
                reader = connection.makefile("rb")
                body = json.dumps(to_plain(request.to_dict()), ensure_ascii=False)
                writer.write(body.encode("utf-8") + b"\n")
                writer.flush()
                line = reader.readline()
        except OSError as exc:
            raise IPCConnectionError(
                "AEGIS daemon is not running. Start it with: aegis daemon serve"
            ) from exc

        if not line:
            raise IPCConnectionError("AEGIS daemon closed the IPC connection.")

        try:
            return IPCResponse.from_dict(json.loads(line.decode("utf-8")))
        except json.JSONDecodeError as exc:
            raise IPCConnectionError("AEGIS daemon returned an invalid IPC response.") from exc

    def request(
        self,
        target: str,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        response = self.invoke(target, action, payload)
        if not response.success:
            raise RuntimeError(response.error or "AEGIS daemon request failed")
        return response.output
