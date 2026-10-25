"""web_loaded (AXLoaded) is the authoritative page-load signal."""
import asyncio

import pytest
from fakes import FakeServer
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator


def orch(server, tmp_path):
    return Orchestrator(server, Catalog.load(),
                        CaptureTracerFor(tmp_path / "t"))


class CaptureTracerFor:
    def __init__(self, path):
        from brain.traces import Tracer
        self._t = Tracer(path)

    @property
    def current(self):
        return self._t.current

    def __getattr__(self, name):
        return getattr(self._t, name)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_web_loaded_overrides_loading_title(tmp_path):
    o = orch(FakeServer(), tmp_path)
    loading_title = {"app": "Zen", "window": "New Tab",
                     "web_loaded": True}
    assert o._page_loading(loading_title) is False
    assert o._page_loading({"app": "Zen", "window": "New Tab",
                            "web_loaded": False}) is True
    assert o._page_loading({"app": "Zen", "window": "New Tab",
                            "web_loaded": True, "web_busy": True}) is True


def test_no_web_loaded_falls_back_to_heuristics(tmp_path):
    o = orch(FakeServer(), tmp_path)
    assert o._page_loading({"app": "Zen", "window": "",
                            "text": ""}) is True
    assert o._page_loading({"app": "Zen", "window": "Inbox",
                            "text": ""}) is False


@pytest.mark.anyio
async def test_await_page_load_noop_when_loaded(tmp_path):
    server = FakeServer()
    o = orch(server, tmp_path)
    o._obs_seen = (0.0, {"app": "Zen", "web_loaded": True})
    await o._await_page_load()
    assert all(m != "observe" for m, _ in server.rpcs)


@pytest.mark.anyio
async def test_wait_returns_early_on_loaded_page(tmp_path):
    server = FakeServer(observe=lambda: {
        "epoch": 2, "app": "Zen", "web_loaded": True,
        "elements": [], "text": 'app: Zen', "ax_ms": 1})
    o = orch(server, tmp_path)
    o._obs_seen = (0.0, {"app": "Zen", "web_loaded": True})
    await o._wait_ms(5000)   # page already loaded -> returns at ~150 ms
    # did not sleep the full 5 s
