"""Bounded planner thinking tests use a scripted tokenizer and model only;
evals/planner_think_report.py ship rule and run-file loading (no model)."""

import asyncio
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import mlx.core as mx
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))

import planner_offline
import planner_think_report as think_report

from brain import cli
from brain.catalog import Catalog
from brain.planner import OpConstraint, Planner, sample_logits
from test_planner_loop import FakePlanner, _diff_orch, trace_for


TOKENS = ["<eos>", "<|im_end|>", "<think>", "</think>", "\n", "\n\n",
          "prefix", "press", " #1", "The", " plan", "done", " done", "ask"]
IDS = {token: i for i, token in enumerate(TOKENS)}
OPEN, CLOSE, NL, AFTER = IDS["<think>"], IDS["</think>"], IDS["\n"], IDS["\n\n"]


class FakeTok:
    eos_token_id = IDS["<eos>"]

    def __init__(self, tokens=None):
        self.tokens = list(tokens or TOKENS)
        self.ids = {token: i for i, token in enumerate(self.tokens)}

    def get_vocab(self):
        return self.ids.copy()

    def encode(self, text, add_special_tokens=False):
        return [self.ids[text]]

    def decode(self, ids):
        return "".join(self.tokens[i] for i in ids)


class FakeModel:
    def __init__(self, predictions, tokenizer=None):
        self.tokenizer = tokenizer or FakeTok()
        self.predictions = [self.tokenizer.ids[x] if isinstance(x, str) else x
                            for x in predictions]
        self.inputs = []
        self.step = 0
        self.model_path = "fake"
        self.model = None
        self.rr = None

    def body(self, value, cache=None):
        self.inputs.append(np.asarray(value).reshape(-1).tolist())
        return mx.zeros((1, 1, 1))

    def lm_head(self, _):
        logits = np.zeros(len(self.tokenizer.tokens), dtype=np.float32)
        token = (self.predictions[self.step] if self.step < len(self.predictions)
                 else self.tokenizer.eos_token_id)
        logits[token] = 10
        self.step += 1
        return mx.array(logits)[None, None, :]


def _planner(predictions=(), **kwargs):
    engine = FakeModel(predictions)
    planner = Planner("fake", Catalog.load(), engine=engine, few_shot=None,
                      **kwargs)
    planner._render_msgs = lambda msgs: [
        IDS["prefix"], OPEN, NL, NL, CLOSE, AFTER]
    planner._content_cut = lambda toks, sentinel: len(toks)
    planner._cache, planner._cut = [], 0
    return planner, engine


def _run_plan(planner, goal="goal", last_batch=None):
    loop = asyncio.new_event_loop()
    try:
        return planner.plan(goal, "obs", last_batch, asyncio.Queue(), loop,
                            threading.Event())
    finally:
        loop.close()


def _action_predictions(*prefix):
    return [*prefix, "press", " #1", "\n", "<eos>"]


def test_budget_zero_preserves_inputs_lines_settings_and_info():
    plain, plain_model = _planner(_action_predictions())
    explicit, explicit_model = _planner(_action_predictions(), think_budget=0)
    a, b = _run_plan(plain), _run_plan(explicit)
    assert plain_model.inputs == explicit_model.inputs
    assert a["lines"] == b["lines"] == ["press #1"]
    assert plain.settings() == explicit.settings()
    assert b["think"] is None and b["think_tokens"] == 0


def test_thinking_prompt_replaces_empty_think_block():
    planner, model = _planner(["The", " plan", *_action_predictions()],
                              think_budget=2)
    _run_plan(planner)
    assert model.inputs[0] == [IDS["prefix"], OPEN, NL]


def test_budget_cutoff_feeds_last_token_and_forced_close_before_actions():
    planner, model = _planner(["The", " plan", *_action_predictions()],
                              think_budget=2, constrain=False)
    info = _run_plan(planner)
    assert info["think"]["tokens"] == 2
    assert info["think"]["closed"] == "budget"
    assert model.inputs[2] == [IDS[" plan"], NL, CLOSE, AFTER]
    assert info["lines"] == ["press #1"]


def test_prose_thought_never_becomes_action_and_constraint_remains_active():
    planner, model = _planner(
        ["The", " plan", " done", "</think>", "The", " #1", "\n", "<eos>"],
        think_budget=8)
    info = _run_plan(planner)
    assert info["think"]["text"] == "The plan done"
    assert info["think"]["closed"] == "model"
    assert model.inputs[4] == [CLOSE, AFTER]
    assert info["lines"] == ["press #1"]
    constraint = OpConstraint(planner.tokenizer, done_alone=True)
    assert IDS["done"] not in constraint.allowed("", True)


