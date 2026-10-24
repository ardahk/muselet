from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import re
import statistics
import os
from collections import Counter, defaultdict
from pathlib import Path

from huggingface_hub import HfApi

from .author import author_items
from .decontam import decontam
from .families import GENERATORS
from .label import (
    LABEL_SYSTEM, ApiClient, BudgetExceeded, BudgetLedger, PRICES, floored, label_item, render_question,
)
from .render import render_records

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "decisions"
CODE_TEACHERS = ("gpt-4.1-mini", "gpt-4.1", "claude-haiku-5-5")
AUTHOR_TEACHERS = ("gpt-4.1", "claude-sonnet-5-5")


def _run_dir(run: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run):
        raise ValueError("--run may contain only letters, digits, '_' and '-'")
    path = RUNS / run
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_jsonl(path: Path, rows: list[dict]):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _argmax(dist: dict | None):
    if not dist:
        return None
    return max(dist, key=dist.get)


def _merged(left: dict | None, right: dict | None, labels: list[str]):
    if not left or not right:
        return None
    return {key: 0.5 * float(left.get(key, 0.0)) + 0.5 * float(right.get(key, 0.0)) for key in labels}


async def _label_batches(records: list[dict], models: list[str], api: ApiClient,
                         ledger: BudgetLedger) -> tuple[list[dict], list[dict]]:
    completed, errors = [], []
    for start in range(0, len(records), 8):
        batch = records[start:start + 8]
        results = await asyncio.gather(
            *(label_item(item, models, api, ledger) for item in batch), return_exceptions=True
        )
        for item, result in zip(batch, results):
            if isinstance(result, Exception):
                errors.append({"id": item["id"], "reason": f"{type(result).__name__}: {result}"})
                item["teacher"] = {}
            else:
                item["teacher"], failures = result
                errors.extend(failures)
            completed.append(item)
        if any(isinstance(result, BudgetExceeded) for result in results):
            break
    return completed, errors


def _select_code_teacher(records: list[dict], unavailable: dict | None = None) -> tuple[str | None, dict, list[dict]]:
    totals = defaultdict(lambda: [0, 0])
    family = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    failed_totals = defaultdict(int)
    failed_family = defaultdict(lambda: defaultdict(int))
    disagreements = []
    for item in records:
        for qid, gold in item["gold"].items():
            for model in CODE_TEACHERS:
                totals[model]
                family[item["family"]][model]
                dist = item.get("teacher", {}).get(qid, {}).get(model)
                prediction = _argmax(dist)
                if dist is None:
                    failed_totals[model] += 1
                    failed_family[item["family"]][model] += 1
                    continue
                totals[model][1] += 1
                family[item["family"]][model][1] += 1
                correct = prediction == gold
                totals[model][0] += int(correct)
                family[item["family"]][model][0] += int(correct)
                if not correct:
                    disagreements.append({
                        "id": item["id"], "family": item["family"], "qid": qid, "gold": gold,
                        "prediction": prediction, "model": model,
                        "question": item["questions"][qid],
                        "teacher_distribution": dist,
                        "state": item["state"],
                    })
    agreement = {
        fam: {model: {"correct": values[0], "total": values[1],
                      "agreement": values[0] / values[1] if values[1] else None,
                      "failed_calls": failed_family[fam][model],
                      "unavailable": model in (unavailable or {})}
              for model, values in candidates.items()}
        for fam, candidates in family.items()
    }
    qualifying = [
        model for model, (correct, total) in totals.items()
        if total and correct / total >= 0.95
    ]
    selected = min(qualifying, key=lambda model: sum(PRICES[model])) if qualifying else None
    agreement["_overall"] = {
        model: {"correct": values[0], "total": values[1],
                "agreement": values[0] / values[1] if values[1] else None,
                "failed_calls": failed_totals[model],
                "unavailable": model in (unavailable or {})}
        for model, values in totals.items()
    }
    agreement["_unavailable_candidates"] = unavailable or {}
    return selected, agreement, disagreements


