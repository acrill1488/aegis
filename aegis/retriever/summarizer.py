"""Document summarization stage for Retriever."""

from __future__ import annotations

from aegis.retriever.models import RetrievedDocument


class Summarizer:
    def summarize(
        self,
        documents: list[RetrievedDocument],
        limit: int = 5,
    ) -> str:
        parts: list[str] = []
        for document in documents[:limit]:
            content = self._preview(document.content)
            if not content:
                continue
            parts.append(f"[{document.source}/{document.title}]\n{content}")
        return "\n\n".join(parts)

    def _preview(self, content: str, limit: int = 500) -> str:
        preview = " ".join(str(content or "").split())
        if len(preview) > limit:
            return preview[: limit - 3].rstrip() + "..."
        return preview
