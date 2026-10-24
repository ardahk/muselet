"""Live Mac E2E failures (cloud/brain-3): planner prose/tag lines, loop
guard, ARGS artifacts, app fill, absolute volume, compound fast path."""

import asyncio
import json

import pytest

from brain import dsl
from brain.catalog import Catalog
from brain.decision import DecisionEngine
from brain.orchestrator import Orchestrator, abs_level, app_in, split_clauses
from brain.planner import BatchCutter
from brain.traces import Tracer

from fakes import FakeEngine, FakeServer
from test_planner_loop import _diff_orch, trace_for

SKILLS = Catalog.load().skills
STUCK = "I'm stuck on that, can you help?"


def run(coro):
    return asyncio.run(coro)


def _skill_rpcs(srv):
    return [(p["name"], p["args"]) for m, p in srv.rpcs if m == "skill"]


def _traces(tracer):
    return [json.loads(ln) for f in tracer.dir.glob("*.jsonl")
            for ln in f.read_text().splitlines()]


# ---------- A. planner robustness ----------

@pytest.mark.parametrize("line,want", [
    ("The previous action failed because the window was not open.", None),
    ("</think>", None),
    ("<think>", None),
    ("```", None),
    ("```dsl", None),
    ("# note", None),
    ("", None),
    ("Done.", None),
    ('open_app app="TextEdit"', 'skill open_app app="TextEdit"'),
    ("take_screenshot", "skill take_screenshot"),
    ('skill open_app app="TextEdit"', 'skill open_app app="TextEdit"'),
    ("press #4", "press #4"),
    ('done "ok"', 'done "ok"'),
    ("frobnicate_all x=1", None),          # not a catalog skill
])
def test_action_line(line, want):
    assert dsl.action_line(line, SKILLS) == want


def test_action_line_without_catalog_keeps_skill_calls():
    assert dsl.action_line('open_app app="TextEdit"') == 'open_app app="TextEdit"'
    assert dsl.action_line("The app failed to open.") is None


def test_batch_cutter_does_not_count_prose():
    c, out = BatchCutter(), []
    for ln in ["Let me think.", "</think>", "```", "press #1", "press #2",
               "press #3", "press #4", "press #5", "press #6"]:
        if (o := c.push(ln)) is not None:
            out.append(o)
        if c.done:
            break
    assert [o for o in out if o.startswith("press")] == \
        [f"press #{i}" for i in range(1, 6)]


def test_planner_skips_prose_and_prefixes_skill(tmp_path):
    turns = [["The previous action failed because TextEdit was closed.",
              "</think>", "```", 'open_app app="TextEdit"', "```"],
             ['done "Opened TextEdit"']]
    o = _diff_orch(tmp_path, turns, lambda p: {"ok": True})
    tr = trace_for(o)
    assert run(o._planner_loop("open textedit", tr)) == "ok"
    assert _skill_rpcs(o.server) == [("open_app", {"app": "TextEdit"})]
    assert "ignored 4 non-action lines" in o.planner.user_msgs[1]["last_batch"]
    assert {"skipped_lines": turns[0][:3] + ["```"]} in tr["decisions"]


def test_loop_guard_same_action_twice(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"]],
                   lambda p: {"ok": False, "error": "no such ref"})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "awaiting_user"
    assert o.planner.calls == 2
    assert o.server.said[-1] == STUCK and o.server.uis[-1] == "confused"
    assert {"loop_guard": "same_action", "line": "press #1"} in tr["decisions"]
    assert o._pending_task["goal"] == "go"


def test_loop_guard_same_action_normalized(tmp_path):
    o = _diff_orch(tmp_path, [['type #1 "hi"'], ['type  #1   "hi"']],
                   lambda p: {"ok": False, "error": "x"})
    assert run(o._planner_loop("go", trace_for(o))) == "awaiting_user"
    assert o.planner.calls == 2


def test_loop_guard_three_failed_turns(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ["press #2"], ["press #3"],
                              ["press #4"]],
                   lambda p: {"ok": False, "error": "x"})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "awaiting_user"
    assert o.planner.calls == 3
    assert any(d.get("loop_guard") == "3_failed_turns" for d in tr["decisions"])


def test_loop_guard_prose_only_turns(tmp_path):
    o = _diff_orch(tmp_path, [["I will now open the app."]],
                   lambda p: {"ok": True})
    assert run(o._planner_loop("go", trace_for(o))) == "awaiting_user"
    assert o.planner.calls == 3 and o.server.said[-1] == STUCK


def test_loop_guard_parse_errors_same_line(tmp_path):
    o = _diff_orch(tmp_path, [["press 4"]], lambda p: {"ok": True})
    assert run(o._planner_loop("go", trace_for(o))) == "awaiting_user"
    assert o.planner.calls == 2


def test_loop_guard_resets_after_success(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ["press #2"], ["press #1"],
                              ['done "ok"']],
                   lambda p: {"ok": p.get("ref") != 1, "error": "x"})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "ok"
    assert not any("loop_guard" in d for d in tr["decisions"])


