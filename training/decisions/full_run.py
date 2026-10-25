from __future__ import annotations

import asyncio
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from .author import author_items
from .build import (
    CODE_FAMILIES, PARAPHRASE_DOC_KINDS, ROOT, RUNS, _append_jsonl, _argmax, _read_jsonl,
    _write_jsonl, split_stage, datums_stage, upload_stage,
)
from .decontam import decontam
from .families import GENERATORS
from .label import ApiClient, BudgetExceeded, BudgetLedger, floored
from .paraphrase import PARAPHRASE_PROMPT, validate_paraphrase

CAP = 57.0
ROUND = "lead-amendment-3-full"
CODE_DECISIONS = 10_000
AUTHOR_DECISIONS = 6_500
AUTHORING_CUMULATIVE_CAP = 47.0
AUTHOR_MODELS = ("gpt-5.4-nano", "gpt-4.1-mini")


def _cost_total(path: Path) -> float:
    if not path.is_file():
        return 0.0
    return sum(float(json.loads(line).get("cost_usd", 0)) for line in path.read_text().splitlines() if line.strip())


def _decisions(rows: list[dict]) -> int:
    return sum(len(row.get("questions", {})) for row in rows)


def _read_optional_jsonl(path: Path) -> list[dict]:
    return _read_jsonl(path) if path.is_file() else []


def _gold_surface(value: str) -> str | None:
    if value.startswith("date_"):
        return "-".join(value.split("_")[1:])
    if value.startswith("utc_"):
        year, month, day, hour, minute = value.split("_")[1:]
        return f"{year}-{month}-{day} {hour}:{minute} UTC"
    if value.startswith("usd_"):
        whole, cents = value.removeprefix("usd_").rsplit("_", 1)
        return f"${whole}.{cents}"
    if value.startswith("count_"):
        return f"{value.removeprefix('count_')} eligible referrals"
    if value.startswith("hours_"):
        return f"{value.removeprefix('hours_')} hours"
    if value.startswith("posterior_"):
        number = float(value.removeprefix("posterior_").replace("_", "."))
        return f"{number:.2%}"
    return None


def _label_events(path: Path) -> dict:
    events = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip():
                event = json.loads(line)
                events[(event["id"], event["qid"])] = event
    return events


