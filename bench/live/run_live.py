#!/usr/bin/env python3
"""Run the Muselet live suite through a timing and confirmation WebSocket proxy."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.harness.core import report_math, resolve_templates, run_case, template_values
from bench.harness.proxy import BenchProxy
from bench.harness.runtime import HandsRuntime


def _load_suite(path: Path) -> list[dict[str, Any]]:
    cases = []
    ids = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path}:{line_number}: case has no non-empty id")
        if case_id in ids:
            raise ValueError(f"{path}:{line_number}: duplicate id {case_id!r}")
        ids.add(case_id)
        cases.append(case)
    return cases


def _values(args: argparse.Namespace) -> dict[str, str]:
    return template_values(sandbox=Path.home() / "MuseletSandbox")


def _filter_reasons(case: dict[str, Any], args: argparse.Namespace) -> list[str]:
    reasons = []
    if args.tier and case.get("tier") not in args.tier:
        reasons.append("tier filter")
    if args.category and case.get("category") not in args.category:
        reasons.append("category filter")
    if args.id and case.get("id") not in args.id:
        reasons.append("id filter")
    if case.get("manual") and not args.include_manual:
        reasons.append("manual (use --include-manual)")
    if case.get("pending") and not args.include_pending:
        reasons.append("pending (use --include-pending)")
    if case.get("online") and args.offline:
        reasons.append("online task skipped by --offline")
    if case.get("requires_user_ok") and not args.allow_user_ok:
        reasons.append("requires user consent (use --allow-user-ok)")
    return reasons


def _step_order(case: dict[str, Any]) -> list[str]:
    steps = []
    if case.get("precondition"):
        steps.append("precondition")
    if case.get("restore"):
        steps.append("restore-get")
    if case.get("setup"):
        steps.append("setup")
    steps.extend(("utterance", "poll-checks", "final-checks"))
    if case.get("forbid"):
        steps.append("forbid")
    if case.get("teardown"):
        steps.append("teardown")
    if case.get("restore"):
        steps.append("restore-set")
    return steps


def _is_event_case(case: dict[str, Any]) -> bool:
    return case.get("id") == "time-event" or case.get("category") == "event"


def _dry_run(cases: list[dict[str, Any]], args: argparse.Namespace) -> int:
    values = _values(args)
    tier_counts: dict[str, int] = {}
    selected_counts: dict[str, int] = {}
    rows = []
    for case in cases:
        tier = str(case.get("tier", "unknown"))
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        reasons = _filter_reasons(case, args)
        if not reasons:
            selected_counts[tier] = selected_counts.get(tier, 0) + 1
        rows.append({
            "id": case["id"],
            "tier": tier,
            "category": case.get("category"),
            "filter": "skip" if reasons else "run",
            "skip_reason": "; ".join(reasons) if reasons else None,
            "resolved": resolve_templates(case, values),
            "step_order": _step_order(case),
        })
    print(json.dumps({
        "suite": str(args.suite),
        "cases": len(cases),
        "tier_counts": tier_counts,
        "selected_tier_counts": selected_counts,
        "repeat": args.repeat,
        "cases_by_repeat": len(cases) * args.repeat,
        "case_plan": rows,
    }, ensure_ascii=False, indent=2))
    return 0


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _write_record(stream, record: dict[str, Any]) -> None:
    stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    stream.flush()


async def _run_live(cases: list[dict[str, Any]], args: argparse.Namespace) -> int:
    from bench.hobbylm.calendar_safety import (
        delete_bench_events, is_local_default, probe_bench_calendar,
        setup_bench_calendar, snapshot_bench_events,
    )

    event_allowed = False
    if any(_is_event_case(case) for case in cases):
        if args.setup_bench_calendar:
            setup_bench_calendar()
        event_allowed = is_local_default(probe_bench_calendar())
    out_dir = args.out or Path("runs/bench/live") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "command.txt").write_text(shlex.join([sys.argv[0], *sys.argv[1:]]) + "\n", encoding="utf-8")
    (out_dir / "git_sha.txt").write_text(_git_sha() + "\n", encoding="utf-8")
    results_path = out_dir / "results.jsonl"
    sandbox = Path.home() / "MuseletSandbox"
    if sandbox.exists() or sandbox.is_symlink():
        raise FileExistsError(f"refusing to replace existing sandbox: {sandbox}")
    sandbox.mkdir()
    made_sandbox = True
    all_results: list[dict[str, Any]] = []
    values = _values(args)
    trace_path = ROOT / "runs" / "traces" / f"{date_today()}.jsonl"
    try:
        async with BenchProxy(
            args.brain_url, port=args.proxy_port,
            safety_guard=not args.no_safety_guard,
        ) as proxy:
            with results_path.open("w", encoding="utf-8") as output:
                for repeat in range(1, args.repeat + 1):
                    for case in cases:
                        base = {
                            "id": case["id"],
                            "tier": case.get("tier"),
                            "category": case.get("category"),
                            "kind": case.get("category"),
                            "utterance": case.get("utterance"),
                            "expect_outcome": case.get("expect_outcome"),
                            "confirm_reply": case.get("confirm_reply"),
                            "repeat": repeat,
                            "manual": bool(case.get("manual")),
                            "pending": case.get("pending"),
                            "unsafe": bool(args.no_safety_guard),
                        }
                        if _is_event_case(case) and not event_allowed:
                            record = base | {
                                "status": "skipped",
                                "strict_pass": False,
                                "skip_reason": "bench calendar not local default",
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            continue
                        reasons = _filter_reasons(case, args)
                        if reasons:
                            record = base | {
                                "status": "skipped",
                                "strict_pass": False,
                                "skip_reason": "; ".join(reasons),
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            continue
                        await proxy.wait_disconnected()
                        await proxy.begin_case(
                            case["id"], case.get("confirm_reply"),
                            allow_confirm_skills=set(case.get("allow_confirm_skills", [])),
                        )
                        runtime = HandsRuntime(
                            proxy, args.hands_bin, out_dir / "hands-logs",
                            f"{case['id']}-r{repeat}", cwd=ROOT,
                        )
                        (out_dir / "hands-logs").mkdir(exist_ok=True)
                        event_before = (
                            snapshot_bench_events() if _is_event_case(case) else []
                        )
                        run_spec = case
                        if _is_event_case(case):
                            run_spec = copy.deepcopy(case)
                            run_spec["precondition"] = []
                            run_spec["teardown"] = []
                            expected_date = values.get("next_friday_ymd")

                            async def grade_bench_event(_runtime, _context):
                                events = await asyncio.to_thread(snapshot_bench_events)
                                before_ids = {row["id"] for row in event_before}
                                created = [row for row in events if row["id"] not in before_ids]
                                matches = [
                                    row for row in created
                                    if row["title"].strip().casefold() == "dentist appointment"
                                    and row["start"].startswith(expected_date)
                                    and "T15:" in row["start"]
                                ]
                                return {
                                    "passed": bool(matches),
                                    "actual": {"created_in_bench_calendar": created},
                                }

                            run_spec["check"] = [grade_bench_event]
                        try:
                            record = await run_case(
                                run_spec,
                                runtime,
                                values=values,
                                trace_path=trace_path,
                                poll_interval=0.5,
                            )
                        except Exception as exc:
                            await runtime.stop()
                            record = {
                                "id": case["id"], "tier": case.get("tier"),
                                "category": case.get("category"),
                                "kind": case.get("category"),
                                "utterance": case.get("utterance"),
                                "status": "failed", "strict_pass": False,
                                "error": str(exc),
                            }
                        finally:
                            if _is_event_case(case):
                                after = await asyncio.to_thread(snapshot_bench_events)
                                before_ids = {row["id"] for row in event_before}
                                await asyncio.to_thread(
                                    delete_bench_events,
                                    [row["id"] for row in after if row["id"] not in before_ids],
                                )
                        record.update(base)
                        all_results.append(record)
                        _write_record(output, record)
    finally:
        if made_sandbox:
            shutil.rmtree(sandbox)
    summary = report_math(all_results, args.repeat)
    summary.update({
        "suite": str(args.suite),
        "git_sha": _git_sha(),
        "pending_included": args.include_pending,
        "manual_included": args.include_manual,
        "offline": args.offline,
        "allow_user_ok": args.allow_user_ok,
        "safety_guard": not args.no_safety_guard,
        "unsafe": bool(args.no_safety_guard),
        "confirm_no_send_cases": [
            {
                "id": row.get("id"),
                "repeat": row.get("repeat"),
                "confirm_asked": int(row.get("confirm_count", 0)) > 0,
                "confirm_cancelled": bool(row.get("confirm_cancelled")),
                "strict_pass": bool(row.get("strict_pass")),
                "expect_outcome": row.get("expect_outcome"),
            }
            for row in all_results
            if row.get("id") == "confirm-no-send"
        ],
        "likely_send_side_effect_cases": [
            {
                "id": case.get("id"),
                "category": case.get("category"),
                "utterance": case.get("utterance"),
                "expected_outcome": case.get("expect_outcome"),
                "result_count": sum(row.get("id") == case.get("id") for row in all_results),
            }
            for case in cases
            if any(token in json.dumps(case, ensure_ascii=False).casefold()
                   for token in ("send", "message", "email", "text", "invite", "attendee", "create_event"))
        ],
        "output": str(out_dir),
    })
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    _print_summary(summary)
    print(f"results: {out_dir}")
    return 0


def date_today() -> str:
    return datetime.now().date().isoformat()


def _print_summary(summary: dict[str, Any]) -> None:
    print("strict pass by tier")
    print(f"{'tier':<12} {'passed':>10} {'executed':>10} {'rate':>10}")
    for key, stats in summary["by_tier"].items():
        rate = stats["strict_pass_rate"]
        rate_text = "-" if rate is None else f"{rate:.1%}"
        print(f"{key:<12} {stats['passed']:>10} {stats['executed']:>10} {rate_text:>10}")
    print("strict pass by category")
    print(f"{'category':<16} {'passed':>10} {'executed':>10} {'rate':>10}")
    for key, stats in summary["by_category"].items():
        rate = stats["strict_pass_rate"]
        rate_text = "-" if rate is None else f"{rate:.1%}"
        print(f"{key:<16} {stats['passed']:>10} {stats['executed']:>10} {rate_text:>10}")
    print(
        "pass^k={passed}/{eligible} false_done={false_done} confirms_asked={confirms_asked}".format(
            passed=summary["pass^k"]["passed"],
            eligible=summary["pass^k"]["eligible"],
            false_done=summary["false_done"],
            confirms_asked=summary["confirms_asked"],
        )
    )
    latency = summary["latency_s"]
    print(
        "latency seconds: first-action p50/p95={}/{} verified p50/p95={}/{}".format(
            *_format_pair(latency["first_action_p50"], latency["first_action_p95"]),
            *_format_pair(latency["verified_p50"], latency["verified_p95"]),
        )
    )
    if summary["pending_cases"]:
        print(f"pending cases reported separately: {len(summary['pending_cases'])}")


def _format_pair(first: float | None, second: float | None) -> tuple[str, str]:
    return tuple("-" if value is None else f"{value:.3f}" for value in (first, second))


def _split_options(values: list[str] | None) -> set[str]:
    return {
        part.strip()
        for value in values or []
        for part in value.split(",")
        if part.strip()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path("evals/live_t1.jsonl"))
    parser.add_argument("--tier", action="append", default=[])
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--id", action="append", default=[])
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--brain-url", default="ws://127.0.0.1:8765")
    parser.add_argument("--proxy-port", type=int, default=8790)
    parser.add_argument("--hands-bin", default="hands")
    parser.add_argument("--include-manual", action="store_true")
    parser.add_argument("--include-pending", action="store_true")
    parser.add_argument("--allow-user-ok", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-safety-guard", action="store_true",
                        help="Disable RPC safety blocking; labels every result unsafe.")
    parser.add_argument("--setup-bench-calendar", action="store_true",
                        help="Create Muselet Bench only in an existing local Calendar source.")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    args.suite = args.suite if args.suite.is_absolute() else ROOT / args.suite
    args.tier = _split_options(args.tier)
    args.category = _split_options(args.category)
    args.id = _split_options(args.id)
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")
    try:
        cases = _load_suite(args.suite)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.id:
        unknown = args.id - {case["id"] for case in cases}
        if unknown:
            parser.error(f"unknown case IDs: {', '.join(sorted(unknown))}")
    if args.dry_run:
        return _dry_run(cases, args)
    try:
        return asyncio.run(_run_live(cases, args))
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
