import asyncio

import pytest

from brain.orchestrator import Orchestrator, PERMISSION_ASK, permission_prompt
from brain.traces import Tracer
from fakes import (FakeServer, ScriptedPlanner, _acts, _skill_rpcs, _traces,
                   engine_orch, run)
from test_planner_loop import FakePlanner


FINDER = {"epoch": 1, "app": "Finder", "window": "Downloads", "elements": [],
          "text": 'app: Finder | window: "Downloads"'}
PROMPT = {"epoch": 2, "app": "UserNotificationCenter", "window": "Permission",
          "elements": [], "text": "app: UserNotificationCenter"}


@pytest.mark.parametrize("following", [
    {"op": "keys", "combo": "return"},
    {"op": "type", "text": "yes", "ref": 1},
    {"op": "press", "ref": 1},
])
@pytest.mark.parametrize("payload", [
    {},
    {"diff_text": "app: UserNotificationCenter"},
    {"observed": PROMPT},
    {"observed": "app: UserNotificationCenter"},
    {"diff_text": 'app: Finder | window: "App wants access to Downloads"\n+ #1 button "Allow"'},
    {"diff_text": "", "full": True},
    {"diff_text": "", "truncated": True},
])
def test_permission_post_action_stops_following_input(tmp_path, following, payload):
    state = {"obs": FINDER}

    def act(params):
        state["obs"] = PROMPT
        return {"ok": True, "epoch": 2, **payload}

    server = FakeServer(act=act, observe=lambda: state["obs"])
    orch = Orchestrator(server, tracer=Tracer(tmp_path / "traces"))
    orch._last_obs = FINDER

    async def scenario():
        assert (await orch._exec_one({"op": "press", "ref": 4}))["status"] == "ok"
        assert (await orch._exec_one(following))["status"] == "awaiting_user"
        assert len([p for m, p in server.rpcs if m == "act"]) == 1
        assert server.said[-1] == PERMISSION_ASK
    asyncio.run(scenario())


def test_brain35_prompt_raised_mid_batch_never_receives_return(tmp_path):
    state = {"obs": FINDER}

    def act(params):
        state["obs"] = PROMPT
        return {"ok": True, "epoch": 2}

    server = FakeServer(act=act, observe=lambda: state["obs"])
    orch = Orchestrator(server, tracer=Tracer(tmp_path / "traces"))
    orch.planner = FakePlanner([["press #4", "keys return"], ['done "ok"']])
    outcome = asyncio.run(orch._planner_loop("list downloads", {"decisions": []}))
    assert outcome == "awaiting_user"
    assert not any(p.get("op") == "keys" for m, p in server.rpcs if m == "act")


@pytest.mark.parametrize("payload", [{}, {"diff_text": ""}])
def test_permission_post_action_allows_clean_input(tmp_path, payload):
    server = FakeServer(act=lambda p: {"ok": True, **payload})
    orch = Orchestrator(server, tracer=Tracer(tmp_path / "traces"))
    orch._last_obs = FINDER

    async def scenario():
        assert (await orch._exec_one({"op": "press", "ref": 4}))["status"] == "ok"
        assert (await orch._exec_one({"op": "keys", "combo": "esc"}))["status"] == "ok"
        assert len([p for m, p in server.rpcs if m == "act"]) == 2
    asyncio.run(scenario())


def test_permission_post_action_missing_observation_stops_input(tmp_path):
    def observe():
        raise RuntimeError("observe unavailable")

    server = FakeServer(observe=observe)
    orch = Orchestrator(server, tracer=Tracer(tmp_path / "traces"))
    orch._last_obs = FINDER

    async def scenario():
        await orch._exec_one({"op": "press", "ref": 4})
        assert (await orch._exec_one({"op": "keys", "combo": "return"}))["status"] == "failed"
        assert len([p for m, p in server.rpcs if m == "act"]) == 1
    asyncio.run(scenario())


