from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from aegis.greenboost import (
    ExecutionPriority,
    GreenBoostMode,
    GreenBoostRuntime,
    GreenBoostSession,
    MemoryState,
    NodeReference,
    NodeScope,
    ProbeWarning,
    ReservationState,
    ResourcePressure,
    ResourceProfile,
    ResourceQuantities,
    ResourceRequest,
    ResourceReservation,
    ResourceSnapshot,
)
from aegis.greenboost.contracts import (
    MAX_METADATA_BYTES,
    MAX_METADATA_ITEMS,
    MAX_METADATA_KEY_LENGTH,
    MAX_METADATA_STRING_LENGTH,
    MAX_METADATA_INTEGER,
    MIN_METADATA_INTEGER,
)
from aegis.task.status import TaskPriority


NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
NODE = NodeReference(id="ubuntu-ai", scope=NodeScope.remote)


def request(**overrides):
    values = {
        "execution_id": "execution_" + uuid4().hex,
        "capability": "ocr.recognize",
        "node": NODE,
    }
    values.update(overrides)
    return ResourceRequest(**values)


def reservation(**overrides):
    values = {
        "reservation_id": "reservation_" + uuid4().hex,
        "execution_id": "execution_" + uuid4().hex,
        "node": NODE,
        "resources": ResourceQuantities(vram_mb=4096),
        "created_at": NOW,
        "owner": "execution-orchestrator",
    }
    values.update(overrides)
    return ResourceReservation(**values)


def test_minimal_request_preserves_unknown_estimates():
    value = request()
    assert value.cpu_cores_min is None
    assert value.ram_mb_min is None
    assert value.vram_mb_min is None
    assert value.priority is ExecutionPriority.normal


def test_complete_request_round_trips_as_json():
    value = request(
        provider="unlimited",
        service="unlimited-ocr",
        model="openbmb/MiniCPM-o-2_6",
        priority=ExecutionPriority.interactive,
        cpu_cores_min=2,
        cpu_cores_preferred=4,
        ram_mb_min=1024,
        ram_mb_preferred=2048,
        vram_mb_min=4096,
        vram_mb_preferred=6144,
        disk_mb=512,
        gpu_required=True,
        gpu_exclusive=True,
        cpu_fallback_allowed=False,
        remote_allowed=True,
        preemptible=False,
        estimated_duration=timedelta(seconds=30),
        queue_timeout=timedelta(minutes=2),
        execution_timeout=timedelta(minutes=5),
        metadata={"estimate": {"source": "benchmark", "confidence": 0.8}},
    )
    restored = ResourceRequest.model_validate_json(value.model_dump_json())
    assert restored == value
    assert json.loads(value.model_dump_json())["priority"] == "interactive"


@pytest.mark.parametrize(
    "field",
    ["cpu_cores_min", "cpu_cores_preferred", "ram_mb_min", "ram_mb_preferred", "vram_mb_min", "vram_mb_preferred", "disk_mb"],
)
def test_negative_resources_are_rejected(field):
    with pytest.raises(ValidationError):
        request(**{field: -1})


@pytest.mark.parametrize(
    ("minimum", "preferred"),
    [("cpu_cores_min", "cpu_cores_preferred"), ("ram_mb_min", "ram_mb_preferred"), ("vram_mb_min", "vram_mb_preferred")],
)
def test_preferred_cannot_be_lower_than_minimum(minimum, preferred):
    with pytest.raises(ValidationError, match="cannot be lower"):
        request(**{minimum: 2, preferred: 1})


@pytest.mark.parametrize("field", ["estimated_duration", "queue_timeout", "execution_timeout"])
@pytest.mark.parametrize("value", [timedelta(0), timedelta(seconds=-1)])
def test_nonpositive_durations_are_rejected(field, value):
    with pytest.raises(ValidationError, match="must be positive"):
        request(**{field: value})


def test_critical_priority_is_explicitly_untrusted_and_metadata_cannot_elevate():
    assert request(priority="critical").requires_priority_authorization is True
    with pytest.raises(ValidationError, match="reserved for execution priority"):
        request(metadata={"priority": "critical"})


@pytest.mark.parametrize(
    "metadata",
    [
        {"value": object()},
        {"value": float("nan")},
        {"nested": [[[[[[[1]]]]]]]},
        {"items": list(range(129))},
        {"text": "x" * 17_000},
    ],
)
def test_metadata_bounds_and_json_types_are_enforced(metadata):
    with pytest.raises(ValidationError):
        request(metadata=metadata)


def test_mutable_metadata_input_is_isolated():
    metadata = {"tags": ["ocr"]}
    value = request(metadata=metadata)
    metadata["tags"].append("changed")
    assert value.metadata == {"tags": ["ocr"]}


