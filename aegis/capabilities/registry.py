from __future__ import annotations

from copy import deepcopy

from .models import CapabilityDescriptor


class CapabilityRegistry:
    def __init__(self):
        self._records: dict[str, dict] = {}

    def register(self, descriptor: CapabilityDescriptor, provider_handle: dict) -> dict:
        self._validate_descriptor(descriptor)
        self._validate_provider_handle(provider_handle)

        record = self._records.setdefault(
            descriptor.id,
            {
                "descriptor": descriptor,
                "provider_handles": [],
            },
        )
        record["descriptor"] = descriptor
        if provider_handle not in record["provider_handles"]:
            record["provider_handles"].append(dict(provider_handle))
        return self.resolve(descriptor.id)

    def unregister(
        self,
        capability_id: str,
        provider_handle: dict | None = None,
    ) -> dict | None:
        record = self._records.get(capability_id)
        if record is None:
            return None

        if provider_handle is None:
            return self._records.pop(capability_id)

        record["provider_handles"] = [
            handle
            for handle in record["provider_handles"]
            if handle != provider_handle
        ]
        if not record["provider_handles"]:
            return self._records.pop(capability_id)
        return self.resolve(capability_id)

    def resolve(self, capability_id: str) -> dict | None:
        record = self._records.get(capability_id)
        if record is None:
            return None
        return {
            "descriptor": record["descriptor"],
            "provider_handles": deepcopy(record["provider_handles"]),
        }

    def list(self) -> list[CapabilityDescriptor]:
        return [record["descriptor"] for record in self._records.values()]

    def find_by_tag(self, tag: str) -> list[CapabilityDescriptor]:
        return [
            record["descriptor"]
            for record in self._records.values()
            if tag in record["descriptor"].tags
        ]

    def _validate_descriptor(self, descriptor: CapabilityDescriptor) -> None:
        if not descriptor.id:
            raise ValueError("Capability descriptor id is required")
        if not descriptor.name:
            raise ValueError("Capability descriptor name is required")

    def _validate_provider_handle(self, provider_handle: dict) -> None:
        if not isinstance(provider_handle, dict):
            raise ValueError("Capability provider_handle must be a dict")
        if not provider_handle.get("type"):
            raise ValueError("Capability provider_handle type is required")
