"""Addendum (d): ROUTE and ARGS on separate models (fakes, no weights)."""
from types import SimpleNamespace

import mlx.core as mx
import pytest

from brain import cli, decision, planner
from brain.catalog import Catalog

V = 16
SENT = [7, 8]                     # "SENTINELMARKER9Z"
WORDS = {10: "level", 11: "=30", 12: "=99"}


class FakeTok:
    eos_token_id = 1

    def encode(self, s, add_special_tokens=False):
        if s == "SENTINELMARKER9Z":
            return list(SENT)
        return {"<|im_end|>": [2], "\n": [3]}.get(s, [9, 9])

    def decode(self, ids):
        return "".join(WORDS.get(i, "") for i in ids)


class FakeLM:
    """body/lm_head that record calls; lm_head emits `script` then eos."""

    def __init__(self, name, script):
        self.name, self.script, self.calls, self.i = name, script, [], 0

    def body(self, tokens, cache=None):
        self.calls.append(tokens.shape[1])
        return mx.zeros((1, tokens.shape[1], 1))

    def lm_head(self, out):
        nxt = self.script[self.i % len(self.script)]
        self.i += 1
        row = [0.0] * V
        row[nxt] = 1.0
        return mx.array([[row]])


class FakeRR:
    def __init__(self, path, catalog):
        self.path, self.options = path, [("A", "a"), ("B", "b")]
        self.route_renderer = SimpleNamespace(
            renderer=SimpleNamespace(build_supervised_example=self._sup),
            render=lambda d: SimpleNamespace(
                tokens=[0, 5] + SENT + [6, 6], choice_pos=5,
                labels=["A", "B"], label_tokens={"A": 3, "B": 4}))
        self.choice_renderer = None

    def decision(self, utt, ctx):
        return utt

    @staticmethod
    def _sup(msgs):
        m = msgs[1]
        user = m["content"] if isinstance(m, dict) else m.content
        mid = SENT if user == "SENTINELMARKER9Z" else [6, 6, 6]
        return SimpleNamespace(to_ints=lambda: [0, 5] + mid + SENT), None


@pytest.fixture
def fake_models(monkeypatch):
    lms = {"A": FakeLM("A", [3, 1]), "B": FakeLM("B", [10, 11, 1])}
    loads = {"mlx_lm": [], "load_model": []}

    def mk(path):
        return SimpleNamespace(lm=lms[path]), FakeTok()

    def mlx_load(path):
        loads["mlx_lm"].append(path)
        return mk(path)

    def load_model(path):
        loads["load_model"].append(path)
        return mk(path)

    monkeypatch.setattr(decision.mlx_lm, "load", mlx_load)
    monkeypatch.setattr(planner, "load_model", load_model)
    monkeypatch.setattr(decision, "split_model",
                        lambda m: (m.lm.body, m.lm.lm_head))
    monkeypatch.setattr(decision, "RouteRenderer", FakeRR)
    import mlx_lm.models.cache as mc
    monkeypatch.setattr(mc, "make_prompt_cache", lambda m: [])
    return lms, loads


def test_route_on_a_args_on_b(fake_models):
    lms, loads = fake_models
    eng = decision.DecisionEngine("A", Catalog.load(), args_model_path="B")
    assert eng.args_model_path == "B"
    assert loads == {"mlx_lm": ["A"], "load_model": ["B"]}
    assert eng.args_rr.path == "B" and eng.rr.path == "A"
    r = eng.route("turn it up", {"online": True})
    assert r.top == "A"
    assert lms["A"].calls and not lms["B"].calls
    a_calls = len(lms["A"].calls)
    out = eng.args("set_volume", "volume to thirty", {})
    assert out["_raw"] == "level=30" and out["level"] == "30"
    assert len(lms["A"].calls) == a_calls        # ARGS never touched model A
    assert lms["B"].calls


def test_default_args_model_is_route_model(fake_models):
    lms, loads = fake_models
    lms["A"].script = [10, 12, 1]
    eng = decision.DecisionEngine("A", Catalog.load())
    assert eng.args_model_path == "A"
    assert eng.args_model is eng.model and eng.args_rr is eng.rr
    assert loads == {"mlx_lm": ["A"], "load_model": []}
    out = eng.args("set_volume", "volume to ninety nine", {})
    assert out["_raw"] == "level=99"
    assert not lms["B"].calls


def test_same_path_is_default(fake_models):
    _, loads = fake_models
    eng = decision.DecisionEngine("A", Catalog.load(), args_model_path="A")
    assert eng.args_model is eng.model and loads["load_model"] == []


def test_separate_prefix_caches(fake_models):
    lms, _ = fake_models
    eng = decision.DecisionEngine("A", Catalog.load(), args_model_path="B")
    eng.route("x", {"online": True})
    eng.args("set_volume", "volume to thirty", {})
    assert eng._route_cache is not None and eng._args_cache is not None
    b_calls = len(lms["B"].calls)
    eng.args("set_volume", "volume to thirty", {})   # cached prefix reused
    assert lms["B"].calls[b_calls] == 3              # only the user content


def test_args_model_shared_with_planner_via_load_model():
    planner._MODELS.clear()
    calls = []
    orig = planner.mlx_lm.load
    try:
        planner.mlx_lm.load = lambda p: calls.append(p) or (object(), object())
        assert planner.load_model("B") is planner.load_model("B")
        assert calls == ["B"]
    finally:
        planner.mlx_lm.load = orig
        planner._MODELS.clear()


def test_cli_args_model_flags():
    a, _ = cli.build_parser(["serve"])
    assert a.args_model is None
    a, _ = cli.build_parser(["serve", "--model", "A", "--args-model", "B"])
    assert (a.model, a.args_model) == ("A", "B")
    e, _ = cli.build_parser(["eval-route", "--cases", "c", "--args-model", "B"])
    assert e.args_model == "B"


def test_cli_serve_passes_args_model(monkeypatch):
    seen = {}

    async def fake_serve(port, model, pmodel, pkw, args_model=None,
                         escalate_model=None, grounder=None):
        seen.update(model=model, args_model=args_model)

    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setattr(cli, "_resolve_model", lambda m: f"/m/{m}")
    cli.run_cmd(*cli.build_parser(["serve", "--model", "A", "--args-model", "B"]))
    assert seen == {"model": "/m/A", "args_model": "/m/B"}
    seen.clear()
    cli.run_cmd(*cli.build_parser(["serve", "--model", "A"]))
    assert seen == {"model": "/m/A", "args_model": None}


def test_cli_eval_route_passes_args_model(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "eval_route",
                        lambda *a, **k: seen.update(k))
    cli.run_cmd(*cli.build_parser(["eval-route", "--cases", "c.jsonl",
                                   "--args-model", "B"]))
    assert seen["args_model"] == "B"
