from __future__ import annotations

import gzip
import json
import random
from dataclasses import dataclass
from pathlib import Path

import tinker
import torch

ROUTE_DATASET = "jonsnov/muselet-route-datums-it2b"
ROUTE_REVISION = "8df540b"


@dataclass(frozen=True)
class RouteExport:
    route: list[dict]
    args: list[dict]
    meta: dict


def _read_jsonl(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_export(source: str | Path = ROUTE_DATASET) -> RouteExport:
    path = Path(source)
    if path.is_dir():
        directory = path
    elif str(source) == ROUTE_DATASET or str(source) == f"{ROUTE_DATASET}@{ROUTE_REVISION}":
        from huggingface_hub import hf_hub_download

        directory = Path(hf_hub_download(
            repo_id=ROUTE_DATASET, filename="route.jsonl.gz", repo_type="dataset",
            revision=ROUTE_REVISION,
        )).parent
        args_path = Path(hf_hub_download(
            repo_id=ROUTE_DATASET, filename="args.jsonl.gz", repo_type="dataset",
            revision=ROUTE_REVISION,
        ))
        meta_path = Path(hf_hub_download(
            repo_id=ROUTE_DATASET, filename="meta.json", repo_type="dataset",
            revision=ROUTE_REVISION,
        ))
        route = _read_jsonl(directory / "route.jsonl.gz")
        return RouteExport(route, _read_jsonl(args_path), json.loads(meta_path.read_text()))
    else:
        raise ValueError(
            f"route data must be {ROUTE_DATASET}@{ROUTE_REVISION} or a local export directory"
        )

    route_path, args_path, meta_path = (
        path / "route.jsonl.gz", path / "args.jsonl.gz", path / "meta.json"
    )
    if not route_path.is_file() or not args_path.is_file():
        raise FileNotFoundError(f"{path} is not a datums_export directory")
    route = _read_jsonl(route_path)
    args = _read_jsonl(args_path)
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    return RouteExport(route, args, meta)


def sample_route_args(export: RouteExport, count: int) -> tuple[list[dict], list[dict]]:
    if count < 0:
        raise ValueError("route/ARGS sample count must be nonnegative")
    route_train = [row for row in export.route if row.get("split") == "train"]
    args_train = [row for row in export.args if row.get("split") == "train"]
    route_count = round(count * 0.6)
    args_count = count - route_count
    if route_count > len(route_train) or args_count > len(args_train):
        raise ValueError(
            f"requested {route_count} route and {args_count} ARGS rows, but train pool has "
            f"{len(route_train)} route and {len(args_train)} ARGS rows"
        )
    rng = random.Random(0)
    return rng.sample(route_train, route_count), rng.sample(args_train, args_count)


def route_datum(row: dict, label_token_ids: dict[str, int]) -> tinker.Datum:
    labels = list(label_token_ids)
    target = {label: max(0.0, float(row.get("target", {}).get(label, 0.0))) for label in labels}
    total = sum(target.values())
    if total <= 0:
        raise ValueError(f"route row has no target mass: {row.get('utterance', '')!r}")
    target = {label: value / total for label, value in target.items()}
    tokens = [int(token) for token in row["tokens"]]
    choice_pos = int(row["choice_pos"])
    if choice_pos < 1 or choice_pos >= len(tokens):
        raise ValueError(f"invalid route choice_pos {choice_pos} for {len(tokens)} tokens")
    target_tokens = torch.zeros((choice_pos, len(labels)), dtype=torch.int64)
    target_tokens[-1] = torch.tensor([label_token_ids[label] for label in labels])
    weights = torch.zeros((choice_pos, len(labels)), dtype=torch.float32)
    weights[-1] = torch.tensor([target[label] for label in labels])
    fields = {
        "target_tokens": tinker.TensorData.from_torch(target_tokens),
        "weights": tinker.TensorData.from_torch(weights),
    }
    if len(labels) > 20:
        fields = {
            key: tinker.TensorData.from_torch_sparse(value.to_torch())
            for key, value in fields.items()
        }
    return tinker.Datum(
        model_input=tinker.ModelInput.from_ints(tokens[:choice_pos]),
        loss_fn_inputs=fields,
    )
