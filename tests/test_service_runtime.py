from aegis.services import BaseService, ServiceRuntime, ServiceStatus


class Events:
    def __init__(self):
        self.published = []

    def publish(self, event_type, source, payload=None, trace_id=None):
        self.published.append(
            {
                "event_type": event_type,
                "source": source,
                "payload": payload,
                "trace_id": trace_id,
            }
        )


class Core:
    def __init__(self):
        self.events = Events()


class ExampleService(BaseService):
    def __init__(self):
        super().__init__("example", "Example")


def test_service_runtime_tracks_lifecycle_and_publishes_events():
    core = Core()
    runtime = ServiceRuntime(core)
    service = ExampleService()

    runtime.register(service)
    started = runtime.start("example")
    health = runtime.health("example")
    stopped = runtime.stop("example")

    assert started["status"] == ServiceStatus.running
    assert health["healthy"] is True
    assert stopped["status"] == ServiceStatus.stopped
    assert [event["event_type"] for event in core.events.published] == [
        "service.registered",
        "service.started",
        "service.stopped",
    ]
