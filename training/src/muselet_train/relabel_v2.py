"""Catalog v2 relabel candidates (lead decision): MULTI_STEP finance-focus items and items mentioning
Bluetooth / lock screen / empty Trash. Writes v2_candidates.jsonl for the teacher + A1 (--differs)."""

from __future__ import annotations

import argparse
import json
import re

from muselet_train.gen import DATA, _load

V2_RX = re.compile(
    r"blue ?tooth"
    r"|\block\b(?: up)?(?: (?:the|my|this|your))? ?(?:screen|mac(?:book)?|computer|laptop|display)\b"
    r"|\b(?:screen ?lock|lock ?screen)\b"
    r"|\b(?:empty|clear|clean|purge|wipe|dump)(?: out| up)?(?: (?:the|my))? (?:trash|bin|rubbish)\b"
    r"|\btrash (?:bin|can)\b",
    re.I)
FINANCE_FOCUS = "spreadsheet/finance"
REGEX_TARGETS = ("bluetooth", "lock_screen", "empty_trash")  # already the new skill: nothing to relabel


def candidates(run: str) -> list[dict]:
    style = {r["id"]: r.get("style") or "" for r in _load(run, "requests.jsonl")}
    out = []
    for r in _load(run, "route.jsonl"):
        fin = r["label"] == "MULTI_STEP" and FINANCE_FOCUS in style.get(r["src"], "")
        if fin or (r["label"] not in REGEX_TARGETS and V2_RX.search(r["utterance"])):
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
