"""Unified Context Builder for Prompt Compiler input."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .models import ContextBundle, ContextSource


class ContextBuilderV2:
    """Build prompt-ready context from Knowledge Engine sources."""

    def __init__(self, core: Any):
        self.core = core

    def build(self, user_prompt: str) -> ContextBundle:
        knowledge_bundle = self.core.knowledge.gather(user_prompt)
        sources = [
            self._from_knowledge_source(source)
            for source in knowledge_bundle.sources
            if self._is_valid_source(source)
        ]

        bundle = ContextBundle(
            user_prompt=user_prompt,
            sources=sources,
            metadata={
                "knowledge_summary": getattr(knowledge_bundle, "summary", ""),
                "knowledge_gaps": list(getattr(knowledge_bundle, "gaps", [])),
            },
        )
        bundle.summary = self._build_summary(
            sources,
            bundle.metadata["knowledge_gaps"],
        )
        return bundle

    def to_prompt_context(self, bundle: ContextBundle) -> str:
        parts = ["CONTEXT:"]
        for source in bundle.sources:
            parts.append(f"[source {source.type}/{source.title} {source.score:.2f}]")
            parts.append(source.content.strip())
            parts.append("")

        parts.append("SUMMARY:")
        parts.append(bundle.summary)
        return "\n".join(parts).strip()

    def _from_knowledge_source(self, source: Any) -> ContextSource:
        metadata = dict(getattr(source, "metadata", {}) or {})
        url = getattr(source, "url", None)
        if url:
            metadata.setdefault("url", url)

        return ContextSource(
            type=str(getattr(source, "type", "knowledge")),
            title=str(getattr(source, "title", "Source")),
            content=str(getattr(source, "content", "") or ""),
            score=float(getattr(source, "score", 1.0)),
            metadata=metadata,
        )

    def _is_valid_source(self, source: Any) -> bool:
        metadata = getattr(source, "metadata", {}) or {}
        return (
            getattr(source, "valid", True)
            and
            not metadata.get("invalid")
            and float(getattr(source, "score", 1.0)) > 0.0
            and bool(str(getattr(source, "content", "") or "").strip())
        )

    def _build_summary(self, sources: list[ContextSource], gaps: list[str]) -> str:
        counts = Counter(source.type for source in sources)
        summary = (
            "Context sources: "
            f"memory={counts.get('memory', 0)}, "
            f"web={counts.get('web', 0)}, "
            f"web_search={counts.get('web_search', 0)}, "
            f"workspace={counts.get('workspace', 0)}"
        )
        if gaps:
            summary += "\nGaps: " + "; ".join(gaps)
        return summary