def _teacher_distribution_stats(records: list[dict], models: tuple[str, ...]) -> dict:
    values = {model: [] for model in models}
    failures = {model: 0 for model in models}
    for item in records:
        for question_labels in item.get("teacher", {}).values():
            for model in models:
                distribution = question_labels.get(model)
                if not distribution:
                    failures[model] += 1
                    continue
                probabilities = [float(value) for value in distribution.values() if float(value) > 0]
                total = sum(probabilities)
                probabilities = [value / total for value in probabilities] if total else []
                if probabilities:
                    values[model].append({
                        "max_probability": max(probabilities),
                        "entropy_nats": -sum(p * math.log(p) for p in probabilities),
                    })
                else:
                    failures[model] += 1
    return {
        model: {
            "labeled_decisions": len(rows),
            "failed_calls": failures[model],
            "mean_max_probability": (
                statistics.mean(row["max_probability"] for row in rows) if rows else None
            ),
            "mean_entropy_nats": (
                statistics.mean(row["entropy_nats"] for row in rows) if rows else None
            ),
        }
        for model, rows in values.items()
    }


async def gen_stage(run_dir: Path, rng: random.Random):
    records = []
    for family, generate in GENERATORS.items():
        for _ in range(25):
            records.append(generate(rng, "mixed", 3, ["choice", "noul", "score"]))
    _write_jsonl(run_dir / "code_generated.jsonl", records)
    return records


async def label_stage(args, run_dir: Path, rng: random.Random):
    ledger = BudgetLedger(args.budget, RUNS / "gen_cost.jsonl", args.run)
    api = ApiClient()
    generated_code = _read_jsonl(run_dir / "code_generated.jsonl")
    code_records = await _label_batches(generated_code, list(CODE_TEACHERS), api, ledger)
    code, code_failures = code_records
    selected, agreement, disagreements = _select_code_teacher(code, api.unavailable_models)
    target_stats = {"code": _teacher_distribution_stats(code, CODE_TEACHERS)}
    (run_dir / "teacher_agreement.json").write_text(json.dumps(agreement, indent=2) + "\n", encoding="utf-8")
    _write_jsonl(run_dir / "code_disagreements.jsonl", disagreements)
    rejected = []
    failed_calls = list(code_failures)
    retained_code = []
    if len(code) < len(generated_code):
        _write_jsonl(run_dir / "label_rejections.jsonl", rejected)
        _write_jsonl(run_dir / "failed_calls.jsonl", failed_calls)
        target_stats["unavailable_candidates"] = api.unavailable_models
        (run_dir / "teacher_target_stats.json").write_text(
            json.dumps(target_stats, indent=2) + "\n", encoding="utf-8"
        )
        raise RuntimeError(
            f"budget exhausted before all code-gold states were labeled ({len(code)}/{len(generated_code)})"
        )
    if selected:
        for item in code:
            questions, gold, teacher, target, basis = {}, {}, {}, {}, {}
            for qid, question in item["questions"].items():
                candidate = item.get("teacher", {}).get(qid, {}).get(selected)
                if _argmax(candidate) != item["gold"][qid]:
                    rejected.append({"id": item["id"], "qid": qid, "family": item["family"],
                                     "reason": "selected code teacher disagreed with code gold"})
                    continue
                questions[qid] = question
                gold[qid] = item["gold"][qid]
                basis[qid] = "code"
                teacher[qid] = {selected: candidate}
                target[qid] = floored(candidate)
            if questions:
                item.update(questions=questions, gold=gold, gold_basis=basis, teacher=teacher, target=target)
                retained_code.append(item)
    if not selected:
        _write_jsonl(run_dir / "label_rejections.jsonl", rejected)
        _write_jsonl(run_dir / "failed_calls.jsonl", failed_calls)
        target_stats["unavailable_candidates"] = api.unavailable_models
        (run_dir / "teacher_target_stats.json").write_text(
            json.dumps(target_stats, indent=2) + "\n", encoding="utf-8"
        )
        raise RuntimeError("no code teacher reached the required 95% pilot agreement")

    authored, author_rejections = await author_items(60, rng, api, ledger)
    generated_authored = authored
    authored, author_failures = await _label_batches(authored, list(AUTHOR_TEACHERS), api, ledger)
    labeled_ids = {item["id"] for item in authored}
    author_rejections.extend(
        {"id": item["id"], "family": item["family"], "reason": "budget exhausted before teacher labeling"}
        for item in generated_authored if item["id"] not in labeled_ids
    )
    target_stats["authored"] = _teacher_distribution_stats(authored, AUTHOR_TEACHERS)
    target_stats["unavailable_candidates"] = api.unavailable_models
    rejected.extend(author_rejections)
    failed_calls.extend(author_failures)
    retained_authored = []
    for item in authored:
        keep_questions, gold, target, teacher = {}, {}, {}, {}
        for qid, question in item["questions"].items():
            labels = list(question["criteria"]) if question["type"] in ("choice", "noul") else [
                str(i) for i in range(len(question["criteria"]))
            ]
            teachers = item.get("teacher", {}).get(qid, {})
            one, two = teachers.get("gpt-4.1"), teachers.get("claude-sonnet-5-5")
            if not one or not two or _argmax(one) != _argmax(two):
                rejected.append({"id": item["id"], "qid": qid, "family": item["family"],
                                 "reason": "GPT-4.1 argmax disagreed with Claude majority or was unlabeled"})
                continue
            merged = _merged(one, two, labels)
            keep_questions[qid] = question
            gold[qid] = _argmax(merged)
            target[qid] = floored(merged)
            teacher[qid] = teachers
        if keep_questions:
            item.update(questions=keep_questions, gold=gold, gold_basis={qid: "teacher" for qid in gold},
                        teacher=teacher, target=target)
            retained_authored.append(item)
    all_records = retained_code + retained_authored
    _write_jsonl(run_dir / "records_labeled.jsonl", all_records)
    _write_jsonl(run_dir / "label_rejections.jsonl", rejected)
    _write_jsonl(run_dir / "failed_calls.jsonl", failed_calls)
    (run_dir / "teacher_target_stats.json").write_text(
        json.dumps(target_stats, indent=2) + "\n", encoding="utf-8"
    )
    return all_records


