"""decision.py unit tests. Model-dependent tests skip when the snapshot
isn't in the HF cache."""

import string

import pytest

from brain.decision import (AlphaChoiceRenderer, DecisionEngine,
                            normalize_delta, normalize_level, parse_duration,
                            parse_datetime)

_parse_args_line = DecisionEngine._parse_args_line


def test_duration_parser():
    assert parse_duration("ten minutes") == 600
    assert parse_duration("90 seconds") == 90
    assert parse_duration("1 hour 30 minutes") == 5400
    assert parse_duration("an hour and a half") == 5400
    assert parse_duration("a minute and a half") == 90
    assert parse_duration("half an hour") == 1800
    assert parse_duration("five minutes") == 300
    assert parse_duration("twenty minutes") == 1200
    assert parse_duration("garbage words") is None


def test_datetime_parser():
    iso = parse_datetime("tomorrow at noon")
    assert iso and "T12:00" in iso


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
