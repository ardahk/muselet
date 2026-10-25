"""brain-72 (main 71badc3): the agentic create_reminder guard treats any
reminder mentioning buy/shop/target/.com as a shopping goal and reroutes it
to the screen planner.
brain-73 (main a524768): any task with a finish criterion turns a failed
planner expect into status ok, so the rest of the batch keeps running on an
unexpected screen (previously the batch stopped at the failed expect)."""
import asyncio
import pytest
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer


@pytest.mark.parametrize("text", [
    "remind me to buy milk tomorrow at 9",
    "remind me to shop for a birthday gift on friday",
    "remind me to return the package to Target",
])
def test_plain_reminder_is_not_rerouted_as_shopping(tmp_path, text):
    orch = Orchestrator(FakeServer(), Catalog.load(),
                        Tracer(tmp_path / "traces"))
    called = []

    async def fake_loop(t, trace):
        called.append(t)
        return "done"

    orch._planner_loop = fake_loop
    trace = {"decisions": []}
    try:
        asyncio.run(orch._agentic_route(
            "create_reminder", {"title": text}, text, trace))
    except Exception:
        pass
    assert not called, trace["decisions"]


_SPOTIFY = {
    "epoch": 1, "app": "Spotify", "window": "Spotify", "focused_ref": 3,
    "elements": [{"ref": 2, "role": "button", "label": "Play"},
                 {"ref": 3, "role": "textfield", "label": "What do you want to play?"}],
    "text": 'app: Spotify | window: "Spotify" | focused: #3\n'
            '#2 button "Play"\n#3 textfield "What do you want to play?"',
    "ax_ms": 1,
}


class _Planner:
    def __init__(self):
        self.calls = 0

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, **kw):
        self.calls += 1
        lines = (['press #2', 'expect title~"Jazz Classics"',
                  'type #3 "lofi"'] if self.calls == 1 else ['done "ok"'])
        for ln in lines:
            loop.call_soon_threadsafe(lines_out.put_nowait, ln)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": lines, "ttft_ms": 1.0, "tokens": 4,
                "plan_ms": 5.0, "decode_tok_s": 10.0}


def test_failed_expect_stops_rest_of_batch(tmp_path):
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
    asyncio.run(asyncio.wait_for(orch._planner_loop(
        "play jazz classics on spotify", {"decisions": []}), 30))
    assert typed_in_first == [], typed_in_first
