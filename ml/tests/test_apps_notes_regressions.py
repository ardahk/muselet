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
    ("Open notes, and write a template about my day", "a template about my day"),
    ("open the notes and make a list", "a list"),
    ("open notes app and create a template", "a template"),
    ("open the notes app, then draft a plan", "a plan"),
    ("open up notes and write a poem", "a poem"),
    ("open up the notes app, and then write a poem", "a poem"),
    ("write a poem in my notes app", "a poem"),
    ("write a poem in apple notes", "a poem"),
    ("Draft a plan in Apple Notes app.", "a plan"),
])
def test_notes_preroute_native_rpc(text, topic):
    """compose_text -> the agentic planner with the original utterance,
    never a coded new_note execution."""
    engine = FakeEngine()
    server = FakeServer()
    orch = Orchestrator(server, engine=engine)
    seen = []
    async def planner_loop(t, trace, hint=None, finish_criterion=None):
        seen.append((t, hint))
        return "ok"
    orch._planner_loop = planner_loop
    assert asyncio.run(orch.handle_utterance(text))["outcome"] == "ok"
    assert len(seen) == 1 and seen[0][0] == text
    assert topic in seen[0][1]
    assert not server.skills()
    assert server.confirms == []


@pytest.mark.parametrize("text", ["", "open notes", "notes about X in TextEdit",
                                       "write notes about X in TextEdit",
                                       "open notes and write", "write in notes",
                                       "write hello in textedit", "open the notes app",
                                       "open up notes", "open notes,",
                                       "write a poem in apple notes in textedit"])
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
    async def planner_loop(t, trace, hint=None, finish_criterion=None):
        if isinstance(generated, Exception):
            raise generated
        return "failed"
    orch._planner_loop = planner_loop
    expected = "error" if isinstance(generated, Exception) else "failed"
    assert asyncio.run(orch.handle_utterance(
        "write a poem in notes"))["outcome"] == expected
    assert server.skills() == []
    assert server.confirms == []


@pytest.mark.parametrize("launch", ['open "Notes"', 'skill open_app app="Notes"'])
def test_planner_waits_for_launch_ax(monkeypatch, launch):
    from brain import orchestrator
    from test_planner_loop import FakePlanner
    monkeypatch.setattr(orchestrator, "LAUNCH_AX_POLL_S", 0)
    launched = [False]
    polls = []

    def observe():
        ready = launched[0] and len(polls) >= 2
        if launched[0]:
            polls.append(1)
        return {"epoch": 1, "app": "Notes", "window_source": "main" if ready else "none",
                "elements": [{"ref": 1, "role": "textfield"}] if ready else [],
                "text": "READY" if ready else "BLIND"}

    def action(params):
        launched[0] = True
        return {"ok": True, "diff_text": ""}

    server = FakeServer(observe=observe, act=action,
                        handlers={"skill": action})
    orch = Orchestrator(server)
    orch.planner = FakePlanner([[launch], ['ask "What next?"']])
    asyncio.run(orch._planner_loop("open Notes", {"decisions": []}))
    assert orch.planner.user_msgs[1]["obs"].startswith("READY")
    assert len(polls) == 3


@pytest.mark.parametrize("obs", [None, {"text": "blind", "window_source": "none", "elements": []},
                                      {"text": "ready", "window_source": "main", "elements": [{"ref": 1}]}])
def test_launch_poll_bounded_or_unneeded(monkeypatch, obs):
    from brain import orchestrator
    monkeypatch.setattr(orchestrator, "LAUNCH_AX_TIMEOUT_S", .001)
    monkeypatch.setattr(orchestrator, "LAUNCH_AX_POLL_S", 0)
    server = FakeServer(observe=lambda: obs)
    orch = Orchestrator(server)
    orch._launch_pending = True
    assert asyncio.run(orch._wait_launch_ax(obs)) == obs
    assert not orch._launch_pending
    if obs is None or obs.get("elements"):
        assert server.rpcs == []


def test_launch_poll_rpc_error_is_bounded(monkeypatch):
    from brain import orchestrator
    monkeypatch.setattr(orchestrator, "LAUNCH_AX_TIMEOUT_S", .001)
    monkeypatch.setattr(orchestrator, "LAUNCH_AX_POLL_S", 0)

    def observe():
        raise RuntimeError("AX unavailable")

    orch = Orchestrator(FakeServer(observe=observe))
    obs = {"window_source": "none", "elements": [], "text": "blind"}
    assert asyncio.run(orch._wait_launch_ax(obs)) == obs
