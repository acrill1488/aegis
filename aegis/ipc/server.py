from __future__ import annotations

import json
import socketserver
from typing import Any, Callable

from aegis.serialization import to_plain

from .client import DEFAULT_IPC_HOST, DEFAULT_IPC_PORT
from .models import IPCRequest, IPCResponse


RouteHandler = Callable[[IPCRequest], Any]


class IPCServer:
    def __init__(
        self,
        *,
        host: str = DEFAULT_IPC_HOST,
        port: int = DEFAULT_IPC_PORT,
        handler: RouteHandler,
    ):
        self.host = host
        self.port = port
        self.handler = handler
        self._server: socketserver.TCPServer | None = None

    def serve_forever(self, on_ready: Callable[[], None] | None = None) -> None:
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                for line in self.rfile:
                    response = outer._handle_line(line)
                    body = json.dumps(to_plain(response.to_dict()), ensure_ascii=False)
                    self.wfile.write(body.encode("utf-8") + b"\n")
                    self.wfile.flush()

        class Server(socketserver.TCPServer):
            allow_reuse_address = True

        self._server = Server((self.host, self.port), Handler)
        try:
            if on_ready is not None:
                on_ready()
            self._server.serve_forever()
        finally:
            self.close()

    def close(self) -> None:
        if self._server is None:
            return
        self._server.server_close()
        self._server = None

    def _handle_line(self, line: bytes) -> IPCResponse:
        request_id = ""
        try:
            data = json.loads(line.decode("utf-8"))
            request = IPCRequest.from_dict(data)
            request_id = request.id
            output = self.handler(request)
            return IPCResponse.ok(request.id, to_plain(output))
        except Exception as exc:
            return IPCResponse.fail(request_id, str(exc))
