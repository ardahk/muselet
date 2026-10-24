from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from bench.systemone.schema import parse_request
from training.decisions.build import _chi_square_position, _leak_errors
from training.decisions.label import ApiClient, BudgetExceeded, BudgetLedger
from training.decisions.paraphrase import validate_paraphrase

from . import FAMILIES
from .common import ROOT
from .decontam2 import decontam2
from .families import GENERATORS, cg_counting, cg_long_policy, cg_multi_hop, cg_numeric, cg_probability, cg_temporal, cg_trap

COST_PATH = ROOT / "runs/decisions/codegold/gen_cost.jsonl"
TEACHER = "gpt-5.4-nano"


def _read(path: Path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows), encoding="utf-8")


def _ledger(args):
    return BudgetLedger(budget=args.budget, path=COST_PATH, run="codegold", round_id="pilot",
                        cumulative_budget=66.0)


MODULES = {
    "cg_counting": cg_counting, "cg_multi_hop": cg_multi_hop, "cg_numeric": cg_numeric,
    "cg_temporal": cg_temporal, "cg_probability": cg_probability, "cg_trap": cg_trap,
    "cg_long_policy": cg_long_policy,
}


def _prompts():
    text = Path("/home/ubuntu/notes/paraphrase_prompts.md").read_text(encoding="utf-8")
    section = text.split("## SECTION_PROMPT\n", 1)[1].split("\n## STYLES", 1)[0]
    styles = [line[2:] for line in text.split("## STYLES", 1)[1].split("\n## QUESTION_PROMPT", 1)[0].splitlines()
              if line.startswith("- ")]
    question = text.split("## QUESTION_PROMPT\n", 1)[1]
    return section, styles, question


def _gen(args, run_dir):
    rng = random.Random(args.seed)
    existing = _read(run_dir / "code_generated.jsonl")
    by_family = Counter(item["family"] for item in existing)
    for family in FAMILIES:
        for _ in range(max(0, args.per_family - by_family[family])):
            item = GENERATORS[family](rng, rng.randint(2, 5))
            errors = _leak_errors(item)
            if errors:
                raise ValueError(f"generator leak audit failed: {errors}")
            parse_request({"state": item["state"], "questions": item["questions"]})
            existing.append(item)
    _write(run_dir / "code_generated.jsonl", existing)


