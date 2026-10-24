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
from .paraphrase import PARAPHRASE_PROMPT, validate_paraphrase
from .render import GenericRenderer, render_question, render_records

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "decisions"
CODE_TEACHERS = ("gpt-5.4-nano", "gpt-5.4-mini", "claude-haiku-5-5")
AUTHOR_TEACHERS = ("gpt-4.1", "claude-sonnet-5-5")
CODE_FAMILIES = tuple(GENERATORS)
PARAPHRASE_DOC_KINDS = {
    "temporal": ("calendar notice", "case-management ticket", "service email"),
    "numeric": ("purchase approval email", "invoice annotation", "procurement form"),
    "counting": ("audit worksheet", "queue export", "operations review"),
    "multi_hop": ("support handoff email", "service desk ticket", "lookup audit log"),
    "long_policy": ("controlled policy excerpt", "claims review memorandum", "portal case file"),
    "probability": ("risk review memo", "screening protocol", "project assessment"),
}


def _run_dir(run: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run):
        raise ValueError("--run may contain only letters, digits, '_' and '-'")
    path = RUNS / run
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_jsonl(path: Path, rows: list[dict]):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _append_jsonl(path: Path, row: dict):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


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


async def gen_stage(args, run_dir: Path, rng: random.Random):
    ledger = BudgetLedger(args.budget, RUNS / "gen_cost.jsonl", args.run, "amendment-2")
    api = ApiClient()
    records, rejected = [], []
    question_rng = random.Random(rng.getrandbits(64))
    _write_jsonl(run_dir / "code_generated.jsonl", [])
    for family, generate in GENERATORS.items():
        family_rows = [
            generate(rng, "mixed", question_rng.randint(1, 6), ["choice", "noul", "score"])
            for _ in range(25)
        ]
        paraphrase_indices = set(rng.sample(range(25), 15))
        for index, item in enumerate(family_rows):
            if index not in paraphrase_indices:
                item["paraphrased"] = False
                records.append(item)
                continue
            accepted = False
            for attempt in range(3):
                doc_kind = rng.choice(PARAPHRASE_DOC_KINDS[family])
                prompt = PARAPHRASE_PROMPT.format(doc_kind=doc_kind) + "\n\n" + item["state"]
                try:
                    rewritten, _ = await api.generate(
                        "gpt-5.4-mini", prompt, ledger, max_output_tokens=8000,
                        role="paraphrase", decision_id=f"paraphrase:{item['id']}",
                        reasoning_effort="low",
                    )
                except BudgetExceeded:
                    raise
                except Exception as exc:
                    rejected.append({
                        "id": item["id"], "family": family, "attempt": attempt + 1,
                        "reason": f"{type(exc).__name__}: {exc}",
                    })
                    continue
                if validate_paraphrase(item["state"], rewritten):
                    item["state"] = rewritten.strip()
                    item["paraphrased"] = True
                    accepted = True
                    break
                rejected.append({
                    "id": item["id"], "family": family, "attempt": attempt + 1,
                    "reason": "verbatim preservation check failed",
                })
                if attempt < 2:
                    item = generate(
                        rng, "mixed", question_rng.randint(1, 6), ["choice", "noul", "score"]
                    )
            if not accepted:
                _write_jsonl(run_dir / "paraphrase_rejections.jsonl", rejected)
                raise RuntimeError(f"could not obtain a valid paraphrase for {family} after 3 attempts")
            records.append(item)
        _write_jsonl(run_dir / "code_generated.jsonl", records)
    _write_jsonl(run_dir / "paraphrase_rejections.jsonl", rejected)
    (run_dir / "paraphrase_stats.json").write_text(
        json.dumps({
            "states": len(records),
            "paraphrase_passes": sum(item.get("paraphrased", False) for item in records),
            "rejections": len(rejected),
            "rejection_reasons": dict(Counter(row["reason"] for row in rejected)),
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    return records


def _gate_subset(records: list[dict], seed: int) -> list[dict]:
    patterns = ((8, 8, 9), (8, 9, 8), (9, 8, 8))
    rng = random.Random(seed)
    rows = []
    for index, family in enumerate(CODE_FAMILIES):
        family_records = [item for item in records if item["family"] == family]
        if len(family_records) != 25:
            raise ValueError(f"expected 25 {family} states, found {len(family_records)}")
        schedule = [kind for kind, count in zip(("choice", "noul", "score"), patterns[index % 3])
                    for _ in range(count)]
        rng.shuffle(family_records)
        rng.shuffle(schedule)
        for item, kind in zip(family_records, schedule):
            qid = next(qid for qid, question in item["questions"].items() if question["type"] == kind)
            rows.append({"item": item, "qid": qid, "type": kind})
    if len(rows) != 150 or Counter(row["type"] for row in rows) != {
        "choice": 50, "noul": 50, "score": 50,
    }:
        raise AssertionError("teacher gate must contain 150 questions, 50 per type")
    return rows


def _gate_metrics(rows: list[dict], model: str, costs: list[dict]) -> dict:
    def aggregate(selected):
        correct = total = ties = failed_questions = failed_calls = 0
        sharpness = []
        for row in selected:
            result = row["teachers"][model]
            failed_calls += len(result["failures"])
            if result["valid_samples"] == 0:
                failed_questions += 1
                continue
            total += 1
            correct += int(result["majority"] == row["gold"])
            ties += int(result["majority"] is None)
            distribution = result["distribution"]
            if distribution:
                probabilities = list(distribution.values())
                sharpness.append({
                    "max_probability": max(probabilities),
                    "entropy_nats": -sum(p * math.log(p) for p in probabilities if p > 0),
                })
        return {
            "correct": correct, "total": total,
            "agreement": correct / total if total else None,
            "failed_calls": failed_calls, "failed_questions": failed_questions,
            "no_majority": ties,
            "mean_max_probability": statistics.mean(x["max_probability"] for x in sharpness) if sharpness else None,
            "mean_entropy_nats": statistics.mean(x["entropy_nats"] for x in sharpness) if sharpness else None,
        }

    overall = aggregate(rows)
    family = {name: aggregate([row for row in rows if row["family"] == name]) for name in CODE_FAMILIES}
    by_type = {name: aggregate([row for row in rows if row["type"] == name])
               for name in ("choice", "noul", "score")}
    spend = sum(float(row["cost_usd"]) for row in costs if row.get("role") == f"gate:{model}")
    return {
        "overall": overall, "by_family": family, "by_type": by_type,
        "cost_usd": spend, "cost_per_decision": spend / 150,
    }


def _write_gate_report(run_dir: Path, run: str, gate: dict, selected: str | None,
                       paraphrase_stats: dict, round_costs: list[dict], cumulative: float):
    report_dir = ROOT / "training/decisions/reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    provider = Counter()
    for row in round_costs:
        provider[row["provider"]] += float(row["cost_usd"])
    records = _read_jsonl(run_dir / "code_generated.jsonl")
    gold_positions = Counter()
    observed_quartiles = [0, 0, 0, 0]
    expected_quartiles = [0.0, 0.0, 0.0, 0.0]
    for item in records:
        for qid, question in item["questions"].items():
            if question["type"] == "choice":
                labels = list(question["criteria"])
                position = labels.index(item["gold"][qid])
                option_count = len(labels)
                gold_positions[str(position)] += 1
                observed_quartiles[min(3, position * 4 // option_count)] += 1
                for slot in range(option_count):
                    expected_quartiles[min(3, slot * 4 // option_count)] += 1 / option_count
    chi_square = sum(
        (observed - expected) ** 2 / expected
        for observed, expected in zip(observed_quartiles, expected_quartiles) if expected
    )
    gamma_x = chi_square / 2
    chi_square_p = math.erfc(math.sqrt(gamma_x)) + (
        2 * math.sqrt(gamma_x) * math.exp(-gamma_x) / math.sqrt(math.pi)
    )
    lines = [
        f"# Reasoning-teacher gate: `{run}`", "",
        f"- Selected teacher: `{selected}`." if selected else "- No teacher reached 95%; downstream stages were not run.",
        f"- Cumulative spend including prior pilot spend: ${cumulative:.6f} of $15.00.",
        f"- Amendment-2 spend: OpenAI ${provider['openai']:.6f}; Anthropic ${provider['anthropic']:.6f}; "
        f"total ${sum(provider.values()):.6f}.",
        f"- Paraphrases accepted: {paraphrase_stats.get('paraphrase_passes', 0)}/150; "
        f"rejected attempts: {paraphrase_stats.get('rejections', 0)}.",
        "", "## Candidate gate results", "",
        "| Candidate | Agreement | Valid questions | Failed calls | $/decision | Mean max-p | Mean entropy (nats) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, result in gate.items():
        overall = result["overall"]
        agreement = f"{overall['agreement']:.2%}" if overall["agreement"] is not None else "n/a"
        max_p = f"{overall['mean_max_probability']:.5f}" if overall["mean_max_probability"] is not None else "n/a"
        entropy = f"{overall['mean_entropy_nats']:.5f}" if overall["mean_entropy_nats"] is not None else "n/a"
        lines.append(
            f"| {model} | {overall['correct']}/{overall['total']} ({agreement}) "
            f"| {overall['total']} | {overall['failed_calls']} | ${result['cost_per_decision']:.6f} "
            f"| {max_p} | {entropy} |"
        )
    for model, result in gate.items():
        lines.extend([
            "", f"### {model}: agreement by family and type", "", "```json",
            json.dumps({"by_family": result["by_family"], "by_type": result["by_type"]}, indent=2), "```",
        ])
    lines.extend([
        "", "## Paraphrase and option-position checks", "",
        f"- Choice gold-position histogram (0-based): `{json.dumps(gold_positions, sort_keys=True)}`.",
        f"- Conditional quartile chi-square: {chi_square:.4f} (df=3, p={chi_square_p:.5f}); "
        f"observed `{observed_quartiles}`, expected under uniform insertion "
        f"`{[round(value, 2) for value in expected_quartiles]}`.",
        "- Gold slots are inserted with a uniform RNG draw among each question's stored option positions.",
        "", "## Full gate metrics", "", "```json", json.dumps(gate, indent=2), "```",
    ])
    (report_dir / "pilot_gen.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not selected:
        (report_dir / "pilot_samples.md").write_text(
            "# Pilot samples\n\nThe reasoning-teacher gate did not pass; no authoring or downstream pilot samples were generated.\n",
            encoding="utf-8",
        )


async def label_stage(args, run_dir: Path, rng: random.Random):
    ledger = BudgetLedger(args.budget, RUNS / "gen_cost.jsonl", args.run, "amendment-2")
    api = ApiClient()
    generated = _read_jsonl(run_dir / "code_generated.jsonl")
    if len(generated) != 150:
        raise RuntimeError(f"expected 150 regenerated code states; found {len(generated)}")
    subset = _gate_subset(generated, args.seed)
    gate_rows = [{
        "id": row["item"]["id"], "family": row["item"]["family"], "qid": row["qid"],
        "type": row["type"], "gold": row["item"]["gold"][row["qid"]],
        "teachers": {},
    } for row in subset]
    for start in range(0, len(subset), 8):
        batch = subset[start:start + 8]
        results = await asyncio.gather(*[
            api.sampled_label(
                model, row["item"]["state"], row["item"]["questions"][row["qid"]], ledger,
                decision_id=f"{row['item']['id']}:{row['qid']}", role=f"gate:{model}",
            )
            for row in batch for model in CODE_TEACHERS
        ], return_exceptions=True)
        cursor = 0
        for row in batch:
            for model in CODE_TEACHERS:
                result = results[cursor]
                cursor += 1
                if isinstance(result, BudgetExceeded):
                    raise result
                if isinstance(result, Exception):
                    result = {"distribution": None, "samples": [], "valid_samples": 0, "majority": None,
                              "failures": [{"reason": f"{type(result).__name__}: {result}"}]}
                gate_rows[start + batch.index(row)]["teachers"][model] = result
    cost_rows = [
        json.loads(line) for line in (RUNS / "gen_cost.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("run") == args.run
        and json.loads(line).get("round_id") == "amendment-2"
    ]
    gate = {model: _gate_metrics(gate_rows, model, cost_rows) for model in CODE_TEACHERS}
    for model in CODE_TEACHERS:
        gate[model]["unavailable"] = api.unavailable_models.get(model)
    qualifying = [model for model in CODE_TEACHERS if
                  (gate[model]["overall"]["agreement"] or 0) >= 0.95]
    selected = min(qualifying, key=lambda model: gate[model]["cost_per_decision"]) if qualifying else None
    _write_jsonl(run_dir / "gate_labels.jsonl", gate_rows)
    (run_dir / "teacher_agreement.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    disagreements = []
    for row in gate_rows:
        for model, result in row["teachers"].items():
            if result["valid_samples"] and result["majority"] != row["gold"]:
                item = next(item for item in generated if item["id"] == row["id"])
                disagreements.append({
                    "id": row["id"], "family": row["family"], "qid": row["qid"],
                    "gold": row["gold"], "majority": result["majority"], "model": model,
                    "samples": result["samples"], "state": item["state"],
                    "question": item["questions"][row["qid"]],
                })
    _write_jsonl(run_dir / "code_disagreements.jsonl", disagreements)
    paraphrase_stats = json.loads((run_dir / "paraphrase_stats.json").read_text(encoding="utf-8"))
    _write_gate_report(run_dir, args.run, gate, selected, paraphrase_stats, cost_rows, ledger.spent)
    if not selected:
        _write_jsonl(run_dir / "failed_calls.jsonl", [
            {"id": row["id"], "qid": row["qid"], "model": model, **failure}
            for row in gate_rows for model, result in row["teachers"].items()
            for failure in result["failures"]
        ])
        raise RuntimeError("no reasoning teacher reached the required 95% majority agreement")

    rejected, failed_calls, retained_code = [], [], []
    gate_by_key = {(row["id"], row["qid"]): row["teachers"][selected] for row in gate_rows}
    for item in generated:
        questions, gold, teacher, target = {}, {}, {}, {}
        for qid, question in item["questions"].items():
            result = gate_by_key.get((item["id"], qid))
            if result is None:
                try:
                    result = await api.sampled_label(
                        selected, item["state"], question, ledger,
                        decision_id=f"{item['id']}:{qid}", role=f"teacher:{selected}",
                    )
                except BudgetExceeded:
                    raise
                except Exception as exc:
                    result = {"distribution": None, "failures": [{"reason": f"{type(exc).__name__}: {exc}"}]}
            distribution = result["distribution"]
            failed_calls.extend(
                {"id": item["id"], "qid": qid, "model": selected, **failure}
                for failure in result.get("failures", [])
            )
            if not distribution or _argmax(distribution) != item["gold"][qid]:
                rejected.append({"id": item["id"], "qid": qid, "family": item["family"],
                                 "reason": "selected teacher's sampled distribution disagreed with code gold"})
                continue
            questions[qid], gold[qid] = question, item["gold"][qid]
            teacher[qid], target[qid] = {selected: distribution}, floored(distribution)
        if questions:
            item.update(questions=questions, gold=gold, gold_basis={qid: "code" for qid in gold},
                        teacher=teacher, target=target)
            retained_code.append(item)

    authored, author_rejections = await author_items(60, rng, api, ledger)
    generated_authored = authored
    authored, author_failures = await _label_batches(authored, list(AUTHOR_TEACHERS), api, ledger)
    labeled_ids = {item["id"] for item in authored}
    author_rejections.extend(
        {"id": item["id"], "family": item["family"], "reason": "budget exhausted before teacher labeling"}
        for item in generated_authored if item["id"] not in labeled_ids
    )
    target_stats = {
        "code_gate": {model: gate[model]["overall"] for model in CODE_TEACHERS},
        "authored": _teacher_distribution_stats(authored, AUTHOR_TEACHERS),
        "unavailable_candidates": api.unavailable_models,
    }
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
            keep_questions[qid], gold[qid] = question, _argmax(merged)
            target[qid], teacher[qid] = floored(merged), teachers
        if keep_questions:
            item.update(questions=keep_questions, gold=gold, gold_basis={qid: "teacher" for qid in gold},
                        teacher=teacher, target=target)
            retained_authored.append(item)
    all_records = retained_code + retained_authored
    _write_jsonl(run_dir / "records_labeled.jsonl", all_records)
    _write_jsonl(run_dir / "label_rejections.jsonl", rejected)
    _write_jsonl(run_dir / "failed_calls.jsonl", failed_calls)
    (run_dir / "teacher_target_stats.json").write_text(json.dumps(target_stats, indent=2) + "\n", encoding="utf-8")
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
    missing_code_families = set(CODE_FAMILIES) - {
        row["family"] for row in records if row.get("source") == "code"
    }
    if missing_code_families:
        raise ValueError(f"decontaminated data is missing code families: {sorted(missing_code_families)}")
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
    train_ids, dev_ids = {row["id"] for row in train}, {row["id"] for row in dev}
    if train_ids & dev_ids:
        raise AssertionError("train and dev contain overlapping states")
    missing_dev_families = set(CODE_FAMILIES) - {
        row["family"] for row in dev if row.get("source") == "code"
    }
    if missing_dev_families:
        raise AssertionError(f"dev split is missing code families: {sorted(missing_dev_families)}")
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
    amendment_provider_cost = defaultdict(float)
    for row in costs:
        role_totals[row["role"]] += float(row["cost_usd"])
        provider_cost[row["provider"]] += float(row["cost_usd"])
        if row.get("round_id") == "amendment-2":
            amendment_provider_cost[row["provider"]] += float(row["cost_usd"])
        if row.get("decision_id"):
            role_decisions[row["role"]].add(row["decision_id"])
    type_counts, option_counts, gold_positions = Counter(), Counter(), Counter()
    noul_balance, score_levels = Counter(), Counter()
    position_records = _read_jsonl(run_dir / "code_generated.jsonl")
    position_observed = [0, 0, 0, 0]
    position_expected = [0.0, 0.0, 0.0, 0.0]
    for item in position_records:
        for qid, question in item["questions"].items():
            if question["type"] != "choice":
                continue
            labels = list(question["criteria"])
            count = len(labels)
            position = labels.index(item["gold"][qid])
            position_observed[min(3, position * 4 // count)] += 1
            for slot in range(count):
                position_expected[min(3, slot * 4 // count)] += 1 / count
    position_chi2 = sum(
        (observed - expected) ** 2 / expected
        for observed, expected in zip(position_observed, position_expected) if expected
    )
    position_x = position_chi2 / 2
    position_p = math.erfc(math.sqrt(position_x)) + (
        2 * math.sqrt(position_x) * math.exp(-position_x) / math.sqrt(math.pi)
    )
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
        row for row in costs if selected and row["role"] in (f"teacher:{selected}", f"gate:{selected}")
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
        f"- Cumulative API spend: OpenAI ${provider_cost['openai']:.6f}; "
        f"Anthropic ${provider_cost['anthropic']:.6f}; total ${sum(provider_cost.values()):.6f}.",
        f"- Amendment-2 API spend: OpenAI ${amendment_provider_cost['openai']:.6f}; "
        f"Anthropic ${amendment_provider_cost['anthropic']:.6f}; "
        f"total ${sum(amendment_provider_cost.values()):.6f}.",
        f"- Code-gold teacher selected: `{selected}`.",
        f"- Retained decisions: {sum(len(item['questions']) for item in records)} across {len(records)} states.",
        "", "## Cost by role", "",
        "| Role | USD per decision | Calls/decisions logged | USD total / decision* |",
        "|---|---:|---:|---:|", *role_lines,
        "", "*Role totals include all logged pilot rounds; totals are divided by the corresponding decision count, "
        "and Claude sampling calls share a decision ID.",
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
                               if key in ("code", "code_gate", "authored")}, indent=2), "```",
        "", "## Rejections", "",
        f"- Rejected questions/items: {len(rejections)}; generated records: {len(all_labeled)}.",
        f"- Rejection rate by generated record: {len(rejections)/max(1,len(all_labeled)):.1%}.",
        "```json", json.dumps(dict(reasons), indent=2), "```",
        "", "## Histograms", "",
        f"- Question types: `{json.dumps(type_counts, sort_keys=True)}`",
        f"- Option counts: `{json.dumps(option_counts, sort_keys=True)}`",
        f"- Gold positions (0-based): `{json.dumps(gold_positions, sort_keys=True)}`",
        f"- Gold-position chi-square, conditional on each question's option count: "
        f"{position_chi2:.4f} (df=3, p={position_p:.5f}).",
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
        for item in family_rows[:1]:
            samples.append((item, next(iter(item["questions"]))))
    authored_rows = [item for item in records if item["source"] == "synthetic-llm"]
    for item in authored_rows[:6]:
        samples.append((item, next(iter(item["questions"]))))
    rendered_samples = ["# Pilot samples for review", "",
                        f"{len(samples)} samples are included: one per code family plus six authored when available."]
    for index, (item, qid) in enumerate(samples, 1):
        question = item["questions"][qid]
        prompt, _ = render_question(item["state"], question)
        sample_prompt = "\n".join(line.rstrip() for line in prompt.splitlines())
        rendered_samples.extend([
            "", f"## Sample {index}: {item['family']} / {qid} / {item['id']}", "",
            f"Source: {item['source']}; target: `{json.dumps(item['target'][qid], sort_keys=True)}`",
            f"Gold metadata: `{item['gold'][qid]}`", "", "```text",
            f"system: {LABEL_SYSTEM}\nuser:\n{sample_prompt}", "```",
        ])
    (report_dir / "pilot_samples.md").write_text("\n".join(rendered_samples) + "\n", encoding="utf-8")


def _surface_for_gold(value: str) -> str | None:
    if value.startswith("date_"):
        return "-".join(value.split("_")[1:])
    if value.startswith("utc_"):
        parts = value.split("_")[1:]
        return f"{parts[0]}-{parts[1]}-{parts[2]} {parts[3]}:{parts[4]} UTC"
    if value.startswith("usd_"):
        whole, cents = value.removeprefix("usd_").rsplit("_", 1)
        return f"${whole}.{cents}"
    if value.startswith("count_"):
        return f"{value.removeprefix('count_')} eligible referrals"
    if value.startswith("hours_"):
        return f"{value.removeprefix('hours_')} hours"
    if value.startswith("posterior_"):
        return f"{float(value.removeprefix('posterior_').replace('_', '.')):.2%}"
    return None


def _leak_errors(item: dict) -> list[str]:
    errors = []
    for qid, answer in item.get("gold", {}).items():
        surface = _surface_for_gold(str(answer))
        if surface and surface.lower() in item["state"].lower():
            errors.append(f"{item['id']}:{qid}: gold surface {surface!r} occurs in state")
    intermediates = [str(value).lower() for value in item.get("_leak_audit", {}).get("intermediate_values", [])]
    for qid, question in item.get("questions", {}).items():
        criteria = question["criteria"]
        descriptions = criteria.values() if isinstance(criteria, dict) else criteria
        for description in descriptions:
            for intermediate in intermediates:
                if intermediate and intermediate in str(description).lower():
                    errors.append(f"{item['id']}:{qid}: intermediate {intermediate!r} occurs in option description")
    return errors


def _chi_square_position(records: list[dict]) -> tuple[list[int], list[float], float, float]:
    observed, expected = [0, 0, 0, 0], [0.0, 0.0, 0.0, 0.0]
    for item in records:
        for qid, question in item["questions"].items():
            if question["type"] != "choice":
                continue
            labels = list(question["criteria"])
            count = len(labels)
            position = labels.index(item["gold"][qid])
            observed[min(3, position * 4 // count)] += 1
            for slot in range(count):
                expected[min(3, slot * 4 // count)] += 1 / count
    chi2 = sum((actual - target) ** 2 / target for actual, target in zip(observed, expected) if target)
    x = chi2 / 2
    p_value = math.erfc(math.sqrt(x)) + 2 * math.sqrt(x) * math.exp(-x) / math.sqrt(math.pi)
    return observed, expected, chi2, p_value


async def mini_check_stage(args, run_dir: Path, rng: random.Random):
    cost_path = RUNS / "gen_cost.jsonl"
    all_costs = [json.loads(line) for line in cost_path.read_text(encoding="utf-8").splitlines()
                 if line.strip()] if cost_path.is_file() else []
    initial_cost_count = len(all_costs)
    prior_spend = sum(float(row.get("cost_usd", 0.0)) for row in all_costs)
    prior_mini_spend = sum(
        float(row.get("cost_usd", 0.0)) for row in all_costs
        if row.get("run") == args.run and row.get("round_id") == "quality-mini"
    )
    cumulative_room = 10.0 - prior_spend
    if cumulative_room <= 0:
        raise BudgetExceeded(f"cumulative spend is already ${prior_spend:.6f}, above the $10 cap")
    ledger = BudgetLedger(
        min(3.0, args.budget, cumulative_room), cost_path, args.run, "quality-mini"
    )
    api = ApiClient()
    question_rng = random.Random(args.seed + 911)
    record_rng = random.Random(args.seed + 1777)
    code_records = []
    for family, generate in GENERATORS.items():
        for _ in range(5):
            count = question_rng.randint(1, 6)
            code_records.append(generate(record_rng, "mixed", count, ["choice", "noul", "score"]))
    _write_jsonl(run_dir / "code_generated.jsonl", code_records)
    leak_errors = [error for item in code_records for error in _leak_errors(item)]

    authored, author_rejections = await author_items(20, rng, api, ledger)
    _write_jsonl(run_dir / "author_generated.jsonl", authored)
    _write_jsonl(run_dir / "author_rejections.jsonl", author_rejections)

    failed_calls, code_question_results = [], {}

    async def label_code_question(item, qid, question):
        try:
            result = await api.sampled_label(
                "gpt-5.4-nano", item["state"], question, ledger,
                decision_id=f"{item['id']}:{qid}", role="teacher:gpt-5.4-nano",
            )
            return item, qid, result
        except BudgetExceeded:
            raise
        except Exception as exc:
            return item, qid, {"distribution": None, "majority": None, "samples": [],
                               "failures": [{"reason": f"{type(exc).__name__}: {exc}"}]}

    code_jobs = [label_code_question(item, qid, question)
                 for item in code_records for qid, question in item["questions"].items()]
    for item, qid, result in await asyncio.gather(*code_jobs):
        code_question_results[(item["id"], qid)] = result
        item.setdefault("teacher", {})[qid] = {"gpt-5.4-nano": result.get("distribution")}
        item.setdefault("teacher_samples", {})[qid] = {"gpt-5.4-nano": {
            "majority": result.get("majority"), "samples": result.get("samples", []),
        }}
        if result.get("distribution"):
            item.setdefault("target", {})[qid] = result["distribution"]
        failed_calls.extend({"id": item["id"], "qid": qid, "model": "gpt-5.4-nano", **failure}
                            for failure in result.get("failures", []))

    author_question_results = {}

    async def label_author_question(item, qid, question):
        decision_id = f"{item['id']}:{qid}"
        async def nano():
            return await api.sampled_label(
                "gpt-5.4-nano", item["state"], question, ledger,
                decision_id=decision_id, role="teacher:gpt-5.4-nano",
            )
        async def classic():
            return await api.classic_label(
                "gpt-4.1-mini", item["state"], question, ledger, decision_id=decision_id
            )
        outputs = await asyncio.gather(nano(), classic(), return_exceptions=True)
        result = {}
        for model, output in zip(("gpt-5.4-nano", "gpt-4.1-mini"), outputs):
            if isinstance(output, BudgetExceeded):
                raise output
            if isinstance(output, Exception):
                result[model] = None
                failed_calls.append({"id": item["id"], "qid": qid, "model": model,
                                     "reason": f"{type(output).__name__}: {output}"})
            elif model == "gpt-5.4-nano":
                result[model] = output
                failed_calls.extend({"id": item["id"], "qid": qid, "model": model, **failure}
                                    for failure in output.get("failures", []))
            else:
                result[model] = output
        return item, qid, result

    author_jobs = [label_author_question(item, qid, question)
                   for item in authored for qid, question in item["questions"].items()]
    for item, qid, result in await asyncio.gather(*author_jobs):
        author_question_results[(item["id"], qid)] = result

    author_model_by_id = {item["id"]: item["author_model"] for item in authored}
    retained_authored, author_agreement = [], []
    author_retained_counts, author_decision_counts = Counter(), Counter()
    for item in authored:
        kept_questions, kept_gold, kept_teacher, kept_target = {}, {}, {}, {}
        for qid, question in item["questions"].items():
            author_model_by_id[item["id"]] = item["author_model"]
            author_decision_counts[item["author_model"]] += 1
            outputs = author_question_results.get((item["id"], qid), {})
            nano = outputs.get("gpt-5.4-nano") or {}
            classic = outputs.get("gpt-4.1-mini")
            labels = list(question["criteria"]) if question["type"] in ("choice", "noul") else [
                str(index) for index in range(len(question["criteria"]))
            ]
            nano_samples = nano.get("samples", [])
            nano_dist = (
                {key: nano_samples.count(key) / len(nano_samples) for key in labels}
                if nano_samples else None
            )
            classic_argmax = _argmax(classic)
            majority = nano.get("majority")
            if nano_dist and classic and majority and classic_argmax:
                author_agreement.append(majority == classic_argmax)
            if not nano_dist or not classic or not majority or majority != classic_argmax:
                continue
            mixed = {
                key: 0.5 * float(nano_dist.get(key, 0.0)) + 0.5 * float(classic.get(key, 0.0))
                for key in labels
            }
            kept_questions[qid] = question
            kept_gold[qid] = _argmax(floored(mixed))
            kept_teacher[qid] = {"gpt-5.4-nano": nano_dist, "gpt-4.1-mini": classic}
            kept_target[qid] = floored(mixed)
            author_retained_counts[item["author_model"]] += 1
        if kept_questions:
            item.update(questions=kept_questions, gold=kept_gold, teacher=kept_teacher,
                        target=kept_target, gold_basis={qid: "teacher" for qid in kept_gold})
            retained_authored.append(item)

    labeled_records = code_records + retained_authored
    _write_jsonl(run_dir / "records_labeled.jsonl", labeled_records)
    _write_jsonl(run_dir / "failed_calls.jsonl", failed_calls)
    _write_jsonl(run_dir / "label_rejections.jsonl", [
        {"id": item["id"], "qid": qid, "family": item["family"],
         "reason": "nano majority disagreed with GPT-4.1-mini argmax or a label failed"}
        for item in authored for qid in item.get("authored_answer", {})
        if qid not in item.get("target", {})
    ])

    cleaned, decontam_report = decontam(labeled_records, ROOT)
    _write_jsonl(run_dir / "records_decontam.jsonl", cleaned)
    (run_dir / "decontam.json").write_text(json.dumps(decontam_report, indent=2) + "\n", encoding="utf-8")
    observed, expected, chi2, chi2_p = _chi_square_position(code_records)

    gate_candidates = []
    for family in CODE_FAMILIES:
        family_rows = [item for item in code_records if item["family"] == family]
        questions = [(item, qid, question)
                     for item in family_rows for qid, question in item["questions"].items()]
        selected = []
        for kind in ("choice", "noul", "score"):
            selected.extend([row for row in questions if row[2]["type"] == kind][:3])
        selected_ids = {(item["id"], qid) for item, qid, _ in selected}
        selected.extend(row for row in questions if (row[0]["id"], row[1]) not in selected_ids
                        and len(selected) < 10)
        gate_candidates.extend(selected[:10])
    gate_candidates = gate_candidates[:60]
    if len(gate_candidates) != 60:
        raise RuntimeError(f"the reasoning-teacher gate requires 60 questions; found {len(gate_candidates)}")
    gate_correct = gate_valid = gate_failed = 0
    gate_by_type = Counter()
    gate_type_valid = Counter()
    gate_by_family = Counter()
    code_all_correct = code_all_valid = code_all_failed = 0
    for item in code_records:
        for qid in item["questions"]:
            result = code_question_results[(item["id"], qid)]
            code_all_failed += len(result.get("failures", []))
            prediction = result.get("majority")
            if prediction:
                code_all_valid += 1
                code_all_correct += prediction == item["gold"][qid]
    for item, qid, question in gate_candidates:
        result = code_question_results[(item["id"], qid)]
        gate_failed += len(result.get("failures", []))
        prediction = result.get("majority")
        if prediction:
            gate_valid += 1
            gate_type_valid[question["type"]] += 1
            correct = prediction == item["gold"][qid]
            gate_correct += correct
            gate_by_type[question["type"] + (":correct" if correct else ":wrong")] += 1
            gate_by_family[item["family"] + (":correct" if correct else ":wrong")] += 1

    all_costs = [json.loads(line) for line in cost_path.read_text(encoding="utf-8").splitlines()
                 if line.strip()] if cost_path.is_file() else []
    round_costs = [row for row in all_costs[initial_cost_count:] if row.get("run") == args.run
                   and row.get("round_id") == "quality-mini"]
    actual_spend = sum(float(row.get("cost_usd", 0.0)) for row in round_costs)
    mini_spend = prior_mini_spend + actual_spend
    cumulative_spend = prior_spend + actual_spend
    if mini_spend > 3.0 + 1e-8 or cumulative_spend > 10.0 + 1e-8:
        raise BudgetExceeded(
            f"spend guard exceeded: mini ${mini_spend:.6f}, cumulative ${cumulative_spend:.6f}"
        )
    author_cost = Counter()
    for row in round_costs:
        cost = float(row.get("cost_usd", 0.0))
        decision_id = str(row.get("decision_id") or "")
        if row.get("role") == "author":
            if decision_id.startswith("author:"):
                author_cost[str(row.get("model"))] += cost
        else:
            owner_id = next((item_id for item_id in author_model_by_id if decision_id.startswith(item_id + ":")), None)
            if owner_id:
                author_cost[author_model_by_id[owner_id]] += cost
    author_states_requested = {"gpt-5.4-mini": 16, "claude-sonnet-5-5": 4}
    author_state_retained = Counter(item["author_model"] for item in authored)
    retained_record_states = Counter(item["author_model"] for item in retained_authored)
    total_generated_questions = sum(len(item["questions"]) for item in code_records + authored)
    total_generated_states = len(code_records) + len(authored)
    mean_questions = total_generated_questions / max(1, total_generated_states)
    code_questions = sum(len(item["questions"]) for item in code_records)
    authored_questions = sum(len(item["questions"]) for item in authored)
    code_mean_questions = code_questions / max(1, len(code_records))
    authored_mean_questions = authored_questions / max(1, len(authored))
    code_cost = sum(float(row.get("cost_usd", 0.0)) for row in round_costs
                    if any(str(row.get("decision_id", "")).startswith(item["id"] + ":")
                           for item in code_records))
    author_projection_cost = sum(
        author_cost[model] / max(1, author_retained_counts[model])
        * round(7000 * author_states_requested[model] / sum(author_states_requested.values()))
        for model in author_states_requested
    )
    code_projection_cost = code_cost / max(1, code_questions) * 9000

    clean_code = [item for item in cleaned if item["source"] == "synthetic-code"]
    clean_authored = [item for item in cleaned if item["source"] == "synthetic-llm"]
    samples = []
    for family in CODE_FAMILIES:
        item = next((row for row in clean_code if row["family"] == family and row.get("target")), None)
        if item:
            qid = next((key for key in item["questions"] if key in item.get("target", {})), None)
            if qid:
                samples.append((item, qid))
    sonnet_samples = [(item, qid) for item in clean_authored if item.get("author_model") == "claude-sonnet-5-5"
                      for qid in item["questions"] if qid in item.get("target", {})]
    mini_samples = [(item, qid) for item in clean_authored if item.get("author_model") == "gpt-5.4-mini"
                    for qid in item["questions"] if qid in item.get("target", {})]
    authored_samples = sonnet_samples[:2]
    authored_samples.extend(mini_samples[:max(0, 6 - len(authored_samples))])
    if len(authored_samples) < 6:
        existing = {(item["id"], qid) for item, qid in authored_samples}
        authored_samples.extend(
            (item, qid) for item in clean_authored for qid in item["questions"]
            if qid in item.get("target", {}) and (item["id"], qid) not in existing
        )
    samples.extend(authored_samples[:6])
    samples = samples[:12]
    sonnet_sample_count = sum(item.get("author_model") == "claude-sonnet-5-5" for item, _ in samples)
    if len(samples) != 12 or sonnet_sample_count < 2:
        raise RuntimeError(
            f"cannot produce 12 review samples with at least two Sonnet samples "
            f"(produced {len(samples)}, Sonnet {sonnet_sample_count})"
        )
    sample_lines = [
        "# Mini-check samples", "",
        f"{len(samples)} samples: one per code family and six authored, with at least two Sonnet samples when retained.",
    ]
    for index, (item, qid) in enumerate(samples, 1):
        prompt, _ = render_question(item["state"], item["questions"][qid])
        sample_lines.extend([
            "", f"## Sample {index}: {item['family']} / {qid} / {item['id']}", "",
            f"Author model: `{item.get('author_model', 'code generator')}`; "
            f"target: `{json.dumps(item['target'][qid], sort_keys=True)}`; gold: `{item['gold'][qid]}`.",
            "", "```text", f"system: {LABEL_SYSTEM}\nuser:\n{prompt}", "```",
        ])
    (ROOT / "training/decisions/reports/pilot_samples.md").write_text(
        "\n".join(sample_lines) + "\n", encoding="utf-8"
    )

    author_metrics = []
    for model, requested in author_states_requested.items():
        retained_questions = author_retained_counts[model]
        valid_states = author_state_retained[model]
        retained_states = retained_record_states[model]
        author_metrics.append(
            f"| {model} | {requested} | {valid_states}/{requested} "
            f"({valid_states/max(1,requested):.1%}) | {retained_states}/{valid_states} "
            f"({retained_states/max(1,valid_states):.1%}) | "
            f"{retained_questions}/{author_decision_counts[model]} "
            f"({retained_questions/max(1,author_decision_counts[model]):.1%}) | "
            f"${author_cost[model]/max(1,retained_questions):.6f} |"
        )
    report = [
        f"# Decisions quality mini-check: `{args.run}`", "",
        f"- Mini-check spend: ${mini_spend:.6f} / $3.00; cumulative spend ${cumulative_spend:.6f} / $10.00.",
        f"- Code: {len(code_records)} states, {code_questions} questions, 5 per family.",
        f"- Authored: {len(authored)} schema-valid states requested from 16 mini / 4 Sonnet; "
        f"{len(retained_authored)} states retained after teacher agreement.",
        f"- Questions/state: overall {mean_questions:.2f}, code {code_mean_questions:.2f}, "
        f"authored {authored_mean_questions:.2f}; expected code draw range 1–6.",
        f"- Nano agreement across all code questions: {code_all_correct}/{code_all_valid} "
        f"({code_all_correct/max(1,code_all_valid):.2%}); failed calls {code_all_failed}.",
        f"- Nano code agreement on the 60-question gate: {gate_correct}/{gate_valid} "
        f"({gate_correct/max(1,gate_valid):.2%}); failed calls {gate_failed}; "
        f"majority coverage {gate_valid}/60 ({gate_valid/60:.2%}); "
        f"95% gate {'PASS' if gate_correct/60 >= 0.95 else 'FAIL'} when unavailable questions count as misses.",
        f"- Nano vs GPT-4.1-mini authored argmax agreement: {sum(author_agreement)}/"
        f"{len(author_agreement)} ({sum(author_agreement)/max(1,len(author_agreement)):.2%}).",
        "", "## Author retention and unit costs", "",
        "| Author model | Requested states | Schema-valid / requested | Retained / schema-valid | Retained decisions / labeled decisions | $ / retained decision |",
        "|---|---:|---:|---:|---:|---:|",
        *author_metrics,
        "", "## Agreement by code question type", "",
        f"`{json.dumps(dict(gate_by_type), sort_keys=True)}`; valid majority counts "
        f"`{json.dumps(dict(gate_type_valid), sort_keys=True)}`.",
        f"- Gate agreement by family: `{json.dumps(dict(gate_by_family), sort_keys=True)}`.",
        "", "## Position and leakage", "",
        f"- Gold-position quartiles: observed `{observed}`, expected `{[round(value, 2) for value in expected]}`; "
        f"χ²={chi2:.4f}, df=3, p={chi2_p:.5f}.",
        f"- Leak test: {'PASS' if not leak_errors else 'FAIL'}; {len(code_records)} states checked, "
        f"{len(leak_errors)} failures.",
        f"- Leak details: `{json.dumps(leak_errors[:20])}`.",
        "", "## Cost projection", "",
        f"- Measured code teacher spend: ${code_cost:.6f} / {code_questions} generated code decisions "
        f"(${code_cost/max(1,code_questions):.6f}/decision); 9,000 decisions: ${code_projection_cost:.2f}.",
        f"- Authored authoring+label spend projected at retained-decision rates for 7,000 decisions: "
        f"${author_projection_cost:.2f}.",
        f"- Combined projection for 9,000 code-gold plus 7,000 authored decisions: "
        f"${code_projection_cost + author_projection_cost:.2f}.",
        "", "## Decontamination", "", "```json", json.dumps(decontam_report, indent=2), "```",
        "", "## Artifacts", "",
        f"- Records: `{run_dir.relative_to(ROOT)}/records_decontam.jsonl`",
        "- Samples: `training/decisions/reports/pilot_samples.md`",
        f"- Author question agreement: {sum(author_agreement)}/{len(author_agreement)} valid pairs.",
    ]
    report_dir = ROOT / "training/decisions/reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "mini_check.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"spend": mini_spend, "cumulative": cumulative_spend, "report": str(report_dir / "mini_check.md")}


def datums_stage(run_dir: Path, run: str, write_report: bool = True):
    records = _read_jsonl(run_dir / "train.jsonl") + _read_jsonl(run_dir / "dev.jsonl")
    token_counts = []
    datum_path = run_dir / "datums.jsonl"
    if run == "full":
        renderer = GenericRenderer("Qwen/Qwen3.5-4B")
        with datum_path.open("w", encoding="utf-8") as handle:
            for item in records:
                for qid, question in item["questions"].items():
                    target = item.get("target", {}).get(qid) or {item["gold"][qid]: 1.0}
                    datum, rendering = render_question(renderer, item["state"], question, target)
                    tensor = datum.loss_fn_inputs["weights"].to_torch()
                    if tensor.is_sparse:
                        tensor = tensor.to_dense()
                    token_counts.append(rendering.choice_pos)
                    row = {
                        "record_id": item["id"], "qid": qid, "family": item["family"],
                        "input_tokens": rendering.tokens[:rendering.choice_pos],
                        "choice_pos": rendering.choice_pos, "label_token_ids": rendering.label_tokens,
                        "target": target, "weights": tensor.tolist(),
                    }
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    else:
        rows = []
        for entry in render_records(records):
            rendering = entry["rendering"]
            token_counts.append(rendering.choice_pos)
            tensor = entry["datum"].loss_fn_inputs["weights"].to_torch()
            if tensor.is_sparse:
                tensor = tensor.to_dense()
            rows.append({
                "record_id": entry["record_id"], "qid": entry["qid"], "family": entry["family"],
                "input_tokens": rendering.tokens[:rendering.choice_pos], "choice_pos": rendering.choice_pos,
                "label_token_ids": rendering.label_tokens, "target": entry["target"],
                "weights": tensor.tolist(),
            })
        _write_jsonl(datum_path, rows)
    stats = {
        "datum_count": len(token_counts),
        "mean_rendered_tokens": statistics.mean(token_counts) if token_counts else 0,
        "p95_rendered_tokens": sorted(token_counts)[int(0.95 * (len(token_counts)-1))] if token_counts else 0,
    }
    (run_dir / "datum_stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    if write_report:
        report_stage(run_dir, run)
    return stats


def upload_stage(args, run_dir: Path):
    repository = "jonsnov/muselet-decisions-v1" if args.run == "full" else f"jonsnov/muselet-decisions-{args.run}"
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(repository, repo_type="dataset", private=True, exist_ok=True)
    commit = api.upload_folder(
        folder_path=str(run_dir), repo_id=repository, repo_type="dataset", path_in_repo="data"
    )
    return {"repository": repository, "revision": commit.oid}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the generic-decision generation dataset.")
    parser.add_argument(
        "stage", choices=("gen", "label", "mini-check", "full", "decontam", "split", "datums", "upload")
    )
    parser.add_argument("--run", default="pilot")
    parser.add_argument("--budget", type=float)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args(argv)
    if args.seed is None:
        args.seed = 20261027 if args.stage == "full" else 814
    if args.budget is None and args.stage != "full":
        args.budget = 5.0
    run_dir = _run_dir(args.run)
    rng = random.Random(args.seed)
    if args.stage == "gen":
        asyncio.run(gen_stage(args, run_dir, rng))
    elif args.stage == "label":
        asyncio.run(label_stage(args, run_dir, rng))
    elif args.stage == "mini-check":
        print(json.dumps(asyncio.run(mini_check_stage(args, run_dir, rng)), indent=2))
    elif args.stage == "full":
        from .full_run import _cost_total, full_stage

        prior_spend = _cost_total(RUNS / "gen_cost.jsonl") if (RUNS / "gen_cost.jsonl").is_file() else 0.0
        ledger_path = RUNS / "gen_cost.jsonl"
        full_spend = sum(
            float(json.loads(line).get("cost_usd", 0))
            for line in ledger_path.read_text().splitlines()
            if line.strip() and json.loads(line).get("run") == args.run
        ) if ledger_path.is_file() else 0.0
        args.budget = args.budget if args.budget is not None else max(0.0, 57.0 - (prior_spend - full_spend))
        (run_dir / "run_config.json").write_text(json.dumps({"seed": args.seed, "budget_usd": args.budget}) + "\n")
        print(json.dumps(asyncio.run(full_stage(args, run_dir)), indent=2))
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