def decontam_stage(run_dir: Path):
    cleaned, report = decontam(_read_jsonl(run_dir / "records_labeled.jsonl"), ROOT)
    _write_jsonl(run_dir / "records_decontam.jsonl", cleaned)
    (run_dir / "decontam.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return cleaned


def split_stage(run_dir: Path, seed: int):
    records = _read_jsonl(run_dir / "records_decontam.jsonl")
    grouped = defaultdict(list)
    for item in records:
        grouped[item["family"]].append(item)
    rng = random.Random(seed)
    dev_ids = set()
    for family, rows in grouped.items():
        rng.shuffle(rows)
        count = max(1, round(len(rows) * 0.05)) if len(rows) >= 10 else 0
        dev_ids.update(row["id"] for row in rows[:count])
    train = []
    dev = []
    for item in records:
        item["split"] = "dev" if item["id"] in dev_ids else "train"
        (dev if item["split"] == "dev" else train).append(item)
    _write_jsonl(run_dir / "train.jsonl", train)
    _write_jsonl(run_dir / "dev.jsonl", dev)
    return train, dev


def report_stage(run_dir: Path, run: str):
    report_dir = ROOT / "training/decisions/reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    records = _read_jsonl(run_dir / "records_decontam.jsonl")
    all_labeled = _read_jsonl(run_dir / "records_labeled.jsonl")
    rejections = _read_jsonl(run_dir / "label_rejections.jsonl")
    failed_calls = _read_jsonl(run_dir / "failed_calls.jsonl")
    agreement = json.loads((run_dir / "teacher_agreement.json").read_text(encoding="utf-8"))
    target_stats = json.loads((run_dir / "teacher_target_stats.json").read_text(encoding="utf-8"))
    decontam_report = json.loads((run_dir / "decontam.json").read_text(encoding="utf-8"))
    cost_path = RUNS / "gen_cost.jsonl"
    costs = [json.loads(line) for line in cost_path.read_text(encoding="utf-8").splitlines()
             if line.strip() and json.loads(line).get("run") == run] if cost_path.is_file() else []
    role_totals = defaultdict(float)
    role_decisions = defaultdict(set)
    provider_cost = defaultdict(float)
    for row in costs:
        role_totals[row["role"]] += float(row["cost_usd"])
        provider_cost[row["provider"]] += float(row["cost_usd"])
        if row.get("decision_id"):
            role_decisions[row["role"]].add(row["decision_id"])
    type_counts, option_counts, gold_positions = Counter(), Counter(), Counter()
    noul_balance, score_levels = Counter(), Counter()
    code_families = ("temporal", "numeric", "counting", "multi_hop", "long_policy", "probability")
    for item in records:
        for qid, question in item["questions"].items():
            kind = question["type"]
            type_counts[kind] += 1
            if kind == "choice":
                labels = list(question["criteria"])
            elif kind == "noul":
                labels = ["false", "true"]
                noul_balance[item["gold"][qid]] += 1
            else:
                labels = [str(i) for i in range(len(question["criteria"]))]
                score_levels[item["gold"][qid]] += 1
            option_counts[str(len(labels))] += 1
            try:
                gold_positions[str(labels.index(str(item["gold"][qid])))] += 1
            except ValueError:
                pass
    role_cost = {}
    if costs:
        decision_totals = defaultdict(int)
        for item in records:
            for qid in item["questions"]:
                decision_totals[item["source"] if item["source"] == "synthetic-code" else "synthetic-llm"] += 1
        for role, amount in role_totals.items():
            if role == "author":
                denominator = decision_totals["synthetic-llm"]
            else:
                denominator = max(1, len(role_decisions[role]))
            role_cost[role] = amount / max(1, denominator)
    token_stats = json.loads((run_dir / "datum_stats.json").read_text(encoding="utf-8"))
    selected = next((name for row in all_labeled if row["source"] == "synthetic-code"
                     for labels in row.get("teacher", {}).values() for name in labels), None)
    selected_rows = [
        row for row in costs if selected and row["role"] == f"teacher:{selected}"
        and not str(row.get("decision_id", "")).startswith("authored-")
    ]
    selected_spend = sum(row["cost_usd"] for row in selected_rows)
    code_decisions = sum(len(item["questions"]) for item in _read_jsonl(run_dir / "code_generated.jsonl"))
    spend_20k = selected_spend / max(1, code_decisions) * 20_000
    train_tokens_per_decision = token_stats["mean_rendered_tokens"] + 1
    train_cost_20k = 20_000 * train_tokens_per_decision * 0.73 / 1_000_000
    reasons = Counter(row.get("reason", "unspecified") for row in rejections)
    role_lines = [
        f"| {role} | ${amount:.6f} | {len(role_decisions[role])} | ${role_totals[role]:.6f} |"
        for role, amount in sorted(role_cost.items())
    ]
    report = [
        f"# Generation pilot: `{run}`", "",
        f"- API spend: OpenAI ${provider_cost['openai']:.6f}; Anthropic ${provider_cost['anthropic']:.6f}; "
        f"total ${sum(provider_cost.values()):.6f}.",
        f"- Code-gold teacher selected: `{selected}`.",
        f"- Retained decisions: {sum(len(item['questions']) for item in records)} across {len(records)} states.",
        "", "## Cost by role", "",
        "| Role | USD per decision | Calls/decisions logged | USD total / decision* |",
        "|---|---:|---:|---:|", *role_lines,
        "", "*Role total is divided by the corresponding decision count; Claude sampling calls share a decision ID.",
        "", "## Code-gold agreement by family and teacher", "",
        "```json", json.dumps(agreement, indent=2), "```",
        "", "## Failed calls and unavailable candidates", "",
        f"- Failed/null teacher predictions: {len(failed_calls)} (excluded from agreement denominators).",
        "```json", json.dumps(dict(Counter(row.get("model", "unknown") for row in failed_calls)), indent=2), "```",
        "Unavailable model statuses:",
        "```json", json.dumps(target_stats.get("unavailable_candidates", {}), indent=2), "```",
        "", "## Teacher target sharpness", "",
        "Mean maximum probability and Shannon entropy (nats) are computed over non-null raw teacher distributions.",
        "```json", json.dumps({key: value for key, value in target_stats.items()
                               if key in ("code", "authored")}, indent=2), "```",
        "", "## Rejections", "",
        f"- Rejected questions/items: {len(rejections)}; generated records: {len(all_labeled)}.",
        f"- Rejection rate by generated record: {len(rejections)/max(1,len(all_labeled)):.1%}.",
        "```json", json.dumps(dict(reasons), indent=2), "```",
        "", "## Histograms", "",
        f"- Question types: `{json.dumps(type_counts, sort_keys=True)}`",
        f"- Option counts: `{json.dumps(option_counts, sort_keys=True)}`",
        f"- Gold positions (0-based): `{json.dumps(gold_positions, sort_keys=True)}`",
        f"- Noul balance: `{json.dumps(noul_balance, sort_keys=True)}`",
        f"- Score levels: `{json.dumps(score_levels, sort_keys=True)}`",
        "", "## Decontamination", "", "```json", json.dumps(decontam_report, indent=2), "```",
        "", "## Render and cost projections", "",
        f"- Mean rendered input tokens/Datum: {token_stats['mean_rendered_tokens']:.1f}.",
        f"- p95 rendered input tokens/Datum: {token_stats['p95_rendered_tokens']}.",
        f"- 20k decision Tinker projection at $0.73/M train tokens: ${train_cost_20k:.4f} "
        f"(using mean input tokens + one target token).",
        f"- 20k code-teacher generation projection using `{selected}`: ${spend_20k:.4f}; "
        "computed from actual selected-teacher API usage per labeled code decision.",
        "", "## Teacher disagreements", "",
        f"See `{run_dir.relative_to(ROOT)}/code_disagreements.jsonl`; the pilot stores the complete state, "
        "question, gold label, and each candidate distribution for manual inspection.",
    ]
    (report_dir / "pilot_gen.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    samples = []
    for family in code_families:
        family_rows = [item for item in records if item["family"] == family]
        for item in family_rows[:2]:
            samples.append((item, next(iter(item["questions"]))))
    authored_rows = [item for item in records if item["source"] == "synthetic-llm"]
    for item in authored_rows[:6]:
        samples.append((item, next(iter(item["questions"]))))
    rendered_samples = ["# Pilot samples for review", "",
                        f"{len(samples)} samples are included: two per code family plus six authored when available. "
                        "This is 18 samples if all requested strata are present (12 code + 6 authored)."]
    for index, (item, qid) in enumerate(samples, 1):
        question = item["questions"][qid]
        prompt, _ = render_question(item["state"], question)
        rendered_samples.extend([
            "", f"## Sample {index}: {item['family']} / {qid} / {item['id']}", "",
            f"Source: {item['source']}; target: `{json.dumps(item['target'][qid], sort_keys=True)}`",
            f"Gold metadata: `{item['gold'][qid]}`", "", "```text",
            f"system: {LABEL_SYSTEM}\nuser:\n{prompt}", "```",
        ])
    (report_dir / "pilot_samples.md").write_text("\n".join(rendered_samples) + "\n", encoding="utf-8")


def datums_stage(run_dir: Path, run: str):
    records = _read_jsonl(run_dir / "train.jsonl") + _read_jsonl(run_dir / "dev.jsonl")
    rendered = render_records(records)
    token_counts = []
    rows = []
    for entry in rendered:
        rendering = entry["rendering"]
        token_counts.append(rendering.choice_pos)
        tensor = entry["datum"].loss_fn_inputs["weights"].to_torch()
        rows.append({
            "record_id": entry["record_id"], "qid": entry["qid"], "family": entry["family"],
            "input_tokens": rendering.tokens[:rendering.choice_pos], "choice_pos": rendering.choice_pos,
            "label_token_ids": rendering.label_tokens, "target": entry["target"],
            "weights": tensor.tolist(),
        })
    _write_jsonl(run_dir / "datums.jsonl", rows)
    stats = {
        "datum_count": len(rows),
        "mean_rendered_tokens": statistics.mean(token_counts) if token_counts else 0,
        "p95_rendered_tokens": sorted(token_counts)[int(0.95 * (len(token_counts)-1))] if token_counts else 0,
    }
    (run_dir / "datum_stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    report_stage(run_dir, run)
    return stats


def upload_stage(args, run_dir: Path):
    repository = f"jonsnov/muselet-decisions-{args.run}"
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(repository, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(folder_path=str(run_dir), repo_id=repository, repo_type="dataset", path_in_repo="data")
    return repository


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the generic-decision generation dataset.")
    parser.add_argument("stage", choices=("gen", "label", "decontam", "split", "datums", "upload"))
    parser.add_argument("--run", default="pilot")
    parser.add_argument("--budget", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=814)
    args = parser.parse_args(argv)
    run_dir = _run_dir(args.run)
    rng = random.Random(args.seed)
    if args.stage == "gen":
        asyncio.run(gen_stage(run_dir, rng))
    elif args.stage == "label":
        asyncio.run(label_stage(args, run_dir, rng))
    elif args.stage == "decontam":
        decontam_stage(run_dir)
    elif args.stage == "split":
        split_stage(run_dir, args.seed)
    elif args.stage == "datums":
        datums_stage(run_dir, args.run)
    else:
        print(upload_stage(args, run_dir))


if __name__ == "__main__":
    main()
