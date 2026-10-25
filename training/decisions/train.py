from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
from collections import defaultdict
from pathlib import Path

import tinker
import torch

from tinker_cookbook.renderers import Message, TrainOnWhat
from tinker_cookbook.supervised.data import conversation_to_datum

from training.decisions.route.loader import (
    ROUTE_DATASET,
    RouteExport,
    load_export,
    route_datum,
    sample_route_args,
)
from training.decisions.route.route_render import (
    RouteContext,
    base_renderer,
    render_route,
)
from training.decisions.route.teacher import CHUNK

PRICE_TRAIN = 0.73
PRICE_EVAL = 0.33
DEFAULT_MODEL = "Qwen/Qwen3.5-4B"
CHECKPOINTS = Path(__file__).resolve().parent / "reports" / "checkpoints.jsonl"


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _download(repo: str, names: tuple[str, ...], revision: str | None = None) -> Path | None:
    path = Path(repo)
    if path.exists():
        root = path.parent if path.is_file() else path
        return next((root / name for name in names if (root / name).is_file()), None)
    from huggingface_hub import hf_hub_download

    repo_id, _, source_revision = repo.partition("@")
    for name in names:
        try:
            return Path(hf_hub_download(
                repo_id=repo_id, filename=name, repo_type="dataset",
                revision=revision or source_revision or None,
            ))
        except Exception:
            continue
    return None


def load_generic(source: str, dev_source: str | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    datum_path = _download(source, ("data/datums.jsonl", "datums.jsonl"))
    if datum_path is None:
        raise FileNotFoundError(f"could not find datums.jsonl in {source}")
    train_path = _download(source, ("data/train.jsonl", "train.jsonl"))
    dev_path = _download(source, ("data/dev.jsonl", "dev.jsonl"))
    train_records = _jsonl(train_path) if train_path else []
    dev_records = _jsonl(dev_path) if dev_path else []
    train_ids = {row["id"] for row in train_records}
    dev_ids = {row["id"] for row in dev_records}
    metadata = {}
    dev_examples = []
    for split, records in (("train", train_records), ("dev", dev_records)):
        for record in records:
            for qid, question in record["questions"].items():
                metadata[(record["id"], qid)] = {
                    "family": record.get("family", "unknown"),
                    "type": question["type"],
                    "gold": record["gold"][qid],
                    "target": record.get("target", {}).get(qid) or {record["gold"][qid]: 1.0},
                }
                if split == "dev":
                    dev_examples.append({
                        "state": record["state"], "question": question,
                        "record_id": record["id"], "qid": qid,
                        **metadata[(record["id"], qid)],
                    })
    rows = _jsonl(datum_path)
    for row in rows:
        key = (row.get("record_id"), row.get("qid"))
        row.update(metadata.get(key, {}))
        row["split"] = "dev" if key[0] in dev_ids else "train"
        if train_ids and key[0] not in train_ids | dev_ids:
            raise ValueError(f"datum references unknown record id {key[0]!r}")
    train_rows = [row for row in rows if row["split"] == "train"]
    dev_rows = [row for row in rows if row["split"] == "dev"]
    if dev_source:
        dev_file = _download(dev_source, ("data/datums.jsonl", "datums.jsonl"))
        if dev_file is None:
            raise FileNotFoundError(f"could not find dev datums in {dev_source}")
        dev_rows = _jsonl(dev_file)
    if not train_rows:
        raise ValueError("generic training split is empty")
    return train_rows, dev_rows, dev_examples


def datum_tokens(row: dict) -> list[int]:
    tokens = row.get("input_tokens", row.get("tokens"))
    if tokens is None and "datum" in row:
        tokens = row["datum"].get("input_tokens", row["datum"].get("tokens"))
    if not isinstance(tokens, list):
        raise ValueError("datum has no token list")
    return [int(token) for token in tokens]


def datum_type(row: dict) -> str:
    return str(row.get("type", row.get("question_type", "unknown")))


def stratified_subset(rows: list[dict], size: int, seed: int) -> list[dict]:
    if size >= len(rows):
        return list(rows)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(str(row.get("family", "unknown")), datum_type(row))].append(row)
    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)
    selected = []
    while len(selected) < size:
        changed = False
        for group in groups.values():
            if group and len(selected) < size:
                selected.append(group.pop())
                changed = True
        if not changed:
            break
    return selected