def test_metadata_is_deeply_immutable():
    value = request(
        metadata={
            "top_list": [1, 2],
            "nested": {"value": 1, "nested_list": [[1]]},
        }
    )
    with pytest.raises(TypeError):
        value.metadata["new"] = "value"
    with pytest.raises(TypeError):
        value.metadata["nested"]["value"] = 2
    with pytest.raises((AttributeError, TypeError)):
        value.metadata["top_list"].append(3)
    with pytest.raises((AttributeError, TypeError)):
        value.metadata["nested"]["nested_list"][0].append(2)


def test_metadata_serializes_as_plain_json_and_round_trips():
    value = request(metadata={"nested": {"items": [1, {"enabled": True}]}})
    dumped = value.model_dump()
    assert type(dumped["metadata"]) is dict
    assert type(dumped["metadata"]["nested"]["items"]) is list
    assert ResourceRequest.model_validate_json(value.model_dump_json()) == value


def test_metadata_serialization_is_deterministic_for_equivalent_input_order():
    first = request(execution_id="execution_same", metadata={"z": 1, "a": {"y": 2, "b": 3}})
    second = request(execution_id="execution_same", metadata={"a": {"b": 3, "y": 2}, "z": 1})
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


RESERVED_PRIORITY_KEYS = (
    "priority",
    "execution_priority",
    "priority_trusted",
    "priority_authorized",
    "critical_authorized",
    "requires_priority_authorization",
)


@pytest.mark.parametrize("key", RESERVED_PRIORITY_KEYS)
@pytest.mark.parametrize("nested", [False, True])
def test_reserved_priority_keys_are_rejected_at_every_depth(key, nested):
    metadata = {"policy": {key: True}} if nested else {key: True}
    with pytest.raises(ValidationError, match="reserved for execution priority"):
        request(metadata=metadata)


def test_reserved_priority_key_matching_is_case_insensitive_but_exact():
    with pytest.raises(ValidationError, match="reserved for execution priority"):
        request(metadata={"PrIoRiTy_AuThOrIzEd": True})
    value = request(metadata={"priority_label": "interactive", "deprioritized": False})
    assert value.model_dump()["metadata"] == {
        "deprioritized": False,
        "priority_label": "interactive",
    }


def test_metadata_key_and_string_length_boundaries():
    accepted = request(
        metadata={"k" * MAX_METADATA_KEY_LENGTH: "x" * MAX_METADATA_STRING_LENGTH}
    )
    assert len(next(iter(accepted.metadata))) == MAX_METADATA_KEY_LENGTH
    with pytest.raises(ValidationError, match="key exceeds maximum length"):
        request(metadata={"k" * (MAX_METADATA_KEY_LENGTH + 1): "value"})
    with pytest.raises(ValidationError, match="string exceeds maximum length"):
        request(metadata={"value": "x" * (MAX_METADATA_STRING_LENGTH + 1)})


@pytest.mark.parametrize("value", [MIN_METADATA_INTEGER, MAX_METADATA_INTEGER])
def test_signed_64_bit_metadata_integer_boundaries_are_accepted(value):
    assert request(metadata={"value": value}).metadata["value"] == value


@pytest.mark.parametrize("value", [MIN_METADATA_INTEGER - 1, MAX_METADATA_INTEGER + 1])
def test_metadata_integers_outside_signed_64_bit_are_rejected(value):
    with pytest.raises(ValidationError, match="signed 64-bit"):
        request(metadata={"value": value})


def test_circular_metadata_containers_are_rejected_explicitly():
    circular_dict = {}
    circular_dict["self"] = circular_dict
    with pytest.raises(ValidationError, match="circular dictionary or list"):
        request(metadata=circular_dict)

    circular_list = []
    circular_list.append(circular_list)
    with pytest.raises(ValidationError, match="circular dictionary or list"):
        request(metadata={"items": circular_list})


def test_repeated_shared_acyclic_metadata_is_allowed_and_isolated():
    shared = {"items": [1, 2]}
    original = {"first": shared, "second": shared}
    value = request(metadata=original)
    shared["items"].append(3)
    assert value.model_dump()["metadata"] == {
        "first": {"items": [1, 2]},
        "second": {"items": [1, 2]},
    }


def _metadata_payload_with_encoded_size(target: int) -> dict[str, str]:
    payload = {f"value_{index}": "" for index in range(5)}
    base_size = len(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")
    )
    remaining = target - base_size
    assert 0 <= remaining <= 5 * MAX_METADATA_STRING_LENGTH
    for key in payload:
        length = min(remaining, MAX_METADATA_STRING_LENGTH)
        payload[key] = "x" * length
        remaining -= length
    assert remaining == 0
    assert len(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")
    ) == target
    return payload


def test_metadata_encoded_payload_exact_boundary():
    accepted = _metadata_payload_with_encoded_size(MAX_METADATA_BYTES)
    assert request(metadata=accepted).model_dump()["metadata"] == accepted
    with pytest.raises(ValidationError, match="maximum encoded size"):
        request(metadata=_metadata_payload_with_encoded_size(MAX_METADATA_BYTES + 1))


