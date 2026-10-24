"""Tuned-vs-tuned route report: fit tau on val for each model, apply it to route_v2 / route_v1_clean.

Runtime rule (ml/src/brain/orchestrator.py): p_top < tau hands the utterance to System 2 with a top-2 hint.
--rule strict: a handoff is correct only when gold is MULTI_STEP. --rule hint: a handoff is correct when gold is
MULTI_STEP or one of the two hinted options. Above tau, tuned accuracy is plain top-1 accuracy.
--rule mac (default; evals/router_check.py): p_top < tau -> MULTI_STEP, tau on TAUS maximizing val macro-F1 over
gold labels (ties: higher accuracy, then lower tau).
--rule precision: tau = lowest grid value whose accepted (p_top >= tau) val items reach --target precision.

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
TAUS = [0.0, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8]


def gated(rows: list[dict], tau: float) -> tuple[float, float]:
    """evals/router_check.py gated(): accuracy and macro-F1 over gold labels of the gated predictions."""
    pairs = [(r["label"], r["pred"] if r["p_pred"] >= tau else "MULTI_STEP") for r in rows]
    acc = sum(g == p for g, p in pairs) / len(pairs)
    f1s = []
    for lab in sorted({g for g, _ in pairs}):
        tp = sum(g == lab and p == lab for g, p in pairs)
        fp = sum(g != lab and p == lab for g, p in pairs)
        fn = sum(g == lab and p != lab for g, p in pairs)
        pr = tp / (tp + fp) if tp + fp else 0
        rc = tp / (tp + fn) if tp + fn else 0
        f1s.append(2 * pr * rc / (pr + rc) if pr + rc else 0)
    return acc, sum(f1s) / len(f1s)


def load(name: str, tag: str) -> list[dict]:
    p = OUT / name / f"pred_{tag}.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


RULE = "mac"


def ok(r: dict, tau: float) -> bool:
    if r["p_pred"] >= tau:
        return r["pred"] == r["label"]
    top2 = sorted(r["probs"], key=r["probs"].get, reverse=True)[:2]
    return r["label"] == "MULTI_STEP" or (RULE == "hint" and r["label"] in top2)



def acc(rows: list[dict], tau: float) -> float:
    return sum(ok(r, tau) for r in rows) / len(rows) if rows else float("nan")


def precision(rows: list[dict], tau: float) -> float:
    acc_rows = [r for r in rows if r["p_pred"] >= tau]
    return sum(r["pred"] == r["label"] for r in acc_rows) / len(acc_rows) if acc_rows else float("nan")


def fit(rows: list[dict], target: float = 0.97) -> float:
    if RULE == "mac":
        return max(TAUS, key=lambda t: (gated(rows, t)[1], gated(rows, t)[0], -t))
    if RULE == "precision":
        return next((t for t in GRID if precision(rows, t) >= target), GRID[-1])
    return max(GRID, key=lambda t: (acc(rows, t), -t))


def block(rows: list[dict], tau: float) -> dict:
    per = collections.defaultdict(list)
    for r in rows:
        per[r["label"]].append(ok(r, tau))
    if not rows:
        return {"n": 0}
    g_acc, g_f1 = gated(rows, tau)
    return {"n": len(rows), "argmax": acc(rows, 0.0), "tuned": g_acc, "tuned_macro_f1": g_f1,
            "argmax_macro_f1": gated(rows, 0.0)[1], "accepted_precision": precision(rows, tau),
            "handoff": sum(r["p_pred"] < tau for r in rows) / len(rows) if rows else float("nan"),
            "per_label": {k: round(sum(v) / len(v), 3) for k, v in sorted(per.items())},
            "per_label_n": {k: len(v) for k, v in sorted(per.items())}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", nargs="+", required=True)
    ap.add_argument("--val-tag", default="val")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rule", choices=["mac", "strict", "hint", "precision"], default="mac")
    ap.add_argument("--target", type=float, default=0.97)
    a = ap.parse_args()
    global RULE
    RULE = a.rule
    clean = json.loads((REPO_ROOT / "training/reports/evalcheck/clean_subsets.json").read_text())["route_v1_clean_both"]
    rep = {}
    for n in a.names:
        val, v2, v1 = load(n, a.val_tag), load(n, "route_v2"), load(n, "route_v1")
        tau = fit(val, a.target)
        rep[n] = {"rule": RULE, "tau": tau, "val": block(val, tau), "route_v2": block(v2, tau),
                  "route_v2_v2labels": block([r for r in v2 if r["label"] not in NEW_V3], tau),
                  "route_v1_clean": block([v1[i] for i in clean] if v1 else [], tau)}
        print(n, json.dumps({k: (v if not isinstance(v, dict) else {x: round(y, 3) for x, y in v.items()
                                                                     if isinstance(y, float)}) for k, v in rep[n].items()}))
    Path(a.out).write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
