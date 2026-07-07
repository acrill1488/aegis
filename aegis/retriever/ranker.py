"""Document ranking stage for Retriever."""

from __future__ import annotations

from aegis.retriever.models import RetrievedDocument


SOURCE_PRIORITY = {
    "browser": 0,
    "web_search": 1,
    "memory": 2,
    "workspace": 3,
}


class Ranker:
    def rank(
        self,
        documents: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        return sorted(
            documents,
            key=lambda document: (
                -float(document.score),
                SOURCE_PRIORITY.get(document.source, len(SOURCE_PRIORITY)),
            ),
        )
