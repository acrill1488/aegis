from datetime import datetime

from aegis.distributed import MachineRecord, MachineRegistry


def test_machine_registry_persists_records(tmp_path):
    registry_path = tmp_path / "machines.json"
    registry = MachineRegistry(path=registry_path)

    record = registry.upsert_machine(
        MachineRecord(
            machine_id="machine-1",
            hostname="host-1",
            os="Windows",
            version="local-dev",
            capabilities=["filesystem.read", "browser.navigate"],
            connected=True,
            last_seen=datetime(2026, 7, 9, 12, 0, 0),
            session_id="session-1",
        )
    )

    loaded = MachineRegistry(path=registry_path)

    assert record.machine_id == "machine-1"
    assert loaded.get("machine-1") == record
    assert loaded.list_available_capabilities() == {
        "browser.navigate": ["machine-1"],
        "filesystem.read": ["machine-1"],
    }


def test_machine_registry_marks_disconnected_and_publishes(tmp_path):
    events = _FakeEvents()
    registry = MachineRegistry(path=tmp_path / "machines.json", event_bus=events)
    registry.upsert_machine(
        MachineRecord(
            machine_id="machine-1",
            hostname="host-1",
            os="Windows",
            version="local-dev",
            capabilities=["filesystem.read"],
            connected=False,
        )
    )

    connected = registry.mark_connected("machine-1", session_id="session-1")

    assert connected.connected is True
    assert connected.session_id == "session-1"

    disconnected = registry.mark_disconnected("machine-1")

    assert disconnected.connected is False
    assert disconnected.session_id is None
    assert [event[0] for event in events.published] == [
        "machine.registered",
        "machine.connected",
        "machine.disconnected",
    ]


class _FakeEvents:
    def __init__(self):
        self.published = []

    def publish(self, event_type, source, payload):
        self.published.append((event_type, source, payload))