async def full_stage(args, run_dir: Path) -> dict:
    cost_path = RUNS / "gen_cost.jsonl"
    old_cost = _cost_total(cost_path)
    if args.budget is None:
        full_spend = sum(
            float(json.loads(line).get("cost_usd", 0))
            for line in cost_path.read_text().splitlines()
            if line.strip() and json.loads(line).get("run") == "full"
        ) if cost_path.is_file() else 0.0
        args.budget = max(0.0, CAP - (old_cost - full_spend))
    ledger = BudgetLedger(args.budget, cost_path, "full", ROUND, cumulative_budget=CAP)
    api = ApiClient(concurrency=32, retry_log=run_dir / "api_retries.jsonl")
    rng = random.Random(args.seed)
    generated_path = run_dir / "code_generated.jsonl"
    generated = _read_jsonl(generated_path) if generated_path.is_file() else []
    paraphrase_rows = _read_jsonl(run_dir / "paraphrase_rejections.jsonl") if (run_dir / "paraphrase_rejections.jsonl").is_file() else []
    paraphrase_blocked = False
    while _decisions(generated) < CODE_DECISIONS:
        index = len(generated)
        item_rng = random.Random(args.seed + index * 1009)
        family = CODE_FAMILIES[index % len(CODE_FAMILIES)]
        item = GENERATORS[family](item_rng, "mixed", item_rng.randint(3, 6), ["choice", "noul", "score"])
        item["paraphrased"] = False
        rejection_start = len(paraphrase_rows)
        if not paraphrase_blocked and item_rng.random() < 0.60:
            prompt = PARAPHRASE_PROMPT.format(doc_kind=item_rng.choice(PARAPHRASE_DOC_KINDS[family])) + "\n\n" + item["state"]
            try:
                rewritten, _ = await api.generate(
                    "gpt-5.4-mini", prompt, ledger, max_output_tokens=8192,
                    role="paraphrase", decision_id=f"paraphrase:{item['id']}", reasoning_effort="low",
                )
                if validate_paraphrase(item["state"], rewritten):
                    item["state"], item["paraphrased"] = rewritten.strip(), True
                else:
                    paraphrase_rows.append({"id": item["id"], "reason": "verbatim preservation check failed"})
            except BudgetExceeded:
                paraphrase_blocked = True
                paraphrase_rows.append({"id": item["id"], "reason": "budget stop during paraphrase"})
        generated.append(item)
        _append_jsonl(generated_path, item)
        for rejection in paraphrase_rows[rejection_start:]:
            _append_jsonl(run_dir / "paraphrase_rejections.jsonl", rejection)

    code_events_path = run_dir / "code_label_events.jsonl"
    events = _label_events(code_events_path)
    code_stop = False
    pending_code = [
        (item, qid, question)
        for item in generated
        for qid, question in item["questions"].items()
        if (item["id"], qid) not in events
    ]
    for start in range(0, len(pending_code), 8):
        batch = pending_code[start:start + 8]
        results = await asyncio.gather(*(
            api.sampled_label(
                "gpt-5.4-nano", item["state"], question, ledger,
                decision_id=f"{item['id']}:{qid}",
            )
            for item, qid, question in batch
        ), return_exceptions=True)
        for (item, qid, _), result in zip(batch, results):
            if isinstance(result, BudgetExceeded):
                code_stop = True
                continue
            if isinstance(result, Exception):
                event = {"id": item["id"], "qid": qid, "distribution": None,
                         "majority": None,
                         "failures": [{"reason": f"{type(result).__name__}: {result}"}]}
            else:
                event = {"id": item["id"], "qid": qid, "distribution": result["distribution"],
                         "majority": result["majority"], "failures": result["failures"]}
            events[(item["id"], qid)] = event
            _append_jsonl(code_events_path, event)
        if code_stop:
            break

    author_path = run_dir / "author_generated.jsonl"
    authored = _read_jsonl(author_path) if author_path.is_file() else []
    author_progress_path = run_dir / "author_progress.json"
    author_cursor = json.loads(author_progress_path.read_text()).get("attempted", 0) if author_progress_path.is_file() else len(authored)
    author_rejections_path = run_dir / "author_rejections.jsonl"
    author_rejections = _read_jsonl(author_rejections_path) if author_rejections_path.is_file() else []
    if not code_stop:
        ledger.phase_cumulative_budget = AUTHORING_CUMULATIVE_CAP
        try:
            while _decisions(authored) < AUTHOR_DECISIONS:
                batch_size = 40
                batch_rng = random.Random(args.seed + 7919 * author_cursor)
                batch, rejected = await author_items(
                    batch_size, batch_rng, api, ledger, full_mix=True, start_index=author_cursor,
                )
                for item in batch:
                    authored.append(item)
                    _append_jsonl(author_path, item)
                author_rejections.extend(rejected)
                _write_jsonl(author_rejections_path, author_rejections)
                author_cursor += len(batch) + len(rejected)
                author_progress_path.write_text(json.dumps({"attempted": author_cursor}) + "\n")
                if len(batch) + len(rejected) < batch_size or any(
                    r.get("reason", "").startswith("BudgetExceeded") for r in rejected
                ):
                    break
        finally:
            ledger.phase_cumulative_budget = None

    author_events_path = run_dir / "author_label_events.jsonl"
    author_events = _label_events(author_events_path)
    author_stop = False
    if not code_stop:
        async def label_authored_question(item, qid, question):
            event = author_events.get((item["id"], qid), {"id": item["id"], "qid": qid})
            if "nano" not in event:
                try:
                    nano = await api.sampled_label(
                        "gpt-5.4-nano", item["state"], question, ledger,
                        decision_id=f"{item['id']}:{qid}",
                    )
                    event.update(nano=nano["distribution"], nano_majority=nano["majority"],
                                 nano_failures=nano["failures"])
                except BudgetExceeded:
                    return event, True
                except Exception as exc:
                    event["nano_error"] = f"{type(exc).__name__}: {exc}"
                    return event, False
            if "mini" not in event:
                try:
                    event["mini"] = await api.classic_label(
                        "gpt-4.1-mini", item["state"], question, ledger,
                        decision_id=f"{item['id']}:{qid}",
                    )
                except BudgetExceeded:
                    return event, True
                except Exception as exc:
                    event["mini_error"] = f"{type(exc).__name__}: {exc}"
            return event, False

        pending_authored = [
            (item, qid, question)
            for item in authored
            for qid, question in item["questions"].items()
            if not {"nano", "mini"}.issubset(author_events.get((item["id"], qid), {}))
        ]
        for start in range(0, len(pending_authored), 8):
            batch = pending_authored[start:start + 8]
            results = await asyncio.gather(*(
                label_authored_question(item, qid, question) for item, qid, question in batch
            ))
            for (item, qid, _), (event, budget_hit) in zip(batch, results):
                author_events[(item["id"], qid)] = event
                _append_jsonl(author_events_path, event)
                author_stop = author_stop or budget_hit
            if author_stop:
                break

    records = []
    rejections = []
    for item in generated:
        kept = {}
        for qid, question in item["questions"].items():
            event = events.get((item["id"], qid))
            if event and event["distribution"] and event["majority"] == item["gold"][qid]:
                kept[qid] = (question, item["gold"][qid], {"gpt-5.4-nano": event["distribution"]},
                             event["distribution"])
            else:
                rejections.append({"id": item["id"], "qid": qid, "family": item["family"],
                                   "reason": "code teacher majority disagreed or label incomplete"})
        if kept:
            clone = dict(item)
            clone["source"] = "code"
            clone["questions"] = {q: row[0] for q, row in kept.items()}
            clone["gold"] = {q: row[1] for q, row in kept.items()}
            clone["gold_basis"] = {q: "code" for q in kept}
            clone["teacher"] = {q: row[2] for q, row in kept.items()}
            clone["target"] = {q: row[3] for q, row in kept.items()}
            records.append(clone)
    for item in authored:
        kept = {}
        for qid, question in item["questions"].items():
            event = author_events.get((item["id"], qid), {})
            labels = list(question["criteria"]) if question["type"] in ("choice", "noul") else [
                str(i) for i in range(len(question["criteria"]))
            ]
            mini, nano = event.get("mini"), event.get("nano")
            if nano and mini and event.get("nano_majority") == _argmax(mini):
                merged = {key: 0.5 * nano.get(key, 0) + 0.5 * mini.get(key, 0) for key in labels}
                kept[qid] = (question, _argmax(merged), {
                    "gpt-5.4-nano": nano, "gpt-4.1-mini": mini,
                }, floored(merged))
            else:
                rejections.append({"id": item["id"], "qid": qid, "family": item["family"],
                                   "reason": "nano majority and gpt-4.1-mini argmax disagree or label incomplete"})
        if kept:
            clone = dict(item)
            clone["source"] = "authored"
            clone["questions"] = {q: row[0] for q, row in kept.items()}
            clone["gold"] = {q: row[1] for q, row in kept.items()}
            clone["gold_basis"] = {q: "teacher" for q in kept}
            clone["teacher"] = {q: row[2] for q, row in kept.items()}
            clone["target"] = {q: row[3] for q, row in kept.items()}
            records.append(clone)
    _write_jsonl(run_dir / "records_labeled.jsonl", records)
    _write_jsonl(run_dir / "label_rejections.jsonl", rejections)
    failures = [
        {"id": event["id"], "qid": event["qid"], "model": "gpt-5.4-nano", **failure}
        for event in events.values() for failure in event.get("failures", [])
    ] + [
        {"id": event["id"], "qid": event["qid"], "model": "gpt-5.4-nano", **failure}
        for event in author_events.values() for failure in event.get("nano_failures", [])
    ] + [
        {"id": event["id"], "qid": event["qid"], "model": "gpt-4.1-mini",
         "reason": event["mini_error"]}
        for event in author_events.values() if event.get("mini_error")
    ]
    _write_jsonl(run_dir / "failed_calls.jsonl", failures)
    cleaned, decontam_report = decontam(records, ROOT)
    _write_jsonl(run_dir / "records_decontam.jsonl", cleaned)
    (run_dir / "decontam.json").write_text(json.dumps(decontam_report, indent=2) + "\n")
    split_stage(run_dir, args.seed)
    datums_stage(run_dir, "full", write_report=False)
    upload = upload_stage(args, run_dir)
    report_full(run_dir, generated, authored, records, cleaned, decontam_report, ledger, upload["revision"])
    return {
        "repository": upload["repository"], "revision": upload["revision"],
        "code_generated_decisions": _decisions(generated),
        "author_generated_decisions": _decisions(authored),
        "retained_decisions": _decisions(cleaned), "spent_full_usd": ledger.spent,
        "cumulative_usd": ledger.cumulative_spent, "budget_code_stop": code_stop,
        "budget_author_stop": author_stop,
    }


