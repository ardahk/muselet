"""brain-68 (main ab850b3): on blind/agentic tasks a failed planner expect
is 'soft' and `continue`s before the loop guard, so the same non-idempotent
action (here: typing) repeats every turn until the 30-turn / 300 s cap."""
import asyncio
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer

_NOTES = {
    "epoch": 1, "app": "Notes", "window": "New Note", "focused_ref": 2,
    "elements": [{"ref": 2, "role": "textarea", "label": "Body"}],
    "text": 'app: Notes | window: "New Note" | focused: #2\n#2 textarea "Body"',
    "ax_ms": 1,
}


class _Planner:
    lines = ['type #2 "buy milk"', 'expect title~"Groceries"']

    def __init__(self):
        self.calls = 0

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, **kw):
        self.calls += 1
        for ln in self.lines:
            loop.call_soon_threadsafe(lines_out.put_nowait, ln)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": list(self.lines), "ttft_ms": 1.0, "tokens": 4,
                "plan_ms": 5.0, "decode_tok_s": 10.0}


def test_repeated_soft_expect_failure_stops(tmp_path):
    typed = []

    def act(p):
        if p.get("op") == "type":
            typed.append(p.get("text"))
        return {"ok": True, "act_ms": 1, "epoch": 2}

    planner = _Planner()
    server = FakeServer(act=act, observe=lambda: dict(_NOTES), handlers={
        "verify": lambda p: {"ok": False, "observed": 'window "New Note"'}})
    orch = Orchestrator(server,
                        Catalog.load(), Tracer(tmp_path / "traces"))
    orch.planner = planner
    orch.verify_done = False
    orch._force_blind = True
    asyncio.run(orch._planner_loop("add buy milk to my groceries note",
                                   {"decisions": []}))
    assert len(typed) <= 3, (len(typed), planner.calls)
