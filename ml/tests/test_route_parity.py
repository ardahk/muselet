"""Token-level parity with the training side's reference file
(training/artifacts/route_render_samples.jsonl, produced on cloud/data-pipeline).
Uses only the locally cached Qwen3.5 tokenizer — no model weights."""

import json
from pathlib import Path

import pytest

from brain.catalog import Catalog
from brain.decision import RouteRenderer, ARGS_SYSTEM, ARGS_USER

SAMPLES = Path(__file__).resolve().parents[2] / \
    "training" / "artifacts" / "route_render_samples.jsonl"
MODEL = "mlx-community/Qwen3.5-0.8B-4bit"
MODEL4B = "mlx-community/Qwen3.5-4B-4bit"


def _snapshot(repo):
    try:
        from huggingface_hub import snapshot_download
        return snapshot_download(repo, local_files_only=True)
    except Exception:
        return None


_SNAP = _snapshot(MODEL)
pytestmark = pytest.mark.skipif(_SNAP is None,
                                reason="Qwen3.5-0.8B tokenizer not cached")


@pytest.fixture(scope="module")
def rr():
    return RouteRenderer(_SNAP, Catalog.load())


@pytest.fixture(scope="module")
def samples():
    return [json.loads(l) for l in SAMPLES.read_text().splitlines()
            if l.strip()]


def test_tokenizer_parity_08b_vs_4b():
    """Both snapshots must tokenize the samples identically."""
    snap4 = _snapshot(MODEL4B)
    if snap4 is None:
        pytest.skip("4B snapshot incomplete")
    from tinker_cookbook import tokenizer_utils
    t8 = tokenizer_utils.get_tokenizer(_SNAP)
    t4 = tokenizer_utils.get_tokenizer(snap4)
    rows = [json.loads(l) for l in SAMPLES.read_text().splitlines()[1:]]
    for r in rows:
        e8 = t8.encode(r["utterance"], add_special_tokens=False)
        e4 = t4.encode(r["utterance"], add_special_tokens=False)
        assert e8 == e4, f"tokenizer mismatch on {r['utterance']!r}"


def test_header_parity(rr, samples):
    h = samples[0]
    assert h["kind"] == "header"
    cat = Catalog.load()
    ours = [n for n, _ in rr.options]
    theirs = [o["name"] for o in h["options"]]
    if theirs != ours:
        pytest.xfail(
            f"samples are for a different catalog (v{cat.version} has "
            f"{len(ours)} options, samples have {len(theirs)}); "
            "xfails until the training side regenerates the file")
    # (a) option names+order match our options
    assert theirs == ours
    # (b) id alphabet, prefix tokens, id tokens
    assert h["id_alphabet"] == "".join(rr.id_alphabet)
    assert h["prefix_tokens"] == \
        rr.tokenizer.encode("choice#", add_special_tokens=False)
    ids = rr.id_alphabet
    prefix = rr.tokenizer.encode("choice#", add_special_tokens=False)
    for name, opt in zip([o["name"] for o in h["options"]],
                         h["options"]):
        c = ids[h["options"].index(opt)]
        toks = rr.tokenizer.encode("choice#" + c, add_special_tokens=False)
        assert toks == prefix + [h["id_tokens"][c]], f"id token {c}"


@pytest.mark.parametrize("i", range(50))
def test_sample_parity(rr, samples, i):
    """Every rendered sample must match tokens + choice_pos exactly."""
    cat = Catalog.load()
    if [o["name"] for o in samples[0]["options"]] != [n for n, _ in rr.options]:
        pytest.xfail(
            f"samples are for a different catalog (v{cat.version}); "
            "xfails until the training side regenerates the file")
    row = samples[i + 1]
    ctx = {k: (v if v is not None else "none") if k != "online"
           else v for k, v in row["context"].items()}
    r = rr.render(row["utterance"], ctx)
    assert r.tokens == row["tokens"], \
        f"sample {i} token mismatch (len {len(r.tokens)} vs {len(row['tokens'])})"
    assert r.choice_pos == row["choice_pos"]


def test_args_templates():
    """ARGS templates must match the training side verbatim
    (training/src/muselet_train/route_render.py on cloud/data-pipeline)."""
    assert ARGS_SYSTEM == (
        "You extract arguments for a macOS assistant skill from the user's "
        "spoken request. Reply with one line of key=value pairs using the skill's "
        "argument names. Quote values that contain spaces. Copy spoken dates, "
        "times and durations exactly as said; do not convert them. Convert spoken "
        "numbers to digits. If a required argument is missing, reply "
        "missing=<argument name>.")
    assert ARGS_USER == (
        'Skill: {name}({sig})\nContext: app={app} | last_action={last}\n'
        'Request: "{request}"')
