"""Teacher soft labels on Tinker (SPEC 1.4).

  python -m muselet_train.teacher --run sample2 --limit 500 [--model Qwen/Qwen3.5-397B-A17B]
Reads /data/gen/<run>/route.jsonl, writes teacher.jsonl (teacher_probs, target, needs_adjudication).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random

import tinker

from muselet_train.catalog import option_names
from muselet_train.gen import DATA, _load
from muselet_train.route_render import RouteContext, render_route

TEACHER = "Qwen/Qwen3.5-397B-A17B"
TEACHER_FALLBACK = "Qwen/Qwen3.6-35B-A3B"
ADJ_P = 0.7


def blend(label: str, probs: dict[str, float]) -> dict[str, float]:
    t = {k: 0.4 * v for k, v in probs.items()}
    t[label] = t.get(label, 0.0) + 0.6
    z = sum(t.values())
    return {k: v / z for k, v in t.items()}


async def run(run_name: str, model: str, limit: int | None, concurrency: int, seed: int,
              out_name: str, labels: list[str] | None) -> None:
    from tinker_cookbook.recipes.decisions.decision import sample_decision

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
            probs = await sample_decision(client, rendering)
        top = max(probs, key=probs.get)
        return {**r, "teacher_model": model, "teacher_probs": probs, "teacher_argmax": top,
                "teacher_p": probs[top], "prompt_tokens": len(rendering.tokens),
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
    a = ap.parse_args()
    asyncio.run(run(a.run, a.model, a.limit, a.concurrency, a.seed, a.out, a.labels))


if __name__ == "__main__":
    main()
