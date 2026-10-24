"""Route eval through a Tinker sampler: route_v1 (evals/route_v1.jsonl) or the held-out val split.
Writes per-item predictions (for error reading) and the same metrics as training evals.

  uv run python -m muselet_train.eval_route --tinker-path tinker://... --set route_v1 --name main
  uv run python -m muselet_train.eval_route --tinker-path tinker://... --set val --teacher-files ... --name main
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import fields
from pathlib import Path

import tinker

from muselet_train import datums as D
from muselet_train.catalog import REPO_ROOT
from muselet_train.route_render import STUDENT_MODEL, RouteContext, render_route
from muselet_train.teacher import chunked_decision
from muselet_train.train import OUT, route_metrics

CTX_KEYS = {f.name for f in fields(RouteContext)}


def route_v1_items(name: str = "route_v1") -> list[D.RouteItem]:
    out = []
    for ln in (REPO_ROOT / "evals" / f"{name}.jsonl").read_text().splitlines():
        if ln.strip():
            r = json.loads(ln)
            ctx = {k: ({"yes": True, "no": False}.get(v, v) if k in ("selection", "online") else v)
                   for k, v in r["ctx"].items() if k in CTX_KEYS}
            out.append(D.RouteItem(r["utterance"], ctx, r["label"], {r["label"]: 1.0}, "eval"))
    return out


async def run(tinker_path: str, items: list[D.RouteItem], conc: int = 32) -> list[dict]:
    sc = tinker.ServiceClient()
    client = sc.create_sampling_client(base_model=tinker_path[5:]) if tinker_path.startswith("base:") \
        else sc.create_sampling_client(model_path=tinker_path)
    sem = asyncio.Semaphore(conc)

    async def one(it):
        async with sem:
            p = await chunked_decision(client, render_route(RouteContext(**it.context), it.utterance, STUDENT_MODEL))
        pred = max(p, key=p.get)
        return {"utterance": it.utterance, "context": it.context, "label": it.label, "pred": pred,
                "p_pred": p[pred], "p_label": p.get(it.label, 0.0), "probs": p}

    return await asyncio.gather(*(one(it) for it in items))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tinker-path", required=True, help="tinker://... or base:<model> for the untrained base")
    ap.add_argument("--set", choices=["route_v1", "route_v2", "val", "items"], required=True)
    ap.add_argument("--name", required=True, help="training run name; outputs go to /data/train/<name>/")
    ap.add_argument("--run", default="v2all")
    ap.add_argument("--teacher-files", nargs="*", default=[])
    ap.add_argument("--items", help="--set items: RouteItem jsonl (e.g. a frozen val dump), scored as pred_<--tag>")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    if a.set == "items":
        items = [D.RouteItem(**json.loads(x)) for x in Path(a.items).read_text().splitlines() if x.strip()]
    else:
        items = route_v1_items(a.set) if a.set.startswith("route_v") else \
            [it for it in D.route_items(a.run, tuple(a.teacher_files)) if it.split == "val"]
    tag = a.tag or a.set
    rows = asyncio.run(run(a.tinker_path, items))
    out = OUT / a.name
    out.mkdir(parents=True, exist_ok=True)
    (out / f"pred_{tag}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    m = route_metrics([(r["label"], r["probs"]) for r in rows])
    (out / f"eval_{tag}.json").write_text(json.dumps(m, indent=1))
    print(json.dumps({k: v for k, v in m.items() if not k.startswith("per_label")}))
    print(Path(out / f"eval_{tag}.json"))


if __name__ == "__main__":
    main()
