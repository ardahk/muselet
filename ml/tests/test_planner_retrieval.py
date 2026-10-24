import asyncio
import sys
import threading
from pathlib import Path

import mlx.core as mx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))

import planner_offline
import planner_retrieval_report
from brain import cli
from brain import planner as P
from brain.catalog import Catalog
from brain.plan_bank import Demo, PlanBank, render_block
from test_planner_flags import _fake_engine


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
    seen = {}

    def fake_load(spec):
        seen["spec"] = spec
        return [_demo("open a clean task", "demo-id")]

    monkeypatch.setattr("brain.plan_bank.load_bank", fake_load)
    args, _ = cli.build_parser(["serve", "--planner-retrieval-k", "2",
                                "--planner-retrieval-bank", "x.jsonl"])
    opts = cli.planner_opts(args)
    assert opts["retrieval_k"] == 2 and opts["retrieval_bank"] == "x.jsonl"
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


def test_retrieval_summary_and_block_size_metrics_are_supported():
    demos = [_demo("create a new folder", "folder"), _demo("sort files by date", "sort")]
    bank = PlanBank(demos)
    hits = bank.retrieve("create a folder", "app: Finder | window: Desktop", 2)
    assert hits
    assert len(render_block(hits)) > 0
