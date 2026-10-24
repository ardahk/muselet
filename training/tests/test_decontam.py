import json
from pathlib import Path

import pytest

from muselet_train.decontam import REPO, Index
from muselet_train.gen import DATA

EVALS = [REPO / "evals" / "route_v1.jsonl", REPO / "evals" / "live_t1.jsonl"]


def _eval_utterances() -> list[str]:
    return [json.loads(ln)["utterance"] for p in EVALS for ln in p.read_text().splitlines() if ln.strip()]


def test_rules_catch_near_copies():
    idx = Index(["set the volume to 40", "open the downloads folder in finder please right now ok"])
    assert idx.match("Set the volume to 40!")[0] == "exact"
    assert idx.match("set the volume to 40 please") is not None
    assert idx.match("what's the weather in Paris") is None


def _kept_files() -> list[Path]:
    return sorted(p for p in DATA.glob("*/route.jsonl") if (p.parent / "decontam.json").exists()) + sorted(
        p for p in DATA.glob("*/args.jsonl") if (p.parent / "decontam.json").exists())


@pytest.mark.parametrize("path", _kept_files(), ids=str)
def test_kept_items_do_not_match_evals(path: Path):
    idx = Index(_eval_utterances())
    bad = [r["utterance"] for r in map(json.loads, path.read_text().splitlines()) if idx.match(r["utterance"])]
    assert not bad, f"{len(bad)} kept items match route_v1/live_t1, e.g. {bad[:5]}"
