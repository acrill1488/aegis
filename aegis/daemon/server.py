"""FastAPI server for the AEGIS daemon."""

from __future__ import annotations

import os
from dataclasses import asdict, is_dataclass
from importlib import metadata
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from aegis.agents.browser import BrowserService
from aegis.agents.windows import ProcessWatcher, SystemWatcher
from aegis.core.core import AegisCore
from aegis.daemon.state import (
    DaemonHeartbeat,
    DaemonStateStore,
    STATE_READY,
    STATE_STARTING,
    STATE_STOPPING,
)
from aegis.ipc import IPCRequest, IPCServer
from aegis.services import ServiceStatus


class AskRequest(BaseModel):
    prompt: str
    capability: str = "auto"
    role: str = "assistant"


class EventPublishRequest(BaseModel):
    type: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


def create_app() -> FastAPI:
    """Create the daemon app and keep one AegisCore instance in memory."""
    app = FastAPI(title="AEGIS Daemon", version=_version())
    app.state.core = AegisCore()
    _publish_daemon_event(app.state.core, "daemon.started", {"mode": "http"})
    _start_default_scheduler_tasks(app.state.core)
    _publish_daemon_event(app.state.core, "daemon.ready", {"mode": "http"})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": _version()}

    @app.get("/status")
    def status() -> dict[str, Any]:
        core = _core(app)
        return {
            "system": _serialize(core.system.status()),
            "skills": [_skill_status(skill) for skill in core.skills.list()],
            "tools": core.tools.status(),
            "events": {"count": len(core.events.history(limit=1_000_000))},
            "scheduler": core.scheduler.status(),
        }

    @app.post("/ask")
    def ask(request: AskRequest) -> dict[str, str]:
        core = _core(app)
        response = core.brain.ask(
            request.prompt,
            capability=request.capability,
            role=request.role,
        )
        return {"response": response}

    @app.post("/events/publish")
    def publish_event(request: EventPublishRequest) -> dict[str, Any]:
        core = _core(app)
        receipt = core.events.publish(request.type, request.source, request.payload)
        return _serialize(receipt)

    @app.get("/events/history")
    def events_history() -> list[dict[str, Any]]:
        core = _core(app)
        return [_serialize(event) for event in core.events.history()]

    return app


