from __future__ import annotations

from types import SimpleNamespace

from aegis.knowledge import KnowledgeRuntime, KnowledgeStore


class EventPlatformStub:
    def __init__(self):
        self.events = []

    def publish(self, type, source, payload=None, **context):
        self.events.append(
            {
                "type": type,
                "source": source,
                "payload": payload or {},
                "context": context,
            }
        )


def test_knowledge_runtime_indexes_documents_searches_and_extracts_entities(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        "# Project Runtime\n\nUse `CodeIdentifier` with MissionPlanner and snake_case.",
        encoding="utf-8",
    )
    (docs / "notes.txt").write_text("Reflection Engine Recovery notes", encoding="utf-8")
    (docs / "config.json").write_text('{"name": "Skill Runtime", "enabled": true}', encoding="utf-8")
    event_platform = EventPlatformStub()
    runtime = KnowledgeRuntime(
        SimpleNamespace(event_platform=event_platform),
        store=KnowledgeStore(tmp_path / "knowledge"),
    )

    indexed = runtime.scan(docs)
    results = runtime.search("runtime mission")
    entities = runtime.entities()
    context = runtime.build_context("Runtime Mission")

    assert len(indexed) == 3
    assert results
    assert context.chunks
    assert {entity.name for entity in entities}.issuperset(
        {"Project Runtime", "CodeIdentifier", "MissionPlanner", "snake_case", "Runtime"}
    )
    assert "knowledge.document.added" in {event["type"] for event in event_platform.events}
    assert "knowledge.scan.completed" in {event["type"] for event in event_platform.events}
    assert "knowledge.entity.created" in {event["type"] for event in event_platform.events}
    assert (tmp_path / "knowledge" / "documents.json").exists()
    assert (tmp_path / "knowledge" / "chunks.json").exists()
    assert (tmp_path / "knowledge" / "entities.json").exists()
    assert (tmp_path / "knowledge" / "index.json").exists()


def test_knowledge_runtime_uses_active_project_knowledge_root(tmp_path):
    project_workspace = tmp_path / "project_alpha"
    core = SimpleNamespace(
        project_runtime=SimpleNamespace(
            get_active=lambda: SimpleNamespace(workspace_path=str(project_workspace))
        )
    )

    runtime = KnowledgeRuntime(core)

    assert runtime.store.root == project_workspace / "knowledge"
