"""Planner knobs from the offline benchmark (constraint, done-alone,
few-shot, history format), BatchCutter limits, CLI flags, Last-batch formats,
brain-16 relative volume, planner-20, the opt-in escalation planner (load,
warm, races) and plan-bank retrieval. Fakes only (no Metal / weights)."""

import asyncio
import json
import sys
import threading
import weakref
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

try:
    import mlx.core as mx
except ImportError:  # _fake_engine skips without MLX; the rest runs anywhere
    mx = None

from fakes import FakeEngine, FakeServer, InlineWorker, _skill_rpcs
from test_planner_loop import _diff_orch, trace_for

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))

import planner_offline
import planner_retrieval_report
from brain import cli, dsl
from brain import planner as P
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator, _log_act, _repr_line, abs_level, rel_delta
from brain.plan_bank import Demo, render_block
from brain.planner import (BatchCutter, OpConstraint, Planner, history,
                           runtime_repr)
from brain.traces import Tracer

SKILLS = Catalog.load().skills

VOCAB = ["<eos>", "<|im_end|>", "skill", " open_app", " app=Safari", "\n", "The",
         " plan", "done", ' "ok"', "press", " #1", "skill!", " ", "script",
         ' applescript """say hi', 'The end"""', "!", "pre"]
ID = {s: i for i, s in enumerate(VOCAB)}


class FakeTok:
    eos_token_id = 0

    def get_vocab(self):
        return dict(ID)

    def decode(self, ids):
        return VOCAB[ids[0]] if ids[0] > 1 else ""

    def encode(self, s, add_special_tokens=False):
        return [1] if s == "<|im_end|>" else [90, 91]


# greedy model: wants `script` tokens in order, else falls back to `base`
BASE = {"press": 3.0, " #1": 2.5, "\n": 2.0, "<eos>": 3.5}


def _fake_engine(wants):
    pytest.importorskip("mlx.core")
    step = [0]

    def lm_head(_):
        lg = np.zeros(len(VOCAB), dtype=np.float32)
        for s, v in BASE.items():
            lg[ID[s]] = v
        lg[ID[wants[step[0]] if step[0] < len(wants) else "<eos>"]] += 10
        step[0] += 1
        return mx.array(lg)[None, None, :]

    return SimpleNamespace(model_path="fake", model=None, tokenizer=FakeTok(),
                           body=lambda x, cache=None: mx.zeros((1, 1, 1)),
                           lm_head=lm_head, rr=None)


def _planner(wants=(), **kw):
    p = Planner("fake", Catalog.load(), engine=_fake_engine(list(wants)), **kw)
    p._render_msgs = lambda msgs: [5, 5]
    p._content_cut = lambda toks, s: 2
    p._cache, p._cut = [], 0
    return p


def _plan(p):
    loop = asyncio.new_event_loop()
    try:
        return p.plan("goal", "obs", None, asyncio.Queue(), loop,
                      threading.Event())["lines"]
    finally:
        loop.close()


# ---------- OpConstraint ----------

def test_constraint_skill_bang_impossible():
    c = OpConstraint(FakeTok(), done_alone=True)
    assert ID["skill!"] not in c.allowed("", False)
    assert ID["skill"] in c.allowed("", False)
    assert ID["!"] not in c.allowed("skill", False)
    assert ID["The"] not in c.allowed("", False)


def test_constraint_skill_open_app_allowed():
    c = OpConstraint(FakeTok(), done_alone=True)
    assert ID[" open_app"] in c.allowed("skill", False)
    assert c.allowed("skill open_app", False) is None     # keyword done: free
    assert ID["pre"] in c.allowed("", False)


def test_constraint_done_alone_blocks_done_after_action():
    c = OpConstraint(FakeTok(), done_alone=True)
    assert ID["done"] in c.allowed("", False)
    assert ID["done"] not in c.allowed("", True)
    assert ID["press"] in c.allowed("", True)
    assert ID["done"] in OpConstraint(FakeTok(), done_alone=False).allowed("", True)


def test_plan_constraint_blocks_prose_and_done_after_action():
    wants = ["The", " plan", "\n", "done"]
    assert _plan(_planner(wants)) == ["press #1"]
    assert _plan(_planner(wants, constrain=False))[0] == "The plan"


def test_plan_stop_only_after_complete_line():
    # eos is masked on an empty batch and mid-keyword; allowed at a line start
    assert _plan(_planner(["<eos>", "<eos>", "\n", "<eos>"])) == ["press #1"]
    assert _plan(_planner(["<eos>"], constrain=False)) == []


def test_plan_script_block_unconstrained():
    wants = ["script", ' applescript """say hi', "\n", 'The end"""', "\n"]
    assert _plan(_planner(wants)) == ['script applescript """say hi\nThe end"""']