def test_natural_close_and_newline_tail_behavior():
    planner, model = _planner(["The", "</think>", *_action_predictions()],
                              think_budget=8, constrain=False)
    info = _run_plan(planner)
    assert info["think"]["closed"] == "model"
    assert model.inputs[2] == [CLOSE, AFTER]

    newline, newline_model = _planner(
        ["The", "\n", *_action_predictions()],
        think_budget=2, constrain=False)
    info = _run_plan(newline)
    assert info["think"]["closed"] == "budget"
    assert newline_model.inputs[2] == [NL, CLOSE, AFTER]


def test_repetition_guard_stops_before_budget():
    planner, _ = _planner(["The"] * 40 + _action_predictions(),
                          think_budget=100, constrain=False)
    info = _run_plan(planner)
    assert info["think"]["closed"] == "loop"
    assert info["think"]["tokens"] == 14


def test_eos_forces_close_without_feeding_eos():
    planner, model = _planner(["The", "<eos>", *_action_predictions()],
                              think_budget=8, constrain=False)
    info = _run_plan(planner)
    assert info["think"]["closed"] == "eos"
    assert model.inputs[2] == [NL, CLOSE, AFTER]
    assert IDS["<eos>"] not in model.inputs[2]


@pytest.mark.parametrize("line", [
    "press #4 -> failed: x", "press #4-> failed", "[failed: x] press #4",
    "press ref=1-> confirmed", "press ref=1-> cancelled",
    "reply -> yes", "reply -> no", "done -> failed: not verified",
])
def test_retry_history_matches_failure_and_confirmation_forms(line):
    from brain.planner import is_retry
    assert is_retry("goal", [line])


@pytest.mark.parametrize("line", [
    "press #4 -> ok", "ask -> ask", "ignored 2 non-action lines",
    "this failed without a result marker",
])
def test_retry_history_ignores_success_and_non_action_notes(line):
    from brain.planner import is_retry
    assert not is_retry("goal", [line])


def test_retry_policy_and_user_answer_marker():
    from brain.planner import is_retry
    planner, _ = _planner(think_budget=2, think_on="retry")
    assert not planner.wants_think("fresh goal", None)
    assert planner.wants_think("fresh goal", ["press -> failed: x"])
    assert is_retry('goal\nUser answer: "the blue one"', None)


def test_planner_trace_records_think_metrics(tmp_path):
    class TracedPlanner(FakePlanner):
        def plan(self, *args, **kwargs):
            info = super().plan(*args, **kwargs)
            info["think"] = {"tokens": 9, "ms": 12.3, "text": "reason",
                             "closed": "budget"}
            return info

    orch = _diff_orch(tmp_path, [["press #1"], ['done "ok"']],
                      lambda params: {"ok": True})
    orch.planner = TracedPlanner([["press #1"], ['done "ok"']])
    trace = trace_for(orch)
    asyncio.run(orch._planner_loop("goal", trace))
    assert {"planner.think": {"turn": 1, "tokens": 9, "ms": 12.3,
                              "text": "reason", "closed": "budget"}} in trace["decisions"]


def test_think_text_is_truncated_to_trace_limit():
    words = [f"word{i:03} " for i in range(80)]
    tokenizer = FakeTok(TOKENS + words)
    planner, _ = _planner([], think_budget=80, constrain=False)
    planner.tokenizer = tokenizer
    # Use a scripted body and vocabulary for unique tokens so the loop guard
    # cannot fire before the full budget.
    model = FakeModel(words, tokenizer)
    planner.body, planner.lm_head = model.body, model.lm_head
    dyn = [tokenizer.ids["prefix"], OPEN, NL, NL, CLOSE, AFTER]
    _, info = planner.think([], dyn)
    assert info["tokens"] == 80
    assert len(info["text"]) == 400


def test_qwen_sampler_is_deterministic_and_top_k_one_is_greedy():
    logits = np.array([0.1, 0.7, 0.4, 0.3])
    a = sample_logits(logits, 0.6, 0.95, 3, np.random.default_rng(4))
    b = sample_logits(logits, 0.6, 0.95, 3, np.random.default_rng(4))
    assert a == b
    assert sample_logits(logits, 0.6, 0.95, 1,
                         np.random.default_rng(4)) == int(np.argmax(logits))
    planner, _ = _planner()
    assert planner.think_sampler == "greedy"


