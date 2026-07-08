"""HTTP daemon support for AEGIS."""

from .client import DaemonClient

__all__ = ["DaemonClient", "create_app"]


def __getattr__(name: str):
    if name == "create_app":
        from .server import create_app

        return create_app
    raise AttributeError(name)