def test_brain18_unconstrained_plan_uses_dispatch_catalog():
    p = _planner(["pre", "\n"] * 6, constrain=False)
    p.catalog = Catalog({"skills": [{"name": "pre"}]})
    assert _plan(p) == ["pre"] * 5


def test_constraint_built_lazily_once(monkeypatch):
    n = [0]
    real = P.OpConstraint

    def counting(*a, **k):
        n[0] += 1
        return real(*a, **k)

    monkeypatch.setattr(P, "OpConstraint", counting)
    p = _planner(["press", " #1", "\n"])
    assert n[0] == 0
    _plan(p)
    c = p._constraint
    _plan(p)
    assert n[0] == 1 and p._constraint is c
    assert _planner(constrain=False)._op_constraint() is None


# ---------- Planner settings ----------

def test_planner_defaults_and_fewshot_in_system():
    p = _planner()
    assert (p.constrain, p.done_alone, p.history) == (
        P.PLANNER_CONSTRAIN_DEFAULT, True, "dsl")
    assert P.PLANNER_CONSTRAIN_DEFAULT is True
    fs = (ROOT / "prompts" / "planner_fewshot.md").read_text()
    assert p.system == _planner(few_shot=None).system + "\n\n" + fs


def test_planner_fewshot_custom_path_and_none(tmp_path):
    f = tmp_path / "fs.md"
    f.write_text("EXAMPLES")
    base = _planner(few_shot="none").system
    assert "Worked examples" not in base
    assert _planner(few_shot=str(f)).system == base + "\n\nEXAMPLES"


def test_planner_bad_history_rejected():
    with pytest.raises(ValueError):
        _planner(history="json")


# ---------- history formats ----------

LINES = ["press #4 -> ok", "skill open_app app=Safari -> failed: no app"]


def test_history_dsl_marked_repr():
    assert history(LINES, "dsl") == LINES
    assert history(LINES, "marked") == ["[ok] press #4",
                                        "[failed: no app] skill open_app app=Safari"]
    assert history(LINES, "repr") == ["press ref=4-> ok",
                                      "skill name=open_app args={'app': 'Safari'}-> failed: no app"]
    assert history(None, "marked") is None and history(["note"], "marked") == ["[ok] note"]


def test_runtime_repr_passthrough():
    assert runtime_repr("ignored 2 non-action lines") == "ignored 2 non-action lines"
    assert runtime_repr("press 4 -> failed: x") == "press 4 -> failed: x"


def _batch(tmp_path, fmt, turns, act):
    o = _diff_orch(tmp_path, turns, act)
    o.planner.history = fmt
    run(o._planner_loop("go", trace_for(o)))
    return o


def _press_fails(p):
    return {"ok": p.get("op") != "press", "error": "boom"}


@pytest.mark.parametrize("fmt,want", [
    ("marked", ['[ok] type #4 "hi there" enter', "[failed: boom] press #1"]),
    ("dsl", ['type #4 "hi there" enter -> ok', "press #1 -> failed: boom"]),
    ("repr", ["type ref=4 text=hi there enter=True-> ok", "press ref=1-> failed: boom"]),
])
def test_orchestrator_batch_log_formats(tmp_path, fmt, want):
    o = _batch(tmp_path, fmt, [['type #4 "hi there" enter', "press #1"],
                               ['done "ok"']], _press_fails)
    assert o.planner.user_msgs[1]["last_batch"] == want


def test_repr_format_is_legacy_dict_repr(tmp_path):
    a = dsl.parse('type #4 "hi there" enter')[0]
    assert _repr_line(a) == "type ref=4 text=hi there enter=True"


@pytest.mark.parametrize("fmt,want", [
    ("marked", "[failed: not verified; check the fresh observation] done"),
    ("dsl", "done -> failed: not verified; check the fresh observation"),
    ("repr", "done -> failed: not verified; check the fresh observation"),
])
def test_done_rejection_line_follows_format(tmp_path, fmt, want):
    o = _batch(tmp_path, fmt, [["press #1"], ['done "ok"']], _press_fails)
    assert o.planner.user_msgs[2]["last_batch"][-1] == want


@pytest.mark.parametrize("fmt", ["marked", "dsl", "repr"])
def test_ignored_note_keeps_wording(tmp_path, fmt):
    o = _batch(tmp_path, fmt, [["Sure, here goes", "press #4"], ['done "ok"']],
               lambda p: {"ok": True})
    assert o.planner.user_msgs[1]["last_batch"][-1] == "ignored 1 non-action lines"