def test_permission_post_action_chains_incremental_diffs(tmp_path):
    diffs = iter(['+ #1 button "Allow"', '+ #2 text "App wants access to Downloads"'])
    server = FakeServer(act=lambda p: {"ok": True, "diff_text": next(diffs)})
    orch = Orchestrator(server, tracer=Tracer(tmp_path / "traces"))
    orch._last_obs = FINDER

    async def scenario():
        assert (await orch._exec_one({"op": "press", "ref": 4}))["status"] == "ok"
        assert (await orch._exec_one({"op": "press", "ref": 5}))["status"] == "ok"
        assert (await orch._exec_one({"op": "keys", "combo": "return"}))["status"] == "awaiting_user"
        assert server.methods() == ["act", "act"]
    asyncio.run(scenario())


# ---------- permission-prompt gate before acting (brain-8) ----------

UNC_OBS = {
    "epoch": 1, "app": "UserNotificationCenter", "window": "",
    "focused_ref": 3,
    "elements": [{"ref": 1, "role": "text",
                  "label": '"Devin" wants access to control "Finder".'},
                 {"ref": 2, "role": "button", "label": "Don't Allow"},
                 {"ref": 3, "role": "button", "label": "Allow"}],
    "text": ('app: UserNotificationCenter | window: "" | focused: #3\n'
             '#1 text "\\"Devin\\" wants access to control \\"Finder\\"."\n'
             '#2 button "Don\'t Allow"\n#3 button "Allow"'),
    "ax_ms": 1}

SECURITY_OBS = {
    "epoch": 1, "app": "SecurityAgent", "window": "",
    "elements": [{"ref": 1, "role": "textfield", "label": "Password"},
                 {"ref": 2, "role": "button", "label": "Cancel"},
                 {"ref": 3, "role": "button", "label": "Modify Settings"}],
    "text": ('app: SecurityAgent | window: ""\n'
             '#0 text "System Settings is trying to modify your system '
             'settings. Enter your password to allow this."\n'
             '#1 textfield "Password"\n#2 button "Cancel"\n'
             '#3 button "Modify Settings"'),
    "ax_ms": 1}

ZEN_OBS = {
    "epoch": 1, "app": "Zen", "window": "Site settings - Zen",
    "elements": [{"ref": 1, "role": "link", "label": "Allow notifications"},
                 {"ref": 2, "role": "button", "label": "Save"}],
    "text": ('app: Zen | window: "Site settings - Zen"\n'
             '#0 text "Allow notifications from this site. A script is '
             'trying to load."\n#1 link "Allow notifications"\n'
             '#2 button "Save"'),
    "ax_ms": 1}


def _planner_orch(tmp_path, obs, turns, goal="list my downloads"):
    state = {"obs": obs}
    server = FakeServer(observe=lambda: state["obs"])
    planner = ScriptedPlanner(turns)
    o = engine_orch(tmp_path, server, {goal: ("MULTI_STEP", 0.95)},
                    planner=planner)
    return o, server, planner, state


def test_permission_prompt_press_is_gated_and_continue_resumes(tmp_path):
    goal = "list my downloads"
    o, server, planner, state = _planner_orch(
        tmp_path, UNC_OBS, [["press #3"], ['done "listed"']], goal)

    out = run(o.handle_utterance(goal))

    assert out["outcome"] == "awaiting_user"
    assert server.said == [PERMISSION_ASK]
    assert _acts(server) == []
    assert planner.plans == []          # gated before planning
    assert server.uis[-1] == "listening"
    trace = _traces(o.tracer)[-1]
    assert trace["permission_prompt_gate"] == {
        "app": "UserNotificationCenter",
        "matched": "app:UserNotificationCenter"}

    # the user answers the prompt; "continue" re-observes and resumes
    state["obs"] = {"epoch": 2, "app": "Finder", "window": "Downloads",
                    "elements": [{"ref": 3, "role": "button",
                                  "label": "List"}],
                    "text": 'app: Finder | window: "Downloads"\n'
                            '#3 button "List"', "ax_ms": 1}
    run(o.handle_utterance("continue"))
    assert planner.plans and planner.plans[0]["goal"].startswith(goal)
    assert "Finder" in planner.plans[0]["obs"]
    assert _acts(server) and _acts(server)[0]["op"] == "press"


