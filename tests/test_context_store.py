from datetime import datetime, timedelta

from aegis.live.context_store import ContextStore


def test_context_store_persists_entries(tmp_path):
    store_path = tmp_path / "context.json"
    store = ContextStore(path=store_path)

    entry = store.set(
        "workspace.git",
        {"branch": "main"},
        source="test",
        metadata={"scope": "workspace"},
    )

    reloaded = ContextStore(path=store_path)
    loaded = reloaded.get("workspace.git")

    assert loaded == entry
    assert loaded.value == {"branch": "main"}
    assert loaded.metadata == {"scope": "workspace"}


def test_context_store_hides_and_prunes_expired_entries(tmp_path):
    store = ContextStore(path=tmp_path / "context.json")
    entry = store.set("system.cpu", {"usage": 10}, source="test", ttl_seconds=1)
    entry.updated_at = datetime.now() - timedelta(seconds=5)

    assert store.get("system.cpu") is None
    assert store.list() == []
    assert store.snapshot().entries == []
    assert store.prune_expired() == 1
    assert store.delete("system.cpu") is False