def test_parse_error_line_marked(tmp_path):
    o = _batch(tmp_path, "marked", [["press 4"], ['done "ok"']], lambda p: {"ok": True})
    line = o.planner.user_msgs[1]["last_batch"][0]
    assert line.startswith("[failed: ") and line.endswith("] press 4")


def test_script_failure_marked(tmp_path):
    o = _batch(tmp_path, "marked", [['script shell """ls nope"""'], ['done "x"']],
               lambda p: {"ok": False, "error": "script_failed: exit 2: no",
                          "exit_code": 2, "stderr": "no"})
    assert o.planner.user_msgs[1]["last_batch"] == [
        '[failed: exit 2; stderr: no] script shell """ls nope"""']


# ---------- dsl.serialize round trip ----------

@pytest.mark.parametrize("line", [
    "skill open_app app=Safari",
    'skill send_message to=Mom body="hi there, see you"',
    "skill dark_mode on=true",
    "press #4",
    'type #4 "hi there" enter',
    "keys cmd+shift+n",
    "scroll #3 down 5",
    "click 10,20 right",
    'open "TextEdit"',
    'url "https://example.com/a?b=1"',
    'script shell """ls ~/Desktop"""',
    "wait 300",
    'ask "Which file?"',
    'confirm "Send it to Mom?"',
    'done "Sent"',
    'refuse "Not allowed"',
])
def test_logged_action_round_trips(line):
    a = dsl.parse(line)[0]
    assert dsl.parse(_log_act(a))[0] == a


def test_logged_action_drops_expect_and_marked_line_parses(tmp_path):
    a = dsl.parse('press #4\nexpect title~"Downloads"')[0]
    assert _log_act(a) == "press #4"
    o = _batch(tmp_path, "marked", [['skill open_app app="Text Edit"'], ['done "ok"']],
               lambda p: {"ok": True})
    logged = o.planner.user_msgs[1]["last_batch"][0]
    assert logged.startswith("[ok] ")
    assert dsl.parse(logged[5:])[0] == dsl.parse('skill open_app app="Text Edit"')[0]


# ---------- BatchCutter: 5-action batches (brain-3, brain-11, brain-18) ----------

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


@pytest.mark.parametrize("lines", [
    ["mute"] * 6,
    ["mute", "skill mute", "press #1", "mute", "keys a", "mute"],
])
def test_brain18_bare_and_explicit_skills_count_once(lines):
    cutter, emitted = BatchCutter(), []
    for line in lines:
        if (out := cutter.push(line)) is not None:
            emitted.append(out)
        if cutter.done:
            break
    assert emitted == lines[:5]
    assert cutter.n == 5 and cutter.full and cutter.done
    normalized = [dsl.action_line(line, SKILLS) for line in emitted]
    assert len(dsl.parse("\n".join(normalized))) == 5


@pytest.mark.parametrize("line,count", [
    ("", 0), ("Let me think.", 0), ("</think>", 0), ("```", 0),
    ("# note", 0), ('expect appears "Saved"', 0), ("unknown", 0),
    ("unknown_skill x=1", 1), ("press #1", 1), ("wait 10", 1),
    ('script shell """echo ok"""', 1),
])
def test_brain18_non_skill_lines_unchanged(line, count):
    cutter = BatchCutter()
    assert cutter.push(line) == line
    assert cutter.n == count
    assert not cutter.full and not cutter.done


def test_brain18_bare_fifth_skill_keeps_expect():
    cutter = BatchCutter()
    for _ in range(5):
        assert cutter.push("mute") == "mute"
    assert cutter.push("# note") is None
    assert cutter.push('expect appears "Muted"') == 'expect appears "Muted"'
    assert cutter.n == 5 and cutter.done


def test_brain18_custom_and_empty_catalogs():
    cutter = BatchCutter(max_actions=1, skills={"customskill"})
    assert cutter.push("customskill") == "customskill"
    assert cutter.n == 1 and cutter.full
    assert cutter.push("customskill") is None
    empty = BatchCutter(skills={})
    assert empty.push("mute") == "mute"
    assert empty.n == 0


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


# ---------- CLI flags ----------

def test_cli_defaults():
    args, _ = cli.build_parser(["serve"])
    assert args.memory is True
    assert args.memory_llm is True
    assert args.longterm is True
    assert cli.planner_opts(args) == {"done_alone": True,
                                      "few_shot": "prompts/planner_fewshot.md",
                                      "history": "dsl", "app_hints": False}


def test_login_hint_is_opt_in():
    planner = Planner.__new__(Planner)
    base = planner.user_message("sign in", 'window: "Home"', None)
    hinted = planner.user_message("sign in", 'window: "Login"', None,
                                  login_page=True)
    assert base == 'Goal: "sign in"\nwindow: "Home"'
    assert "Login page: ask the user to sign in" not in base
    assert "Login page: ask the user to sign in" in hinted


