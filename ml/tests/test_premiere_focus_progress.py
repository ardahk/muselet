import asyncio

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer
from test_planner_loop import FakePlanner

PREMIERE = "Adobe Premiere"
FOCUS_ERROR = ("Timeline focus shortcut already sent for this window; "
               "focus is not verified by the unchanged AX tree")


def _premiere(window="Timeline", state=None):
    def obs():
        w = state["window"] if state is not None else window
        return {"epoch": 1, "app": PREMIERE, "window": w,
                "focused_ref": 1,
                "elements": [{"ref": 1, "role": "button",
                              "label": "Play", "frame": [0, 0, 9, 9]}],
                "text": f'app: {PREMIERE} | window: "{w}" | focused: #1\n'
                        '#1 button "Play"',
                "ax_ms": 1}
    return obs


def _focus_rpcs(server):
    return [p for m, p in server.rpcs
            if m == "act" and p.get("op") == "keys"
            and p.get("combo") == "shift+3"]


def _orch(server, turns, tmp_path):
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"))
    orch.planner = FakePlanner(turns)
    return orch


def test_repeat_focus_blocked_across_turns(tmp_path):
    async def go():
        server = FakeServer(
            act=lambda p: {"ok": True, "epoch": 2, "diff_text": ""},
            observe=_premiere())
        orch = _orch(server, [["keys shift+3"], ["keys shift+3"],
                              ['ask "which clip?"']], tmp_path)
        tr = {"utterance": "x", "decisions": []}
        return await orch._planner_loop("double the speed", tr), server, orch, tr
    outcome, server, orch, tr = asyncio.run(go())
    assert outcome == "awaiting_user"
    assert len(_focus_rpcs(server)) == 1
    assert {"repeated_panel_focus": {"combo": "shift+3",
                                   "app": PREMIERE}} in tr["decisions"]
    last = "\n".join(orch.planner.user_msgs[-1]["last_batch"] or [])
    assert FOCUS_ERROR.split(";")[0] in last


def test_repeat_focus_blocked_within_batch(tmp_path):
    async def go():
        server = FakeServer(
            act=lambda p: {"ok": True, "epoch": 2, "diff_text": ""},
            observe=_premiere())
        orch = _orch(server, [["keys shift+3", "keys shift+3"],
                              ['ask "which clip?"']], tmp_path)
        tr = {"utterance": "x", "decisions": []}
        return await orch._planner_loop("double the speed", tr), server, tr
    outcome, server, tr = asyncio.run(go())
    assert outcome == "awaiting_user"
    assert len(_focus_rpcs(server)) == 1
    assert any("repeated_panel_focus" in d for d in tr["decisions"])


def test_intervening_action_allows_refocus(tmp_path):
    async def go():
        server = FakeServer(
            act=lambda p: {"ok": True, "epoch": 2, "diff_text": ""},
            observe=_premiere())
        orch = _orch(server, [["keys shift+3", "keys d"],
                              ["keys shift+3"],
                              ['ask "which clip?"']], tmp_path)
        tr = {"utterance": "x", "decisions": []}
        await orch._planner_loop("double the speed", tr)
        return server
    server = asyncio.run(go())
    assert len(_focus_rpcs(server)) == 2


def test_finder_repeat_focus_not_blocked(tmp_path):
    def obs():
        return {"epoch": 1, "app": "Finder", "window": "Recents",
                "focused_ref": 1,
                "elements": [{"ref": 1, "role": "button",
                              "label": "Back", "frame": [0, 0, 9, 9]}],
                "text": 'app: Finder | window: "Recents" | focused: #1\n'
                        '#1 button "Back"', "ax_ms": 1}
    async def go():
        server = FakeServer(
            act=lambda p: {"ok": True, "epoch": 2, "diff_text": ""},
            observe=obs)
        orch = _orch(server, [["keys shift+3"], ["keys shift+3"],
                              ['ask "which clip?"']], tmp_path)
        await orch._planner_loop("double the speed", {"decisions": []})
        return server
    server = asyncio.run(go())
    assert len(_focus_rpcs(server)) == 2


