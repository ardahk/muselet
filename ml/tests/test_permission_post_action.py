import asyncio

import pytest

from brain.orchestrator import Orchestrator, PERMISSION_ASK
from brain.traces import Tracer
from fakes import FakeServer
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
