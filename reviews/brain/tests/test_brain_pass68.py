"""brain-50 (premiere-route-fix 7769c32): moving the Premiere pre-route ahead of comms.parse_message sends messages that mention export/cut/premiere to premiere_edit."""
import asyncio
import pytest

pe = pytest.importorskip("brain.tools.premiere_edit")
from brain import comms  # noqa: E402
from test_premiere_edit import make_orch  # noqa: E402


@pytest.mark.parametrize("text,app", [
    ("text mom I'll export it tonight", "Adobe Premiere Pro 2026"),
    ("text john the premiere cut is ready", "Messages"),
])
def test_messages_mentioning_premiere_words_reach_comms(tmp_path, monkeypatch, text, app):
    orch = make_orch(tmp_path)
    orch.engine = None
    orch.memory_enabled = False
    orch.route = lambda _text: {"kind": "answer"}
    calls = []

    async def brain_tool(name, args, utt):
        calls.append(name)
        return "ok"

    async def start(_orch, msg, utt):
        calls.append("comms")
        return "ok"

    monkeypatch.setattr(orch, "_brain_tool", brain_tool)
    monkeypatch.setattr(comms, "start", start)
    asyncio.run(orch.handle_utterance(text, {"app": app}))
    assert calls[:1] == ["comms"], calls
