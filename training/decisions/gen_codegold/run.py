from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from bench.systemone.schema import parse_request
from training.decisions.build import _chi_square_position, _leak_errors
from training.decisions.label import ApiClient, BudgetExceeded, BudgetLedger
from training.decisions.paraphrase import preservation_signature, validate_paraphrase

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
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _append_jsonl(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
        handle.flush()


def _paraphrase_targets(records, seed):
    state_rng = random.Random(seed + 101)
    candidates = [
        item["id"] for item in records
        if item.get("_meta", {}).get("prose_sections")
    ]
    selected_states = state_rng.sample(
        candidates, min(len(candidates), round(len(records) * 0.50))
    )
    questions = [
        (item["id"], qid)
        for item in records
        for qid in item["questions"]
    ]
    question_rng = random.Random(seed + 202)
    selected_questions = question_rng.sample(
        questions, round(len(questions) * 0.40)
    )
    return selected_states, selected_questions


def _stable_rng(seed, key):
    digest = hashlib.blake2b(f"{seed}:{key}".encode(), digest_size=8).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _preserved_marker_count(text):
    return sum(preservation_signature(text).values())


def _pending_label_questions(records, label_rows):
    completed = {(row["id"], row["qid"]) for row in label_rows}
    return [
        (item, qid, question)
        for item in records
        for qid, question in item["questions"].items()
        if (item["id"], qid) not in completed
    ]


def _ledger(args):
    return BudgetLedger(
        budget=args.budget,
        path=COST_PATH,
        run="codegold",
        round_id=args.run,
        cumulative_budget=68.0,
    )


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
    records_by_id = {item["id"]: item for item in records}
    if len(records_by_id) != len(records):
        raise ValueError("generated records contain duplicate IDs")
    manifest_path = run_dir / "paraphrase_manifest.json"
    events_path = run_dir / "paraphrase_progress.jsonl"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("seed") != args.seed:
            raise ValueError("paraphrase checkpoint seed does not match this run")
    else:
        selected_states, selected_questions = _paraphrase_targets(records, args.seed)
        manifest = {
            "version": 1,
            "seed": args.seed,
            "selected_states": selected_states,
            "selected_questions": selected_questions,
        }
        _write_json(manifest_path, manifest)
    selected_states = set(manifest["selected_states"])
    selected_questions = {
        (state_id, qid) for state_id, qid in manifest["selected_questions"]
    }
    if not selected_states <= records_by_id.keys():
        raise ValueError("paraphrase checkpoint refers to missing state IDs")
    events = _read(events_path)
    progress = {event["key"]: event for event in events}
    for event in progress.values():
        if event["status"] != "accepted":
            continue
        item = records_by_id[event["id"]]
        if event["kind"] == "section":
            index = event["section_index"]
            current = item["_meta"]["prose_sections"][index]
            if current == event["original"]:
                if event["original"] not in item["state"]:
                    raise ValueError(f"paraphrase checkpoint lost section {event['key']}")
                item["state"] = item["state"].replace(event["original"], event["rewritten"], 1)
            elif current != event["rewritten"]:
                raise ValueError(f"paraphrase checkpoint conflicts with section {event['key']}")
            item["_meta"]["prose_sections"][index] = event["rewritten"]
        else:
            question = item["questions"][event["qid"]]
            if question["instructions"] == event["original"]:
                question["instructions"] = event["rewritten"]
            elif question["instructions"] != event["rewritten"]:
                raise ValueError(f"paraphrase checkpoint conflicts with question {event['key']}")

    api, ledger = ApiClient(concurrency=32), _ledger(args)

    def persist():
        accepted = Counter(
            (event["id"], event["kind"])
            for event in progress.values()
            if event["status"] == "accepted"
        )
        for item in records:
            item["_meta"]["paraphrased_sections"] = accepted[(item["id"], "section")]
            item["_meta"]["paraphrased_questions"] = accepted[(item["id"], "question")]
        _write(run_dir / "code_generated.jsonl", records)
        _write(
            run_dir / "paraphrase_rejections.jsonl",
            [
                event for event in progress.values()
                if event["status"] == "rejected"
            ],
        )
        rejection_reasons = Counter(
            event["reason"]
            for event in progress.values()
            if event["status"] == "rejected"
        )
        _write_json(run_dir / "paraphrase_stats.json", {
            "selected_states": len(selected_states),
            "selected_questions": len(selected_questions),
            "paraphrased_sections": sum(
                event["status"] == "accepted" and event["kind"] == "section"
                for event in progress.values()
            ),
            "paraphrased_questions": sum(
                event["status"] == "accepted" and event["kind"] == "question"
                for event in progress.values()
            ),
            "rejected": sum(event["status"] == "rejected" for event in progress.values()),
            "skipped_sections": sum(event["status"] == "skipped" for event in progress.values()),
            "rejection_reasons": dict(rejection_reasons),
        })

    persist()

    def record_event(event):
        _append_jsonl(events_path, event)
        progress[event["key"]] = event

    def check_and_apply(job, rewritten):
        item = job["item"]
        if not isinstance(rewritten, str):
            return None, "paraphrase response is not text"
        if not validate_paraphrase(job["original"], rewritten):
            return None, "preservation signature mismatch"
        trial = dict(item)
        if job["kind"] == "section":
            trial["state"] = item["state"].replace(job["original"], rewritten, 1)
        else:
            trial["questions"] = dict(item["questions"])
            trial["questions"][job["qid"]] = dict(job["question"])
            trial["questions"][job["qid"]]["instructions"] = rewritten
        if not MODULES[item["family"]].verify_rendered(trial):
            return None, "family verifier failed"
        if job["kind"] == "section":
            item["state"] = trial["state"]
            item["_meta"]["prose_sections"][job["section_index"]] = rewritten
        else:
            item["questions"][job["qid"]]["instructions"] = rewritten
        return rewritten, None

    async def run_jobs(jobs):
        for start in range(0, len(jobs), 32):
            batch = jobs[start:start + 32]
            tasks = {}
            for job in batch:
                tasks[asyncio.create_task(api.generate(
                    "gpt-5.4-mini", job["prompt"], ledger,
                    max_output_tokens=job["max_tokens"], role="paraphrase",
                    decision_id=job["decision_id"], reasoning_effort="low",
                ))] = job
            pending = set(tasks)
            budget_error = None
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    job = tasks[task]
                    base_event = {
                        "key": job["key"], "id": job["item"]["id"],
                        "kind": job["kind"], "marker_count": job.get("marker_count", 0),
                    }
                    if "qid" in job:
                        base_event["qid"] = job["qid"]
                    if "section_index" in job:
                        base_event["section_index"] = job["section_index"]
                    try:
                        result = task.result()
                    except BudgetExceeded as exc:
                        budget_error = exc
                        continue
                    except Exception as exc:
                        record_event({
                            **base_event, "status": "rejected",
                            "reason": f"api error: {type(exc).__name__}: {exc}",
                        })
                        continue

                    try:
                        raw = result[0]
                        if job["kind"] == "question":
                            payload = json.loads(
                                raw.strip().removeprefix("```json").removesuffix("```").strip()
                            )
                            variants = payload["variants"]
                            if not isinstance(variants, list) or not variants:
                                raise ValueError("response has no paraphrase variants")
                            rewritten = _stable_rng(args.seed, job["key"]).choice(variants)
                        else:
                            rewritten = raw.strip()
                    except Exception as exc:
                        record_event({
                            **base_event, "status": "rejected",
                            "reason": f"invalid response: {type(exc).__name__}: {exc}",
                        })
                        continue

                    accepted_text, reason = check_and_apply(job, rewritten)
                    if reason:
                        record_event({
                            **base_event, "status": "rejected", "reason": reason,
                        })
                    else:
                        record_event({
                            **base_event, "status": "accepted",
                            "original": job["original"], "rewritten": accepted_text,
                        })
            persist()
            if budget_error:
                raise budget_error

    section_jobs = []
    for state_id in sorted(selected_states):
        item = records_by_id[state_id]
        for section_index, original in enumerate(item["_meta"]["prose_sections"]):
            key = f"section:{state_id}:{section_index}"
            if key in progress:
                continue
            marker_count = _preserved_marker_count(original)
            if marker_count > 15:
                record_event({
                    "key": key, "id": state_id, "kind": "section",
                    "section_index": section_index, "marker_count": marker_count,
                    "status": "skipped", "reason": "more than 15 preserved markers",
                })
                continue
            style = _stable_rng(args.seed, key).choice(styles)
            prompt = (
                section_prompt.replace("{doc_kind}", item["family"])
                .replace("{style}", style).replace("{section}", original)
            )
            section_jobs.append({
                "key": key, "kind": "section", "item": item,
                "section_index": section_index, "original": original,
                "marker_count": marker_count, "prompt": prompt,
                "decision_id": f"paraphrase:{item['family']}:{state_id}:section:{section_index}",
                "max_tokens": min(1024, max(128, len(original.split()) * 2 + 64)),
            })
    persist()
    await run_jobs(section_jobs)

    question_jobs = []
    for state_id, qid in sorted(selected_questions):
        key = f"question:{state_id}:{qid}"
        if key in progress:
            continue
        item = records_by_id[state_id]
        question = item["questions"][qid]
        original = question["instructions"]
        prompt = (
            question_prompt.replace("{doc_kind}", item["family"])
            .replace("{question}", original)
        )
        question_jobs.append({
            "key": key, "kind": "question", "item": item,
            "qid": qid, "question": question, "original": original,
            "prompt": prompt,
            "decision_id": f"paraphrase:{item['family']}:{state_id}:question:{qid}",
            "max_tokens": 512,
        })
    await run_jobs(question_jobs)
    persist()


async def _label(args, run_dir):
    records = _read(run_dir / "code_generated.jsonl")
    api, ledger = ApiClient(concurrency=32, retry_log=run_dir / "api_retries.jsonl"), _ledger(args)
    label_rows = _read(run_dir / "label_results.jsonl")

    async def label_one(item, qid, question):
        decision_id = f"label:{item['family']}:{item['id']}:{qid}"
        return await api.sampled_label(TEACHER, item["state"], question, ledger, decision_id=decision_id)

    def persist():
        rows_by_key = {(row["id"], row["qid"]): row for row in label_rows}
        labeled_records, disagreements, failures = [], [], []
        for item in records:
            kept, targets, teachers, samples = {}, {}, {}, {}
            for qid, question in item["questions"].items():
                row = rows_by_key.get((item["id"], qid))
                if row is None:
                    continue
                if row.get("failures"):
                    failures.extend(
                        {"id": item["id"], "qid": qid, **failure}
                        for failure in row["failures"]
                    )
                if row.get("agree") and row.get("distribution"):
                    kept[qid] = question
                    targets[qid] = row["distribution"]
                    teachers[qid] = {TEACHER: row["distribution"]}
                    samples[qid] = {TEACHER: row["samples"]}
                else:
                    disagreements.append({
                        "id": item["id"], "qid": qid, "family": item["family"],
                        "gold": item["gold"][qid], "samples": row.get("samples", []),
                        "majority": row.get("majority"), "failures": row.get("failures", []),
                        "state": item["state"], "question": question,
                    })
            if not kept:
                continue
            labeled = dict(item)
            labeled["questions"] = kept
            for key in ("gold", "gold_basis", "_meta"):
                if key == "_meta":
                    meta = dict(labeled[key])
                    meta["surface"] = {
                        qid: value for qid, value in meta.get("surface", {}).items()
                        if qid in kept
                    }
                    labeled[key] = meta
                elif isinstance(labeled.get(key), dict):
                    labeled[key] = {
                        qid: value for qid, value in labeled[key].items() if qid in kept
                    }
            labeled["teacher"] = teachers
            labeled["teacher_samples"] = samples
            labeled["target"] = targets
            labeled_records.append(labeled)
        _write(run_dir / "labeled.jsonl", labeled_records)
        _write(run_dir / "label_results.jsonl", label_rows)
        _write(run_dir / "teacher_disagreements.jsonl", disagreements)
        _write(run_dir / "failed_calls.jsonl", failures)

    persist()
    pending = _pending_label_questions(records, label_rows)
    for start in range(0, len(pending), 8):
        batch = pending[start:start + 8]
        results = await asyncio.gather(
            *(label_one(item, qid, question) for item, qid, question in batch),
            return_exceptions=True,
        )
        budget_error = None
        for (item, qid, question), result in zip(batch, results):
            if isinstance(result, BudgetExceeded):
                budget_error = result
                continue
            if isinstance(result, Exception):
                result = {
                    "distribution": None, "majority": None, "samples": [],
                    "failures": [{"reason": f"{type(result).__name__}: {result}"}],
                }
            gold = item["gold"][qid]
            label_rows.append({
                "id": item["id"], "family": item["family"], "qid": qid,
                "type": question["type"],
                "question_kind": item.get("_meta", {}).get("quantity_kinds", {}).get(
                    qid, question["instructions"]
                ),
                "gold": gold, "majority": result["majority"],
                "distribution": result["distribution"], "samples": result["samples"],
                "failures": result["failures"], "agree": result["majority"] == gold,
            })
        persist()
        if budget_error:
            raise budget_error


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
    costs = [
        row for row in costs
        if row.get("run") == "codegold" and row.get("round_id") == args.run
    ]
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
        "project_cumulative_spend_usd": sum(
            float(row.get("cost_usd", 0))
            for row in (
                [json.loads(line) for line in COST_PATH.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
                if COST_PATH.is_file() else []
            )
        ),
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
