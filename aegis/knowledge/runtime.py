"""Runtime facade for the local Knowledge & Context Platform."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

from .entities import extract_entities
from .models import (
    KnowledgeChunk,
    KnowledgeContext,
    KnowledgeDocument,
)
from .sources.filesystem import FilesystemSource
from .store import DEFAULT_KNOWLEDGE_ROOT, KnowledgeStore


class KnowledgeRuntime:
    """Local document index, entity catalog, and fast keyword search."""

    def __init__(
        self,
        core: Any | None = None,
        *,
        store: KnowledgeStore | None = None,
        root: str | Path | None = None,
    ):
        self.core = core
        self.store = store or KnowledgeStore(root or self._resolve_root())
        self._legacy_engine = None

    def add(self, path: str | Path) -> KnowledgeDocument:
        source = FilesystemSource(path)
        target = Path(path)
        if target.is_dir():
            documents = self.scan(target)
            if not documents:
                raise FileNotFoundError(f"No supported knowledge files found: {target}")
            return documents[-1]
        if not target.exists():
            raise FileNotFoundError(str(target))
        return self._index_file(source, target)

    def scan(self, path: str | Path) -> list[KnowledgeDocument]:
        source = FilesystemSource(path)
        documents = [self._index_file(source, item) for item in source.scan()]
        self._publish(
            "knowledge.scan.completed",
            {"path": str(path), "document_count": len(documents)},
        )
        return documents

    def documents(self) -> list[KnowledgeDocument]:
        return self.store.documents()

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        return self.store.search(query, limit=limit)

    def entities(self):
        return self.store.entities()

    def show(self, document_id: str) -> dict[str, Any]:
        document = self.store.get_document(document_id)
        if document is None:
            raise KeyError(f"Knowledge document not found: {document_id}")
        return {
            "document": document,
            "chunks": self.store.chunks_for_document(document_id),
            "entities": [
                entity
                for entity in self.store.entities()
                if entity.document_id == document_id
            ],
        }

    def stats(self) -> dict[str, Any]:
        return self.store.stats()

    def build_context(self, goal: str) -> KnowledgeContext:
        results = self.search(goal, limit=5)
        chunks = [result["chunk"] for result in results if result.get("chunk") is not None]
        documents_by_id = {
            result["document"].id: result["document"]
            for result in results
            if result.get("document") is not None
        }
        return KnowledgeContext(
            goal=goal,
            chunks=chunks,
            documents=list(documents_by_id.values()),
            metadata={"source": "knowledge_runtime_v1", "result_count": len(results)},
        )

    def gather(self, query: str):
        return self._engine().gather(query)

    def summarize(self, bundle, profile: str = "general") -> str:
        return self._engine().summarize(bundle, profile=profile)

    def build_prompt_context(self, query: str) -> str:
        return self._engine().build_context(query)

    def __getattr__(self, name: str):
        legacy = self._engine()
        if hasattr(legacy, name):
            return getattr(legacy, name)
        raise AttributeError(name)

    def _index_file(
        self,
        source: FilesystemSource,
        path: Path,
    ) -> KnowledgeDocument:
        raw = source.load(path)
        parsed = source.parse(path)
        checksum = sha1(raw.encode("utf-8")).hexdigest()
        document_id = f"doc_{sha1(str(path.resolve()).encode('utf-8')).hexdigest()[:16]}"
        stat = path.stat()
        document = KnowledgeDocument(
            id=document_id,
            path=str(path),
            title=str(parsed.get("title") or path.stem),
            type=str(parsed.get("type") or path.suffix.lower().lstrip(".")),
            checksum=checksum,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            metadata={
                **source.metadata(path),
                **dict(parsed.get("metadata") or {}),
            },
        )
        chunks = [
            KnowledgeChunk(
                id=f"{document_id}:chunk:{index}",
                document_id=document_id,
                text=str(item.get("text") or ""),
                index=index,
                metadata=dict(item.get("metadata") or {}),
            )
            for index, item in enumerate(parsed.get("chunks") or [])
            if str(item.get("text") or "").strip()
        ]
        entities = extract_entities(
            document_id=document_id,
            text=str(parsed.get("text") or raw),
            parsed_metadata=dict(parsed.get("metadata") or {}),
        )
        self.store.upsert_document(document, chunks, entities)
        self._publish(
            "knowledge.document.added",
            {"document_id": document.id, "path": document.path, "chunk_count": len(chunks)},
        )
        for entity in entities:
            self._publish(
                "knowledge.entity.created",
                {
                    "entity_id": entity.id,
                    "document_id": entity.document_id,
                    "name": entity.name,
                    "type": entity.type,
                },
            )
        return document

    def _resolve_root(self) -> Path:
        active_project = self._active_project()
        workspace_path = getattr(active_project, "workspace_path", "") if active_project else ""
        if workspace_path:
            return Path(workspace_path) / "knowledge"
        return DEFAULT_KNOWLEDGE_ROOT

    def _active_project(self):
        project_runtime = getattr(self.core, "project_runtime", None)
        get_active = getattr(project_runtime, "get_active", None)
        if not callable(get_active):
            return None
        try:
            return get_active()
        except Exception:
            return None

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event_platform = getattr(self.core, "event_platform", None)
        publish = getattr(event_platform, "publish", None)
        if not callable(publish):
            return
        try:
            publish(event_type, "knowledge_runtime", payload)
        except Exception:
            return

    def _engine(self):
        if self._legacy_engine is None:
            from .engine import KnowledgeEngine

            self._legacy_engine = KnowledgeEngine(self.core)
        return self._legacy_engine


def build_context(goal: str, runtime: KnowledgeRuntime | None = None) -> KnowledgeContext:
    knowledge_runtime = runtime or KnowledgeRuntime()
    return knowledge_runtime.build_context(goal)