def test_cli_and_offline_flags_old_summary_and_escalation_inheritance(monkeypatch):
    args, _ = cli.build_parser(["serve"])
    assert not ({"think_budget", "think_on", "think_sampler"} &
                cli.planner_opts(args).keys())
    args, _ = cli.build_parser([
        "serve", "--planner-think", "512", "--planner-think-on", "retry",
        "--planner-think-sampler", "qwen"])
    assert cli.planner_opts(args) == {
        "done_alone": True, "few_shot": "prompts/planner_fewshot.md",
        "history": "dsl", "app_hints": False,
        "think_budget": 512, "think_on": "retry",
        "think_sampler": "qwen"}

    offline = planner_offline.build_parser().parse_args(
        ["--think", "32", "--think-on", "retry", "--think-sampler", "qwen"])
    assert (offline.think, offline.think_on, offline.think_sampler) == (
        32, "retry", "qwen")
    old = {"tags": ["single_step"], "pass": True, "strict_pass": True,
           "valid": True, "strict_valid": True, "skipped": 0,
           "ttft_ms": 20.0, "plan_ms": 100.0, "decode_tok_s": 12.0, "tokens": 5}
    summary = planner_offline.summarize("old", "model", {}, [old])
    assert summary["knobs"]["think"] == 0
    assert summary["knobs"]["think_on"] == "all"
    assert summary["knobs"]["think_sampler"] == "greedy"
    assert summary["think_tokens_mean"] is None and summary["think_ms_p50"] is None

    captured = {}

    class Server:
        def __init__(self, port):
            self.port = port

        async def start(self):
            pass

        async def close(self):
            pass

    class Orch:
        def __init__(self, *args, **kwargs):
            self.grounder_cfg = {}
            captured["orch"] = self

        async def handle_utterance(self, text, ctx=None):
            raise asyncio.CancelledError

        async def set_escalation(self, enabled):
            pass

        def _speculative_route(self, text, ctx=None):
            pass

        def _schedule_warm_planner(self, planner, tag="planner"):
            pass

    async def inputs():
        yield "stop"

    def make_planner(model, engine, opts, tag="planner", **_kw):
        captured.setdefault("planner_opts", []).append((model, dict(opts), tag))
        return object()

    monkeypatch.setattr(cli, "BrainServer", Server)
    monkeypatch.setattr(cli, "Orchestrator", Orch)
    monkeypatch.setattr(cli, "_resolve_model", lambda model: model)
    monkeypatch.setattr(cli, "_stdin_lines", inputs)
    monkeypatch.setattr(cli, "make_planner", make_planner)
    asyncio.run(cli.serve(
        planner_model="main", planner_kw={"think_budget": 512,
                                         "think_on": "retry",
                                         "think_sampler": "qwen"},
        escalate_model="big"))
    esc = captured["orch"].escalate_opts
    assert esc == {**cli.ESCALATE_OPTS, "think_budget": 512,
                   "think_on": "retry", "think_sampler": "qwen"}
    assert captured["planner_opts"][1] == ("big", esc, "planner-escalate")


@pytest.mark.parametrize("kwargs", [
    {"think_budget": -1}, {"think_on": "sometimes"},
    {"think_sampler": "nucleus"},
])
def test_invalid_thinking_options_raise(kwargs):
    with pytest.raises(ValueError):
        _planner(**kwargs)


# --- evals/planner_think_report.py: pre-registered ship rule ---

def _rows(n, n_pass, ms, think=0):
    return [{"pass": i < n_pass, "plan_ms": ms, "retrieval_ms": 1.0, "think_tokens": think} for i in range(n)]


def _st(mean, p50):
    return {"holdout_mean": mean, "p50_ms": p50}


def test_decide_gates_and_ties():
    best, notes = think_report.decide({"a": _st(0.70, 2000), "b": _st(0.70, 1500), "c": _st(0.80, 3500), "d": _st(0.66, 900)})
    assert best == "b"
    assert "c: FAIL (step p50 3500 ms > 3000)" in notes
    assert "d: FAIL (holdout mean 0.660 < 0.672)" in notes
    assert think_report.decide({"x": _st(0.672, 3000)})[0] == "x"
    assert think_report.decide({"y": _st(0.671, 100)}) == (None, ["y: FAIL (holdout mean 0.671 < 0.672)"])
    assert think_report.decide({"lo": _st(0.70, 100), "hi": _st(0.75, 2900)})[0] == "hi"


def test_load_and_stats(tmp_path, capsys):
    def put(name, rows):
        (tmp_path / f"think-{name}.json").write_text(json.dumps({"summary": {}, "rows": rows}))
    put("4b-t512-qwen-all-v1holdout", _rows(10, 7, 1000, 300))
    put("4b-t512-qwen-all-v1holdout2", _rows(10, 8, 2000, 300))
    put("4b-t512-qwen-all-v2holdout", _rows(20, 10, 3000, 300))
    put("4b-t512-qwen-all-v1tune", _rows(4, 4, 9000))
    put("4b-t0-greedy-all-v1holdout", _rows(10, 6, 100))
    stats = think_report.load(tmp_path, "think")
    assert list(stats) == ["4b-t512-qwen-all"] and "skip 4b-t0-greedy-all" in capsys.readouterr().out
    st = stats["4b-t512-qwen-all"]
    assert round(st["holdout_mean"], 3) == round((0.7 + 0.8 + 0.5) / 3, 3)
    assert st["p50_ms"] == 2501.0 and st["p95_ms"] == 3001.0     # holdout rows only, tune excluded
    assert st["rates"]["v1-tune"] == 1.0 and st["think_tokens_mean"] == 300
