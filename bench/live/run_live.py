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
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.harness.core import report_math, resolve_templates, run_case, template_values
from bench.harness.documents import document_apps_for_case
from bench.harness.proxy import BenchProxy
from bench.harness.runtime import (
    HandsRuntime,
    release_slot_for_case,
    serve_timeout_supported,
)
from bench.harness.session import probe_session


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
        if "turns" in case:
            error = _turns_error(case)
            if error:
                raise ValueError(f"{path}:{line_number}: {case_id}: {error}")
        cases.append(case)
    return cases


def _turns_error(case: dict[str, Any]) -> str | None:
    turns = case.get("turns")
    if "utterance" in case or "text" in case:
        return "use either turns or utterance, not both"
    if not isinstance(turns, list) or not turns:
        return "turns must be a non-empty list"
    for number, turn in enumerate(turns, 1):
        if not isinstance(turn, dict) or not str(turn.get("utterance", "")).strip():
            return f"turn {number} has no utterance"
        if turn.get("confirm_reply", None) not in (None, True, False):
            return f"turn {number} confirm_reply must be null, true or false"
        if not isinstance(turn.get("check", []), list):
            return f"turn {number} check must be a list"
        wait_s = turn.get("wait_s", 1.0)
        if isinstance(wait_s, bool) or not isinstance(wait_s, (int, float)) or wait_s < 0:
            return f"turn {number} wait_s must be a number >= 0"
    return None


def _case_utterance(case: dict[str, Any]) -> str | None:
    if case.get("turns"):
        return " → ".join(str(turn["utterance"]) for turn in case["turns"])
    return case.get("utterance")


def _turn_steps(case: dict[str, Any]) -> list[str]:
    steps = []
    for number, turn in enumerate(case["turns"], 1):
        step = f"turn {number}: {turn['utterance']!r}"
        reply = turn.get("confirm_reply", case.get("confirm_reply"))
        if reply is not None:
            step += f" confirm_reply={str(reply).lower()}"
        step += f" wait_s={turn.get('wait_s', 1.0)}"
        if turn.get("check"):
            step += f" turn-checks={len(turn['check'])}"
        steps.append(step)
    return steps


def _values(args: argparse.Namespace) -> dict[str, str]:
    return template_values(sandbox=Path.home() / "MuseletSandbox")


def _pending_report_only(case: dict[str, Any], args: argparse.Namespace) -> bool:
    return bool(
        case.get("pending")
        and args.include_pending
        and not getattr(args, "run_pending", False)
    )


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
    if case.get("pending") and not args.include_pending and not getattr(
        args, "run_pending", False
    ):
        reasons.append("pending (use --include-pending or --run-pending)")
    if case.get("online") and args.offline:
        reasons.append("online task skipped by --offline")
    if (
        case.get("requires_user_ok")
        and not args.allow_user_ok
        and not _pending_report_only(case, args)
    ):
        reasons.append("requires user consent (use --allow-user-ok)")
    return reasons


def _step_order(case: dict[str, Any], *, report_only: bool = False) -> list[str]:
    if report_only:
        return ["report only: no session probe, setup, or utterance"]
    steps = ["session: hands probe session (skip if locked/asleep)"]
    if case.get("precondition"):
        steps.append("precondition")
    if case.get("restore"):
        steps.append("restore-get")
    if case.get("setup"):
        steps.append("setup")
    if case.get("turns"):
        steps.extend((*_turn_steps(case), "poll-checks", "final-checks"))
    else:
        steps.extend(("utterance", "poll-checks", "final-checks"))
    if case.get("forbid"):
        steps.append("forbid")
    if case.get("teardown"):
        steps.append("teardown")
    if case.get("restore"):
        steps.append("restore-set")
    return steps


def _local_ymd_hour(start: str) -> tuple[str, int] | None:
    """Bench snapshots give UTC ISO starts; the case expects the local `YYYY-M-D` date and hour."""
    try:
        d = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone()
    except (AttributeError, ValueError):
        return None
    return f"{d.year}-{d.month}-{d.day}", d.hour


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
        pending_report = _pending_report_only(case, args)
        report_only = pending_report and not reasons
        if not reasons and not pending_report:
            selected_counts[tier] = selected_counts.get(tier, 0) + 1
        rows.append({
            "id": case["id"],
            "tier": tier,
            "category": case.get("category"),
            "document_apps": [
                app.name for app in document_apps_for_case(case)
            ],
            "filter": (
                "report" if report_only else "skip" if reasons else "run"
            ),
            "skip_reason": (
                "; ".join(reasons) if reasons else
                "pending (use --run-pending to execute)" if report_only else None
            ),
            "resolved": resolve_templates(case, values),
            "step_order": _step_order(case, report_only=pending_report),
        })
        if case.get("turns"):
            rows[-1]["turns"] = [
                {
                    "utterance": turn["utterance"],
                    "confirm_reply": turn.get("confirm_reply", case.get("confirm_reply")),
                    "wait_s": turn.get("wait_s", 1.0),
                    "checks": len(turn.get("check", [])),
                }
                for turn in resolve_templates(case["turns"], values)
            ]
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


