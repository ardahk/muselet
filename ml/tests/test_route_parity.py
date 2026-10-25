"""Token-level parity with the training side's reference files, one per catalog:
route_render_samples.jsonl (skills/catalog.json, v2: r2/it2) and
route_render_samples_v3.jsonl (training/artifacts/catalog_v3.json: it3),
both produced on cloud/data-pipeline by muselet_train.render_samples.
Also planner LoRA samples (planner_lora_render_samples.jsonl) vs the brain
planner prompt builder on the 4B tokenizer.
Uses only the locally cached Qwen3.5 tokenizers — no model weights. Each test
skips on its own missing snapshot."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from brain.catalog import Catalog
from brain.decision import RouteRenderer, ARGS_SYSTEM, ARGS_USER
from brain.planner import FEWSHOT_PATH, Planner, history

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "training" / "artifacts" / "route_render_samples.jsonl"
CATALOGS = {"v2": (ROOT / "skills" / "catalog.json", SAMPLES),
            "v3": (ROOT / "training" / "artifacts" / "catalog_v3.json",
                   ROOT / "training" / "artifacts" / "route_render_samples_v3.jsonl")}
MODEL = "mlx-community/Qwen3.5-0.8B-4bit"
MODEL4B = "mlx-community/Qwen3.5-4B-4bit"
LORA_SAMPLES = ROOT / "training" / "artifacts" / \
    "planner_lora_render_samples.jsonl"
LOGIN_RE = re.compile(
    r"\b(?:sign\s*in|sign-in|log\s*in|login|password)\b", re.IGNORECASE)


def _snapshot(repo):
    try:
        from huggingface_hub import snapshot_download
        return snapshot_download(repo, local_files_only=True)
    except Exception:
        return None


_SNAP = _snapshot(MODEL)
_SNAP4B = _snapshot(MODEL4B)
needs_08b = pytest.mark.skipif(_SNAP is None,
                               reason="Qwen3.5-0.8B tokenizer not cached")
needs_4b = pytest.mark.skipif(_SNAP4B is None,
                              reason="Qwen3.5-4B tokenizer not cached")


@pytest.fixture(scope="module", params=sorted(CATALOGS))
def which(request):
    return request.param


@pytest.fixture(scope="module")
def cat(which):
    return Catalog.load(CATALOGS[which][0])


@pytest.fixture(scope="module")
def rr(cat):
    return RouteRenderer(_SNAP, cat)


@pytest.fixture(scope="module")
def samples(which):
    return [json.loads(l) for l in CATALOGS[which][1].read_text().splitlines()
            if l.strip()]


@needs_08b
@needs_4b
def test_tokenizer_parity_08b_vs_4b():
    """Both snapshots must tokenize the samples identically."""
    from tinker_cookbook import tokenizer_utils
    t8 = tokenizer_utils.get_tokenizer(_SNAP)
    t4 = tokenizer_utils.get_tokenizer(_SNAP4B)
    rows = [json.loads(l) for l in SAMPLES.read_text().splitlines()[1:]]
    for r in rows:
        e8 = t8.encode(r["utterance"], add_special_tokens=False)
        e4 = t4.encode(r["utterance"], add_special_tokens=False)
        assert e8 == e4, f"tokenizer mismatch on {r['utterance']!r}"


@needs_08b
def test_header_parity(rr, samples, cat):
    h = samples[0]
    assert h["kind"] == "header"
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


@needs_08b
@pytest.mark.parametrize("i", range(50))
def test_sample_parity(rr, samples, cat, i):
    """Every rendered sample must match tokens + choice_pos exactly."""
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


# --- Planner LoRA samples vs brain planner prompt (4B tokenizer) ---

@pytest.fixture(scope="module")
def planners():
    catalog = Catalog.load()
    rr = RouteRenderer(_SNAP4B, catalog)
    engine = SimpleNamespace(
        model_path=_SNAP4B,
        model=None,
        tokenizer=rr.tokenizer,
        body=None,
        lm_head=None,
        rr=rr,
        catalog=catalog,
    )
    return (
        Planner(_SNAP4B, catalog, engine=engine, few_shot=None, retrieval_k=0),
        Planner(_SNAP4B, catalog, engine=engine, few_shot=FEWSHOT_PATH,
                retrieval_k=0),
    )


def _lora_samples():
    rows = [json.loads(line) for line in LORA_SAMPLES.read_text().splitlines()
            if line.strip()]
    assert rows[0]["meta"] == {
        "demos": "jonsnov/muselet-planner-demos-v1@9453ff6",
        "tokenizer": MODEL4B,
        "few_shot": None,
        "retrieval_k": 0,
    }
    return rows[1:]


def _login_page(observation):
    window = re.match(
        r'^app: [^|]+ \| window: "((?:[^"\\]|\\.)*)"', observation)
    title = window[1] if window else ""
    return bool(LOGIN_RE.search(f"{title}\n{observation}"))


@needs_4b
def test_sample_tokens_match_brain_planner(planners):
    planner, default_planner = planners
    rows = _lora_samples()
    im_end_id = planner.tokenizer.convert_tokens_to_ids("<|im_end|>")

    for row in rows:
        state = row["state"]
        prompt = planner.prompt_tokens(
            state["goal"],
            state["observation"],
            history(state.get("last_batch"), "dsl"),
            None,
            state.get("script_output"),
            _login_page(state["observation"]),
        )

        assert row["n_prompt"] == len(prompt), row["id"]
        assert row["tokens"][:row["n_prompt"]] == prompt, row["id"]
        expected_completion = planner.tokenizer.encode(
            row["completion"], add_special_tokens=False) + [im_end_id]
        assert row["tokens"][row["n_prompt"]:] == expected_completion, row["id"]

        default_prompt = default_planner.prompt_tokens(
            state["goal"],
            state["observation"],
            history(state.get("last_batch"), "dsl"),
            None,
            state.get("script_output"),
            _login_page(state["observation"]),
        )
        assert len(default_prompt) > len(prompt), row["id"]
