"""decision.py unit tests. Model-dependent tests skip when the snapshot
isn't in the HF cache."""

import string
from datetime import datetime
from types import SimpleNamespace

import pytest

try:
    import mlx.core as mx
except ImportError:  # the args-model fixture skips without MLX
    mx = None

from brain import cli, decision, planner
from brain.catalog import Catalog
from brain.decision import (AlphaChoiceRenderer, DecisionEngine, RouteRenderer,
                            catalog_options, normalize_delta, normalize_level,
                            parse_datetime, parse_duration, split_model)

_parse_args_line = DecisionEngine._parse_args_line


@pytest.mark.parametrize("text,secs", [
    ("ten minutes", 600), ("90 seconds", 90), ("five minutes", 300),
    ("twenty minutes", 1200), ("a minute and a half", 90),
    ("one hour twenty five minutes", 5100), ("ninety seconds", 90),
    ("twenty five minutes", 1500), ("forty-five minutes", 2700),
    ("thirteen minutes", 780), ("fifty seconds", 50),
    ("an hour and a half", 5400), ("1 hour and a half", 5400),
    ("two and a half hours", 9000), ("half an hour", 1800),
    ("10 minutes", 600), ("1 hour 30 minutes", 5400), ("a minute", 60),
    ("garbage words", None), ("five", None), ("soon", None),
])
def test_duration_parser(text, secs):
    assert parse_duration(text) == secs


def test_datetime_parser():
    iso = parse_datetime("tomorrow at noon")
    assert iso and "T12:00" in iso


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


def test_level_normalization():
    assert normalize_level("max") == 100
    assert normalize_level("full") == 100
    assert normalize_level("half") == 50
    assert normalize_level("30") == 30
    assert normalize_level(45) == 45
    assert normalize_level("junk") is None


def test_delta_normalization():
    assert normalize_delta("a bit") == 10
    assert normalize_delta("a little") == 10
    assert normalize_delta("a lot") == 25
    assert normalize_delta("10") == 10
    assert normalize_delta("a bit", "down") == -10


def test_args_line_parser():
    assert _parse_args_line('level=30') == {"level": "30"}
    assert _parse_args_line('title="Lunch with Sam" start="tomorrow at noon"') \
        == {"title": "Lunch with Sam", "start": "tomorrow at noon"}
    assert _parse_args_line('missing=duration') == {"missing": "duration"}
    assert _parse_args_line('query="hello world" limit=5') == \
        {"query": "hello world", "limit": "5"}


def test_args_line_strips_trailing_punct():
    p = DecisionEngine._parse_args_line
    assert p("parent=~/Desktop, name=receipts", {"parent", "name"}) == \
        {"parent": "~/Desktop", "name": "receipts"}
    assert p("level=30.", {"level"}) == {"level": "30"}
    assert p("app=Safari;", {"app"}) == {"app": "Safari"}
    assert p('body="buy milk."', {"body"}) == {"body": "buy milk."}


def test_hidden_router_skill_does_not_change_route_question():
    base = Catalog({"skills": [
        {"name": "a", "description": "A"},
    ], "special_options": [{"name": "ASK", "description": "Ask"}]})
    with_hidden = Catalog({"skills": [
        {"name": "a", "description": "A"},
        {"name": "hidden", "description": "H", "router": False},
    ], "special_options": [{"name": "ASK", "description": "Ask"}]})
    left, right = RouteRenderer.__new__(RouteRenderer), \
        RouteRenderer.__new__(RouteRenderer)
    left._options, right._options = catalog_options(base), \
        catalog_options(with_hidden)
    utterance, ctx = "write a short note", {"app": "Notes"}
    assert left.decision(utterance, ctx).text == \
        right.decision(utterance, ctx).text
    assert left.decision(utterance, ctx).choices == \
        right.decision(utterance, ctx).choices

class _FakeTok:
    """Enough of the HF tokenizer API for _content_cut + alphabet filter."""
    def encode(self, s, add_special_tokens=False):
        # one token per char for determinism
        return [ord(c) for c in s]

    def decode(self, toks):
        return "".join(chr(t) for t in toks)


class _FakeRenderer:
    tokenizer = _FakeTok()


def test_content_cut():
    from brain.decision import DecisionEngine
    eng = DecisionEngine.__new__(DecisionEngine)
    eng.tokenizer = _FakeTok()
    toks = [ord(c) for c in "hello SENTINELMARKER9Z world"]
    assert eng._content_cut(toks, "SENTINELMARKER9Z") == 6
    with pytest.raises(RuntimeError):
        eng._content_cut([1, 2, 3], "SENTINELMARKER9Z")


def test_alphabet_rule_fake():
    cr = AlphaChoiceRenderer(_FakeRenderer())
    # every char maps to one token in the fake tokenizer -> all 62 usable
    assert len(cr.usable_ids) == 62
    assert cr.usable_ids[:4] == list("ABCD")


# ---------- split_model: untied lm_head vs tied embedding ----------

# split_model must use an untied lm_head when the model has one (Qwen3.5-9B,
# Qwen3.6-35B-A3B keep it at model.language_model.lm_head) and fall back to the
# tied embedding only when there is none (Qwen3.5-4B).

def _wrapper(lm_head):
    embed = SimpleNamespace(as_linear="tied-embedding")
    body = SimpleNamespace(embed_tokens=embed)
    lm = SimpleNamespace(model=body, lm_head=lm_head) if lm_head else SimpleNamespace(model=body)
    return SimpleNamespace(model=body, language_model=lm), body


def test_untied_head_on_language_model_is_used():
    model, body = _wrapper("untied-head")
    inner, head = split_model(model)
    assert inner is body
    assert head == "untied-head"


def test_tied_model_falls_back_to_embedding():
    model, body = _wrapper(None)
    inner, head = split_model(model)
    assert inner is body
    assert head == "tied-embedding"


# ---------- ROUTE and ARGS on separate models (addendum d; fakes, no weights) ----------

V = 16
SENT = [7, 8]                     # "SENTINELMARKER9Z"
WORDS = {10: "level", 11: "=30", 12: "=99"}


class _ArgsTok:
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
    pytest.importorskip("mlx.core")
    pytest.importorskip("mlx_lm")
    lms = {"A": FakeLM("A", [3, 1]), "B": FakeLM("B", [10, 11, 1])}
    loads = {"mlx_lm": [], "load_model": []}

    def mk(path):
        return SimpleNamespace(lm=lms[path]), _ArgsTok()

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
    pytest.importorskip("mlx_lm")
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
                         escalate_model=None, grounder=None,
                         verify_done=True, open_ended_route=False,
                         planner_aux_model=None, **_kw):
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

_MODEL = "mlx-community/Qwen3.5-0.8B-4bit"


def _model_available():
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(_MODEL, local_files_only=True)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _model_available(), reason="model not cached")
def test_alphabet_and_prefix_real_model():
    """Real Qwen3.5 tokenizer: >=40 usable ids; prefix assert holds."""
    from brain.catalog import Catalog
    from brain.decision import DecisionEngine
    eng = DecisionEngine(_MODEL, Catalog.load())
    assert len(eng.choice_renderer.usable_ids) >= 40
    eng._build_route_cache()
    r = eng.route("set volume to 30", {"app": "Finder", "focused": "none",
                                       "selection": False,
                                       "last_action": "none"})
    assert r.top in r.probs
    assert abs(sum(r.probs.values()) - 1.0) < 1e-3
    assert r.p_top > 0
