"""Document collection stage for Retriever."""

from __future__ import annotations

from aegis.retriever.models import RetrievedDocument


class Collector:
    def collect(
        self,
        documents: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        return documents
