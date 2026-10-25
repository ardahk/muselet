"""brain-57/brain-58 (cloud/agentic-apps 523d2c1): with --agentic-apps on (default), a planner that keeps emitting a now-disabled app skill (the LoRA was trained on 'skill start_timer ...') never hits the loop guard: 'skill disabled' takes no strike and resets the same-failure key, so the loop runs to the turn cap. brain-58: the agentic send confirmation is built from the parsed args, not from the text the planner actually typed or the conversation that is open."""
import asyncio
import time
import pytest
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer


class _Planner:
    def __init__(self, line):
        self.line, self.calls = line, 0

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, **kw):
        self.calls += 1
        loop.call_soon_threadsafe(lines_out.put_nowait, self.line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": [self.line], "ttft_ms": 1.0, "tokens": 4,
                "plan_ms": 5.0, "decode_tok_s": 10.0}


def test_repeated_disabled_skill_stops_like_a_repeated_failure(tmp_path):
    if getattr(Catalog.load(), "kind", lambda n: None)("start_timer") != "app":
        pytest.skip("no agentic app skills on this branch")
    planner = _Planner('skill start_timer duration="10 minutes"')
    orch = Orchestrator(FakeServer(), Catalog.load(),
                        Tracer(tmp_path / "traces"))
    orch.agentic_apps = True
    orch.planner = planner
    asyncio.run(orch._planner_loop("start a 10 minute timer",
                                   {"decisions": []}))
    assert planner.calls <= 4, planner.calls


_MOM_CHAT = {
    "epoch": 1, "app": "Messages", "window": "Mom", "focused_ref": 2,
    "elements": [{"ref": 2, "role": "textfield", "label": "Message"},
                 {"ref": 3, "role": "button", "label": "Send"}],
    "text": 'app: Messages | window: "Mom" | focused: #2\n'
            '#2 textfield "Message"\n#3 button "Send"',
    "ax_ms": 1,
}


def test_send_confirmation_shows_what_was_typed(tmp_path):
    if getattr(Catalog.load(), "kind", lambda n: None)("send_message") != "app":
        pytest.skip("no agentic app skills on this branch")
    from fakes import FakeEngine
    planner = _Planner('type #2 "running late, sorry" enter')
    server = FakeServer(observe=lambda: _MOM_CHAT)
    server.confirm_yes = False
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"),
                        engine=FakeEngine())
    orch.agentic_apps = True
    orch.planner = planner
    orch.verify_done = False
    asyncio.run(orch.handle_utterance("text Caleb that I'll be there in ten"))
    assert server.confirms, "no confirmation"
    assert any("running late" in c or "Mom" in c for c in server.confirms), \
        server.confirms
