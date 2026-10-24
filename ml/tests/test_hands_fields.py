"""HandsKit 68fa473 fields: observe web_ax_pending, act truncated, script
timed_out / script_failed (brain side, fakes only)."""

import asyncio
import time

import pytest

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator, _script_failure
from brain.traces import Tracer

from fakes import FakeServer
from test_planner_loop import _OBS0, _diff_orch, trace_for

READ = 'script applescript """tell application "Safari" to get URL of document 1"""'


def run(coro):
    return asyncio.run(coro)


def _obs(text=_OBS0, **kw):
    return dict({"epoch": 1, "app": "Google Chrome", "window": "Docs",
                 "elements": [], "text": text, "ax_ms": 1}, **kw)


def _pending_then(seq, tmp_path, window=0.05):
    it = iter(seq)
    srv = FakeServer(observe=lambda: next(it))
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"))
    o.WEB_AX_WINDOW_S = window
    return o


# ---- (1) web_ax_pending ----

def test_web_ax_pending_waits_window_then_reobserves_once(tmp_path):
    o = _pending_then([_obs("empty", web_ax_pending=True), _obs("web tree")],
                      tmp_path)
    tr = o.tracer.begin("search docs")
    t = time.perf_counter()
    res = run(o._observe())
    assert res["text"] == "web tree"
    assert o.server.methods() == ["observe", "observe"]   # no screenshot
    assert time.perf_counter() - t >= 0.045
    assert 40 <= tr["web_ax_wait_ms"] < 1000


def test_web_ax_still_pending_plans_on_second_observe(tmp_path):
    o = _pending_then([_obs("a", web_ax_pending=True),
                       _obs("b", web_ax_pending=True)], tmp_path)
    o.tracer.begin("x")
    assert run(o._observe())["text"] == "b"
    assert o.server.methods() == ["observe", "observe"]


def test_web_ax_window_counts_from_first_pending_arrival(tmp_path):
    o = _pending_then([_obs("a", web_ax_pending=True), _obs("b")], tmp_path,
                      window=1.0)
    o._web_ax_t0 = time.perf_counter() - 1.0   # first pending came 1 s ago
    tr = o.tracer.begin("x")
    run(o._observe())
    assert tr["web_ax_wait_ms"] < 200


def test_web_ax_not_pending_no_wait(tmp_path):
    o = _pending_then([_obs("ready")], tmp_path, window=5)
    tr = o.tracer.begin("x")
    assert run(o._observe())["text"] == "ready"
    assert o.server.methods() == ["observe"] and "web_ax_wait_ms" not in tr


def test_planner_plans_on_filled_web_tree(tmp_path):
    seq = iter([_obs("app: Google Chrome | window: \"Docs\"",
                     web_ax_pending=True),
                _obs('app: Google Chrome | window: "Docs"\n#9 link "Sign in"')])
    o = _diff_orch(tmp_path, [['done "ok"']], lambda p: {"ok": True})
    o.server.observe = lambda: next(seq)
    o.WEB_AX_WINDOW_S = 0.02
    tr = o.tracer.begin("sign in")
    assert run(o._planner_loop("sign in", trace_for(o))) == "ok"
    assert '#9 link "Sign in"' in o.planner.user_msgs[0]["obs"]
    assert "screenshot" not in o.server.methods()
    assert tr["web_ax_wait_ms"] >= 15


# ---- (2) act truncated ----

def test_act_truncated_forces_fresh_observe(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ['done "ok"']],
                   lambda p: {"ok": True, "epoch": 2, "diff_text": "- #1",
                              "truncated": True})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "ok"
    assert o.server.methods() == ["observe", "act", "observe"]
    assert not any("obs_from_diff" in d for d in tr["decisions"])
    assert "#1" in o.planner.user_msgs[1]["obs"]     # not removed by the diff


def test_act_not_truncated_reuses_diff(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ['done "ok"'], ['done "ok"']],
                   lambda p: {"ok": True, "epoch": 2, "diff_text": "- #1"})
    tr = trace_for(o)
    run(o._planner_loop("go", tr))
    assert {"obs_from_diff": 1, "n_diffs": 1} in tr["decisions"]


# ---- (3) script timed_out / script_failed ----

TIMEOUT = {"ok": False, "error": "script_failed: timed out after 30 s",
           "timed_out": True, "exit_code": -1, "stdout": "", "stderr": ""}
EXIT2 = {"ok": False, "error": "script_failed: exit 2: ls: nope: No such file",
         "exit_code": 2, "stdout": "", "stderr": "ls: nope: No such file\n"}


@pytest.mark.parametrize("err,res,want", [
    (TIMEOUT["error"], TIMEOUT, ("That script timed out", "timed out")),
    (EXIT2["error"], EXIT2,
     ("Script failed", "exit 2; stderr: ls: nope: No such file")),
    ("script_failed: exit 1: boom", None, ("Script failed", "exit 1; stderr: boom")),
    ("script_failed: exit 3", {"exit_code": 3}, ("Script failed", "exit 3")),
    ("app disconnected", None, ("Script failed", "app disconnected")),
])
def test_script_failure_text(err, res, want):
    assert _script_failure(err, res) == want


def test_script_failure_stderr_head_capped():
    _, why = _script_failure("x", {"exit_code": 1, "stderr": "e" * 999})
    assert why == "exit 1; stderr: " + "e" * 200


@pytest.mark.parametrize("res,bubble,line", [
    (TIMEOUT, "That script timed out", "script -> failed: timed out"),
    (EXIT2, "Script failed",
     "script -> failed: exit 2; stderr: ls: nope: No such file"),
])
def test_planner_script_failure_bubble_and_last_batch(tmp_path, res, bubble, line):
    o = _diff_orch(tmp_path, [[READ], ['done "gave up"']], lambda p: dict(res))
    run(o._planner_loop("get url", trace_for(o)))
    assert bubble in o.server.said
    assert line in o.planner.user_msgs[1]["last_batch"]


@pytest.mark.parametrize("res,bubble", [(TIMEOUT, "That script timed out"),
                                        (EXIT2, "Script failed")])
def test_execute_actions_script_failure_bubble(tmp_path, res, bubble):
    srv = FakeServer(act=lambda p: dict(res))
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"))
    out = run(o.execute_actions([{"op": "script", "lang": "applescript",
                                  "code": 'tell application "Safari" to get '
                                          'URL of document 1'}]))
    assert out == "failed"
    assert srv.said[-1] == bubble and srv.uis[-1] == "confused"
