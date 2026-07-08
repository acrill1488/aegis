from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import MachineRecord


DEFAULT_MACHINE_REGISTRY_PATH = Path(r"F:\AI_WORKSPACE\distributed\machines.json")


class MachineRegistry:
    """Persistent runtime view of distributed machines."""

    def __init__(
        self,
        path: str | Path = DEFAULT_MACHINE_REGISTRY_PATH,
        event_bus: Any | None = None,
    ):
        self.path = Path(path)
        self.event_bus = event_bus
        self._machines: dict[str, MachineRecord] = {}
        self._persistence_available = True
        self._ensure_file()
        self._load()

    def upsert_machine(self, record: MachineRecord) -> MachineRecord:
        self._machines[record.machine_id] = record
        self._save()
        self._publish("machine.registered", record)
        if record.connected:
            self._publish("machine.connected", record)
        return record

    def get(self, machine_id: str) -> MachineRecord | None:
        return self._machines.get(machine_id)

    def list(self) -> list[MachineRecord]:
        return list(self._machines.values())

    def bind_session(self, machine_id: str, session_id: str) -> MachineRecord:
        record = self._require_machine(machine_id)
        record.session_id = session_id
        record.connected = True
        record.last_seen = datetime.now()
        self._save()
        self._publish("machine.connected", record)
        return record

    def update_last_seen(self, machine_id: str) -> MachineRecord:
        record = self._require_machine(machine_id)
        record.last_seen = datetime.now()
        self._save()
        return record

    def mark_connected(
        self,
        machine_id: str,
        session_id: str | None = None,
    ) -> MachineRecord:
        record = self._require_machine(machine_id)
        record.connected = True
        record.session_id = session_id
        record.last_seen = datetime.now()
        self._save()
        self._publish("machine.connected", record)
        return record

    def mark_disconnected(self, machine_id: str) -> MachineRecord:
        record = self._require_machine(machine_id)
        record.connected = False
        record.session_id = None
        record.last_seen = datetime.now()
        self._save()
        self._publish("machine.disconnected", record)
        return record

    def list_available_capabilities(self) -> dict[str, list[str]]:
        capabilities: dict[str, list[str]] = {}
        for record in self._machines.values():
            if not record.connected:
                continue
            for capability in record.capabilities:
                capabilities.setdefault(capability, []).append(record.machine_id)
        return {key: sorted(value) for key, value in sorted(capabilities.items())}

    def _require_machine(self, machine_id: str) -> MachineRecord:
        record = self.get(machine_id)
        if record is None:
            raise KeyError(f"Machine not found: {machine_id}")
        return record

    def _ensure_file(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.write_text("[]", encoding="utf-8")
        except OSError:
            self._persistence_available = False

    def _load(self) -> None:
        if not self._persistence_available:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []

        if isinstance(data, dict):
            items = data.get("machines", data.values())
        elif isinstance(data, list):
            items = data
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                record = self._record_from_plain(item)
            except (KeyError, TypeError, ValueError):
                continue
            self._machines[record.machine_id] = record

        self._save()

    def _save(self) -> None:
        if not self._persistence_available:
            return
        try:
            self.path.write_text(
                json.dumps(
                    to_plain(self.list()),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            self._persistence_available = False

    def _record_from_plain(self, item: dict) -> MachineRecord:
        capabilities = item.get("capabilities") or []
        if not isinstance(capabilities, list):
            capabilities = []

        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        return MachineRecord(
            machine_id=str(item["machine_id"]),
            hostname=str(item["hostname"]),
            os=str(item["os"]),
            version=str(item["version"]),
            capabilities=[str(capability) for capability in capabilities],
            connected=bool(item.get("connected", False)),
            last_seen=self._parse_datetime(item.get("last_seen")),
            session_id=(
                str(item["session_id"])
                if item.get("session_id") is not None
                else None
            ),
            metadata=metadata,
        )

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None
        return datetime.fromisoformat(value)

    def _publish(self, event_type: str, record: MachineRecord) -> None:
        if self.event_bus is None or not hasattr(self.event_bus, "publish"):
            return
        try:
            self.event_bus.publish(
                event_type,
                source=f"machine_registry:{record.machine_id}",
                payload={"machine": to_plain(record)},
            )
        except Exception:
            return