async def _paraphrase(args, run_dir):
    records = _read(run_dir / "code_generated.jsonl")
    if not records:
        raise FileNotFoundError(run_dir / "code_generated.jsonl")
    section_prompt, styles, question_prompt = _prompts()
    rng = random.Random(args.seed + 101)
    candidates = [index for index, item in enumerate(records)
                  if item.get("_meta", {}).get("prose_sections")]
    selected = set(rng.sample(candidates, min(len(candidates), round(len(records) * 0.70))))
    api, ledger = ApiClient(concurrency=32), _ledger(args)
    rejected, changed_sections, changed_questions = [], 0, 0
    for item in records:
        item["_meta"]["paraphrased_sections"] = 0
        item["_meta"]["paraphrased_questions"] = 0
    async def request(prompt, decision_id, max_tokens):
        return await api.generate("gpt-5.4-mini", prompt, ledger, max_output_tokens=max_tokens,
                                  role="paraphrase", decision_id=decision_id, reasoning_effort="low")

    async def request_batches(jobs, result_index, batch_size=32):
        results = []
        for start in range(0, len(jobs), batch_size):
            batch = jobs[start:start + batch_size]
            results.extend(await asyncio.gather(
                *(job[result_index] for job in batch), return_exceptions=True
            ))
        return results

    section_jobs = []
    for index in sorted(selected):
        item = records[index]
        for section_index, original in enumerate(list(item["_meta"]["prose_sections"])):
            prompt = (section_prompt.replace("{doc_kind}", item["family"])
                      .replace("{style}", rng.choice(styles)).replace("{section}", original))
            section_jobs.append((item, section_index, original,
                request(prompt, f"paraphrase:{item['family']}:{item['id']}:section:{section_index}",
                        min(1024, max(128, len(original.split()) * 2 + 64)))))
    section_results = await request_batches(section_jobs, 3)
    for (item, section_index, original, _), result in zip(section_jobs, section_results):
        if isinstance(result, BaseException):
            if isinstance(result, BudgetExceeded):
                raise result
            rejected.append({"id": item["id"], "kind": "section",
                             "reason": f"{type(result).__name__}: {result}"})
            continue
        rewritten = result[0].strip()
        trial = dict(item)
        trial["state"] = item["state"].replace(original, rewritten, 1)
        if validate_paraphrase(original, rewritten) and MODULES[item["family"]].verify_rendered(trial):
            item["state"] = trial["state"]
            item["_meta"]["prose_sections"][section_index] = rewritten
            item["_meta"]["paraphrased_sections"] += 1
            changed_sections += 1
        else:
            rejected.append({"id": item["id"], "kind": "section", "reason": "validation or verifier failed"})
    questions = [(item, qid, question) for item in records for qid, question in item["questions"].items()]
    question_jobs = []
    for item, qid, question in rng.sample(questions, round(len(questions) * 0.50)):
        original = question["instructions"]
        prompt = question_prompt.replace("{doc_kind}", item["family"]).replace("{question}", original)
        question_jobs.append((item, qid, question, original,
            request(prompt, f"paraphrase:{item['family']}:{item['id']}:question:{qid}", 512)))
    question_results = await request_batches(question_jobs, 4)
    for (item, qid, question, original, _), result in zip(question_jobs, question_results):
        try:
            if isinstance(result, BaseException):
                raise result
            raw = result[0]
            payload = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            rewritten = rng.choice(payload["variants"])
        except BudgetExceeded:
            raise
        except Exception as exc:
            rejected.append({"id": item["id"], "qid": qid, "kind": "question",
                             "reason": f"{type(exc).__name__}: {exc}"})
            continue
        trial = dict(item)
        trial["questions"] = dict(item["questions"])
        trial["questions"][qid] = dict(question)
        trial["questions"][qid]["instructions"] = rewritten
        if validate_paraphrase(original, rewritten) and MODULES[item["family"]].verify_rendered(trial):
            question["instructions"] = rewritten
            item["_meta"]["paraphrased_questions"] += 1
            changed_questions += 1
        else:
            rejected.append({"id": item["id"], "qid": qid, "kind": "question", "reason": "validation or verifier failed"})
    _write(run_dir / "code_generated.jsonl", records)
    _write(run_dir / "paraphrase_rejections.jsonl", rejected)
    (run_dir / "paraphrase_stats.json").write_text(json.dumps({
        "selected_states": len(selected), "paraphrased_sections": changed_sections,
        "paraphrased_questions": changed_questions, "rejected": len(rejected),
    }, indent=2) + "\n", encoding="utf-8")


async def _label(args, run_dir):
    records = _read(run_dir / "code_generated.jsonl")
    completed = _read(run_dir / "labeled.jsonl")
    done = {item["id"] for item in completed}
    pending = [item for item in records if item["id"] not in done]
    api, ledger = ApiClient(concurrency=32, retry_log=run_dir / "api_retries.jsonl"), _ledger(args)
    label_rows, disagreements, failures = _read(run_dir / "label_results.jsonl"), \
        _read(run_dir / "teacher_disagreements.jsonl"), _read(run_dir / "failed_calls.jsonl")

    async def label_one(item, qid, question):
        decision_id = f"label:{item['family']}:{item['id']}:{qid}"
        return await api.sampled_label(TEACHER, item["state"], question, ledger, decision_id=decision_id)

    for item in pending:
        jobs = [(qid, question, asyncio.create_task(label_one(item, qid, question)))
                for qid, question in item["questions"].items()]
        kept = {}
        targets = {}
        teachers, samples = {}, {}
        for qid, question, task in jobs:
            try:
                result = await task
            except BudgetExceeded:
                raise
            except Exception as exc:
                result = {"distribution": None, "majority": None, "samples": [],
                          "failures": [{"reason": f"{type(exc).__name__}: {exc}"}]}
            gold = item["gold"][qid]
            agree = result["majority"] == gold
            row = {"id": item["id"], "family": item["family"], "qid": qid,
                   "type": question["type"],
                   "question_kind": item.get("_meta", {}).get("quantity_kinds", {}).get(
                       qid, question["instructions"]),
                   "gold": gold, "majority": result["majority"],
                   "samples": result["samples"], "failures": result["failures"], "agree": agree}
            label_rows.append(row)
            if result["failures"]:
                failures.extend({"id": item["id"], "qid": qid, **failure} for failure in result["failures"])
            if agree and result["distribution"]:
                kept[qid] = question
                targets[qid] = result["distribution"]
                teachers[qid] = {TEACHER: result["distribution"]}
                samples[qid] = {TEACHER: result["samples"]}
            else:
                disagreements.append({
                    "id": item["id"], "qid": qid, "family": item["family"], "gold": gold,
                    "samples": result["samples"], "majority": result["majority"],
                    "failures": result["failures"], "state": item["state"],
                    "question": question,
                })
        if kept:
            labeled = dict(item)
            labeled["questions"] = kept
            for key in ("gold", "gold_basis", "_meta"):
                if key == "_meta":
                    meta = dict(labeled[key])
                    meta["surface"] = {qid: value for qid, value in meta.get("surface", {}).items() if qid in kept}
                    labeled[key] = meta
                elif isinstance(labeled.get(key), dict):
                    labeled[key] = {qid: value for qid, value in labeled[key].items() if qid in kept}
            labeled["teacher"], labeled["teacher_samples"], labeled["target"] = teachers, samples, targets
            completed.append(labeled)
        _write(run_dir / "labeled.jsonl", completed)
        _write(run_dir / "label_results.jsonl", label_rows)
        _write(run_dir / "teacher_disagreements.jsonl", disagreements)
        _write(run_dir / "failed_calls.jsonl", failures)


