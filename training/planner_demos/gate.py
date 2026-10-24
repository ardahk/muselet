"""Decontamination gate for planner demo states: the router's hard gate (cloud/data-pipeline
training/src/muselet_train/evalcheck.py + decontam.norm / tok_edit_le1, copied here because that package is not on main).

A state's goal overlaps an eval item when, after norm(): exact match; a shared word 13-gram; or token edit distance <= 1
when either side has <= 5 tokens. CJK characters count as one token each. Eval items that normalize to nothing never match.
Eval items: v2-holdout goals, v1 tune/holdout/holdout2 goals (evals/planner_offline.py), evals/live_t1.jsonl, and every
evals/external/utterances.jsonl row (HobbyLM sealed r1-r4, calc, system-settings; DeskMind diag/dyn/proposals).
Also rejected: a state whose (goal, observation) equals any v1 / v2-holdout scenario's.
"""

from __future__ import annotations

import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
N, SHORT = 13, 5
_CJK = "\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af"
_CJK_CHAR = re.compile(f"([{_CJK}])")
_DROP = re.compile(f"[^a-z0-9' {_CJK}]")


def norm(t: str) -> str:
    t = _CJK_CHAR.sub(r" \1 ", unicodedata.normalize("NFKC", t).lower())
    return " ".join(_DROP.sub(" ", t).split())


def tok_edit_le1(a: list[str], b: list[str]) -> bool:
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    s, t = (a, b) if len(a) < len(b) else (b, a)
    return any(t[:i] + t[i + 1:] == s for i in range(len(t)))


def _grams(t):
    return {tuple(t[i:i + N]) for i in range(len(t) - N + 1)}


def eval_items() -> tuple[list[tuple[str, str]], set[tuple[str, str]]]:
    """([(source, text)], {(goal, observation)} of forbidden scenarios)"""
    sys.path.insert(0, str(REPO / "evals"))
    import planner_offline as po
    items, pairs = [], set()
    for name, rows in (("v1/tune", po.TUNE), ("v1/holdout", po.HOLDOUT), ("v1/holdout2", po.HOLDOUT2)):
        for s in rows:
            items.append((name, s["goal"]))
            pairs.add((s["goal"], s["observation"]))
    for ln in (REPO / "evals/planner_scenarios_v2.jsonl").read_text().splitlines():
        s = json.loads(ln)
        if s["split"] == "v2-holdout":
            items.append(("v2-holdout", s["goal"]))
            pairs.add((s["goal"], s["observation"]))
    for ln in (REPO / "evals/live_t1.jsonl").read_text().splitlines():
        if ln.strip():
            items.append(("live_t1", json.loads(ln)["utterance"]))
    for ln in (REPO / "evals/external/utterances.jsonl").read_text().splitlines():
        if ln.strip():
            r = json.loads(ln)
            items.append((f"external/{r['source']}", r["text"]))
    return items, pairs


class Gate:
    def __init__(self):
        items, self.pairs = eval_items()
        self.counts = collections.Counter(src for src, _ in items)
        self.ev = [(src, t, norm(t).split()) for src, t in items if norm(t)]
        self.exact, self.grams, self.by_len = (collections.defaultdict(list) for _ in range(3))
        for e in self.ev:
            self.exact[" ".join(e[2])].append(e)
            for g in _grams(e[2]):
                self.grams[g].append(e)
            self.by_len[len(e[2])].append(e)

    def hits(self, goal: str, observation: str | None = None) -> list[dict]:
        out = {}
        if observation is not None and (goal, observation) in self.pairs:
            out[("pair", goal)] = {"rule": "same_scenario", "eval": "scenario", "eval_text": goal}
        tk = norm(goal).split()
        if not tk:
            return list(out.values())
        for e in self.exact.get(" ".join(tk), []):
            out.setdefault(e[:2], {"rule": "exact", "eval": e[0], "eval_text": e[1]})
        for g in _grams(tk):
            for e in self.grams.get(g, []):
                out.setdefault(e[:2], {"rule": "ngram13", "eval": e[0], "eval_text": e[1]})
        for L in (len(tk) - 1, len(tk), len(tk) + 1):
            for e in self.by_len.get(L, []):
                if min(len(tk), len(e[2])) <= SHORT and tok_edit_le1(tk, e[2]):
                    out.setdefault(e[:2], {"rule": "short_edit1", "eval": e[0], "eval_text": e[1]})
        return list(out.values())


if __name__ == "__main__":
    g = Gate()
    print(dict(g.counts))
    for t in ["open safari", "turn on dark mode and set volume to 30", "make a folder called taxes in downloads"]:
        print(t, "->", g.hits(t))