def batches(rows: list[dict], batch_size: int, seed: int) -> list[list[dict]]:
    if batch_size < 1:
        raise ValueError("batch size must be positive")
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    return [shuffled[start:start + batch_size] for start in range(0, len(shuffled), batch_size)]


def estimate(train_rows: list[dict], dev_rows: list[dict], epochs: int,
             eval_every: int = 50, batch_size: int = 128,
             extra_eval_tokens: int = 0) -> dict:
    train_tokens = sum(len(datum_tokens(row)) for row in train_rows) * epochs
    steps = math.ceil(len(train_rows) / batch_size) * epochs
    eval_count = max(1, math.ceil(steps / eval_every))
    eval_tokens = (sum(len(datum_tokens(row)) for row in dev_rows) + extra_eval_tokens) * eval_count
    train_usd = train_tokens * PRICE_TRAIN / 1_000_000
    eval_usd = eval_tokens * PRICE_EVAL / 1_000_000
    return {
        "train_tokens": train_tokens, "train_usd": train_usd,
        "eval_tokens": eval_tokens, "eval_usd": eval_usd,
        "total_usd": train_usd + eval_usd, "steps": steps, "eval_count": eval_count,
    }


def _generic_datum(row: dict) -> tinker.Datum:
    tokens = datum_tokens(row)
    label_ids = row["label_token_ids"]
    labels = list(label_ids)
    weights = torch.tensor(row["weights"], dtype=torch.float32)
    target_tokens = torch.zeros((len(tokens), len(labels)), dtype=torch.int64)
    target_tokens[-1] = torch.tensor([int(label_ids[label]) for label in labels])
    if weights.shape != target_tokens.shape:
        raise ValueError(f"generic weights shape {tuple(weights.shape)} does not match target shape")
    fields = {
        "target_tokens": tinker.TensorData.from_torch(target_tokens),
        "weights": tinker.TensorData.from_torch(weights),
    }
    if len(labels) > 20:
        fields = {key: tinker.TensorData.from_torch_sparse(value.to_torch())
                  for key, value in fields.items()}
    return tinker.Datum(model_input=tinker.ModelInput.from_ints(tokens), loss_fn_inputs=fields)


def _args_datum(row: dict, renderer) -> tinker.Datum:
    messages = [Message(role=message["role"], content=message["content"])
                for message in row["messages"]]
    datum = conversation_to_datum(
        messages, renderer, max_length=None,
        train_on_what=TrainOnWhat.LAST_ASSISTANT_MESSAGE,
    )
    end_think = renderer.tokenizer.convert_tokens_to_ids("</think>")
    target_tokens = datum.loss_fn_inputs["target_tokens"].to_torch()
    weights = datum.loss_fn_inputs["weights"].to_torch().clone()
    positions = (weights > 0).nonzero().flatten().tolist()
    close = next(
        (index for index in positions if int(target_tokens[index]) == end_think), None
    )
    if close is not None:
        close += 1
        while close < len(target_tokens) and renderer.tokenizer.decode(
            [int(target_tokens[close])]
        ).strip() == "":
            close += 1
        weights[:close] = 0
    return tinker.Datum(
        model_input=datum.model_input,
        loss_fn_inputs={
            **datum.loss_fn_inputs,
            "weights": tinker.TensorData.from_torch(weights),
        },
    )


def _route_labels(rows: list[dict], model: str) -> dict[str, int]:
    if not rows:
        return {}
    row = rows[0]
    rendered = render_route(
        RouteContext(**row["context"]),
        row.get("rendered_utterance", row["utterance"]),
        model,
    )
    if list(row["tokens"]) != rendered.tokens:
        raise ValueError("pinned route datum tokens do not match the vendored renderer")
    return rendered.label_tokens