def test_window_change_allows_refocus(tmp_path):
    state = {"window": "Timeline"}

    def act(p):
        if p.get("op") == "keys":
            state["window"] = "Clip speed / duration"
        return {"ok": True, "epoch": 2}

    async def go():
        server = FakeServer(act=act, observe=_premiere(state=state))
        orch = _orch(server, [["keys shift+3"], ["keys shift+3"],
                              ['ask "which clip?"']], tmp_path)
        await orch._planner_loop("double the speed", {"decisions": []})
        return server
    server = asyncio.run(go())
    assert len(_focus_rpcs(server)) == 2


def test_failed_focus_does_not_block_retry(tmp_path):
    calls = iter([{"ok": False, "error": "rpc down"},
                  {"ok": True, "epoch": 2, "diff_text": ""}])

    def act(p):
        return next(calls, {"ok": True, "epoch": 2, "diff_text": ""})

    async def go():
        server = FakeServer(act=act, observe=_premiere())
        orch = _orch(server, [["keys shift+3"], ["keys shift+3"],
                              ['ask "which clip?"']], tmp_path)
        await orch._planner_loop("double the speed", {"decisions": []})
        return server
    server = asyncio.run(go())
    assert len(_focus_rpcs(server)) == 2


def test_new_task_resets_focus_guard(tmp_path):
    async def go():
        server = FakeServer(
            act=lambda p: {"ok": True, "epoch": 2, "diff_text": ""},
            observe=_premiere())
        orch = _orch(server, [["keys shift+3"], ['ask "which clip?"']],
                     tmp_path)
        tr = {"utterance": "x", "decisions": []}
        await orch._planner_loop("double the speed", tr)
        orch.planner = FakePlanner([["keys shift+3"], ['ask "which clip?"']])
        await orch._planner_loop("triple the speed", tr)
        return server
    server = asyncio.run(go())
    assert len(_focus_rpcs(server)) == 2


def _premiere_dialog_obs(state):
    def obs():
        if state["dialog"]:
            return {"epoch": 2, "app": PREMIERE,
                    "window": "Clip speed / duration", "focused_ref": 2,
                    "elements": [{"ref": 2, "role": "button",
                                  "label": "clipSpeed", "value": "200",
                                  "frame": [0, 0, 9, 9]}],
                    "text": f'app: {PREMIERE} | window: "Clip speed / duration"'
                            ' | focused: #2\n#2 button "clipSpeed" value="200"',
                    "ax_ms": 1}
        return {"epoch": 1, "app": PREMIERE, "window": "Project",
                "focused_ref": 1,
                "elements": [{"ref": 1, "role": "button",
                              "label": "Play", "frame": [0, 0, 9, 9]}],
                "text": f'app: {PREMIERE} | window: "Project" | focused: #1\n'
                        '#1 button "Play"', "ax_ms": 1}
    return obs


def test_ui_only_planner_observes_fresh(tmp_path):
    state = {"dialog": False}

    def act(p):
        state["dialog"] = True
        return {"ok": True, "epoch": 2, "diff_text": ""}

    async def go():
        server = FakeServer(act=act, observe=_premiere_dialog_obs(state))
        orch = _orch(server, [["keys cmd+r"], ['done "ok"']], tmp_path)
        orch.planner.ui_only = True
        tr = {"utterance": "x", "decisions": []}
        await orch._planner_loop("double the speed", tr)
        return server, orch, tr
    server, orch, tr = asyncio.run(go())
    obs = orch.planner.user_msgs[1]["obs"]
    assert "Clip speed / duration" in obs
    assert '#2 button "clipSpeed" value="200"' in obs
    assert not any("obs_from_diff" in d for d in tr["decisions"])


def test_non_ui_only_keeps_diff_chaining(tmp_path):
    state = {"dialog": False}

    def act(p):
        state["dialog"] = True
        return {"ok": True, "epoch": 2, "diff_text": ""}

    async def go():
        server = FakeServer(act=act, observe=_premiere_dialog_obs(state))
        orch = _orch(server, [["keys cmd+r"], ['done "ok"']], tmp_path)
        tr = {"utterance": "x", "decisions": []}
        await orch._planner_loop("double the speed", tr)
        return server, orch, tr
    server, orch, tr = asyncio.run(go())
    assert {"obs_from_diff": 1, "n_diffs": 1} in tr["decisions"]
    assert "Clip speed / duration" not in orch.planner.user_msgs[1]["obs"]
