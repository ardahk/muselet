"""ux-3: after ask_confirm times out the brain never tells the app the confirm is
over; the app keeps pendingConfirm set (bubble stuck, every utterance parsed as
yes/no, the 'Okay, cancelled' say is suppressed by AppDelegate.onSay)."""
import asyncio, sys
sys.path.insert(0, "ml/src")
from brain.orchestrator import Orchestrator


class FakeServer:
    def __init__(self):
        self.sent = []
    async def ask_confirm(self, summary, timeout=120):
        self.sent.append(("confirm", summary))
        raise RuntimeError("confirm timed out")
    async def say(self, t): self.sent.append(("say", t))
    async def ui(self, m, b=None): self.sent.append(("ui", m, b))
    async def rpc(self, *a, **k): raise AssertionError("must not execute")


class NullTracer:
    def __getattr__(self, n): return lambda *a, **k: {"decisions": []}


def test_confirm_timeout_clears_app_confirm():
    s = FakeServer()
    o = Orchestrator(s, tracer=NullTracer())
    out = asyncio.run(o._skill({"name": "send_message",
                                "args": {"to": "Mom", "body": "hi"}}))
    print(s.sent, out)
    # Expect some frame that lets the app drop pendingConfirm (e.g. confirm_cancel / ui idle).
    assert any(m[0] == "ui" and m[1] in ("idle", "confused") for m in s.sent[1:]), s.sent


def test_confirm_summary_names_object():
    s = FakeServer()
    o = Orchestrator(s, tracer=NullTracer())
    asyncio.run(o._skill({"name": "send_message", "args": {"to": "Mom", "body": "hi"}}))
    summary = next(m[1] for m in s.sent if m[0] == "confirm")
    assert "Mom" in summary, summary
