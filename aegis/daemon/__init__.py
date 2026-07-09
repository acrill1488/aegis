"""HTTP daemon support for AEGIS."""

from .client import DaemonClient
from .supervisor import DaemonSupervisor

__all__ = ["DaemonClient", "DaemonSupervisor", "create_app"]


def __getattr__(name: str):
    if name == "create_app":
        from .server import create_app

        return create_app
    raise AttributeError(name)