def _sparse(datum: tinker.Datum) -> tinker.Datum:
    if not datum.loss_fn_inputs:
        return datum
    return tinker.Datum(
        model_input=datum.model_input,
        loss_fn_inputs={
            key: tinker.TensorData.from_torch_sparse(value.to_torch())
            for key, value in datum.loss_fn_inputs.items()
        },
    )


async def _sample_logits(client, rendering, semaphore: asyncio.Semaphore) -> list[float]:
    labels = list(rendering.label_tokens)
    results = []
    for start in range(0, len(labels), CHUNK):
        part = labels[start:start + CHUNK]
        targets = torch.full((len(rendering.tokens) - 1, len(part)), -1, dtype=torch.int64)
        targets[rendering.choice_pos - 1] = torch.tensor(
            [rendering.label_tokens[label] for label in part], dtype=torch.int64
        )
        async with semaphore:
            response = await client.sample_async(
                prompt=tinker.ModelInput.from_ints(rendering.tokens),
                num_samples=1,
                sampling_params=tinker.SamplingParams(max_tokens=1),
                target_prompt_logprobs=tinker.TensorData.from_torch_sparse(targets, pad_value=-1),
            )
        if response.target_prompt_logprobs is None:
            raise RuntimeError("sampler did not return target prompt logprobs")
        results.extend(response.target_prompt_logprobs.to_torch()[rendering.choice_pos - 1].tolist())
    return [float(value) for value in results]


def _softmax(logits: list[float], temperature: float = 1.0) -> list[float]:
    values = torch.softmax(torch.tensor(logits, dtype=torch.float32) / temperature, dim=0)
    return [float(value) for value in values.tolist()]


def _metrics(rows: list[dict]) -> dict:
    result = {}
    for kind in sorted({row["type"] for row in rows}):
        subset = [row for row in rows if row["type"] == kind]
        acc, kl, brier, bins = 0, 0.0, 0.0, [[] for _ in range(15)]
        for row in subset:
            probs = _softmax(row["logits"])
            labels, gold = row["labels"], row["gold"]
            gold_index = labels.index(gold)
            pred_index = max(range(len(probs)), key=probs.__getitem__)
            correct = int(pred_index == gold_index)
            acc += correct
            target = row["target"]
            kl += sum(t * math.log(max(t, 1e-12) / max(p, 1e-12))
                      for t, p in zip(target, probs, strict=True) if t > 0)
            brier += sum((p - int(i == gold_index)) ** 2 for i, p in enumerate(probs))
            confidence = probs[pred_index]
            bins[min(int(confidence * 15), 14)].append((confidence, correct))
        count = max(len(subset), 1)
        ece = sum(
            len(bucket) / count * abs(
                sum(p for p, _ in bucket) / len(bucket)
                - sum(c for _, c in bucket) / len(bucket)
            )
            for bucket in bins if bucket
        )
        result[kind] = {
            "n": len(subset), "accuracy": acc / count, "kl": kl / count,
            "brier": brier / count, "ece": ece,
        }
    return result


async def evaluate_synthetic(client, examples: list[dict], renderer) -> tuple[dict, list[dict]]:
    semaphore = asyncio.Semaphore(16)
    from training.decisions.render import render_question

    rendered_examples = []
    for example in examples:
        datum, rendering = render_question(
            renderer, example["state"], example["question"], example["target"]
        )
        del datum
        rendered_examples.append((example, rendering))
    logits = await asyncio.gather(*(
        _sample_logits(client, rendering, semaphore)
        for _, rendering in rendered_examples
    ))
    rows = []
    for (example, rendering), values in zip(rendered_examples, logits, strict=True):
        labels = list(rendering.label_tokens)
        rows.append({
            "record_id": example.get("record_id"), "qid": example.get("qid"),
            "type": example["type"], "labels": labels, "logits": values,
            "target": [float(example["target"].get(label, 0.0)) for label in labels],
            "gold": example["gold"],
        })
    return _metrics(rows), rows


def _append_checkpoint(name: str, step: int, kind: str, path: str) -> None:
    CHECKPOINTS.parent.mkdir(parents=True, exist_ok=True)
    with CHECKPOINTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"run": name, "step": step, "kind": kind, "path": path}) + "\n")