def test_cli_memory_flags_and_planner_recent_prompt():
    args, _ = cli.build_parser(["serve", "--no-memory", "--no-memory-llm"])
    assert args.memory is False
    assert args.memory_llm is False
    args, _ = cli.build_parser(["serve", "--no-longterm"])
    assert args.longterm is False

    p = _planner()
    baseline = p.user_message("goal", "observation", None)
    assert baseline == 'Goal: "goal"\nobservation'
    assert p.user_message("goal", "observation", None, recent=None) == baseline
    assert p.user_message(
        "goal", "observation", None, recent=None, memory=None) == baseline
    assert p.user_message(
        "goal", "observation", None, hint="Open Safari",
        recent=["open Safari ok"]
    ) == ('Goal: "goal"\nHint: likely Open Safari\nRecent:\nopen Safari ok\n'
          'observation')
    with_memory = p.user_message(
        "goal", "observation", None, recent=["recent"],
        memory=["Memory: person mom = Jane", "Memory: fact tea = green"])
    assert with_memory.endswith(
        "Recent:\nrecent\nMemory: person mom = Jane\n"
        "Memory: fact tea = green\nobservation")


def test_planner_complete_greedy_stops_at_newline():
    p = _planner(["press", " #1", "\n", "The"])
    p._rewrite_cut, p._rewrite_cache = 1, []
    assert p.complete("prompt", max_tokens=40) == "press #1"


def test_cli_flags_parse():
    args, _ = cli.build_parser([
        "serve", "--no-planner-constrain", "--no-planner-done-alone",
        "--planner-fewshot", "none", "--planner-history", "dsl"])
    assert cli.planner_opts(args) == {"constrain": False, "done_alone": False,
                                      "few_shot": None, "history": "dsl",
                                      "app_hints": False}
    args, _ = cli.build_parser(["serve", "--planner-constrain",
                                "--planner-fewshot", "x.md"])
    assert cli.planner_opts(args)["constrain"] is True
    assert cli.planner_opts(args)["few_shot"] == "x.md"
    with pytest.raises(SystemExit):
        cli.build_parser(["serve", "--planner-history", "json"])


def test_flags_reach_planner_and_startup_log(capsys):
    args, _ = cli.build_parser([
        "serve", "--no-planner-constrain", "--no-planner-done-alone",
        "--planner-fewshot", "none", "--planner-history", "repr"])
    p = cli.make_planner("fake", _fake_engine([]), cli.planner_opts(args))
    assert (p.constrain, p.done_alone, p.few_shot, p.history) == (
        False, False, None, "repr")
    assert "Worked examples" not in p.system
    out = capsys.readouterr().out
    assert "[planner] fake constrain=False done_alone=False few_shot=none " \
        "history=repr" in out
    d = cli.make_planner("fake", _fake_engine([]), cli.planner_opts(
        cli.build_parser(["serve"])[0]))
    assert d.constrain is P.PLANNER_CONSTRAIN_DEFAULT
    assert "few_shot=prompts/planner_fewshot.md history=dsl" in capsys.readouterr().out


def test_serve_cmd_passes_planner_opts(monkeypatch):
    got = {}

    async def fake_serve(port, model, planner_model, planner_kw=None,
                         args_model=None, escalate_model=None, grounder=None,
                         verify_done=True, open_ended_route=False,
                         planner_aux_model=None, **_kw):
        got.update(planner_kw)

    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setattr(cli, "_resolve_model", lambda m: "m")
    cli.run_cmd(*cli.build_parser(["serve", "--planner-history", "dsl",
                                   "--no-planner-constrain"]))
    assert got == {"constrain": False, "done_alone": True,
                   "few_shot": "prompts/planner_fewshot.md", "history": "dsl",
                   "app_hints": False}


def test_serve_cmd_passes_memory_toggles(monkeypatch):
    got = {}

    async def fake_serve(*args, **kwargs):
        got.update(kwargs)

    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setattr(cli, "_resolve_model", lambda m: "m")
    cli.run_cmd(*cli.build_parser([
        "serve", "--no-memory", "--no-memory-llm"]))
    assert got["memory_enabled"] is False
    assert got["memory_llm"] is False


# ---------- brain-16: relative volume never becomes an absolute level ----------

