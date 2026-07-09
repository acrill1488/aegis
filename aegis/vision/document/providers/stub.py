"""Dependency-light document extraction provider."""

from __future__ import annotations

import json
from pathlib import Path

from aegis.vision.document.models import DocumentExtraction


class StubDocumentProvider:
    name = "stub"

    def available(self) -> bool:
        return True

    def supported_types(self) -> list[str]:
        return [".txt", ".md", ".json"]

    def extract(self, path: str | Path) -> DocumentExtraction:
        target = Path(path)
        suffix = target.suffix.lower()
        if not target.exists():
            raise FileNotFoundError(str(target))

        if suffix in {".txt", ".md"}:
            text = target.read_text(encoding="utf-8", errors="replace")
            return DocumentExtraction(
                path=str(target),
                type=suffix.lstrip("."),
                text=text,
                provider=self.name,
                metadata={"mode": "plain_text"},
            )

        if suffix == ".json":
            raw = target.read_text(encoding="utf-8", errors="replace")
            try:
                text = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
                metadata = {"mode": "json_pretty_print"}
            except json.JSONDecodeError as exc:
                text = raw
                metadata = {"mode": "json_raw", "warning": str(exc)}
            return DocumentExtraction(
                path=str(target),
                type="json",
                text=text,
                provider=self.name,
                metadata=metadata,
            )

        return DocumentExtraction(
            path=str(target),
            type=suffix.lstrip("."),
            text="",
            supported=False,
            provider=self.name,
            metadata={
                "warning": f"Unsupported document type: {suffix or '<none>'}",
                "supported_types": self.supported_types(),
            },
        )
