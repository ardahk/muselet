"""Fail-closed EventKit preflight for the benchmark-only calendar."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BENCH_CALENDAR = "Muselet Bench"
_PROBE = Path(__file__).with_name("calendar_probe.swift")


def _eventkit(action: str, *args: str) -> dict[str, Any]:
    if sys.platform != "darwin":
        raise RuntimeError("Calendar EventKit preflight requires macOS")
    result = subprocess.run(
        ["swift", str(_PROBE), action, *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Calendar EventKit probe returned invalid JSON: {result.stderr.strip()}") from exc
    if result.returncode:
        raise RuntimeError(payload.get("error") or result.stderr.strip() or "Calendar EventKit probe failed")
    return payload


def probe_bench_calendar() -> dict[str, Any]:
    return _eventkit("probe")


def setup_bench_calendar() -> dict[str, Any]:
    result = _eventkit("setup")
    if result.get("source_type") != "local":
        raise RuntimeError(
            "Refusing to use or create Muselet Bench outside a local Calendar source."
        )
    return result


def is_local_default(result: dict[str, Any]) -> bool:
    return (
        result.get("exists") is True
        and result.get("source_type") == "local"
        and result.get("is_default_for_new_events") is True
    )


def snapshot_bench_events() -> list[dict[str, Any]]:
    return list(_eventkit("events").get("events", []))


def delete_bench_events(identifiers: list[str]) -> list[str]:
    if not identifiers:
        return []
    return list(_eventkit("delete", *identifiers).get("deleted", []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe or set up the benchmark Calendar")
    parser.add_argument("action", choices=("probe", "setup"))
    args = parser.parse_args(argv)
    try:
        result = (
            probe_bench_calendar()
            if args.action == "probe"
            else setup_bench_calendar()
        )
    except Exception as exc:
        print(json.dumps({"exists": False, "error": str(exc)}), flush=True)
        return 1 if args.action == "setup" else 0
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if args.action == "probe" or is_local_default(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