@pytest.mark.parametrize("text,level,delta", [
    ("turn it up two to three notches", None, 25),
    ("turn it down two notches", None, -20),
    ("turn it up three steps", None, 30),
    ("turn it down 10 points", None, -10),
    ("turn it up a bit", None, 10),
    ("turn it down by 20", None, -20),
    ("turn it up 20 percent", None, 20),
    ("turn it up two to three", None, 25),
    ("turn it up to three", 3, None),
    ("turn it down to 30 percent", 30, None),
    ("volume 40 percent", 40, None),
    ("set it at half", 50, None),
])
def test_abs_level_vs_rel_delta(text, level, delta):
    assert abs_level(text) == level
    if level is None:
        assert rel_delta(text) == delta


@pytest.mark.parametrize("text,model_delta,want", [
    ("turn it up two to three notches", "3", 25),
    ("turn it down two notches", "-2", -20),
    ("turn it up a bit", "5", 10),
    ("make it louder", "10", 10),          # no amount stated: model delta stands
])
def test_relative_volume_stays_change_volume(tmp_path, text, model_delta, want):
    srv = FakeServer()
    eng = FakeEngine(routes={text: ("change_volume", 0.9)},
                     argmap={("change_volume", text): {"delta": model_delta}})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    run(o.handle_utterance(text))
    assert _skill_rpcs(srv) == [("change_volume", {"delta": want})]


# ---------- planner-20: harness done-rejection isn't a guard failure ----------

def test_done_rejection_not_counted_by_loop_guard(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ["press #2"], ['done "ok"'],
                              ['done "ok"']], _press_fails)
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "ok"
    assert o.planner.calls == 4
    assert not any("loop_guard" in d for d in tr["decisions"])


def test_three_real_failures_still_trip_guard(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ["press #2"], ['done "ok"'],
                              ["press #3"], ["press #4"]], _press_fails)
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "awaiting_user"
    assert o.planner.calls == 4
    assert any(d.get("loop_guard") == "3_failed_turns" for d in tr["decisions"])


def run(coro):
    return asyncio.run(coro)


# ---------- (e) opt-in escalation planner ----------

STUCK = "I'm stuck on that, can you help?"


def _esc_orch(tmp_path, main_turns, esc_turns, act):
    from test_planner_loop import FakePlanner
    o = _diff_orch(tmp_path, main_turns, act)
    o.planner_escalate = FakePlanner(esc_turns, history="dsl")
    return o


def test_escalation_takes_over_after_two_failed_turns(tmp_path):
    o = _esc_orch(tmp_path, [["press #1"], ["press #2"]],
                  [["press #3"], ['done "ok"']],
                  lambda p: {"ok": p.get("ref") == 3, "error": "boom"})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "ok"
    assert o.planner.calls == 2 and o.planner_escalate.calls == 2
    assert tr["planner_escalated"] is True
    assert {"planner_escalated": 1} in tr["decisions"]
    assert not any("loop_guard" in d for d in tr["decisions"])
    # it sees the failed batch, in its own (dsl) history format
    assert o.planner_escalate.user_msgs[0]["last_batch"] == \
        ["press ref=2-> failed: boom"]
    assert o.planner_escalate.user_msgs[1]["last_batch"] == ["press #3 -> ok"]


def test_escalation_on_same_action_twice(tmp_path):
    o = _esc_orch(tmp_path, [["press #1"]], [['done "ok"']],
                  lambda p: {"ok": False, "error": "no such ref"})
    tr = trace_for(o)
    run(o._planner_loop("go", tr))
    assert o.planner.calls == 2 and tr["planner_escalated"] is True


def test_escalation_fails_twice_then_stops(tmp_path):
    o = _esc_orch(tmp_path, [["press #1"], ["press #2"]],
                  [["press #3"], ["press #4"], ["press #5"]],
                  lambda p: {"ok": False, "error": "x"})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "awaiting_user"
    assert o.planner.calls == 2 and o.planner_escalate.calls == 2
    assert o.server.said[-1] == STUCK and o.server.uis[-1] == "confused"
    assert tr["planner_escalated"] is True
    assert any("loop_guard" in d for d in tr["decisions"])
    assert o._pending_task["goal"] == "go"


def test_no_escalation_keeps_today_guard(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ["press #2"], ["press #3"]],
                   lambda p: {"ok": False, "error": "x"})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "awaiting_user"
    assert o.planner.calls == 3 and "planner_escalated" not in tr


def test_escalation_unused_when_main_succeeds(tmp_path):
    o = _esc_orch(tmp_path, [["press #1"], ['done "ok"']], [['done "x"']],
                  lambda p: {"ok": True})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "ok"
    assert o.planner_escalate.calls == 0 and "planner_escalated" not in tr


