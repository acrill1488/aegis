"""Manifest-driven AEGIS installer and package manager."""

from .manager import PackageManager
from .models import (
    DiagnosticReport,
    InstallReport,
    PackageManifest,
    PackageRef,
    RemoveReport,
    UpdateReport,
)

__all__ = [
    "DiagnosticReport",
    "InstallReport",
    "PackageManager",
    "PackageManifest",
    "PackageRef",
    "RemoveReport",
    "UpdateReport",
]
