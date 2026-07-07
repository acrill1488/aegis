"""Document cleaning stage for Retriever."""

from __future__ import annotations

from dataclasses import replace

from aegis.retriever.models import RetrievedDocument


BLOCKED_LINE_MARKERS = (
    "robot policy",
    "captcha",
    "access denied",
    "cloudflare",
    "failed to fetch",
    "no readable text",
)


class Cleaner:
    def clean(
        self,
        documents: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        cleaned: list[RetrievedDocument] = []

        for document in documents:
            content = self._clean_content(document.content)
            if not content:
                continue
            cleaned.append(replace(document, content=content))

        return cleaned

    def _clean_content(self, content: str) -> str:
        lines: list[str] = []
        for line in str(content or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            normalized = stripped.lower()
            if any(marker in normalized for marker in BLOCKED_LINE_MARKERS):
                continue
            lines.append(stripped)

        return "\n".join(lines).strip()