def test_cli_escalate_flag(monkeypatch):
    args, _ = cli.build_parser(["serve"])
    assert args.planner_escalate_model is None
    seen = {}

    async def fake_serve(port, model, pmodel, pkw, args_model=None,
                         escalate_model=None, grounder=None,
                         verify_done=True, open_ended_route=False,
                         planner_aux_model=None, **_kw):
        seen["esc"] = escalate_model

    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setattr(cli, "_resolve_model", lambda m: f"/m/{m}")
    cli.run_cmd(*cli.build_parser(["serve", "--planner-escalate-model", "Big"]))
    assert seen["esc"] == "/m/Big"
    for argv in (["serve"], ["serve", "--planner-escalate-model", "none"]):
        cli.run_cmd(*cli.build_parser(argv))
        assert seen["esc"] is None


def test_escalation_planner_settings(capsys):
    p = cli.make_planner("fake", _fake_engine([]), cli.ESCALATE_OPTS,
                         tag="planner-escalate")
    assert (p.constrain, p.few_shot, p.history) == (
        False, "prompts/planner_fewshot.md", "dsl")
    assert p._op_constraint() is None
    fs = (ROOT / "prompts" / "planner_fewshot.md").read_text()
    assert p.system.endswith("\n\n" + fs)
    assert "[planner-escalate] fake constrain=False" in capsys.readouterr().out


# ---------- escalation load / unload and planner warm-up (brain-9, first use) ----------

