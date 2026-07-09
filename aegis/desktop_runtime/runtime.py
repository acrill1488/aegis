from __future__ import annotations

from typing import Any

from aegis.capabilities import CapabilityDescriptor
from aegis.serialization import to_plain

from .windows_provider import WindowsProvider


class DesktopRuntime:
    """Provider-neutral facade for local desktop control."""

    def __init__(self, core: Any, provider: WindowsProvider | None = None):
        self.core = core
        self.provider = provider or WindowsProvider()

    def windows(self, payload: dict | None = None) -> dict:
        windows = self.provider.list_windows()
        output = {"windows": to_plain(windows)}
        self._publish("desktop.window.listed", output)
        return output

    def active(self, payload: dict | None = None) -> dict:
        return {"window": to_plain(self.provider.active_window())}

    def activate(self, window_id: str | int | dict | None = None) -> dict:
        resolved_id = self._window_id(window_id)
        window = self.provider.activate_window(resolved_id)
        output = {"window": to_plain(window)}
        self._publish("desktop.window.activated", output)
        return output

    def close(self, window_id: str | int | dict | None = None) -> dict:
        output = self.provider.close_window(self._window_id(window_id))
        return to_plain(output)

    def launch(self, command: str | list[str] | dict | None = None) -> dict:
        resolved_command = self._command(command)
        app = self.provider.launch_app(resolved_command)
        output = {"app": to_plain(app)}
        self._publish("desktop.app.launched", output)
        return output

    def processes(self, payload: dict | None = None) -> dict:
        limit = int((payload or {}).get("limit", 100))
        return {"processes": to_plain(self.provider.list_processes(limit=limit))}

    def screenshot(self, payload: str | dict | None = None) -> dict:
        path = payload.get("path") if isinstance(payload, dict) else payload
        output = self.provider.screenshot(path=path)
        self._publish("desktop.screenshot.created", output)
        return to_plain(output)

    def register_capabilities(self) -> None:
        capability_runtime = getattr(self.core, "capability_runtime", None)
        if capability_runtime is None:
            return
        for capability_id, name, method, permissions, input_schema, side_effects in (
            (
                "desktop.windows",
                "List Desktop Windows",
                "windows",
                ["desktop.window.read"],
                {"type": "object"},
                [],
            ),
            (
                "desktop.active",
                "Get Active Desktop Window",
                "active",
                ["desktop.window.read"],
                {"type": "object"},
                [],
            ),
            (
                "desktop.activate",
                "Activate Desktop Window",
                "activate",
                ["desktop.window.control"],
                {
                    "type": "object",
                    "required": ["window_id"],
                    "properties": {"window_id": {"type": "string"}},
                },
                ["desktop.window.focus"],
            ),
            (
                "desktop.close",
                "Close Desktop Window",
                "close",
                ["desktop.window.control"],
                {
                    "type": "object",
                    "required": ["window_id"],
                    "properties": {"window_id": {"type": "string"}},
                },
                ["desktop.window.close"],
            ),
            (
                "desktop.launch",
                "Launch Desktop App",
                "launch",
                ["desktop.app.launch"],
                {
                    "type": "object",
                    "required": ["command"],
                    "properties": {"command": {"type": "string"}},
                },
                ["process.start"],
            ),
            (
                "desktop.processes",
                "List Desktop Processes",
                "processes",
                ["desktop.process.read"],
                {"type": "object", "properties": {"limit": {"type": "integer"}}},
                [],
            ),
            (
                "desktop.screenshot",
                "Create Desktop Screenshot",
                "screenshot",
                ["desktop.screenshot"],
                {"type": "object", "properties": {"path": {"type": "string"}}},
                ["filesystem.write"],
            ),
        ):
            descriptor = CapabilityDescriptor(
                id=capability_id,
                name=name,
                version="1",
                owner_agent="desktop_runtime",
                machine_scope="local",
                permissions=permissions,
                input_schema=input_schema,
                output_schema={"type": "object"},
                tags=["desktop", "windows"],
                metadata={
                    "provider_type": "runtime",
                    "side_effects": side_effects,
                    "description": name,
                },
            )
            capability_runtime.unregister(descriptor.id)
            capability_runtime.register(
                descriptor,
                {
                    "type": "runtime",
                    "runtime": "desktop_runtime",
                    "method": method,
                },
            )

    def _window_id(self, value: str | int | dict | None) -> str | int:
        if isinstance(value, dict):
            value = value.get("window_id") or value.get("id")
        if value in (None, ""):
            raise ValueError("window_id is required")
        return value

    def _command(self, value: str | list[str] | dict | None) -> str | list[str]:
        if isinstance(value, dict):
            value = value.get("command")
        if value in (None, ""):
            raise ValueError("command is required")
        return value

    def _publish(self, event_type: str, payload: dict) -> None:
        events = getattr(self.core, "events", None)
        publish = getattr(events, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, source="desktop_runtime", payload=to_plain(payload))
        except Exception:
            return
