"""JSON-backed storage for the local knowledge platform."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from aegis.serialization import to_plain

from .models import KnowledgeChunk, KnowledgeDocument, KnowledgeEntity


DEFAULT_KNOWLEDGE_ROOT = Path(r"F:\AI_WORKSPACE\knowledge")


class KnowledgeStore:
    def __init__(self, root: str | Path = DEFAULT_KNOWLEDGE_ROOT):
        self.root = Path(root)
        self.documents_path = self.root / "documents.json"
        self.chunks_path = self.root / "chunks.json"
        self.entities_path = self.root / "entities.json"
        self.index_path = self.root / "index.json"
        self._ensure()

    def documents(self) -> list[KnowledgeDocument]:
        return [
            KnowledgeDocument.from_dict(item)
            for item in self._load_list(self.documents_path)
            if isinstance(item, dict)
        ]

    def chunks(self) -> list[KnowledgeChunk]:
        return [
            KnowledgeChunk.from_dict(item)
            for item in self._load_list(self.chunks_path)
            if isinstance(item, dict)
        ]

    def entities(self) -> list[KnowledgeEntity]:
        return [
            KnowledgeEntity.from_dict(item)
            for item in self._load_list(self.entities_path)
            if isinstance(item, dict)
        ]

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        return next((doc for doc in self.documents() if doc.id == document_id), None)

    def chunks_for_document(self, document_id: str) -> list[KnowledgeChunk]:
        return [chunk for chunk in self.chunks() if chunk.document_id == document_id]

    def upsert_document(
        self,
        document: KnowledgeDocument,
        chunks: list[KnowledgeChunk],
        entities: list[KnowledgeEntity],
    ) -> KnowledgeDocument:
        documents = [item for item in self.documents() if item.id != document.id]
        all_chunks = [item for item in self.chunks() if item.document_id != document.id]
        all_entities = [item for item in self.entities() if item.document_id != document.id]

        documents.append(document)
        all_chunks.extend(chunks)
        all_entities.extend(entities)

        self._save_list(self.documents_path, sorted(documents, key=lambda item: item.path))
        self._save_list(
            self.chunks_path,
            sorted(all_chunks, key=lambda item: (item.document_id, item.index)),
        )
        self._save_list(
            self.entities_path,
            sorted(all_entities, key=lambda item: (item.document_id, item.type, item.name)),
        )
        self.rebuild_index()
        return document

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        terms = _tokens(query)
        if not terms:
            return []
        chunks_by_id = {chunk.id: chunk for chunk in self.chunks()}
        docs_by_id = {doc.id: doc for doc in self.documents()}
        index = self._load_index()
        scores: Counter[str] = Counter()
        for term in terms:
            for chunk_id, count in index.get("terms", {}).get(term, {}).items():
                scores[chunk_id] += int(count)
        results: list[dict[str, Any]] = []
        for chunk_id, score in scores.most_common(limit):
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            document = docs_by_id.get(chunk.document_id)
            results.append({"score": score, "chunk": chunk, "document": document})
        return results

    def stats(self) -> dict[str, Any]:
        documents = self.documents()
        chunks = self.chunks()
        entities = self.entities()
        return {
            "root": str(self.root),
            "document_count": len(documents),
            "chunk_count": len(chunks),
            "entity_count": len(entities),
            "index_path": str(self.index_path),
            "documents_path": str(self.documents_path),
        }

    def rebuild_index(self) -> dict[str, Any]:
        terms: dict[str, dict[str, int]] = defaultdict(dict)
        for chunk in self.chunks():
            counts = Counter(_tokens(chunk.text))
            for term, count in counts.items():
                terms[term][chunk.id] = count
        index = {"version": 1, "terms": {key: dict(value) for key, value in terms.items()}}
        self.index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return index

    def _ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for path in (
            self.documents_path,
            self.chunks_path,
            self.entities_path,
        ):
            if not path.exists():
                path.write_text("[]", encoding="utf-8")
        if not self.index_path.exists():
            self.index_path.write_text(
                json.dumps({"version": 1, "terms": {}}, indent=2),
                encoding="utf-8",
            )

    def _load_list(self, path: Path) -> list[Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def _load_index(self) -> dict[str, Any]:
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "terms": {}}
        return data if isinstance(data, dict) else {"version": 1, "terms": {}}

    def _save_list(self, path: Path, values: list[Any]) -> None:
        path.write_text(
            json.dumps([to_plain(asdict(value)) for value in values], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-zА-Яа-я0-9_]{2,}", text)]
