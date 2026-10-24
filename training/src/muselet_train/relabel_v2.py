"""Catalog v2 relabel candidates (lead decision): MULTI_STEP finance-focus items and items mentioning
Bluetooth / lock screen / empty Trash. Writes v2_candidates.jsonl for the teacher + A1 (--differs)."""

from __future__ import annotations

import argparse
import json
import re

from muselet_train.gen import DATA, _load

V2_RX = re.compile(r"bluetooth|lock (the )?(screen|mac|computer)|empty (the )?trash", re.I)
FINANCE_FOCUS = "spreadsheet/finance"


def candidates(run: str) -> list[dict]:
    style = {r["id"]: r.get("style") or "" for r in _load(run, "requests.jsonl")}
    out = []
    for r in _load(run, "route.jsonl"):
        fin = r["label"] == "MULTI_STEP" and FINANCE_FOCUS in style.get(r["src"], "")
        if fin or V2_RX.search(r["utterance"]):
            out.append({**r, "v2_reason": "finance" if fin else "regex"})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    rows = candidates(a.run)
    (DATA / a.run / "v2_candidates.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(len(rows), sum(r["v2_reason"] == "finance" for r in rows))


if __name__ == "__main__":
    main()
