"""Tuned-vs-tuned route report: fit tau on val for each model, apply it to route_v2 / route_v1_clean.

Runtime rule (ml/src/brain/orchestrator.py): p_top < tau hands the utterance to System 2 (the planner). A
handoff counts as correct only when gold is MULTI_STEP; otherwise tuned accuracy is plain top-1 accuracy.

  uv run python -m muselet_train.tau --names base it2 it3 --val-tag val3 --out reports/it3_route_v2.json
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from muselet_train.catalog import REPO_ROOT
from muselet_train.train import OUT

NEW_V3 = {"draft_email", "compose_text"}
GRID = [round(0.05 * i, 2) for i in range(20)]


def load(name: str, tag: str) -> list[dict]:
    p = OUT / name / f"pred_{tag}.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def ok(r: dict, tau: float) -> bool:
    return r["label"] == "MULTI_STEP" if r["p_pred"] < tau else r["pred"] == r["label"]


def acc(rows: list[dict], tau: float) -> float:
    return sum(ok(r, tau) for r in rows) / len(rows) if rows else float("nan")


def fit(rows: list[dict]) -> float:
    return max(GRID, key=lambda t: (acc(rows, t), -t))


def block(rows: list[dict], tau: float) -> dict:
    per = collections.defaultdict(list)
    for r in rows:
        per[r["label"]].append(ok(r, tau))
    return {"n": len(rows), "argmax": acc(rows, 0.0), "tuned": acc(rows, tau),
            "handoff": sum(r["p_pred"] < tau for r in rows) / len(rows) if rows else float("nan"),
            "per_label": {k: round(sum(v) / len(v), 3) for k, v in sorted(per.items())},
            "per_label_n": {k: len(v) for k, v in sorted(per.items())}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", nargs="+", required=True)
    ap.add_argument("--val-tag", default="val")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    clean = json.loads((REPO_ROOT / "training/reports/evalcheck/clean_subsets.json").read_text())["route_v1_clean_both"]
    rep = {}
    for n in a.names:
        val, v2, v1 = load(n, a.val_tag), load(n, "route_v2"), load(n, "route_v1")
        tau = fit(val)
        rep[n] = {"tau": tau, "val": block(val, tau), "route_v2": block(v2, tau),
                  "route_v2_v2labels": block([r for r in v2 if r["label"] not in NEW_V3], tau),
                  "route_v1_clean": block([v1[i] for i in clean] if v1 else [], tau)}
        print(n, json.dumps({k: (v if not isinstance(v, dict) else {x: round(y, 3) for x, y in v.items()
                                                                     if isinstance(y, float)}) for k, v in rep[n].items()}))
    Path(a.out).write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
