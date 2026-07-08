"""HTTP client for the AEGIS daemon."""

from __future__ import annotations

from typing import Any

import httpx


class DaemonClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8765", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def status(self) -> dict[str, Any]:
        return self._get("/status")

    def ask(
        self,
        prompt: str,
        capability: str = "auto",
        role: str = "assistant",
    ) -> dict[str, Any]:
        return self._post(
            "/ask",
            {
                "prompt": prompt,
                "capability": capability,
                "role": role,
            },
        )

    def publish_event(
        self,
        event_type: str,
        source: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "/events/publish",
            {
                "type": event_type,
                "source": source,
                "payload": payload or {},
            },
        )

    def events_history(self) -> list[dict[str, Any]]:
        return self._get("/events/history")

    def _get(self, path: str) -> Any:
        response = httpx.get(
            f"{self.base_url}{path}",
            timeout=self.timeout,
            trust_env=False,
        )
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        response = httpx.post(
            f"{self.base_url}{path}",
            json=payload,
            timeout=self.timeout,
            trust_env=False,
        )
        response.raise_for_status()
        return response.json()
