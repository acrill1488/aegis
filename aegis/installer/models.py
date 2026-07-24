from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ComponentType = Literal[
    "runtime", "provider", "model", "workflow", "service", "system", "bundle"
]


class PackageRef(BaseModel):
    name: str
    version: str | None = None
    source: str | None = None
    trust_policy: str = "checksum"
    profile: str | None = None


class Healthcheck(BaseModel):
    type: Literal["http", "command", "provider", "path", "none"] = "none"
    endpoint: str | None = None
    service: str | None = None
    command: list[str] = Field(default_factory=list)
    path: str | None = None
    expected_status: int = 200


class Action(BaseModel):
    type: Literal["docker_compose", "command", "directory", "config", "noop"]
    operation: str | None = None
    path: str | None = None
    command: list[str] = Field(default_factory=list)
    values: dict[str, Any] = Field(default_factory=dict)


class PackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    id: str
    name: str
    type: ComponentType
    version: str
    python_requires: str | None = None
    python_recommended: str | None = None
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    healthcheck: Healthcheck = Field(default_factory=Healthcheck)
    config: dict[str, Any] = Field(default_factory=dict)
    install: list[Action] = Field(default_factory=list)
    remove: list[Action] = Field(default_factory=list)
    source: str = "builtin"
    permissions: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in value):
            raise ValueError("id must contain only lowercase letters, numbers, '-' and '_'")
        return value


class CheckResult(BaseModel):
    name: str
    ok: bool
    details: str = ""
    required: bool = True


class DiagnosticReport(BaseModel):
    ok: bool
    checks: list[CheckResult] = Field(default_factory=list)


class InstallReport(BaseModel):
    success: bool
    package_id: str
    version: str
    changed: bool = False
    installed_items: list[str] = Field(default_factory=list)
    registrations: list[str] = Field(default_factory=list)
    diagnostics: DiagnosticReport | None = None
    warnings: list[str] = Field(default_factory=list)
    rolled_back: bool = False
    next_steps: list[str] = Field(default_factory=list)


class RemoveReport(BaseModel):
    success: bool
    package_id: str
    changed: bool = False
    diagnostics: DiagnosticReport | None = None
    warnings: list[str] = Field(default_factory=list)


class UpdateReport(BaseModel):
    success: bool
    updated: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)


class InstalledPackage(BaseModel):
    component: str
    version: str
    install_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str
    status: str = "installed"
    health: str = "unknown"
    dependencies: list[str] = Field(default_factory=list)
    manifest_digest: str


class RollbackRecord(BaseModel):
    operation_id: str
    package_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_state: InstalledPackage | None = None
    completed_actions: list[Action] = Field(default_factory=list)