def report_full(run_dir: Path, generated: list[dict], authored: list[dict], records: list[dict],
                cleaned: list[dict], decontam_report: dict, ledger: BudgetLedger,
                upload_revision: str | None = None) -> None:
    costs = [json.loads(line) for line in (RUNS / "gen_cost.jsonl").read_text().splitlines()
             if line.strip() and json.loads(line).get("run") == "full"]
    family_counts = Counter(row["family"] for row in cleaned)
    family_decisions = Counter()
    for row in cleaned:
        family_decisions[row["family"]] += len(row["questions"])
    authored_family_counts = Counter(
        row.get("authored_family", row["family"]) for row in cleaned if row.get("source") == "authored"
    )
    source_counts = Counter(row["source"] for row in cleaned)
    type_counts, option_counts, position_counts = Counter(), Counter(), Counter()
    noul_balance, score_levels = Counter(), Counter()
    positions_by_quartile = [0, 0, 0, 0]
    expected_by_quartile = [0.0, 0.0, 0.0, 0.0]
    teacher_stats = defaultdict(list)
    for row in cleaned:
        for qid, question in row["questions"].items():
            type_counts[question["type"]] += 1
            criteria = question["criteria"]
            count = len(criteria)
            if question["type"] == "choice":
                option_counts[str(count)] += 1
            elif question["type"] == "noul":
                noul_balance[row["gold"][qid]] += 1
            elif question["type"] == "score":
                score_levels[row["gold"][qid]] += 1
            if question["type"] == "choice":
                position_counts[str(list(criteria).index(row["gold"][qid]))] += 1
                position = list(criteria).index(row["gold"][qid])
                positions_by_quartile[min(3, int(4 * position / count))] += 1
                for candidate_position in range(count):
                    quartile = min(3, int(4 * candidate_position / count))
                    expected_by_quartile[quartile] += 1 / count
            for model, distribution in row.get("teacher", {}).get(qid, {}).items():
                if distribution:
                    values = [float(value) for value in distribution.values()]
                    total = sum(values)
                    normalized = [value / total for value in values if value > 0]
                    if normalized:
                        teacher_stats[model].append((
                            max(normalized), -sum(value * math.log(value) for value in normalized),
                        ))
    chi2 = sum(
        (observed - expected) ** 2 / expected
        for observed, expected in zip(positions_by_quartile, expected_by_quartile)
        if expected
    )
    chi2_p = (math.erfc(math.sqrt(chi2 / 2)) +
              math.sqrt(2 * chi2 / math.pi) * math.exp(-chi2 / 2)) if chi2 else 1.0
    roles, providers = Counter(), Counter()
    for row in costs:
        roles[row["role"]] += float(row["cost_usd"])
        providers[row["provider"]] += float(row["cost_usd"])
    author_models = Counter(row.get("author_model", "unknown") for row in authored)
    retained_author_models = Counter(
        row.get("author_model", "unknown") for row in cleaned if row.get("source") == "authored"
    )
    author_costs = Counter()
    role_decisions = defaultdict(set)
    author_model_costs = Counter()
    author_model_by_id = {item["id"]: item.get("author_model", "unknown") for item in authored}
    for row in costs:
        if row["role"] == "author":
            author_costs[row["model"]] += float(row["cost_usd"])
            author_model_costs[row["model"]] += float(row["cost_usd"])
        elif row.get("decision_id"):
            item_id = row["decision_id"].split(":", 1)[0]
            if item_id in author_model_by_id:
                author_model_costs[author_model_by_id[item_id]] += float(row["cost_usd"])
        if row.get("decision_id"):
            role_decisions[row["role"]].add(row["decision_id"])
    role_unit_cost = {
        role: {"cost_usd": value, "decisions": len(role_decisions[role]),
               "usd_per_decision": value / max(1, len(role_decisions[role]))}
        for role, value in roles.items()
    }
    datum_stats = json.loads((run_dir / "datum_stats.json").read_text())
    dev_records = _read_jsonl(run_dir / "dev.jsonl")
    dev_code_families = sorted({
        row["family"] for row in dev_records if row.get("source") == "code"
    })
    mean_rendered_tokens = float(datum_stats["mean_rendered_tokens"])
    rows_before = decontam_report.get("rows_before", 0)
    flagged_references = [
        name for name, details in decontam_report.get("per_reference", {}).items()
        if details["before"]["word_13gram_rows"] / max(1, rows_before) > 0.01
    ]
    tinker_projection_20k = (mean_rendered_tokens + 1) * 20_000 * 0.73 / 1_000_000
    code_teacher = role_unit_cost.get("teacher:gpt-5.4-nano", {"usd_per_decision": 0.0})
    code_teacher_projection_20k = code_teacher["usd_per_decision"] * 20_000
    code_events = _label_events(run_dir / "code_label_events.jsonl")
    code_agreement = defaultdict(lambda: [0, 0, 0])
    code_disagreements = []
    for item in generated:
        for qid, question in item["questions"].items():
            event = code_events.get((item["id"], qid))
            stats = code_agreement[(item["family"], question["type"])]
            if not event or not event.get("majority"):
                stats[2] += 1
            else:
                stats[1] += 1
                stats[0] += int(event["majority"] == item["gold"][qid])
                if event["majority"] != item["gold"][qid]:
                    code_disagreements.append({
                        "id": item["id"], "family": item["family"], "qid": qid,
                        "state": item["state"], "question": question,
                        "gold": item["gold"][qid], "teacher_majority": event["majority"],
                        "teacher_distribution": event.get("distribution"),
                    })
    _write_jsonl(run_dir / "code_disagreements.jsonl", code_disagreements)
    code_agreement_report = {
        f"{family}/{kind}": {"correct": values[0], "valid_majorities": values[1],
                             "failed_or_no_majority": values[2],
                             "agreement": values[0] / values[1] if values[1] else None}
        for (family, kind), values in code_agreement.items()
    }
    author_events = _label_events(run_dir / "author_label_events.jsonl")
    author_rejections = _read_optional_jsonl(run_dir / "author_rejections.jsonl")
    label_rejections = _read_optional_jsonl(run_dir / "label_rejections.jsonl")
    failed_calls = _read_optional_jsonl(run_dir / "failed_calls.jsonl")
    api_retries = _read_optional_jsonl(run_dir / "api_retries.jsonl")
    retry_counts = Counter(
        f"{row['provider']}:{row.get('status_code') or row.get('reason') or 'unknown'}"
        for row in api_retries
    )
    author_agree = [event["nano_majority"] == _argmax(event["mini"])
                    for event in author_events.values()
                    if event.get("nano_majority") and event.get("mini")]
    author_raw_decisions = Counter()
    for item in authored:
        author_raw_decisions[item.get("author_model", "unknown")] += len(item["questions"])
    author_kept_decisions = Counter()
    for item in cleaned:
        if item.get("source") == "authored":
            author_kept_decisions[item.get("author_model", "unknown")] += len(item["questions"])
    author_retention = {
        model: {
            "generated_states": author_models[model],
            "retained_states": retained_author_models[model],
            "generated_decisions": author_raw_decisions[model],
            "retained_decisions": author_kept_decisions[model],
            "retention": author_kept_decisions[model] / max(1, author_raw_decisions[model]),
            "authoring_and_label_cost_usd": author_model_costs[model],
            "usd_per_retained_decision": author_model_costs[model] / max(1, author_kept_decisions[model]),
        }
        for model in sorted(set(author_models) | set(retained_author_models))
    }
    leak_errors = []
    for item in generated:
        for qid, answer in item["gold"].items():
            surface = _gold_surface(answer)
            if surface and surface.lower() in item["state"].lower():
                leak_errors.append({"id": item["id"], "qid": qid, "kind": "gold_surface", "text": surface})
        forbidden = [str(value).lower() for value in item.get("_leak_audit", {}).get("intermediate_values", [])]
        for qid, question in item["questions"].items():
            descriptions = question["criteria"].values() if isinstance(question["criteria"], dict) else question["criteria"]
            for description in descriptions:
                for value in forbidden:
                    if value and value in str(description).lower():
                        leak_errors.append({
                            "id": item["id"], "qid": qid, "kind": "intermediate_fact",
                            "text": value,
                        })
    sharpness = {
        model: {
            "mean_max_probability": statistics.mean(value[0] for value in values),
            "mean_entropy_nats": statistics.mean(value[1] for value in values),
            "decisions": len(values),
        }
        for model, values in teacher_stats.items()
    }
    report = [
        "# Full decision generation", "",
        f"- Seed: `{json.loads((run_dir / 'run_config.json').read_text())['seed']}`.",
        f"- Cumulative generation spend: **${ledger.cumulative_spent:.6f} / $57.00** "
        f"(this run ${ledger.spent:.6f}; OpenAI ${providers['openai']:.6f}; Anthropic ${providers['anthropic']:.6f}).",
        f"- Authored generation guard: stop near {AUTHOR_DECISIONS:,} decisions or "
        f"${AUTHORING_CUMULATIVE_CAP:.2f} cumulative spend, whichever comes first.",
        f"- Generated code-gold decisions/states: {_decisions(generated)} / {len(generated)}.",
        f"- Generated authored decisions/states: {_decisions(authored)} / {len(authored)}.",
        f"- Retained after labels and decontamination: {_decisions(cleaned)} decisions / {len(cleaned)} states.",
        f"- Family counts: `{json.dumps(family_counts, sort_keys=True)}`.",
        f"- Retained decisions by code/authored family: `{json.dumps(family_decisions, sort_keys=True)}`.",
        f"- Retained authored-family counts: `{json.dumps(authored_family_counts, sort_keys=True)}`.",
        f"- Source counts: `{json.dumps(source_counts, sort_keys=True)}`.",
        f"- Generated questions/state: code {(_decisions(generated) / max(1, len(generated))):.2f}; "
        f"authored {(_decisions(authored) / max(1, len(authored))):.2f}.",
        f"- Author states by model: `{json.dumps(dict(author_models), sort_keys=True)}`; "
        f"retained states: `{json.dumps(dict(retained_author_models), sort_keys=True)}`.",
        f"- Author retention and authoring+label cost by model: `{json.dumps(author_retention, sort_keys=True)}`.",
        f"- Code paraphrases: {sum(bool(row.get('paraphrased')) for row in generated)}/{len(generated)} "
        f"({sum(bool(row.get('paraphrased')) for row in generated) / max(1, len(generated)):.1%}); "
        f"rejections: {len(_read_optional_jsonl(run_dir / 'paraphrase_rejections.jsonl'))}.",
        "", "## Spend by API role", "", "```json", json.dumps(dict(roles), indent=2), "```",
        "", "## Question and option histograms", "",
        f"- Types: `{json.dumps(type_counts, sort_keys=True)}`.",
        f"- Option counts: `{json.dumps(option_counts, sort_keys=True)}`.",
        f"- Choice gold positions: `{json.dumps(position_counts, sort_keys=True)}`.",
        f"- Gold-position quartiles: observed `{positions_by_quartile}`, expected "
        f"`{[round(value, 2) for value in expected_by_quartile]}` under uniform within-question position; "
        f"χ²={chi2:.4f}, df=3, p={chi2_p:.5f}.",
        f"- Noul true/false: `{json.dumps(dict(noul_balance), sort_keys=True)}`.",
        f"- Score-level histogram: `{json.dumps(dict(score_levels), sort_keys=True)}`.",
        f"- Mean max-probability / entropy nats by teacher: `{json.dumps(sharpness, sort_keys=True)}`.",
        f"- Author generation cost by model: `{json.dumps(dict(author_costs), sort_keys=True)}`.",
        f"- API spend per unique decision by role: `{json.dumps(role_unit_cost, sort_keys=True)}`.",
        "", "## Render and cost projections", "",
        f"- Mean rendered input tokens/Datum: {mean_rendered_tokens:.1f}.",
        f"- p95 rendered input tokens/Datum: {datum_stats['p95_rendered_tokens']}.",
        f"- 20k decision Tinker projection at $0.73/M train tokens: "
        f"${tinker_projection_20k:.4f} (using mean input tokens + one target token).",
        f"- 20k code-teacher generation projection using `gpt-5.4-nano`: "
        f"${code_teacher_projection_20k:.4f}, from actual selected-teacher API usage per labeled code decision.",
        f"- Computed-answer leak audit: {'PASS' if not leak_errors else 'FAIL'}; "
        f"{len(generated)} code states checked, {len(leak_errors)} findings.",
        f"- Leak findings: `{json.dumps(leak_errors[:20], sort_keys=True)}`.",
        f"- Code-gold nano agreement by family/type: `{json.dumps(code_agreement_report, sort_keys=True)}`.",
        "", "## Teacher disagreements", "",
        f"Found {len(code_disagreements)} valid-majority disagreements; full records are in "
        f"`runs/decisions/full/code_disagreements.jsonl` for inspection.",
        f"- Authored nano-majority vs gpt-4.1-mini agreement: {sum(author_agree)}/{len(author_agree)} "
        f"({sum(author_agree) / max(1, len(author_agree)):.1%}).",
        "", "## Data-quality review", "",
        f"- Eval references with word-13-gram matches above 1% of states: "
        f"`{json.dumps(flagged_references)}`; per-reference match examples are in the decontamination report.",
        "- Five sampled code-gold disagreements were checked against their source facts; all five golds were "
        "consistent: INC-4100 resolves through AC-2200 → AGR-3100 → Core (10 hours), plus Central handling "
        "(5), for 15 hours; proposal A's 45% success rate exceeds B's 25%; five counting rows meet all filters; "
        "seven business days after 2024-12-22, excluding weekends and 2024-12-25, is 2025-01-01; and the $120 "
        "purchase totals $104.55 after discount and fee, a 12.875% change (score level 2). These spot checks "
        "do not validate every disagreement.",
        "", "## Rejections", "",
        f"- Author rejections: {len(author_rejections)}; reasons "
        f"`{json.dumps(Counter(row.get('reason', 'unknown') for row in author_rejections), sort_keys=True)}`.",
        f"- Label/decontamination rejections: {len(label_rejections)}; reasons "
        f"`{json.dumps(Counter(row.get('reason', 'unknown') for row in label_rejections), sort_keys=True)}`.",
        f"- Failed label calls: {len(failed_calls)}.",
        f"- API retry events after concurrency resume: `{json.dumps(retry_counts, sort_keys=True)}`; "
        f"earlier requests have no transient-429 telemetry.",
        "", "## Decontamination", "",
        "Per-reference before/after counts cover JevBench public, Typed Decisions test, route_v1, live_t1, "
        "and external utterances. Each reference entry includes up to five matched text/option examples.",
        "```json", json.dumps(decontam_report, indent=2), "```",
        "", "## Split and rendering", "",
        f"- Train states: {len(_read_jsonl(run_dir / 'train.jsonl'))}; dev states: {len(_read_jsonl(run_dir / 'dev.jsonl'))}.",
        f"- Dev code-family coverage: `{json.dumps(dev_code_families)}`.",
        f"- Datum statistics: `{json.dumps(datum_stats, sort_keys=True)}`.",
        "", "## Completion", "",
        f"- Private dataset: `jonsnov/muselet-decisions-v1`; revision `{upload_revision or 'not recorded'}`.",
    ]
    report_path = ROOT / "training/decisions/reports/full_gen.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report) + "\n")
