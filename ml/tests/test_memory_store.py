from brain.memory.store import IMPORTANCE, MemoryStore, render


def test_upsert_add_update_noop_and_superseded_visibility(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    added = store.upsert("person", "Mom", "Jane Kim", now=1)
    unchanged = store.upsert("person", "mom", "Jane Kim", now=2)
    updated = store.upsert("person", "mom", "Jane Lee", now=3)

    assert added["action"] == "ADD"
    assert unchanged["action"] == "NOOP"
    assert updated["action"] == "UPDATE"
    assert added["importance"] == IMPORTANCE["person"]
    assert [row["value"] for row in store.list()] == ["Jane Lee"]
    assert [row["value"] for row in store.search("mom", now=4)] == ["Jane Lee"]
    assert store.delete(updated["id"])["value"] == "Jane Lee"
    assert store.list() == []
    store.close()


def test_fts_search_limits_results_and_rendering(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.upsert("fact", "favorite tea", "green tea every morning", now=1)
    store.upsert("person", "mom", "Jane Kim", now=1)
    store.upsert("preference", "music", "jazz", now=1)

    rows = store.search("tea", k=3, now=2)
    assert len(rows) <= 3
    assert rows[0]["key"] == "favorite tea"
    assert all(len(line) <= 80 for line in render(rows))
    assert sum(len(line.split()) * 1.3 for line in render(rows)) <= 150
    assert rows[0]["used"] == 2
    store.close()


def test_like_fallback_search_and_forget_candidates(tmp_path):
    store = MemoryStore(tmp_path / "memory.db", fts=False)
    first = store.upsert("fact", "coffee", "dark roast", now=1)
    store.upsert("fact", "tea", "green", now=1)

    assert store._fts_enabled is False
    assert [row["id"] for row in store.search("coffee", now=2)] == [
        first["id"]]
    assert [row["id"] for row in store.forget("roast", now=2)] == [
        first["id"]]
    assert store.clear() == 2
    store.close()


def test_environment_override_sets_database_path(tmp_path, monkeypatch):
    path = tmp_path / "override" / "memory.db"
    monkeypatch.setenv("MUSELET_MEMORY_DB", str(path))
    store = MemoryStore()
    assert store.path == path
    store.close()
