"""Pass 39 repros (cloud/brain-8@4546d09)."""
import asyncio, time

import pytest

from brain.catalog import Catalog
from brain.orchestrator import PERMISSION_ASK, Orchestrator
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer

FINDER = {"epoch": 1, "app": "Finder", "window": "Recents", "focused_ref": 4,
          "elements": [{"ref": 4, "role": "row", "label": "Downloads"}],
          "text": 'app: Finder | window: "Recents" | focused: #4\n#4 row "Downloads"',
          "ax_ms": 1}
UNC = {"epoch": 2, "app": "UserNotificationCenter", "window": "", "focused_ref": 3,
       "elements": [{"ref": 1, "role": "text",
                     "label": '"Muselet" would like to access files in your Downloads folder.'},
                    {"ref": 2, "role": "button", "label": "Don't Allow"},
                    {"ref": 3, "role": "button", "label": "Allow"}],
       "text": ('app: UserNotificationCenter | window: "" | focused: #3\n'
                '#1 text "Muselet would like to access files in your Downloads folder."\n'
                '#2 button "Don\'t Allow"\n#3 button "Allow"'),
       "ax_ms": 1}


class Planner:
    def __init__(self, turns):
        self.turns, self.plans = turns, []

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel, **kw):
        lines = self.turns[min(len(self.plans), len(self.turns) - 1)]
        self.plans.append(observation)
        for line in lines:
            time.sleep(0.005)
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": lines, "ttft_ms": 1.0, "tokens": 4, "plan_ms": 5.0,
                "decode_tok_s": 10.0}


def test_brain35_prompt_raised_mid_batch_is_answered_by_next_key(tmp_path):
    """brain-35: the gate in _exec_action reads self._last_obs, which is the
    pre-batch observation. An action that raises a TCC prompt is followed by
    `keys return` in the same batch, and Return goes to the prompt."""
    state = {"obs": FINDER}

    def act(p):
        if p.get("op") == "press":
            state["obs"] = UNC          # opening Downloads raises the TCC prompt
        return {"ok": True, "act_ms": 1, "epoch": 2}

    server = FakeServer(act=act, observe=lambda: state["obs"])
    goal = "list my downloads"
    o = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"),
                     engine=FakeEngine({goal: ("MULTI_STEP", 0.95)}, {}))
    o.planner = Planner([["press #4", "keys return"], ['done "ok"']])
    asyncio.run(o.handle_utterance(goal))
    keys = [p for m, p in server.rpcs if m == "act" and p.get("op") == "keys"]
    assert keys == [], f"Return sent while UserNotificationCenter was frontmost: {keys}"


@pytest.mark.parametrize("text,model,want", [
    ("turn it up, but not too much", 10, 10),
    ("by the way, turn the volume down", -10, -10),
])
def test_brain36_degree_word_outside_the_request(tmp_path, text, model, want):
    """brain-36: 'much' / 'way' anywhere in the utterance force +-30."""
    server = FakeServer()
    o = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"),
                     engine=FakeEngine({text: ("change_volume", 0.95)},
                                       {("change_volume", text): {"delta": model}}))
    asyncio.run(o.handle_utterance(text))
    skills = [(p["name"], p["args"]) for m, p in server.rpcs if m == "skill"]
    assert skills == [("change_volume", {"delta": want})]
