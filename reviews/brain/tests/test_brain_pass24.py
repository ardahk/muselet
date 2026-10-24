"""brain pass 24 repro (main d502b78): calculator delivery sends keystrokes without verifying Calculator is frontmost."""
import asyncio
import copy

from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer


class _T(Tracer):
    def finish(self, outcome):
        self.last = copy.deepcopy(self.current)
        super().finish(outcome)


def test_brain25_calculator_keys_gated_on_calculator_frontmost(tmp_path):
    """HandsKit `act open` ignores waitFrontmost's result (Act.swift:417-424) and the fused re-observation binds
    the session to whatever app is frontmost, so the brain must check it: an `expect app "Calculator"` on the open,
    or no keys when the open's observation shows another app."""
    def act(p):
        if p["op"] == "open":     # activation ignored: the user's TextEdit document is still frontmost
            return {"ok": True, "epoch": 2, "diff_text": "app: TextEdit | window: \"Notes.rtf\""}
        if p["op"] == "script":
            return {"ok": True, "output": ""}
        return {"ok": True, "epoch": 2}

    async def run():
        server = FakeServer(act=act)
        orch = Orchestrator(server, tracer=_T(tmp_path / "t"))
        await orch.handle_utterance("what's 11 plus 4 on the calculator", {"app": "TextEdit"})
        acts = [p for m, p in server.rpcs if m == "act"]
        opened = [a for a in acts if a["op"] == "open"]
        keys = [a["combo"] for a in acts if a["op"] == "keys"]
        assert opened and (opened[0].get("expect") or not keys), \
            f"keys posted to the frontmost app without a Calculator check: {keys}"
    asyncio.run(run())
