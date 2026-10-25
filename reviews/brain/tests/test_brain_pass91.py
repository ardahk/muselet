"""wip/local de6319c/e2cb384: a planner `wait <ms>` on a browser page that
already reports web_loaded=True returns after ~150 ms, so waits meant for
in-page updates (autocomplete, SPA results, playback start) are cut short."""
import asyncio
import time
import pytest
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer

_PAGE = {"epoch": 1, "app": "Google Chrome", "window": "YouTube - Google Chrome",
         "web_loaded": True, "web_busy": False, "elements": [],
         "text": 'app: Google Chrome | window: "YouTube"', "ax_ms": 1}


def test_wait_on_loaded_page_honours_requested_ms(tmp_path):
    orch = Orchestrator(FakeServer(observe=lambda: dict(_PAGE)),
                        Catalog.load(), Tracer(tmp_path / "t"))
    if not hasattr(orch, "_wait_ms"):
        pytest.skip("no _wait_ms on this branch")
    orch._obs_seen = (time.perf_counter(), dict(_PAGE))
    t0 = time.perf_counter()
    asyncio.run(orch._wait_ms(1500))
    took = time.perf_counter() - t0
    assert took >= 1.0, f"wait 1500 returned after {took*1000:.0f} ms"
