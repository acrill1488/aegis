from aegis.capabilities import CapabilityInvocationRequest, CapabilityRuntime
from aegis.desktop_runtime import DesktopApp, DesktopRuntime, DesktopWindow


class FakeEvents:
    def __init__(self):
        self.events = []

    def publish(self, event_type, source, payload=None, **context):
        self.events.append(
            {
                "type": event_type,
                "source": source,
                "payload": payload,
                "context": context,
            }
        )


class FakeRegistry:
    def __init__(self):
        self.services = {}

    def register(self, name, service):
        self.services[name] = service

    def get(self, name):
        return self.services.get(name)


class FakeCore:
    def __init__(self):
        self.events = FakeEvents()
        self.registry = FakeRegistry()
        self.capability_runtime = CapabilityRuntime(self)


class FakeProvider:
    def __init__(self):
        self.activated = []
        self.closed = []
        self.launched = []

    def list_windows(self):
        return [
            DesktopWindow(
                id="1",
                title="Editor",
                process_name="code.exe",
                pid=10,
                active=True,
                visible=True,
                bounds={"x": 0, "y": 0, "width": 800, "height": 600},
            )
        ]

    def active_window(self):
        return self.list_windows()[0]

    def activate_window(self, window_id):
        self.activated.append(window_id)
        return self.list_windows()[0]

    def close_window(self, window_id):
        self.closed.append(window_id)
        return {"window_id": str(window_id), "status": "close_requested"}

    def launch_app(self, command):
        self.launched.append(command)
        return DesktopApp(
            name="demo.exe",
            executable="demo.exe",
            pid=20,
            status="running",
        )

    def list_processes(self, limit=100):
        return [
            DesktopApp(
                name="demo.exe",
                executable="C:/demo.exe",
                pid=20,
                status="running",
                metadata={"limit": limit},
            )
        ]

    def screenshot(self, path=None):
        return {"path": path or "screen.png", "width": 100, "height": 50}


def test_desktop_runtime_delegates_and_publishes_events():
    core = FakeCore()
    provider = FakeProvider()
    runtime = DesktopRuntime(core, provider=provider)

    assert runtime.windows()["windows"][0]["title"] == "Editor"
    assert runtime.activate("1")["window"]["id"] == "1"
    assert runtime.launch("demo.exe")["app"]["pid"] == 20
    assert runtime.screenshot({"path": "out.png"})["path"] == "out.png"

    assert provider.activated == ["1"]
    assert provider.launched == ["demo.exe"]
    assert [event["type"] for event in core.events.events] == [
        "desktop.window.listed",
        "desktop.window.activated",
        "desktop.app.launched",
        "desktop.screenshot.created",
    ]


def test_desktop_runtime_registers_capabilities_and_invokes_provider():
    core = FakeCore()
    provider = FakeProvider()
    runtime = DesktopRuntime(core, provider=provider)
    core.registry.register("desktop_runtime", runtime)

    runtime.register_capabilities()

    assert core.capability_runtime.resolve("desktop.windows")["provider_type"] == "runtime"
    result = core.capability_runtime.invoke(
        CapabilityInvocationRequest(
            capability_id="desktop.activate",
            payload={"window_id": "1"},
            caller="test",
        )
    )

    assert result.success
    assert result.output["window"]["title"] == "Editor"
    assert provider.activated == ["1"]
