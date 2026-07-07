"""Retriever pipeline orchestration."""

from __future__ import annotations

from typing import Any

from aegis.retriever.cleaner import Cleaner
from aegis.retriever.collector import Collector
from aegis.retriever.models import RetrievedDocument, RetrieverResult
from aegis.retriever.providers import BaseProvider, DEFAULT_PROVIDERS
from aegis.retriever.ranker import Ranker
from aegis.retriever.summarizer import Summarizer


class RetrieverPipeline:
    """Orchestrate retrieval stages without provider-specific logic."""

    def __init__(
        self,
        providers: list[BaseProvider] | None = None,
        core: Any | None = None,
        collector: Collector | None = None,
        cleaner: Cleaner | None = None,
        ranker: Ranker | None = None,
        summarizer: Summarizer | None = None,
    ):
        self.core = core
        self.providers = providers or [
            provider(core=core) for provider in DEFAULT_PROVIDERS
        ]
        self.collector = collector or Collector()
        self.cleaner = cleaner or Cleaner()
        self.ranker = ranker or Ranker()
        self.summarizer = summarizer or Summarizer()

    def retrieve(self, query: str) -> RetrieverResult:
        documents: list[RetrievedDocument] = []
        gaps: list[str] = []

        for provider in self.providers:
            try:
                documents.extend(provider.search(query))
            except Exception as exc:
                gaps.append(f"{provider.name()}: {exc}")

        collected = self.collector.collect(documents)
        cleaned = self.cleaner.clean(collected)
        ranked = self.ranker.rank(cleaned)
        summary = self.summarizer.summarize(ranked)

        return RetrieverResult(
            query=query,
            documents=ranked,
            summary=summary,
            gaps=gaps,
        )