def _split(args, run_dir):
    records = _read(run_dir / "decontam.jsonl") or _read(run_dir / "labeled.jsonl")
    rng = random.Random(args.seed + 303)
    by_family = defaultdict(list)
    for item in records:
        by_family[item["family"]].append(item)
    for family_rows in by_family.values():
        rng.shuffle(family_rows)
        n_dev = round(len(family_rows) * 0.05)
        for index, item in enumerate(family_rows):
            item["split"] = "dev" if index < n_dev else "train"
    _write(run_dir / "split.jsonl", records)


def _distribution_checks(seed: int):
    results = {}
    for family in FAMILIES:
        rng = random.Random(seed + FAMILIES.index(family) * 10007)
        records, noul, score, choices = [], Counter(), Counter(), Counter()
        token_sizes = []
        for _ in range(2000):
            item = GENERATORS[family](rng, rng.randint(2, 5))
            records.append(item)
            token_sizes.append(item["_meta"]["approx_tokens"])
            for qid, question in item["questions"].items():
                if question["type"] == "noul":
                    noul[item["gold"][qid]] += 1
                elif question["type"] == "score":
                    score[item["gold"][qid]] += 1
                else:
                    choices[len(question["criteria"])] += 1
        positions = _chi_square_position(records)
        levels = {key: count for key, count in sorted(score.items())}
        total = sum(score.values())
        uniform = total / max(1, len(score))
        results[family] = {
            "noul_true_share": noul["true"] / max(1, sum(noul.values())),
            "score_level_counts": levels,
            "score_level_ratio_to_uniform": {key: count / uniform for key, count in levels.items()},
            "choice_position_p": positions[-1],
            "choice_option_count_histogram": dict(sorted(choices.items())),
            "long_policy_approx_tokens": {"min": min(token_sizes), "max": max(token_sizes)}
            if family == "cg_long_policy" else None,
        }
    return results


