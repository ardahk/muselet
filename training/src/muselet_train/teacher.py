"""Teacher soft labels on Tinker (SPEC 1.4). sample_decision needs 36 target ids in one request,
which Tinker rejects (<= 20); chunked splits ids, topk uses top-20 prompt logprobs.

  python -m muselet_train.teacher --run sample2 --limit 500 [--model Qwen/Qwen3.5-397B-A17B]
Reads /data/gen/<run>/route.jsonl, writes teacher.jsonl (teacher_probs, target, needs_adjudication).
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

TEACHER = "Qwen/Qwen3.5-397B-A17B"
TEACHER_FALLBACK = "Qwen/Qwen3.6-35B-A3B"
ADJ_P = 0.7
CHUNK = 18  # Tinker: <= 20 distinct target ids per request at our prompt length


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


async def run(run_name: str, model: str, limit: int | None, concurrency: int, seed: int,
              out_name: str, labels: list[str] | None, method: str) -> None:
    score = {"chunked": chunked_decision, "topk": topk_decision}[method]
    rows = _load(run_name, "route.jsonl")
    if labels:
        rows = [r for r in rows if r["label"] in labels]
    if limit and limit < len(rows):
        rows = random.Random(seed).sample(rows, limit)
    client = tinker.ServiceClient().create_sampling_client(base_model=model)
    sem = asyncio.Semaphore(concurrency)
    names = option_names()

    async def one(r: dict) -> dict:
        rendering = render_route(RouteContext(**r["context"]), r["utterance"], model=model)
        async with sem:
            probs = await score(client, rendering)
        top = max(probs, key=probs.get)
        return {**r, "teacher_model": model, "teacher_probs": probs, "teacher_argmax": top,
                "teacher_p": probs[top], "teacher_method": method, "prompt_tokens": len(rendering.tokens),
                "needs_adjudication": top != r["label"] and probs[top] >= ADJ_P,
                "target": blend(r["label"], probs)}

    out = await asyncio.gather(*(one(r) for r in rows))
    assert all(set(o["teacher_probs"]) == set(names) for o in out)
    (DATA / run_name / out_name).write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out))
    toks = sum(o["prompt_tokens"] for o in out)
    agree = sum(o["teacher_argmax"] == o["label"] for o in out)
    print(json.dumps({"items": len(out), "prompt_tokens": toks, "agree": agree,
                      "needs_adjudication": sum(o["needs_adjudication"] for o in out)}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--model", default=TEACHER)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--labels", nargs="*")
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="teacher.jsonl")
    ap.add_argument("--method", choices=["chunked", "topk"], default="chunked")
    a = ap.parse_args()
    asyncio.run(run(a.run, a.model, a.limit, a.concurrency, a.seed, a.out, a.labels, a.method))


if __name__ == "__main__":
    main()
