from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import fields
from pathlib import Path

import tinker

from training.decisions.route.catalog import REPO_ROOT
from training.decisions.route.datums import RouteItem
from training.decisions.route.loader import ROUTE_DATASET, load_export
from training.decisions.route.route_render import RouteContext
from training.decisions.route.train import evaluate


def route_v1_items() -> list[RouteItem]:
    context_fields = {field.name for field in fields(RouteContext)}
    rows = []
    path = REPO_ROOT / "evals" / "route_v1.jsonl"
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        context = {
            key: ({"yes": True, "no": False}.get(value, value)
                  if key in ("selection", "online") else value)
            for key, value in row["ctx"].items()
            if key in context_fields
        }
        rows.append(RouteItem(
            row["utterance"], context, row["label"], {row["label"]: 1.0}, "eval"
        ))
    return rows


async def evaluate_sampler(sampler_path: str, export, model: str) -> dict:
    from training.decisions.route.train import evaluate as evaluate_route

    client = tinker.ServiceClient().create_sampling_client(model_path=sampler_path)
    route_val = [
        RouteItem(row["utterance"], row["context"], row["label"], row["target"], "val")
        for row in export.route if row.get("split") == "val"
    ]
    args_val = [row for row in export.args if row.get("split") == "val"]
    route_v1 = route_v1_items()
    return {
        "route_val": await evaluate_route(client, route_val, args_val, model),
        "route_v1": await evaluate_route(client, route_v1, [], model),
        "counts": {
            "route_val": len(route_val), "args_val": len(args_val), "route_v1": len(route_v1),
        },
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate route and ARGS with a Tinker sampler.")
    parser.add_argument("--sampler", required=True, help="tinker:// sampler weights path")
    parser.add_argument("--datums", default=ROUTE_DATASET)
    parser.add_argument("--name", default="it2-final")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.sampler.startswith("tinker://"):
        parser.error("--sampler must be a tinker:// path")
    if args.datums not in (ROUTE_DATASET, f"{ROUTE_DATASET}@8df540b"):
        parser.error(f"only {ROUTE_DATASET}@8df540b is permitted")
    export = load_export(args.datums)
    result = asyncio.run(evaluate_sampler(args.sampler, export, "Qwen/Qwen3.5-4B"))
    output = args.output or Path("runs/decisions/eval_route") / args.name / "metrics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"sampler": args.sampler, **result}, indent=2) + "\n")
    print(json.dumps({"sampler": args.sampler, **result}, indent=2))
    print(output)


if __name__ == "__main__":
    main()
