"""Planner knobs from the offline benchmark (constraint, done-alone,
few-shot, history format), CLI flags, Last-batch formats, brain-16
relative volume, planner-20. Fakes only (no Metal / weights)."""

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import mlx.core as mx
import numpy as np
import pytest

from brain import cli, dsl
from brain import planner as P
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator, _log_act, _repr_line, abs_level, rel_delta
from brain.planner import OpConstraint, Planner, history, runtime_repr
from brain.traces import Tracer

from fakes import FakeEngine, FakeServer
from test_live_e2e_fixes import _skill_rpcs
from test_planner_loop import _diff_orch, trace_for

ROOT = Path(__file__).resolve().parents[2]

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
        P.PLANNER_CONSTRAIN_DEFAULT, True, "marked")
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


# ---------- CLI flags ----------

def test_cli_defaults():
    args, _ = cli.build_parser(["serve"])
    assert cli.planner_opts(args) == {"done_alone": True,
                                      "few_shot": "prompts/planner_fewshot.md",
                                      "history": "marked"}


def test_cli_flags_parse():
    args, _ = cli.build_parser([
        "serve", "--no-planner-constrain", "--no-planner-done-alone",
        "--planner-fewshot", "none", "--planner-history", "dsl"])
    assert cli.planner_opts(args) == {"constrain": False, "done_alone": False,
                                      "few_shot": None, "history": "dsl"}
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
    assert "few_shot=prompts/planner_fewshot.md history=marked" in capsys.readouterr().out


def test_serve_cmd_passes_planner_opts(monkeypatch):
    got = {}

    async def fake_serve(port, model, planner_model, planner_kw=None):
        got.update(planner_kw)

    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setattr(cli, "_resolve_model", lambda m: "m")
    cli.run_cmd(*cli.build_parser(["serve", "--planner-history", "dsl",
                                   "--no-planner-constrain"]))
    assert got == {"constrain": False, "done_alone": True,
                   "few_shot": "prompts/planner_fewshot.md", "history": "dsl"}


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