def test_warm_planner_records_event_and_swallows_failure(
        tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", InlineWorker)
    orch = Orchestrator(FakeServer(), Catalog.load(),
                        Tracer(tmp_path / "traces"), engine=FakeEngine())

    class WarmPlanner:
        model_path = "fake/model"

        def warm(self):
            return {"warm_ms": 42.0, "prefix_ms": 1.0,
                    "constraint_ms": 2.0, "retrieval_ms": 3.0,
                    "decode_ms": 4.0}

    asyncio.run(orch.warm_planner(WarmPlanner()))
    rows = [json.loads(line) for path in orch.tracer.dir.glob("*.jsonl")
            for line in path.read_text().splitlines()]
    assert rows[-1]["event"] == "planner.warm"
    assert rows[-1]["warm_ms"] == 42.0
    assert rows[-1]["model"] == "fake/model"

    class BrokenPlanner:
        def warm(self):
            raise RuntimeError("warm failed")

    asyncio.run(orch.warm_planner(BrokenPlanner()))


def test_successful_escalation_load_schedules_planner_warm(
        tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", InlineWorker)
    orch = Orchestrator(FakeServer(), Catalog.load(),
                        Tracer(tmp_path / "traces"), engine=FakeEngine())
    orch.planner = object()
    orch._sysctl_reader = lambda name: {
        "hw.memsize": 64 * 1024 ** 3,
        "kern.memorystatus_level": 50,
    }[name]
    warmed = []

    class EscalationPlanner:
        model_path = "fake/escalation"

        def warm(self):
            warmed.append(True)
            return {"warm_ms": 5.0}

    planner = EscalationPlanner()
    orch._escalate_loader = lambda *args, **kwargs: planner

    async def enable_and_warm():
        result = await orch.set_escalation(True)
        await asyncio.gather(*list(orch._warm_tasks))
        return result

    result = asyncio.run(enable_and_warm())

    assert result == {"loaded": True}
    assert orch.planner_escalate is planner
    assert warmed


@pytest.mark.parametrize("memory,pressure,reason", [
    (32 * 1024 ** 3, 60, "needs 48 GB RAM"),
    (64 * 1024 ** 3, 30, "memory pressure"),
])
def test_escalation_refuses_insufficient_memory(memory, pressure, reason):
    orch = Orchestrator(FakeServer(), Catalog.load())
    orch.planner = object()
    values = {"hw.memsize": memory, "kern.memorystatus_level": pressure}
    orch._sysctl_reader = values.__getitem__
    result = asyncio.run(orch.set_escalation(True))
    assert result == {"loaded": False, "reason": reason}
    assert orch.planner_escalate is None


def test_escalation_loads_once_and_unloads():
    orch = Orchestrator(FakeServer(), Catalog.load())
    orch.planner = object()
    orch._sysctl_reader = lambda name: {
        "hw.memsize": 64 * 1024 ** 3,
        "kern.memorystatus_level": 60,
    }[name]
    calls = []
    planner = object()
    orch._escalate_loader = lambda *args, **kwargs: (
        calls.append((args, kwargs)) or planner)
    async def go():
        first = await orch.set_escalation(True)
        second = await orch.set_escalation(True)
        await orch.set_escalation(False)
        return first, second
    first, second = asyncio.run(go())
    assert first == second == {"loaded": True}
    assert len(calls) == 1
    assert calls[0][1]["tag"] == "planner-escalate"
    assert orch.planner_escalate is None


def test_escalation_refuses_without_base_planner():
    orch = Orchestrator(FakeServer(), Catalog.load())
    assert asyncio.run(orch.set_escalation(True)) == {
        "loaded": False, "reason": "no planner"}


# ---------- escalation load races (brain-30) ----------

def _race_orch(gate, calls):
    orch = Orchestrator(FakeServer())
    orch.planner = object()
    orch._sysctl_reader = lambda name: {
        "hw.memsize": 64 * 1024 ** 3, "kern.memorystatus_level": 60}[name]

    class Planner:
        pass

    def loader(*args, **kwargs):
        planner = Planner()
        calls.append(weakref.ref(planner))
        assert gate.wait(5)
        return planner

    orch._escalate_loader = loader
    return orch


async def _loading(calls):
    async with asyncio.timeout(5):
        while not calls:
            await asyncio.sleep(0.001)


def test_brain30_toggle_off_during_load_leaves_no_planner():
    gate, calls = threading.Event(), []
    orch = _race_orch(gate, calls)

    async def scenario():
        on = asyncio.create_task(orch.set_escalation(True))
        await _loading(calls)
        assert await asyncio.wait_for(orch.set_escalation(False), 1) == {"loaded": False}
        gate.set()
        assert await on == {"loaded": False}
        assert orch.planner_escalate is None
        assert calls[0]() is None

    asyncio.run(scenario())


def test_brain30_two_enables_load_one_copy():
    gate, calls = threading.Event(), []
    orch = _race_orch(gate, calls)

    async def scenario():
        first = asyncio.create_task(orch.set_escalation(True))
        await _loading(calls)
        second = asyncio.create_task(orch.set_escalation(True))
        gate.set()
        assert await asyncio.gather(first, second) == [{"loaded": True}] * 2
        assert len(calls) == 1
        assert orch.planner_escalate is calls[0]()

    asyncio.run(scenario())


def test_escalation_checks_memory_after_waiting_for_lock():
    gate, calls = threading.Event(), []
    orch = _race_orch(gate, calls)

    async def scenario():
        await orch._escalate_lock.acquire()
        enable = asyncio.create_task(orch.set_escalation(True))
        await asyncio.sleep(0)
        orch._sysctl_reader = lambda name: 0
        orch._escalate_lock.release()
        assert await enable == {"loaded": False, "reason": "needs 48 GB RAM"}
        assert not calls

    asyncio.run(scenario())


# ---------- plan-bank retrieval knobs ----------

def _demo(goal, demo_id=None):
    return Demo(goal=goal, app="Finder", category="single_step",
                obs_header='app: Finder | window: "Desktop"', obs_lines=['#1 button "New Folder"'],
                batch=["press #1"], id=demo_id)


def test_planner_retrieval_layout_keeps_examples_after_cached_prefix(monkeypatch):
    demos = [_demo("create a folder on desktop", "folder"),
             _demo("rename a file in downloads", "rename")]
    monkeypatch.setattr("brain.plan_bank.load_bank", lambda spec: demos)
    message_calls = []

    def renderer(msgs):
        message_calls.append(msgs)
        return list("".join(f"<|{message['role']}|>{message['content']}<|end|>"
                            for message in msgs).encode("utf-8"))

    def make_planner(k):
        p = P.Planner("fake", Catalog.load(), engine=_fake_engine(["<eos>"]),
                      constrain=False, few_shot=None, retrieval_k=k)
        p._render_msgs = renderer
        p.tokenizer.encode = lambda text, add_special_tokens=False: list(text.encode("utf-8"))
        p._prefill = lambda tokens: []
        return p

    observation = 'app: Finder | window: "Desktop"\n#1 button "New Folder"'
    plain, retrieved = make_planner(0), make_planner(2)
    plain_result = plain.plan("make a new folder", observation, None, asyncio.Queue(),
                              asyncio.new_event_loop(), threading.Event())
    retrieved_result = retrieved.plan("make a new folder", observation, None, asyncio.Queue(),
                                      asyncio.new_event_loop(), threading.Event())
    assert plain.system == retrieved.system
    assert plain._prefix_tokens == retrieved._prefix_tokens
    assert plain._prefix_tokens == renderer([{"role": "system", "content": plain.system},
                                             {"role": "user", "content": ""}])[:plain._cut]
    plain_user = next(message["content"] for message in message_calls[1]
                      if message["role"] == "user")
    retrieved_user = next(message["content"] for message in message_calls[3]
                          if message["role"] == "user")
    assert plain_user == plain.user_message("make a new folder", observation, None)
    chosen = retrieved.plan_bank.retrieve("make a new folder", observation, 2)
    assert retrieved_user == render_block(chosen) + retrieved.user_message(
        "make a new folder", observation, None)
    assert retrieved_user.startswith("# Similar worked examples")
    assert renderer(message_calls[3])[:retrieved._cut] == retrieved._prefix_tokens
    assert plain_result["retrieved"] == []
    assert retrieved_result["retrieved"] == [demo.id or demo.goal for demo in chosen]
    assert {"prompt_tokens", "dynamic_tokens"} <= plain_result.keys()
    assert retrieved_result["dynamic_tokens"] > plain_result["dynamic_tokens"]


def test_planner_retrieval_flags_load_bank_only_when_enabled(monkeypatch, capsys):
    args, _ = cli.build_parser(["serve"])
    assert not ({"retrieval_k", "retrieval_bank"} & cli.planner_opts(args).keys())
    with pytest.raises(SystemExit):
        cli.build_parser(["serve", "--help"])
    help_text = capsys.readouterr().out
    assert "@REV" in help_text and "bank.jsonl.gz" in help_text
    seen = {}

    def fake_load(spec):
        seen["spec"] = spec
        return [_demo("open a clean task", "demo-id")]

    monkeypatch.setattr("brain.plan_bank.load_bank", fake_load)
    args, _ = cli.build_parser(["serve", "--planner-retrieval-k", "2",
                                "--planner-retrieval-bank", "x.jsonl"])
    opts = cli.planner_opts(args)
    assert opts["retrieval_k"] == 2 and opts["retrieval_bank"] == "x.jsonl"
    assert opts["app_hints"] is False
    planner = cli.make_planner("fake", _fake_engine([]), opts)
    assert seen["spec"] == "x.jsonl"
    assert planner.retrieval_k == 2
    assert "retrieval_k=2 retrieval_bank=x.jsonl" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.build_parser(["serve", "--planner-retrieval-k", "3"])
    with pytest.raises(ValueError):
        P.Planner("fake", Catalog.load(), engine=_fake_engine([]), retrieval_k=3)


def test_offline_parser_runner_and_old_summary(monkeypatch):
    args = planner_offline.build_parser().parse_args(["--retrieval-k", "2"])
    assert args.retrieval_k == 2 and args.retrieval_bank == "v2-tune"
    assert planner_offline.build_parser().parse_args(
        ["--app-hints"]).app_hints is True
    seen = {}

    class FakePlanner:
        def __init__(self, *args, **kwargs):
            seen.update(kwargs)
            self.tokenizer = type("FakeTokenizer", (), {
                "eos_token_id": 0,
                "encode": lambda self, text, add_special_tokens=False: [],
            })()

    monkeypatch.setattr("brain.planner.Planner", FakePlanner)
    runner = planner_offline.Runner("fake", None, retrieval_k=2, retrieval_bank="x.jsonl")
    assert seen["retrieval_k"] == 2 and seen["retrieval_bank"] == "x.jsonl"
    assert seen["app_hints"] is False

    old_row = {
        "tags": ["single_step"], "pass": True, "strict_pass": True,
        "valid": True, "strict_valid": True, "skipped": 0,
        "ttft_ms": 20.0, "plan_ms": 100.0, "decode_tok_s": 12.0, "tokens": 5,
    }
    summary = planner_offline.summarize("old", "model", {}, [old_row])
    assert summary["knobs"]["retrieval_k"] == 0
    assert summary["knobs"]["retrieval_bank"] == "v2-tune"
    assert summary["prompt_tokens_mean"] is None
    assert summary["dynamic_tokens_mean"] is None
    assert summary["retrieval_ms_p50"] is None


def test_decide_pre_registered_pass_fail_gates_and_tie():
    sets = planner_retrieval_report.SETS

    def rows(passes, ttft=100):
        return {name: {"n": 100, "n_pass": passes, "ttft_ms_p50": ttft}
                for name in sets}

    base = rows(50)
    passing = rows(55, 120)
    small_gain = rows(51, 120)
    one_drop = rows(52, 120)
    one_drop["v1-tune"]["n_pass"] = 48
    slow = rows(55, 120)
    slow["v2-holdout"]["ttft_ms_p50"] = 251
    decision, notes = planner_retrieval_report.decide(
        {0: base, 1: passing, 2: small_gain})
    assert decision == 1 and "k=1: gain +0.050 -> PASS" in notes
    assert "holdout gain +0.010 < +0.030" in planner_retrieval_report.decide(
        {0: base, 1: small_gain})[1][0]
    assert "drop > 1 scenario" in planner_retrieval_report.decide(
        {0: base, 1: one_drop})[1][0]
    assert "TTFT p50 > +150 ms" in planner_retrieval_report.decide(
        {0: base, 1: slow})[1][0]
    assert planner_retrieval_report.decide({0: base, 1: passing, 2: passing})[0] == 1