def _shell_rooted_case(case: dict[str, Any]) -> dict[str, Any]:
    rooted = copy.deepcopy(case)
    prefix = f"cd {shlex.quote(str(ROOT))} && "
    for key in ("setup", "teardown"):
        for step in rooted.get(key, []):
            if isinstance(step, dict) and isinstance(step.get("shell"), str):
                step["shell"] = prefix + step["shell"]
    return rooted


def _prepare_run_spec(
    case: dict[str, Any],
    *,
    event_check: Callable[[Any, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    run_spec = case
    if event_check is not None:
        run_spec = copy.deepcopy(case)
        run_spec["precondition"] = []
        run_spec["teardown"] = []
        run_spec["check"] = [event_check]
    run_spec = _shell_rooted_case(run_spec)
    run_spec["pre_setup_guard"] = _fixture_plan_guard(run_spec)
    return run_spec


def _fixture_plan_guard(case: dict[str, Any]):
    async def guard(runtime, _result):
        for step in case.get("setup", []):
            command = step.get("shell") if isinstance(step, dict) else None
            if not command or "setup_mac.sh" not in command or "--apply" not in command:
                continue
            dry_run = command.replace("--apply", "--dry-run")
            try:
                result = await runtime.run_script("shell", dry_run)
                if result.get("ok") is False or result.get("exit_code", 0) != 0:
                    return {
                        "status": "skipped",
                        "skip_reason": "fixture_plan_unverifiable",
                    }
                output = "\n".join(str(result.get(key, "")) for key in ("output", "stdout"))
            except Exception as exc:
                return {
                    "status": "skipped",
                    "skip_reason": "fixture_plan_unverifiable",
                    "fixture_plan_error": str(exc),
                }
            if "differs: overwrite" in output:
                return {"status": "skipped", "skip_reason": "fixture_would_overwrite"}
        return None
    return guard


async def _run_live(cases: list[dict[str, Any]], args: argparse.Namespace) -> int:
    from bench.hobbylm.calendar_safety import (
        delete_bench_events, is_local_default, probe_bench_calendar,
        setup_bench_calendar, snapshot_bench_events,
    )

    event_allowed = False
    event_probe_done = False
    event_skip_reason = "bench calendar not local default"
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
            serve_timeout_flag = serve_timeout_supported(args.hands_bin)
            with results_path.open("w", encoding="utf-8") as output:
                for repeat in range(1, args.repeat + 1):
                    for case in cases:
                        base = {
                            "id": case["id"],
                            "tier": case.get("tier"),
                            "category": case.get("category"),
                            "kind": case.get("category"),
                            "utterance": _case_utterance(case),
                            "expect_outcome": case.get("expect_outcome"),
                            "confirm_reply": case.get("confirm_reply"),
                            "repeat": repeat,
                            "manual": bool(case.get("manual")),
                            "pending": case.get("pending"),
                            "unsafe": bool(args.no_safety_guard),
                        }
                        if _pending_report_only(case, args):
                            reasons = _filter_reasons(case, args)
                            record = base | {
                                "status": "skipped",
                                "strict_pass": False,
                                "skip_reason": (
                                    "; ".join(reasons) if reasons else
                                    "pending (use --run-pending to execute)"
                                ),
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            continue
                        try:
                            session = probe_session(args.hands_bin)
                        except Exception as exc:
                            record = base | {
                                "status": "failed", "strict_pass": False,
                                "error": str(exc),
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            continue
                        base.update(session)
                        if session["skip_reason"]:
                            record = base | {
                                "status": "skipped",
                                "strict_pass": False,
                                "skip_reason": session["skip_reason"],
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            continue
                        if _is_event_case(case) and not event_probe_done:
                            event_probe_done = True
                            try:
                                if args.setup_bench_calendar:
                                    setup_bench_calendar()
                                event_allowed = is_local_default(probe_bench_calendar())
                            except Exception as exc:
                                event_skip_reason = f"calendar probe unavailable: {exc}"[:200]
                                print(
                                    f"warning: {event_skip_reason}; event cases will be skipped",
                                    file=sys.stderr,
                                )
                        if _is_event_case(case) and not event_allowed:
                            record = base | {
                                "status": "skipped",
                                "strict_pass": False,
                                "skip_reason": event_skip_reason,
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
                        try:
                            slot_released = await release_slot_for_case(proxy)
                        except Exception as exc:
                            record = base | {
                                "status": "failed", "strict_pass": False,
                                "error": str(exc),
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            continue
                        if not slot_released:
                            record = base | {
                                "status": "harness_timeout",
                                "strict_pass": False,
                                "harness_timeout": {
                                    "stage": "between_cases",
                                    "slot_released": False,
                                },
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            continue
                        try:
                            await proxy.begin_case(
                                case["id"], case.get("confirm_reply"),
                                allow_confirm_skills=set(case.get("allow_confirm_skills", [])),
                            )
                        except Exception as exc:
                            record = base | {
                                "status": "failed", "strict_pass": False,
                                "error": str(exc),
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            continue
                        try:
                            runtime = HandsRuntime(
                                proxy, args.hands_bin, out_dir / "hands-logs",
                                f"{case['id']}-r{repeat}", cwd=ROOT,
                            )
                            (out_dir / "hands-logs").mkdir(exist_ok=True)
                        except Exception as exc:
                            record = base | {
                                "status": "failed", "strict_pass": False,
                                "error": str(exc),
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            continue
                        try:
                            event_before = (
                                snapshot_bench_events() if _is_event_case(case) else []
                            )
                        except Exception as exc:
                            record = base | {
                                "status": "failed", "strict_pass": False,
                                "error": f"event snapshot failed: {exc}",
                            }
                            all_results.append(record)
                            _write_record(output, record)
                            try:
                                await runtime.stop()
                            except Exception:
                                pass
                            continue
                        event_check = None
                        if _is_event_case(case):
                            expected_date = values.get("next_friday_ymd")

                            async def grade_bench_event(_runtime, _context):
                                events = await asyncio.to_thread(snapshot_bench_events)
                                before_ids = {row["id"] for row in event_before}
                                created = [row for row in events if row["id"] not in before_ids]
                                matches = [
                                    row for row in created
                                    if row["title"].strip().casefold() == "dentist appointment"
                                    and _local_ymd_hour(row["start"]) == (expected_date, 15)
                                ]
                                return {
                                    "passed": bool(matches),
                                    "actual": {"created_in_bench_calendar": created},
                                }

                            event_check = grade_bench_event
                        run_spec = _prepare_run_spec(case, event_check=event_check)
                        try:
                            record = await run_case(
                                run_spec,
                                runtime,
                                values=values,
                                trace_path=trace_path,
                                poll_interval=0.5,
                            )
                        except Exception as exc:
                            try:
                                await runtime.stop()
                            except Exception:
                                pass
                            record = {
                                "id": case["id"], "tier": case.get("tier"),
                                "category": case.get("category"),
                                "kind": case.get("category"),
                                "utterance": _case_utterance(case),
                                "status": "failed", "strict_pass": False,
                                "error": str(exc),
                            }
                        finally:
                            if _is_event_case(case):
                                try:
                                    after = await asyncio.to_thread(snapshot_bench_events)
                                    before_ids = {row["id"] for row in event_before}
                                    await asyncio.to_thread(
                                        delete_bench_events,
                                        [row["id"] for row in after if row["id"] not in before_ids],
                                    )
                                except Exception as exc:
                                    record["event_cleanup_error"] = str(exc)
                                    record["strict_pass"] = False
                                    record["status"] = "failed"
                        record.update({k: v for k, v in base.items()
                                       if not (k == "skip_reason" and not v)})
                        record["hands_serve_timeout_flag"] = serve_timeout_flag
                        all_results.append(record)
                        _write_record(output, record)
    finally:
        if made_sandbox:
            shutil.rmtree(sandbox)
    summary = report_math(all_results, args.repeat)
    summary.update({
        "suite": str(args.suite),
        "git_sha": _git_sha(),
        "pending_included": args.include_pending or getattr(args, "run_pending", False),
        "run_pending": getattr(args, "run_pending", False),
        "manual_included": args.include_manual,
        "offline": args.offline,
        "allow_user_ok": args.allow_user_ok,
        "hands_serve_timeout_flag": serve_timeout_flag,
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
                "utterance": _case_utterance(case),
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
        print("pending strict pass by tier")
        for tier, stats in summary["pending"]["by_tier"].items():
            rate = stats["strict_pass_rate"]
            rate_text = "-" if rate is None else f"{rate:.1%}"
            pass_k = stats["pass^k"]
            latency = stats["latency_s"]
            print(
                f"{tier}: {stats['passed']}/{stats['executed']} strict ({rate_text}); "
                f"pass^{pass_k['k']}={pass_k['passed']}/{pass_k['eligible']}; "
                f"first-action p50={_format_pair(latency['first_action_p50'], latency['first_action_p95'])[0]}s"
            )


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
    parser.add_argument(
        "--include-pending", action="store_true",
        help="Report pending cases without executing them.",
    )
    parser.add_argument(
        "--run-pending", action="store_true",
        help="Execute pending cases through the normal guarded path.",
    )
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
