#!/usr/bin/env python3
"""Month-to-date Tinker spend from `tinker billing usage` (reads TINKER_API_KEY from .env, never prints it).

  python3 tools/tinker_spend.py                 # summary JSON
  python3 tools/tinker_spend.py --log F --guard  # append summary to F; exit 2 at phase cap, 3 near hard cap

Billing data lags real time by up to a few hours, so this is a backstop; the cloud session's pre-run
token/$ estimates and approval gates remain the primary control.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from devin_cloud import load_env  # noqa: E402

TINKER = str(ROOT / "ml/.venv/bin/tinker")
PHASE_CAP, HARD_CAP, HARD_WARN = 120.0, 150.0, 140.0


def tinker(env: dict, *args: str) -> dict:
    r = subprocess.run([TINKER, "-f", "json", *args], capture_output=True, text=True, env=env, timeout=120)
    if r.returncode:
        sys.exit(f"tinker {' '.join(args[:2])} failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log")
    ap.add_argument("--guard", action="store_true")
    a = ap.parse_args()
    env = {**os.environ, "TINKER_API_KEY": load_env()["TINKER_API_KEY"]}

    now = datetime.now(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = []
    while start < end:
        stop = min(start + timedelta(days=14), end)
        fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
        rows += tinker(env, "billing", "usage", fmt(start), fmt(stop)).get("data", [])
        start = stop

    total, unpriced = 0.0, defaultdict(int)
    by_model, by_type, tokens = defaultdict(float), defaultdict(float), defaultdict(int)
    last = None
    for r in rows:
        info = r.get("event_info") or {}
        kind = info.get("type", "?") + ("_cached" if info.get("cached") else "")
        model = r.get("base_model") or "?"
        tokens[kind] += info.get("token_count") or 0
        cost = r.get("estimated_cost_usd")
        if cost is None:
            unpriced[kind] += info.get("token_count") or 0
            continue
        total += cost
        by_model[model] += cost
        by_type[kind] += cost
        last = max(last or r["bucket_start"], r["bucket_start"])

    runs = tinker(env, "run", "list").get("runs", [])
    out = {
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "month_to_date_usd": round(total, 4),
        "phase_cap": PHASE_CAP, "hard_cap": HARD_CAP,
        "by_model": {k: round(v, 4) for k, v in by_model.items()},
        "by_type": {k: round(v, 4) for k, v in by_type.items()},
        "tokens": dict(tokens), "unpriced_tokens": dict(unpriced),
        "latest_priced_bucket": last, "runs": len(runs),
    }
    print(json.dumps(out))
    if a.log:
        with open(a.log, "a") as f:
            f.write(json.dumps(out) + "\n")
    if a.guard:
        sys.exit(3 if total >= HARD_WARN else 2 if total >= PHASE_CAP else 0)


if __name__ == "__main__":
    main()
