import asyncio

import pytest

from brain.orchestrator import Orchestrator
from fakes import FakeEngine, FakeServer


@pytest.mark.parametrize("entry", ["skill", "planner", "execute"])
@pytest.mark.parametrize("spoken,expected", [
    ("text edit", "TextEdit"), ("face time", "FaceTime"),
    ("you tube music", "YouTube Music"), ("v s code", "Visual Studio Code"),
    ("vs code", "Visual Studio Code"), ("vscode", "Visual Studio Code"),
    ("chrome", "Google Chrome"), ("settings", "System Settings"),
    ("TextEdit", "TextEdit"), ("TextEdit.app", "TextEdit"),
])
def test_spoken_apps(entry, spoken, expected):
    async def scenario():
        server = FakeServer(apps={"installed": ["TextEdit", "FaceTime", "YouTube Music",
                                               "Visual Studio Code", "Google Chrome",
                                               "System Settings"], "running": []})
        orch = Orchestrator(server)
        orch._utterance = f"open {spoken}"
        if entry == "skill":
            await orch._run_skill("open_app", {"app": spoken}, orch._utterance,
                                  {"decisions": []})
            assert server.skills()[-1]["args"]["app"] == expected
        else:
            action = {"op": "open", "app": spoken}
            if entry == "planner":
                await orch._exec_one(action)
            else:
                await orch.execute_actions([action])
            assert [p for m, p in server.rpcs if m == "act"][-1]["app"] == expected
    asyncio.run(scenario())


@pytest.mark.parametrize("apps,expected", [
    ({"installed": ["Notes"], "running": []}, "awaiting_user"),
    ({"running": []}, "ok"),
    (lambda: (_ for _ in ()).throw(RuntimeError("unavailable")), "ok"),
])
def test_unknown_or_unavailable_apps(apps, expected):
    server = FakeServer(apps=apps)
    orch = Orchestrator(server)
    result = asyncio.run(orch._run_skill("open_app", {"app": "vscode"},
                                       "open vscode", {"decisions": []}))
    assert result == expected
    assert bool(server.skills()) == (expected == "ok")
    if expected == "awaiting_user":
        assert server.said == ["Which app?"]


def test_exact_compound_text_edit(tmp_path):
    engine = FakeEngine(
        routes={"open text edit": ("open_app", .99), "write hello": ("type_text", .99)},
        argmap={("open_app", "open text edit"): {"app": "text edit"},
                ("type_text", "write hello"): {"text": "hello"}})
    server = FakeServer(apps={"installed": ["TextEdit"], "running": []})
    orch = Orchestrator(server, engine=engine)
    result = asyncio.run(orch.handle_utterance("Open text edit and write hello"))
    assert result["outcome"] == "ok"
    assert server.skills()[0] == {"name": "open_app", "args": {"app": "TextEdit"}}
    assert server.skills()[1] == {"name": "type_text", "args": {"text": "hello"}}


@pytest.mark.parametrize("text,topic", [
    ("Open notes and write a template about my day so I can fill it out",
     "a template about my day so I can fill it out"),
    ("write a poem in my notes", "a poem"),
    ("make a list on the notes", "a list"),
    ("create a template into notes", "a template"),
    ("draft a plan in a notes", "a plan"),
])
def test_notes_preroute_native_rpc(text, topic):
    class Writer:
        def generate(self, system, user, **kwargs):
            assert f"Topic: {topic}" in user
            return "My day\nMood: ____\nHighlights: ____"

    engine = FakeEngine()
    server = FakeServer()
    orch = Orchestrator(server, engine=engine)
    orch.planner = Writer()
    assert asyncio.run(orch.handle_utterance(text))["outcome"] == "ok"
    assert engine.route_calls == []
    assert server.skills() == [{"name": "new_note", "args": {
        "title": "My day", "body": "My day\nMood: ____\nHighlights: ____"}}]
    assert server.confirms == []
    assert not any(m == "act" for m, _ in server.rpcs)


@pytest.mark.parametrize("text", ["", "open notes", "notes about X in TextEdit",
                                       "write notes about X in TextEdit",
                                       "open notes and write", "write in notes"])
def test_notes_preroute_does_not_overmatch(text):
    from brain.tools.compose_text import parse_request
    assert parse_request(text) is None


@pytest.mark.parametrize("generated", ["", RuntimeError("generation failed")])
def test_notes_preroute_generation_failure(generated):
    class Writer:
        def generate(self, *args, **kwargs):
            if isinstance(generated, Exception):
                raise generated
            return generated

    server = FakeServer()
    orch = Orchestrator(server, engine=FakeEngine())
    orch.planner = Writer()
    assert asyncio.run(orch.handle_utterance("write a poem in notes"))["outcome"] == "failed"
    assert server.skills() == []
    assert server.confirms == []
