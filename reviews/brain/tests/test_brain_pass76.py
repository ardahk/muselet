"""brain-59 (main de1070d): progress_evidence auto-done for 'cancel/stop'
timer goals fires whenever no live timer row is visible (Clock not even open).
brain-60 (cloud/agentic-evidence c4703c4): auto-done skips all verification;
'email' evidence with no body accepts any non-empty focused field (the To:
field) and an approved send stops before Send is pressed."""
import asyncio
import inspect
import pytest
from brain import finish
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer, FakeEngine

_FINDER = 'app: Finder | window: "Desktop"\n#1 button "Back"'


@pytest.mark.parametrize("goal", [
    "cancel the timer",
    "set a 10 minute timer to stop the oven",
])
def test_timer_auto_done_needs_clock_evidence(goal):
    fn = getattr(finish, "progress_evidence", None)
    if fn is None:
        if "progress" not in inspect.signature(finish.evidence).parameters:
            pytest.skip("no progress evidence on this branch")
        fn = lambda g, t: finish.evidence("timer", "", t, goal=g,
                                          progress=True)
    assert not fn(goal, _FINDER)


def test_email_progress_not_satisfied_by_to_field():
    if "progress" not in inspect.signature(finish.evidence).parameters:
        pytest.skip("no unified progress evidence on this branch")
    text = ('app: Mail | window: "New Message" | focused: #3\n'
            '#3 textfield "To" value="john@example.com"\n'
            '#4 textview "Body" value=""')
    assert not finish.evidence("email", "", {"text": text, "focused_ref": "3"},
                               args={"to": "john"}, progress=True)


_CHAT = {
    "epoch": 1, "app": "Messages", "window": "Caleb Kawano", "focused_ref": 2,
    "elements": [{"ref": 2, "role": "textfield", "label": "Message",
                  "value": "I'll be there in ten"},
                 {"ref": 3, "role": "button", "label": "Send"}],
    "text": 'app: Messages | window: "Caleb Kawano" | focused: #2\n'
            '#2 textfield "Message" value="I\'ll be there in ten"\n'
            '#3 button "Send"',
    "ax_ms": 1,
}


class _Lines:
    def __init__(self, batches):
        self.batches, self.calls = batches, 0

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, **kw):
        lines = self.batches[min(self.calls, len(self.batches) - 1)]
        self.calls += 1
        for line in lines:
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": lines, "ttft_ms": 1.0, "tokens": 4,
                "plan_ms": 5.0, "decode_tok_s": 10.0}


def test_approved_send_is_sent():
    if "progress" not in inspect.signature(finish.evidence).parameters:
        pytest.skip("no unified progress evidence on this branch")
    import tempfile, pathlib
    planner = _Lines([['confirm "Text Caleb: I\'ll be there in ten?"',
                       "press #3", 'done "sent"']])
    server = FakeServer(observe=lambda: _CHAT)
    server.confirm_yes = True
    orch = Orchestrator(server, Catalog.load(),
                        Tracer(pathlib.Path(tempfile.mkdtemp()) / "t"),
                        engine=FakeEngine())
    orch.agentic_apps = True
    orch.planner = planner
    asyncio.run(orch.handle_utterance("text Caleb that I'll be there in ten"))
    assert server.confirms, "no confirmation"
    pressed = [p for m, p in server.rpcs if m == "act" and
               str(p.get("ref", (p.get("action") or {}).get("ref"))) == "3"]
    assert pressed, (server.said if hasattr(server, "said") else server.rpcs)


def test_play_progress_needs_the_requested_subject():
    if "progress" not in inspect.signature(finish.evidence).parameters:
        pytest.skip("no unified progress evidence on this branch")
    text = 'app: Spotify | window: "Spotify"\n#5 button "Pause"\n' \
           '#6 text "Now playing: White Noise Rain"'
    assert not finish.evidence("play", "jazz", {"text": text},
                               goal="play some jazz on spotify", progress=True)