# ---------- B. ARGS artifacts ----------

def test_args_line_strips_trailing_punct():
    p = DecisionEngine._parse_args_line
    assert p("parent=~/Desktop, name=receipts", {"parent", "name"}) == \
        {"parent": "~/Desktop", "name": "receipts"}
    assert p("level=30.", {"level"}) == {"level": "30"}
    assert p("app=Safari;", {"app"}) == {"app": "Safari"}
    assert p('body="buy milk."', {"body"}) == {"body": "buy milk."}


def test_dsl_skill_arg_strips_trailing_punct():
    a = dsl.parse("skill new_folder parent=~/Desktop, name=receipts")[0]
    assert a["args"] == {"parent": "~/Desktop", "name": "receipts"}
    a = dsl.parse('skill new_note body="hi." title=x;')[0]
    assert a["args"] == {"body": "hi.", "title": "x"}


@pytest.mark.parametrize("text,names,want", [
    ("open chrome please", ["Google Chrome", "Safari"], "Google Chrome"),
    ("switch to google chrome", ["Google Chrome"], "Google Chrome"),
    ("launch premiere", ["Adobe Premiere Pro 2025"], "Adobe Premiere Pro 2025"),
    ("launch premiere", [], "Adobe Premiere Pro"),
    ("open safari", [], "Safari"),
    ("bring up finder", [], "Finder"),
    ("open visual studio code", ["Visual Studio Code", "Code"],
     "Visual Studio Code"),
    ("open textedit", ["TextEdit"], "TextEdit"),
    ("open the thing", ["Safari"], None),
])
def test_app_in(text, names, want):
    assert app_in(text, names) == want


def test_missing_app_filled_from_apps_rpc_and_cached(tmp_path):
    srv = FakeServer(apps={"running": [{"name": "Google Chrome", "pid": 1}],
                           "installed": ["Safari", "TextEdit"]})
    eng = FakeEngine(routes={"open chrome": ("open_app", 0.95),
                             "open textedit": ("open_app", 0.95)})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    assert run(o.handle_utterance("open chrome"))["outcome"] == "ok"
    assert run(o.handle_utterance("open textedit"))["outcome"] == "ok"
    assert _skill_rpcs(srv) == [("open_app", {"app": "Google Chrome"}),
                                ("open_app", {"app": "TextEdit"})]
    assert srv.methods().count("apps") == 1          # 60 s cache
    assert any({"app_fill": "Google Chrome"} in t["decisions"]
               for t in _traces(o.tracer))


def test_app_fill_survives_apps_rpc_failure(tmp_path):
    def boom():
        raise RuntimeError("hands offline")
    srv = FakeServer(apps=boom)
    eng = FakeEngine(routes={"open safari": ("open_app", 0.95)})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    run(o.handle_utterance("open safari"))
    assert _skill_rpcs(srv) == [("open_app", {"app": "Safari"})]


def test_app_given_by_args_skips_apps_rpc(tmp_path):
    srv = FakeServer()
    eng = FakeEngine(routes={"open safari": ("open_app", 0.95)},
                     argmap={("open_app", "open safari"): {"app": "Safari"}})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    run(o.handle_utterance("open safari"))
    assert "apps" not in srv.methods()


@pytest.mark.parametrize("text,want", [
    ("turn the volume down to twenty", 20),
    ("turn it up to 30 percent", 30),
    ("set it at half", 50),
    ("crank it to the max", 100),
    ("bring it down to twenty five", 25),
    ("volume to 70%", 70),
    ("turn it down a bit", None),
    ("turn it up by 20", None),
    ("louder so I can listen to music", None),
    ("turn it down to 200", None),
])
def test_abs_level(text, want):
    assert abs_level(text) == want


def test_change_volume_with_absolute_target_becomes_set_volume(tmp_path):
    srv = FakeServer()
    eng = FakeEngine(
        routes={"turn the volume down to twenty": ("change_volume", 0.9)},
        argmap={("change_volume", "turn the volume down to twenty"):
                {"delta": "-20"}})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    run(o.handle_utterance("turn the volume down to twenty"))
    assert _skill_rpcs(srv) == [("set_volume", {"level": 20})]
    assert srv.said[-1] == "Volume 20"


def test_change_volume_relative_unchanged(tmp_path):
    srv = FakeServer()
    eng = FakeEngine(routes={"turn it down a bit": ("change_volume", 0.9)},
                     argmap={("change_volume", "turn it down a bit"):
                             {"delta": "-10"}})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    run(o.handle_utterance("turn it down a bit"))
    assert _skill_rpcs(srv) == [("change_volume", {"delta": -10})]


# ---------- C. compound fast path ----------