def _route_eval_data(export: RouteExport, seed: int, model: str):
    from training.decisions.route.datums import RouteItem

    route_val = [row for row in export.route if row.get("split") == "val"]
    args_val = [row for row in export.args if row.get("split") == "val"]
    rng = random.Random(seed)
    val_route = rng.sample(route_val, min(300, len(route_val)))
    val_args = rng.sample(args_val, min(200, len(args_val)))
    route_items = [
        RouteItem(row["utterance"], row["context"], row["label"], row["target"], "val")
        for row in val_route
    ]
    return route_items, val_args, route_val, args_val


async def main_async(args) -> None:
    if args.init_from != DEFAULT_MODEL and not args.init_from.startswith("tinker://"):
        raise SystemExit("--init-from must be Qwen/Qwen3.5-4B or an explicit tinker:// sampler path")
    generic_train, generic_dev, dev_examples = load_generic(args.datums, args.dev_datums)
    if args.subset is not None:
        generic_train = stratified_subset(generic_train, args.subset, args.seed)
    if not dev_examples:
        raise ValueError("the generic dataset must provide records for the synthetic dev split")
    generic_items = [{"datum": _generic_datum(row), "kind": "generic",
                      "tokens": datum_tokens(row), **row} for row in generic_train]
    generic_dev_items = generic_dev

    export = None
    route_items = []
    args_items = []
    val_route_items, val_args_items = [], []
    if args.route_datums:
        export = load_export(args.route_datums)
        count = args.route_size
        if count is None:
            count = round(len(generic_items) * args.route_frac / (1 - args.route_frac))
        sampled_route, sampled_args = sample_route_args(export, count)
        label_ids = _route_labels(
            sampled_route or [row for row in export.route if row["split"] == "train"],
            DEFAULT_MODEL,
        ) if count else {}
        route_items = [{"datum": _sparse(route_datum(row, label_ids)), "kind": "route",
                        "tokens": row["tokens"], **row} for row in sampled_route]
        args_renderer = base_renderer(DEFAULT_MODEL)
        args_items = []
        for row in sampled_args:
            datum = _args_datum(row, args_renderer)
            args_items.append({
                "datum": datum, "kind": "args",
                "tokens": [0] * datum.model_input.length, **row,
            })
        val_route_items, val_args_items, full_route_val, full_args_val = _route_eval_data(
            export, args.seed, DEFAULT_MODEL
        )
    train_items = generic_items + route_items + args_items
    mixed = [{"datum": item["datum"], "kind": item["kind"],
              "tokens": item["tokens"] if isinstance(item["tokens"], list) else datum_tokens(item)}
             for item in train_items]
    dev_for_estimate = [{"tokens": datum_tokens(row)} for row in generic_dev_items]
    extra_eval_tokens = 0
    if export:
        extra_eval_tokens += sum(len(row["tokens"]) * 1.4 for row in full_route_val[:300])
        extra_eval_tokens += len(full_args_val[:200]) * 250
    costs = estimate(mixed, dev_for_estimate, args.epochs, args.eval_every,
                     args.batch_size, int(extra_eval_tokens))
    result = {
        "model": args.init_from, "generic_train": len(generic_items),
        "route_train": len(route_items), "args_train": len(args_items),
        "generic_dev": len(generic_dev_items), "route_val_subset": len(val_route_items),
        "args_val_subset": len(val_args_items), "epochs": args.epochs,
        "batch_size": args.batch_size, "rank": args.rank, "optimizer": "Adam",
        **costs,
    }
    print(json.dumps(result, indent=2), flush=True)
    if args.dry_run:
        if costs["total_usd"] > 25 and not args.approved_over_25:
            raise SystemExit("preflight exceeds $25; pass --approved-over-25 to acknowledge")
        return
    if costs["total_usd"] > args.max_usd:
        raise SystemExit(
            f"preflight ${costs['total_usd']:.2f} exceeds --max-usd ${args.max_usd:.2f}"
        )
    if costs["total_usd"] > 25 and not args.approved_over_25:
        raise SystemExit("preflight exceeds $25; pass --approved-over-25 to acknowledge")

    from training.decisions.render import GenericRenderer
    from training.decisions.route.train import evaluate as evaluate_route

    run_dir = Path("runs/decisions/train") / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    generic_renderer = GenericRenderer(DEFAULT_MODEL)
    route_val_sample = val_route_items
    args_val_sample = val_args_items
    client = await tinker.ServiceClient().create_lora_training_client_async(
        base_model=args.init_from, rank=args.rank, seed=args.seed
    )
    adam = tinker.AdamParams(learning_rate=args.learning_rate)
    step, loss = 0, float("nan")
    history_path = run_dir / "metrics.jsonl"

    async def checkpoint(kind: str, final: bool = False) -> str:
        artifact_name = f"{args.name}-final" if final else f"{args.name}-step-{step}"
        if kind == "state":
            response = await (await client.save_state_async(artifact_name)).result_async()
        else:
            response = await (await client.save_weights_for_sampler_async(artifact_name)).result_async()
        _append_checkpoint(args.name, step, kind, response.path)
        return response.path

    async def evaluate(step_number: int) -> None:
        nonlocal loss
        sampler_path = await checkpoint("sampler")
        await checkpoint("state")
        sampler = tinker.ServiceClient().create_sampling_client(model_path=sampler_path)
        synthetic, predictions = await evaluate_synthetic(sampler, dev_examples, generic_renderer)
        route_metrics = {}
        if export:
            route_metrics = await evaluate_route(
                sampler, route_val_sample, args_val_sample, DEFAULT_MODEL
            )
        metric = {
            "step": step_number, "train_loss": loss,
            "synthetic_dev": synthetic, "route_val_subset": route_metrics,
        }
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metric) + "\n")
        (run_dir / "dev_predictions.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in predictions), encoding="utf-8"
        )

    for epoch in range(args.epochs):
        for batch in batches(mixed, args.batch_size, args.seed + epoch):
            datums = [row["datum"] for row in batch]
            fb = await (await client.forward_backward_async(datums, "cross_entropy")).result_async()
            await (await client.optim_step_async(adam)).result_async()
            weights = sum(
                float(row["datum"].loss_fn_inputs["weights"].to_torch().sum())
                for row in batch if row["datum"].loss_fn_inputs
            )
            loss = float(fb.metrics.get("loss:sum", float("nan"))) / max(weights, 1.0)
            step += 1
            if step % args.eval_every == 0:
                await evaluate(step)
    if step % args.eval_every:
        await evaluate(step)
    await checkpoint("sampler", final=True)
    await checkpoint("state", final=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train a mixed generic/route/ARGS decision LoRA.")
    parser.add_argument("--datums", default="jonsnov/muselet-decisions-v1")
    parser.add_argument("--dev-datums")
    parser.add_argument("--route-datums")
    parser.add_argument("--route-size", type=int)
    parser.add_argument("--route-frac", type=float, default=0.3)
    parser.add_argument("--subset", type=int)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--eval-every", type=int, default=50)
    parser.add_argument("--rank", type=int, default=32)
    parser.add_argument("--init-from", default=DEFAULT_MODEL)
    parser.add_argument("--name", default="decisions")
    parser.add_argument("--seed", type=int, default=20261025)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--max-usd", type=float, default=25.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approved-over-25", action="store_true")
    args = parser.parse_args(argv)
    if not 0 <= args.route_frac < 1:
        parser.error("--route-frac must be in [0, 1)")
    if args.route_size is not None and args.route_size < 0:
        parser.error("--route-size must be nonnegative")
    if args.route_datums and args.route_datums not in (
        ROUTE_DATASET, f"{ROUTE_DATASET}@8df540b"
    ):
        parser.error(f"only {ROUTE_DATASET}@8df540b is permitted")
    if args.epochs < 1 or args.batch_size < 1 or args.eval_every < 1:
        parser.error("epochs, batch-size, and eval-every must be positive")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
