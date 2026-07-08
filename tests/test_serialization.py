from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from uuid import UUID

from aegis.serialization import to_json, to_plain


class SampleEnum(Enum):
    value = "sample"


@dataclass
class SampleDataclass:
    when: datetime
    kind: SampleEnum


class ModelDumpObject:
    def model_dump(self):
        return {"path": Path("data/file.txt")}


class DictObject:
    def dict(self):
        return {"payload": b"hello\xff"}


def test_to_plain_serializes_supported_types():
    value = {
        "dataclass": SampleDataclass(
            when=datetime(2026, 7, 8, 12, 30, 45),
            kind=SampleEnum.value,
        ),
        "date": date(2026, 7, 8),
        "path": Path("F:/AEGIS"),
        "uuid": UUID("12345678-1234-5678-1234-567812345678"),
        "items": (SampleEnum.value, [1, 2]),
        "set": {3, 4},
        "model": ModelDumpObject(),
        "dict": DictObject(),
        "none": None,
    }

    plain = to_plain(value)

    assert sorted(plain.pop("set")) == [3, 4]
    assert plain == {
        "dataclass": {"when": "2026-07-08T12:30:45", "kind": "sample"},
        "date": "2026-07-08",
        "path": "F:\\AEGIS",
        "uuid": "12345678-1234-5678-1234-567812345678",
        "items": ["sample", [1, 2]],
        "model": {"path": "data\\file.txt"},
        "dict": {"payload": "hello\ufffd"},
        "none": None,
    }


def test_to_json_uses_to_plain():
    assert to_json({"kind": SampleEnum.value}, indent=None) == '{"kind": "sample"}'
