"""brain-73 widened (main 36422a7): any agentic app task (self._agentic set)
now turns a failed planner expect into status ok even with no finish
criterion, so the rest of the batch keeps running."""
import asyncio
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer
from test_brain_pass85 import _SPOTIFY, _Planner


def test_agentic_failed_expect_stops_rest_of_batch(tmp_path):
    planner = _Planner()
    typed_in_first = []

    def act(p):
        if p.get("op") == "type" and planner.calls == 1:
            typed_in_first.append(p.get("text"))
        return {"ok": True, "act_ms": 1, "epoch": 2}

    server = FakeServer(act=act, observe=lambda: dict(_SPOTIFY), handlers={
        "verify": lambda p: {"ok": False, "observed": 'window "Spotify"'}})
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"))
    orch.planner = planner
    orch.verify_done = False
    orch._agentic = {"skill": "spotify_playlist", "args": {}}
    trace = {"decisions": []}
    asyncio.run(asyncio.wait_for(orch._planner_loop(
        "rename my lofi playlist to study beats in spotify", trace), 30))
    assert typed_in_first == [], (typed_in_first, orch._progress)