def _report(args, run_dir):
    records = _read(run_dir / "split.jsonl") or _read(run_dir / "decontam.jsonl") or _read(run_dir / "labeled.jsonl")
    generated = _read(run_dir / "code_generated.jsonl")
    kept_records = _read(run_dir / "decontam.jsonl") or _read(run_dir / "labeled.jsonl")
    labels = _read(run_dir / "label_results.jsonl")
    costs = [json.loads(line) for line in COST_PATH.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if COST_PATH.is_file() else []
    costs = [row for row in costs if row.get("run") == "codegold" and row.get("round_id") == "pilot"]
    summary = {}
    kind_stats = defaultdict(list)
    questions_by_key = {
        (item["id"], qid): (item, question)
        for item in generated for qid, question in item["questions"].items()
    }
    for family in FAMILIES:
        rows = [item for item in generated if item["family"] == family]
        kept_rows = [item for item in kept_records if item["family"] == family]
        decisions = [row for row in labels if row["family"] == family]
        by_type = {}
        for kind in ("choice", "noul", "score"):
            group = [row for row in decisions if row["type"] == kind]
            by_type[kind] = {"count": len(group), "agreement": (
                sum(row["agree"] for row in group) / len(group) if group else None)}
        family_costs = [row for row in costs if str(row.get("decision_id", "")).split(":")[1:2] == [family]]
        for result in decisions:
            item, question = questions_by_key.get((result["id"], result["qid"]), ({}, {}))
            question_kind = result.get("question_kind") or item.get("_meta", {}).get(
                "quantity_kinds", {}
            ).get(result["qid"], question.get("instructions", result["type"]))
            kind_stats[question_kind].append(result["agree"])
        decision_count = len(decisions)
        kept_decisions = sum(len(item["questions"]) for item in kept_rows)
        family_spend = sum(float(row.get("cost_usd", 0)) for row in family_costs)
        summary[family] = {
            "states": len(rows), "decisions": decision_count, "kept_decisions": kept_decisions,
            "nano_agreement_percentage": (100 * sum(row["agree"] for row in decisions) / decision_count
                                          if decision_count else None),
            "nano_agreement_by_type": by_type,
            "failed_calls": sum(len(row["failures"]) for row in decisions),
            "spend_usd": family_spend,
            "spend_per_decision_usd": family_spend / max(1, decision_count),
            "mean_approx_tokens": (sum(item["_meta"]["approx_tokens"] for item in rows) / len(rows)
                                   if rows else None),
        }
    question_kinds = {
        kind: {"count": len(agreements), "agreement_percentage": 100 * sum(agreements) / len(agreements)}
        for kind, agreements in kind_stats.items()
    }
    lowest_kinds = dict(sorted(question_kinds.items(), key=lambda item: item[1]["agreement_percentage"])[:3])
    stage_spend = {
        "gen": 0.0,
        "paraphrase": sum(float(row.get("cost_usd", 0)) for row in costs if row.get("role") == "paraphrase"),
        "label": sum(float(row.get("cost_usd", 0)) for row in costs
                     if str(row.get("role", "")).startswith("teacher:")),
        "decontam": 0.0,
        "split": 0.0,
        "report": 0.0,
    }
    paraphrase_stats = json.loads((run_dir / "paraphrase_stats.json").read_text(encoding="utf-8")) \
        if (run_dir / "paraphrase_stats.json").is_file() else {}
    report = {
        "run": args.run, "families": summary,
        "agreement_by_question_kind_lowest_three": lowest_kinds,
        "stage_spend_usd": stage_spend,
        "paraphrase": paraphrase_stats,
        "decontam": json.loads((run_dir / "decontam_report.json").read_text(encoding="utf-8"))
        if (run_dir / "decontam_report.json").is_file() else None,
        "distribution_checks": _distribution_checks(args.seed),
        "spend_usd": sum(float(row.get("cost_usd", 0)) for row in costs),
        "label_settings": {"api": "ApiClient.sampled_label", "model": TEACHER, "k": 4,
                           "reasoning": "low", "retention": "strict majority equals code gold"},
    }
    (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.run == "pilot":
        lines = ["# Pilot samples", ""]
        majorities = {(row["id"], row["qid"]): row.get("majority") for row in labels}
        teacher_samples = {(row["id"], row["qid"]): row.get("samples", []) for row in labels}
        for family in FAMILIES:
            sample_rows = [item for item in generated if item["family"] == family][:2]
            lines.append(f"## {family}")
            for item in sample_rows:
                subset = {key: item.get(key) for key in
                          ("id", "state", "questions", "gold", "_meta")}
                subset["family"] = family
                subset["teacher_majorities"] = {
                    qid: majorities.get((item["id"], qid)) for qid in item["questions"]
                }
                subset["teacher_samples"] = {
                    qid: teacher_samples.get((item["id"], qid), []) for qid in item["questions"]
                }
                lines.extend(["```json", json.dumps(subset, indent=2, ensure_ascii=False), "```"])
        (run_dir / "samples.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        disagreements = _read(run_dir / "teacher_disagreements.jsonl")
        (run_dir / "disagreements_summary.md").write_text("\n".join(
            f"- {row['id']} {row['qid']}: gold `{row['gold']}`, samples `{row['samples']}`"
            for row in disagreements
        ) + "\n", encoding="utf-8")


async def main_async(args):
    run_dir = ROOT / "runs/decisions/codegold" / args.run
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.stage == "gen":
        _gen(args, run_dir)
    elif args.stage == "paraphrase":
        await _paraphrase(args, run_dir)
    elif args.stage == "label":
        await _label(args, run_dir)
    elif args.stage == "decontam":
        output, report = decontam2(_read(run_dir / "labeled.jsonl"))
        _write(run_dir / "decontam.jsonl", output)
        rejections = report.pop("rejections", [])
        report.pop("rejections", None)
        (run_dir / "decontam_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        _write(run_dir / "decontam_rejections.jsonl", rejections)
    elif args.stage == "split":
        _split(args, run_dir)
    elif args.stage == "report":
        _report(args, run_dir)
    else:
        raise ValueError(f"unsupported stage: {args.stage}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("gen", "paraphrase", "label",
                                          "decontam", "split", "report"))
    parser.add_argument("--run", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--per-family", type=int, default=15)
    parser.add_argument("--budget", type=float, default=4.0)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
