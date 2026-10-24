"""Planner LoRA data: demos (jonsnov/muselet-planner-demos-v1) rendered with the brain's own prompt builder.

Prompt = brain.planner.Planner.prompt_tokens (what plan() decodes from) with few_shot=None and retrieval_k=0:
system prompt, DSL history, no hint, login_page by the orchestrator's regex. Target = the demo's action batch.
Tokens come from the qwen3_5 renderer's build_supervised_example (empty think block); loss weights are 1 only on
the tokens plan() generates (the batch text + <|im_end|>), 0 on the prompt (incl. the think block plan() prefills).
"""

from __future__ import annotations

import collections
import gzip
import json
import random
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "ml" / "src"), str(REPO / "training" / "planner_demos"), str(REPO / "evals")]
DEMOS_REPO, DEMOS_REV = "jonsnov/muselet-planner-demos-v1", "9453ff6"
TOKENIZER = "mlx-community/Qwen3.5-4B-4bit"     # identical vocab/encoding to Qwen/Qwen3.5-4B (checked)
BASE_MODEL = "Qwen/Qwen3.5-4B"
LOGIN_RE = re.compile(r"\b(?:sign\s*in|sign-in|log\s*in|login|password)\b", re.IGNORECASE)  # orchestrator.py
DEV_FRAC, DEV_SEED = 0.05, 0


def load_demos(path: str | None = None) -> list[dict]:
    if path is None:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(DEMOS_REPO, "demos.jsonl.gz", repo_type="dataset", revision=DEMOS_REV)
    return [json.loads(x) for x in gzip.open(path, "rt") if x.strip()]


def make_planner():
    """Weightless Planner: real system prompt and rendering, no model (engine stub carries the renderer)."""
    from brain.catalog import Catalog
    from brain.decision import RouteRenderer
    from brain.planner import Planner
    cat = Catalog.load()
    rr = RouteRenderer(TOKENIZER, cat)
    eng = SimpleNamespace(model_path="tokenizer-only", model=None, tokenizer=rr.tokenizer, body=None, lm_head=None,
                          rr=rr, catalog=cat)
    return Planner("tokenizer-only", cat, engine=eng, few_shot=None, retrieval_k=0)


def login_page(state: dict) -> bool:
    window = re.match(r'^app: [^|]+ \| window: "((?:[^"\\]|\\.)*)"', state["observation"])
    return bool(LOGIN_RE.search(f"{window[1] if window else ''}\n{state['observation']}"))


def plan_args(state: dict) -> tuple:
    from brain.planner import history
    return (state["goal"], state["observation"], history(state.get("last_batch"), "dsl"), None,
            state.get("script_output"), login_page(state))


def render(planner, state: dict, completion: str) -> dict:
    """{'tokens', 'weights', 'n_prompt'}; asserts the supervised rendering extends plan()'s prompt exactly."""
    from tinker_cookbook.renderers import Message
    prompt = planner.prompt_tokens(*plan_args(state))
    msgs = [Message(role="system", content=planner.system),
            Message(role="user", content=planner.user_content(*plan_args(state))),
            Message(role="assistant", content=completion)]
    mi, w = planner.rr.renderer.build_supervised_example(msgs)
    toks, w = mi.to_ints(), [float(x) for x in w.tolist()]
    n = len(prompt)
    assert toks[:n] == prompt, f"supervised rendering diverges from plan() prompt: {state['goal']!r}"
    assert all(x > 0 for x in w[n:]) and toks[-1] == planner.tokenizer.convert_tokens_to_ids("<|im_end|>")
    return {"tokens": toks, "weights": [0.0] * n + [1.0] * (len(toks) - n), "n_prompt": n}


def split(demos: list[dict]) -> tuple[list[dict], list[dict]]:
    """5% dev (seed 0) for checkpoint selection; the rest trains."""
    ids = sorted(d["id"] for d in demos)
    random.Random(DEV_SEED).shuffle(ids)
    dev = set(ids[:round(DEV_FRAC * len(ids))])
    return [d for d in demos if d["id"] not in dev], [d for d in demos if d["id"] in dev]


def _git_show(ref_path: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), "show", ref_path], capture_output=True, text=True, check=True).stdout


def gate_report(demos: list[dict]) -> dict:
    """training/planner_demos/gate.py (v1 tune/holdout/holdout2, v2-holdout, live_t1, HobbyLM sealed r1-r4 + calc +
    system-settings, DeskMind diag/dyn/proposals; exact, shared 13-gram, short-item edit <= 1, CJK-aware, same
    (goal, observation) scenario) plus the router evals route_v1*.jsonl and route_v2.jsonl (origin/cloud/data-pipeline)."""
    import gate as G
    g = G.Gate()
    extra = []
    for p in sorted((REPO / "evals").glob("route_v1*.jsonl")):
        extra += [(p.stem, json.loads(x)["utterance"]) for x in p.read_text().splitlines() if x.strip()]
    try:
        extra += [("route_v2", json.loads(x)["utterance"])
                  for x in _git_show("origin/cloud/data-pipeline:evals/route_v2.jsonl").splitlines() if x.strip()]
    except subprocess.CalledProcessError:
        raise SystemExit("route_v2.jsonl not found on origin/cloud/data-pipeline (git fetch first)")
    for src, t in extra:
        g.counts[src] += 1
        tk = G.norm(t).split()
        if tk:
            e = (src, t, tk)
            g.exact[" ".join(tk)].append(e)
            for gr in G._grams(tk):
                g.grams[gr].append(e)
            g.by_len[len(tk)].append(e)
    hits = collections.Counter()
    pairs = []
    for d in demos:
        for h in g.hits(d["state"]["goal"], d["state"]["observation"]):
            hits[(h["eval"], h["rule"])] += 1
            pairs.append({"id": d["id"], "goal": d["state"]["goal"], **h})
    return {"eval_items": dict(sorted(g.counts.items())), "demos": len(demos),
            "hits": {f"{k[0]}|{k[1]}": v for k, v in sorted(hits.items())}, "pairs": pairs}


def to_lines(text: str) -> list[str]:
    """Reply text -> planner lines as the runtime stream cuts them (keep.py / plan())."""
    import keep
    return keep.to_lines(text)


def grade(state: dict, lines: list[str]) -> dict:
    import planner_offline as po
    return po.grade(state, lines)


def clean(demos: list[dict]) -> tuple[list[dict], dict]:
    """Drop every demo the extended gate flags; returns (clean demos, gate report of the input)."""
    rep = gate_report(demos)
    bad = {p["id"] for p in rep["pairs"]}
    return [d for d in demos if d["id"] not in bad], rep
