"""FastAPI server for the AEGIS daemon."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from importlib import metadata
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from aegis.core.core import AegisCore


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


def _core(app: FastAPI) -> AegisCore:
    return app.state.core


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
