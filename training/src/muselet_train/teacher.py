"""Teacher soft labels on Tinker (SPEC 1.4). sample_decision needs 36 target ids in one request,
which Tinker rejects (<= 20); chunked splits ids, topk uses top-20 prompt logprobs.

  python -m muselet_train.teacher --run R --limit 500 [--subset stratified] [--phase1-spent 0.4]
Reads /data/gen/<run>/route.jsonl, writes teacher.jsonl (teacher_probs, target, needs_adjudication)
and teacher_tokens.json (prompt tokens per call type). --limit is required; 0 means all selected rows.
A pre-flight estimate aborts the run if it exceeds the remaining Phase-1 budget minus the training reserve.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random

import tinker
import torch

from muselet_train.catalog import option_names
from muselet_train.gen import DATA, _load
from muselet_train.route_render import RouteContext, render_route

TEACHER = "Qwen/Qwen3.6-35B-A3B"  # lead: 397B only on the small adjudication subsets
TEACHER_397B = "Qwen/Qwen3.5-397B-A17B"
PHASE1_CAP, TRAIN_RESERVE, TEACHER_CAP = 60.0, 35.0, 12.0
# $/1M tokens (SPEC); cached prefill = 20% of prefill. SPEC lists no sample price: train price is used as an upper bound.
PRICES = {TEACHER: {"prefill": 0.45, "sample": 1.17}, TEACHER_397B: {"prefill": 1.65, "sample": 1.65}}
STRATIFIED_ALL = ("ASK", "REFUSE", "MULTI_STEP", "finance_review")
STRATIFIED_REST = 0.30
ADJ_P = 0.7
CHUNK = 18  # Tinker: <= 20 distinct target ids per request at our prompt length


TOKENS = {"first_chunk_prompt": 0, "later_chunk_prompt": 0, "sampled": 0, "calls": 0}


def n_chunks(n_labels: int) -> int:
    return -(-n_labels // CHUNK)


def estimate(model: str, prompt_tokens: list[int], n_labels: int) -> float:
    p = PRICES[model]
    k = n_chunks(n_labels)
    tok = sum(prompt_tokens)
    return (tok * p["prefill"] + (k - 1) * tok * 0.2 * p["prefill"] + len(prompt_tokens) * k * p["sample"]) / 1e6


async def chunked_decision(client, rendering) -> dict[str, float]:
    """Exact softmax over all choice tokens via several <= CHUNK-id target_prompt_logprobs calls."""
    labels = rendering.labels

    async def part(ls):
        t = torch.full((len(rendering.tokens) - 1, len(ls)), -1, dtype=torch.int64)
        t[rendering.choice_pos - 1] = torch.tensor([rendering.label_tokens[x] for x in ls])
        r = await client.sample_async(
            prompt=tinker.ModelInput.from_ints(rendering.tokens), num_samples=1,
            sampling_params=tinker.SamplingParams(max_tokens=1),
            target_prompt_logprobs=tinker.TensorData.from_torch_sparse(t, pad_value=-1))
        if r.target_prompt_logprobs is None:
            raise RuntimeError("target_prompt_logprobs not returned for this model")
        TOKENS["first_chunk_prompt" if ls[0] == labels[0] else "later_chunk_prompt"] += len(rendering.tokens)
        TOKENS["sampled"] += 1
        TOKENS["calls"] += 1
        return r.target_prompt_logprobs.to_torch()[rendering.choice_pos - 1].tolist()

    first = await part(labels[:CHUNK])  # warm the prefix cache before the remaining chunks
    rest = await asyncio.gather(*(part(labels[i:i + CHUNK]) for i in range(CHUNK, len(labels), CHUNK)))
    lp = torch.tensor(first + [x for r in rest for x in r])
    return dict(zip(labels, torch.softmax(lp.float(), 0).tolist(), strict=True))


async def topk_decision(client, rendering, k: int = 20) -> dict[str, float]:
    """Top-k prompt logprobs at the answer position; ids outside the top-k get the k-th logprob."""
    r = await client.sample_async(
        prompt=tinker.ModelInput.from_ints(rendering.tokens[:rendering.choice_pos + 1]), num_samples=1,
        sampling_params=tinker.SamplingParams(max_tokens=1), include_prompt_logprobs=True,
        topk_prompt_logprobs=k, prompt_logprobs_last_n=1)
    ids, lps = r.topk_prompt_logprobs_np.token_ids[-1], r.topk_prompt_logprobs_np.logprobs[-1]
    got = {int(i): float(v) for i, v in zip(ids, lps)}
    floor = min(got.values())
    lp = torch.tensor([got.get(rendering.label_tokens[x], floor) for x in rendering.labels])
    return dict(zip(rendering.labels, torch.softmax(lp, 0).tolist(), strict=True))


def blend(label: str, probs: dict[str, float]) -> dict[str, float]:
    t = {k: 0.4 * v for k, v in probs.items()}
    t[label] = t.get(label, 0.0) + 0.6
    z = sum(t.values())
    return {k: v / z for k, v in t.items()}


def stratified(rows: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed)
    return [r for r in rows if r["label"] in STRATIFIED_ALL or r.get("v2_reason") or rng.random() < STRATIFIED_REST]


async def run(run_name: str, model: str, limit: int, concurrency: int, seed: int, out_name: str,
              labels: list[str] | None, method: str, infile: str, subset: str, phase1_spent: float) -> None:
    score = {"chunked": chunked_decision, "topk": topk_decision}[method]
    rows = _load(run_name, infile)
    if labels:
        rows = [r for r in rows if r["label"] in labels]
    if subset == "stratified":
        rows = stratified(rows, seed)
    if 0 < limit < len(rows):
        rows = random.Random(seed).sample(rows, limit)
    names = option_names()
    renders = [render_route(RouteContext(**r["context"]), r["utterance"], model=model) for r in rows]
    est = estimate(model, [len(x.tokens) for x in renders], len(names))
    budget = min(PHASE1_CAP - phase1_spent - TRAIN_RESERVE, TEACHER_CAP)
    print(json.dumps({"items": len(rows), "model": model, "chunks": n_chunks(len(names)),
                      "prompt_tokens": sum(len(x.tokens) for x in renders), "est_usd": round(est, 2),
                      "budget_usd": round(budget, 2)}), flush=True)
    if est > budget:
        raise SystemExit(f"pre-flight estimate ${est:.2f} exceeds budget ${budget:.2f}; aborting")
    client = tinker.ServiceClient().create_sampling_client(base_model=model)
    sem = asyncio.Semaphore(concurrency)

    async def one(r: dict, rendering) -> dict:
        async with sem:
            probs = await score(client, rendering)
        top = max(probs, key=probs.get)
        return {**r, "teacher_model": model, "teacher_probs": probs, "teacher_argmax": top,
                "teacher_p": probs[top], "teacher_method": method, "prompt_tokens": len(rendering.tokens),
                "needs_adjudication": top != r["label"] and probs[top] >= ADJ_P,
                "target": blend(r["label"], probs)}

    out = await asyncio.gather(*(one(r, x) for r, x in zip(rows, renders, strict=True)))
    assert all(set(o["teacher_probs"]) == set(names) for o in out)
    (DATA / run_name / out_name).write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out))
    (DATA / run_name / out_name.replace(".jsonl", "_tokens.json")).write_text(
        json.dumps({"model": model, "items": len(out), "est_usd": est, **TOKENS}))
    toks = sum(o["prompt_tokens"] for o in out)
    agree = sum(o["teacher_argmax"] == o["label"] for o in out)
    print(json.dumps({"items": len(out), "prompt_tokens": toks, "agree": agree,
                      "needs_adjudication": sum(o["needs_adjudication"] for o in out)}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--model", default=TEACHER)
    ap.add_argument("--limit", type=int, required=True, help="0 = every selected row")
    ap.add_argument("--subset", choices=["none", "stratified"], default="none")
    ap.add_argument("--phase1-spent", type=float, required=True, help="Tinker $ already spent in Phase 1")
    ap.add_argument("--labels", nargs="*")
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="teacher.jsonl")
    ap.add_argument("--in", dest="infile", default="route.jsonl")
    ap.add_argument("--method", choices=["chunked", "topk"], default="chunked")
    a = ap.parse_args()
    asyncio.run(run(a.run, a.model, a.limit, a.concurrency, a.seed, a.out, a.labels, a.method, a.infile, a.subset, a.phase1_spent))


if __name__ == "__main__":
    main()