@pytest.mark.parametrize("text,parts,joins", [
    ("turn the volume down to twenty and switch to dark mode",
     ["turn the volume down to twenty", "switch to dark mode"], ["and"]),
    ("open safari and then open notes", ["open safari", "open notes"],
     ["and then"]),
    ("mute, then open notes", ["mute", "open notes"], ["then"]),
    ('type "salt and pepper" in notes', ['type "salt and pepper" in notes'], []),
    ("open safari", ["open safari"], []),
    ("and then", ["and then"], []),
])
def test_split_clauses(text, parts, joins):
    assert split_clauses(text) == (parts, joins)


def _compound_orch(tmp_path, routes, argmap=None):
    srv = FakeServer()
    eng = FakeEngine(routes=routes, argmap=argmap or {})
    return Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"),
                        engine=eng), srv, eng


def test_compound_live_case(tmp_path):
    o, srv, eng = _compound_orch(
        tmp_path,
        {"turn the volume down to twenty": ("change_volume", 0.9),
         "switch to dark mode": ("dark_mode", 0.95)},
        {("dark_mode", "switch to dark mode"): {"on": "true"}})
    text = "turn the volume down to twenty and switch to dark mode"
    assert run(o.handle_utterance(text))["outcome"] == "ok"
    assert eng.route_calls == ["turn the volume down to twenty",
                               "switch to dark mode"]
    assert _skill_rpcs(srv) == [("set_volume", {"level": 20}),
                                ("dark_mode", {"on": True})]
    assert srv.said == ["Volume 20, dark mode on"]
    assert srv.uis[-1] == "success"
    assert _traces(o.tracer)[-1]["compound"] == 2


def test_compound_then_allows_same_skill(tmp_path):
    o, srv, eng = _compound_orch(
        tmp_path, {"open safari": ("open_app", 0.9),
                   "open notes": ("open_app", 0.9)},
        {("open_app", "open safari"): {"app": "Safari"},
         ("open_app", "open notes"): {"app": "Notes"}})
    run(o.handle_utterance("open safari and then open notes"))
    assert _skill_rpcs(srv) == [("open_app", {"app": "Safari"}),
                                ("open_app", {"app": "Notes"})]
    assert srv.said == ["Opened Safari, opened Notes"]


def test_compound_not_split_search_salt_and_pepper(tmp_path):
    o, srv, eng = _compound_orch(
        tmp_path, {"search for salt": ("web_search", 0.9),
                   "search for salt and pepper": ("web_search", 0.95)},
        {("web_search", "search for salt and pepper"):
         {"query": "salt and pepper"}})
    run(o.handle_utterance("search for salt and pepper"))
    assert _skill_rpcs(srv) == [("web_search", {"query": "salt and pepper"})]
    assert eng.route_calls[-1] == "search for salt and pepper"
    assert "compound" not in _traces(o.tracer)[-1]


def test_compound_same_skill_plain_and_stays_one(tmp_path):
    text = "text mom I love you and miss you"
    o, srv, eng = _compound_orch(
        tmp_path, {"text mom i love you": ("send_message", 0.9),
                   "miss you": ("send_message", 0.8),
                   text.lower(): ("send_message", 0.95)},
        {("send_message", text.lower()):
         {"to": "Mom", "body": "I love you and miss you"}})
    result = run(o.handle_utterance(text))
    assert result["outcome"] == "awaiting_user"
    assert eng.route_calls[-1] == text
    assert not _skill_rpcs(srv)
    assert srv.methods() == ["contacts_search"]


def test_compound_low_confidence_clause_falls_back(tmp_path):
    o, srv, eng = _compound_orch(
        tmp_path, {"mute": ("mute", 0.9), "open notes": ("open_app", 0.6),
                   "mute and open notes": ("MULTI_STEP", 0.9)})
    o.planner = None
    run(o.handle_utterance("mute and open notes"))
    assert _skill_rpcs(srv) == []
    assert eng.route_calls == ["mute", "open notes", "mute and open notes"]


def test_compound_special_option_falls_back_early(tmp_path):
    o, srv, eng = _compound_orch(
        tmp_path, {"what time is it": ("ANSWER", 0.95)})
    run(o.handle_utterance("what time is it and then mute"))
    assert eng.route_calls[:2] == ["what time is it",
                                   "what time is it and then mute"]


def test_compound_stops_at_first_failure(tmp_path):
    o, srv, eng = _compound_orch(
        tmp_path, {"open safari": ("open_app", 0.9), "mute": ("mute", 0.9)},
        {("open_app", "open safari"): {"app": "Safari"},
         ("mute", "mute"): {"on": "true"}})
    calls = []
    real = srv.rpc

    async def rpc(method, params, timeout=30):
        if method == "skill":
            calls.append(params["name"])
            return {"ok": False, "error": "app not found"}
        return await real(method, params, timeout)
    srv.rpc = rpc
    assert run(o.handle_utterance("open safari then mute"))["outcome"] == \
        "failed"
    assert calls == ["open_app"] and srv.uis[-1] == "confused"
