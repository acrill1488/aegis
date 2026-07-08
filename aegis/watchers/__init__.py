"""Watcher framework primitives for passive runtime observation."""

from .base import BaseWatcher
from .registry import WatcherRegistry

__all__ = ["BaseWatcher", "WatcherRegistry"]