def test_metadata_aggregate_count_across_mixed_containers():
    exact = {
        "items": [{"value": index} for index in range(63)],
        "marker": True,
    }
    assert 2 + 63 + 63 == MAX_METADATA_ITEMS
    request(metadata=exact)
    exact["items"].append(0)
    with pytest.raises(ValidationError, match="maximum item count"):
        request(metadata=exact)


def test_reservation_validates_utc_timeline_and_released_state():
    value = reservation(
        state=ReservationState.released,
        lease_expires_at=NOW + timedelta(minutes=5),
        last_heartbeat_at=NOW + timedelta(minutes=1),
        lease_owner="worker-1",
        released_at=NOW + timedelta(minutes=2),
    )
    restored = ResourceReservation.model_validate_json(value.model_dump_json())
    assert restored == value
    assert restored.created_at.tzinfo is timezone.utc


def test_reservation_is_an_immutable_replacement_state_record():
    assert "Immutable reservation state record" in (ResourceReservation.__doc__ or "")
    assert "newly validated" in (ResourceReservation.__doc__ or "")
    original = reservation(state=ReservationState.active)
    replacement = ResourceReservation.model_validate(
        {**original.model_dump(), "state": ReservationState.suspected_stale}
    )
    assert original.state is ReservationState.active
    assert replacement.state is ReservationState.suspected_stale
    with pytest.raises(ValidationError):
        original.state = ReservationState.suspected_stale


def test_reconstructed_reservation_transition_runs_complete_validation():
    original = reservation(state=ReservationState.active)
    with pytest.raises(ValidationError, match="cannot precede created_at"):
        ResourceReservation.model_validate(
            {
                **original.model_dump(),
                "state": ReservationState.released,
                "released_at": NOW - timedelta(seconds=1),
            }
        )


def test_timezone_naive_datetimes_are_rejected():
    with pytest.raises(ValidationError, match="timezone-aware"):
        reservation(created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError, match="timezone-aware"):
        ResourceSnapshot(timestamp=NOW.replace(tzinfo=None), node=NODE)


@pytest.mark.parametrize("field", ["lease_expires_at", "last_heartbeat_at", "released_at"])
def test_reservation_timestamps_cannot_precede_creation(field):
    values = {field: NOW - timedelta(seconds=1)}
    if field == "released_at":
        values["state"] = ReservationState.released
    if field == "last_heartbeat_at":
        values["lease_owner"] = "worker-1"
    with pytest.raises(ValidationError, match="cannot precede"):
        reservation(**values)


def test_released_state_and_timestamp_must_be_consistent():
    with pytest.raises(ValidationError, match="require released_at"):
        reservation(state=ReservationState.released)
    with pytest.raises(ValidationError, match="only valid"):
        reservation(released_at=NOW + timedelta(seconds=1))


def test_suspected_stale_and_modes_serialize_to_lowercase_values():
    stale = reservation(state=ReservationState.suspected_stale)
    assert json.loads(stale.model_dump_json())["state"] == "suspected_stale"
    assert [mode.value for mode in GreenBoostMode] == ["disabled", "observe", "enforce"]
    assert [profile.value for profile in ResourceProfile] == ["performance", "balanced", "eco", "emergency"]


def test_snapshot_preserves_unknown_telemetry_and_structured_warnings():
    snapshot = ResourceSnapshot(
        timestamp=NOW,
        node=NODE,
        ram=MemoryState(),
        queue_depth=None,
        pressure=ResourcePressure.unknown,
        probe_warnings=(ProbeWarning(code="gpu.unavailable", message="GPU probe failed", resource="gpu"),),
        fresh_until=NOW + timedelta(seconds=30),
    )
    payload = json.loads(snapshot.model_dump_json())
    assert payload["ram"]["total_mb"] is None
    assert payload["ram"]["available_mb"] is None
    assert payload["queue_depth"] is None
    assert payload["pressure"] == "unknown"
    assert payload["probe_warnings"][0]["code"] == "gpu.unavailable"
    assert ResourceSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


def test_contracts_are_frozen():
    with pytest.raises(ValidationError):
        NODE.id = "changed"


def test_existing_public_imports_and_distinct_existing_priority_remain_compatible():
    assert GreenBoostRuntime.__name__ == "GreenBoostRuntime"
    assert GreenBoostSession.__name__ == "GreenBoostSession"
    assert TaskPriority.NORMAL.value == "normal"
    assert ExecutionPriority is not TaskPriority


def test_contract_import_and_construction_do_not_load_runtime_dependencies():
    before = set(sys.modules)
    from aegis.greenboost.contracts import ResourceRequest as ImportedRequest

    ImportedRequest(execution_id="execution_test", capability="test", node=NODE)
    loaded = set(sys.modules) - before
    assert not {"httpx", "paramiko", "PIL.Image"}.intersection(loaded)