def test_press_mid_batch_on_permission_prompt_never_acts(tmp_path):
    o = engine_orch(tmp_path, FakeServer())
    o._last_obs = UNC_OBS
    res = run(o._exec_action({"op": "press", "ref": 3}))
    assert res["status"] == "awaiting_user"
    assert _acts(o.server) == []
    assert o.server.said == [PERMISSION_ASK]


def test_security_agent_password_sheet_asks(tmp_path):
    o, server, planner, _ = _planner_orch(
        tmp_path, SECURITY_OBS, [['type #1 "hunter2"', "press #3"]])
    out = run(o.handle_utterance("list my downloads"))
    assert out["outcome"] == "awaiting_user"
    assert server.said == [PERMISSION_ASK]
    assert _acts(server) == []
    assert _traces(o.tracer)[-1]["permission_prompt_gate"]["app"] == \
        "SecurityAgent"


def test_allow_notifications_text_in_a_zen_page_is_not_gated(tmp_path):
    goal = "save the site settings"
    o, server, planner, _ = _planner_orch(
        tmp_path, ZEN_OBS, [["press #2"], ['done "saved"']], goal)
    run(o.handle_utterance(goal))
    assert PERMISSION_ASK not in server.said
    assert [a["op"] for a in _acts(server)] == ["press"]
    assert permission_prompt(ZEN_OBS) is None


def test_grounded_click_while_user_notification_center_frontmost(tmp_path):
    o = engine_orch(tmp_path, FakeServer(observe=lambda: UNC_OBS))
    o._last_obs = UNC_OBS
    res = run(o._exec_action({"op": "click", "target": "Allow"}))
    assert res["status"] == "awaiting_user"
    assert o.server.said == [PERMISSION_ASK]
    methods = o.server.methods()
    assert "screenshot" not in methods and "act" not in methods

    goal = "click allow"
    o2, server, _, _ = _planner_orch(
        tmp_path / "planner", UNC_OBS, [['click "Allow"']], goal)
    run(o2.handle_utterance(goal))
    assert server.said == [PERMISSION_ASK]
    assert "screenshot" not in server.methods()
    assert _acts(server) == []


def test_routed_keys_and_type_text_are_gated(tmp_path):
    text = "type hello"
    server = FakeServer(observe=lambda: UNC_OBS)
    o = engine_orch(tmp_path, server, {text: ("type_text", 0.95)},
                    {("type_text", text): {"text": "hello"}})
    out = run(o.handle_utterance(text, {"app": "UserNotificationCenter"}))
    assert out["outcome"] == "awaiting_user"
    assert server.said == [PERMISSION_ASK]
    assert _skill_rpcs(server) == []

    o2 = engine_orch(tmp_path / "keys", FakeServer(observe=lambda: UNC_OBS))
    assert run(o2.execute_actions(
        [{"op": "keys", "combo": "return"}])) == "awaiting_user"
    assert _acts(o2.server) == []


@pytest.mark.parametrize("app", [
    "UserNotificationCenter", "CoreServicesUIAgent", "SecurityAgent",
    "universalAccessAuthWarn", "coreautha", "AccessibilityUIServer"])
def test_permission_agent_apps(app):
    hit = permission_prompt({"app": app, "text": f"app: {app}"})
    assert hit == {"app": app, "matched": f"app:{app}"}


@pytest.mark.parametrize("phrase", [
    "wants access to", "would like to access", "wants to control",
    "would like to control", "wants to use your", "is trying to",
    "enter your password to allow"])
def test_permission_text_patterns(phrase):
    obs = {"app": "Finder", "text": f'#1 text "Devin {phrase} Contacts"',
           "elements": [{"role": "button", "label": "Allow"}]}
    assert permission_prompt(obs)["matched"] == phrase
    mail = {"app": "Mail", "text": f'#1 text "Devin {phrase} Contacts"',
            "elements": [{"role": "button", "label": "Reply"}]}
    assert permission_prompt(mail) is None
    # inside a browser page the phrase alone isn't a system prompt
    page = {"app": "Safari", "text": f'#1 text "Devin {phrase} Contacts"',
            "elements": [{"role": "link", "label": "Allow"}]}
    assert permission_prompt(page) is None
