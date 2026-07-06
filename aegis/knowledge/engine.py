"""Knowledge Engine v2."""

from __future__ import annotations

from typing import Any

from .models import KnowledgeBundle, KnowledgeSource
from .providers import (
    MemoryKnowledgeProvider,
    WebSearchKnowledgeProvider,
    WebURLKnowledgeProvider,
    WorkspaceKnowledgeProvider,
)


class KnowledgeEngine:
    """Gather ranked, attributed context from AEGIS knowledge providers."""

    def __init__(self, core: Any):
        self.core = core
        self.memory_provider = MemoryKnowledgeProvider(core)
        self.web_provider = WebURLKnowledgeProvider(core)
        self.web_search_provider = WebSearchKnowledgeProvider(core)
        self.workspace_provider = WorkspaceKnowledgeProvider(core)

    def gather(self, query: str) -> KnowledgeBundle:
        sources: list[KnowledgeSource] = []

        sources.extend(self.memory_provider.gather(query))
        if self.web_provider.has_urls(query):
            sources.extend(self.web_provider.gather(query))
        else:
            sources.extend(self.web_search_provider.gather(query))
        sources.extend(self.workspace_provider.gather(query))

        invalid_sources = [
            source
            for source in sources
            if not getattr(source, "valid", True)
        ]
        filtered_sources = [
            source
            for source in sources
            if getattr(source, "valid", True)
            and float(getattr(source, "score", 1.0)) > 0.0
            and str(source.content or "").strip()
        ]
        filtered_sources.sort(key=lambda source: source.score, reverse=True)

        bundle = KnowledgeBundle(query=query, sources=filtered_sources)
        for source in invalid_sources:
            reason = source.error or source.metadata.get("error") or "invalid_source"
            bundle.gaps.append(f"{source.type}/{source.title}: {reason}")
        bundle.summary = self.summarize(bundle)
        if not filtered_sources:
            bundle.gaps.append("No knowledge sources returned usable content.")
        return bundle

    def summarize(self, bundle: KnowledgeBundle, profile: str = "general") -> str:
        if not bundle.sources:
            return ""

        lines = []
        for source in bundle.sources:
            content = " ".join(source.content.split())
            if len(content) > 240:
                content = content[:237].rstrip() + "..."
            lines.append(f"- {source.type}/{source.title}: {content}")
        return "\n".join(lines)

    def build_context(self, query: str) -> str:
        bundle = self.gather(query)
        if not bundle.sources:
            return ""

        parts = ["KNOWLEDGE CONTEXT:"]
        for source in bundle.sources:
            parts.append(f"[source {source.type}/{source.title}]")
            parts.append(source.content.strip())
            parts.append("")
        return "\n".join(parts).strip()