class DaemonRuntime:
    """Foreground daemon runtime that owns local services and IPC routing."""

    def __init__(self, *, headless_browser: bool = False):
        self.core = AegisCore()
        _publish_daemon_event(self.core, "daemon.started", {"mode": "ipc"})
        self.browser_service = BrowserService(headless=headless_browser)
        self.core.service_runtime.register(self.browser_service)
        _start_default_scheduler_tasks(self.core)
        _publish_daemon_event(self.core, "daemon.ready", {"mode": "ipc"})

    def handle_ipc(self, request: IPCRequest) -> Any:
        if request.target == "browser":
            return self._handle_browser(request.action, request.payload)
        if request.target == "ui":
            return self._handle_ui(request.action, request.payload)
        if request.target == "health":
            return self._health()
        if request.target == "services":
            return self._services(request.action)
        raise ValueError(f"Unsupported IPC target: {request.target}")

    def stop(self) -> None:
        try:
            if self.browser_service.status not in {
                ServiceStatus.stopped,
                ServiceStatus.stopping,
            }:
                self.core.service_runtime.stop(self.browser_service.id)
        finally:
            try:
                self.core.scheduler.stop()
                _publish_daemon_event(self.core, "daemon.stopped", {"mode": "ipc"})
            except Exception:
                _publish_daemon_event(
                    self.core,
                    "daemon.failed",
                    {"mode": "ipc", "stage": "stop"},
                    severity="error",
                )

    def _handle_browser(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "status":
            return self.browser_service.health()
        if action != "close" and self.browser_service.status != ServiceStatus.running:
            self.core.service_runtime.start(self.browser_service.id)
        try:
            result = self.browser_service.invoke(action, payload)
        except Exception as exc:
            self._publish_browser_event(action, payload, False, error=str(exc))
            raise
        self._publish_browser_event(action, payload, True, output=result)
        return result

    def _handle_ui(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.browser_service.status != ServiceStatus.running:
            self.core.service_runtime.start(self.browser_service.id)
        if action == "observe":
            return _serialize(self.core.ui_intelligence.observe(payload))
        if action == "describe":
            return _serialize(self.core.ui_intelligence.describe(payload))
        if action == "locate":
            return _serialize(
                self.core.ui_intelligence.locate(
                    payload.get("query"),
                    role=payload.get("role"),
                )
            )
        mapping = {
            "tree": "ui_tree",
        }
        browser_action = mapping.get(action)
        if browser_action is None:
            raise ValueError(f"Unsupported UI Runtime action: {action}")
        return self.browser_service.invoke(browser_action, payload)

    def _health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "version": _version(),
            "services": {
                "count": len(self.core.service_runtime.list()),
                "browser": self.browser_service.health(),
            },
        }

    def _services(self, action: str) -> list[dict[str, Any]]:
        if action not in {"list", "status"}:
            raise ValueError(f"Unsupported services action: {action}")
        return self.core.service_runtime.list()

    def _publish_browser_event(
        self,
        action: str,
        payload: dict[str, Any],
        success: bool,
        *,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        event_platform = getattr(self.core, "event_platform", None)
        publish = getattr(event_platform, "publish", None)
        if not callable(publish):
            return
        event_type = "browser.opened" if action == "open" and success else (
            "browser.action.completed" if success else "browser.action.failed"
        )
        try:
            publish(
                event_type,
                "daemon.browser",
                {
                    "action": action,
                    "payload": _serialize(payload),
                    "output": _serialize(output) if output is not None else None,
                    "error": error,
                },
                severity="info" if success else "error",
            )
        except Exception:
            return


def serve_ipc(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    headless_browser: bool = False,
    on_ready: Any | None = None,
) -> None:
    state_store = DaemonStateStore()
    state_store.write(STATE_STARTING, pid=os.getpid(), host=host, port=port)
    heartbeat: DaemonHeartbeat | None = None
    runtime = DaemonRuntime(headless_browser=headless_browser)
    server = IPCServer(host=host, port=port, handler=runtime.handle_ipc)

    def mark_ready() -> None:
        nonlocal heartbeat
        heartbeat = DaemonHeartbeat(
            state_store,
            state=STATE_READY,
            pid=os.getpid(),
            host=host,
            port=port,
        )
        heartbeat.start()
        if on_ready is not None:
            on_ready()

    try:
        server.serve_forever(on_ready=mark_ready)
    finally:
        if heartbeat is not None:
            heartbeat.stop()
        state_store.write(STATE_STOPPING, pid=os.getpid(), host=host, port=port)
        runtime.stop()


def _core(app: FastAPI) -> AegisCore:
    return app.state.core


def _start_default_scheduler_tasks(core: AegisCore) -> None:
    ProcessWatcher(core).start()
    SystemWatcher(core).start()
    core.scheduler.start()


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return _serialize(asdict(value))
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _skill_status(skill: Any) -> dict[str, Any]:
    return {
        "name": skill.name,
        "description": skill.description,
        "capabilities": list(skill.capabilities),
        "enabled": bool(getattr(skill, "enabled", True)),
    }


def _version() -> str:
    try:
        return metadata.version("aegis")
    except metadata.PackageNotFoundError:
        return "0.1.0"


def _publish_daemon_event(
    core: AegisCore,
    event_type: str,
    payload: dict[str, Any],
    *,
    severity: str = "info",
) -> None:
    event_platform = getattr(core, "event_platform", None)
    publish = getattr(event_platform, "publish", None)
    if not callable(publish):
        return
    try:
        publish(event_type, "daemon", payload, severity=severity)
    except Exception:
        return
