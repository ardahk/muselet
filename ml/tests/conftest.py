import pytest


@pytest.fixture(autouse=True)
def isolate_longterm_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSELET_MEMORY_DB", str(tmp_path / "memory.db"))


@pytest.fixture(autouse=True)
def no_default_browser(monkeypatch):
    monkeypatch.setattr("brain.orchestrator.default_browser", lambda: None)
