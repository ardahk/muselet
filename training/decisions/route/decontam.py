"""Eval decontamination filter (lead decision A, mandatory after generation, before soft labels).

Drop a route or ARGS item if, against ANY eval utterance, its normalized text is equal, char-5-gram
Jaccard >= 0.5, token-bigram Jaccard >= 0.6, or token-8-gram Jaccard >= 0.6 (both texts >= 12 tokens).
Items of <= 5 tokens are also dropped within token-level edit distance 1 of any eval utterance (decisions-9).
  python -m muselet_train.decontam --run R
Rewrites route.jsonl / args.jsonl in place (originals kept as *.pre_decontam.jsonl).
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import re
import unicodedata
from pathlib import Path

from .gen import DATA

REPO = Path(__file__).resolve().parents[3]
HOBBY = Path("/data/evals/hobbylm/data/frozen")


_CJK = "\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af"
_CJK_CHAR = re.compile(f"([{_CJK}])")
_DROP = re.compile(f"[^a-z0-9' {_CJK}]")


def norm(t: str) -> str:
    """Latin text: lowercase [a-z0-9'] words. CJK (Han, kana, Hangul) is kept and compared by characters: every CJK
    character is its own token, so the word rules (exact, n-gram, short edit) apply per character."""
    t = _CJK_CHAR.sub(r" \1 ", unicodedata.normalize("NFKC", t).lower())
    return " ".join(_DROP.sub(" ", t).split())


def _ngrams(seq, n: int) -> set:
    return {tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)}


def _j(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


class Feats:
    __slots__ = ("text", "toks", "c5", "b2", "g8", "src")

    def __init__(self, text: str, src: str = ""):
        self.src = src
        self.text = norm(text)
        self.toks = self.text.split()
        self.c5 = _ngrams(self.text, 5) or {self.text}
        self.b2 = _ngrams(self.toks, 2)
        self.g8 = _ngrams(self.toks, 8) if len(self.toks) >= 12 else set()


def eval_utterances() -> list[tuple[str, str]]:
    """(source, utterance) for every repo eval JSONL (route_v1, live_t1, external/utterances, ...) and the
    HobbyLM frozen tests. Rows carry the text as `utterance` (route_v1, live_t1) or `text` (evals/external);
    external rows are tagged with their own `source` (HobbyLM / DeskMind)."""
    out = []
    for p in sorted((REPO / "evals").glob("**/*.jsonl")):
        for ln in p.read_text().splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            t = r.get("utterance") or r.get("text")
            if isinstance(t, str) and t.strip():
                out.append((f"external/{r.get('source', p.stem)}" if "external" in p.parts else p.stem, t))
    for p in sorted(HOBBY.glob("*.tsv")):
        out += [("hobbylm/" + p.stem, row[2]) for row in csv.reader(p.open(), delimiter="\t")
                if len(row) > 2 and row[2].strip()]
    return out


SHORT = 5


def tok_edit_le1(a: list[str], b: list[str]) -> bool:
    """Token-level Levenshtein distance <= 1."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    s, t = (a, b) if len(a) < len(b) else (b, a)
    return any(t[:i] + t[i + 1:] == s for i in range(len(t)))


class Index:
    def __init__(self, texts: list[str] | list[tuple[str, str]]):
        pairs = [t if isinstance(t, tuple) else ("", t) for t in texts]
        self.evals = [Feats(t, src) for src, t in pairs if norm(t)]
        self.exact = {e.text: e for e in self.evals}
        self.by_len = collections.defaultdict(list)
        for e in self.evals:
            self.by_len[len(e.toks)].append(e)
        self.by_c5 = collections.defaultdict(list)
        for i, e in enumerate(self.evals):
            for g in e.c5:
                self.by_c5[g].append(i)

    def match(self, text: str) -> tuple[str, Feats] | None:
        f = Feats(text)
        if f.text in self.exact:
            return "exact", self.exact[f.text]
        cands = {i for g in f.c5 for i in self.by_c5.get(g, ())}
        for i in cands:  # every rule needs shared char-5-grams, so candidates cover all rules
            e = self.evals[i]
            if _j(f.c5, e.c5) >= 0.5:
                return "char5", e
            if _j(f.b2, e.b2) >= 0.6:
                return "bigram", e
            if f.g8 and e.g8 and _j(f.g8, e.g8) >= 0.6:
                return "tok8", e
        for n in (len(f.toks) - 1, len(f.toks), len(f.toks) + 1):  # either side short (<= 5 tokens)
            for e in self.by_len.get(n, ()):
                if min(len(f.toks), len(e.toks)) <= SHORT and tok_edit_le1(f.toks, e.toks):
                    return "short_edit1", e
        return None


def run(run_name: str, seed: int) -> dict:
    idx = Index(eval_utterances())
    d = DATA / run_name
    rep = {"eval_utterances": dict(collections.Counter(e.src for e in idx.evals)), "dropped": {},
           "dropped_by_eval_source": {}, "pairs": []}
    pairs = []
    for name, lab_key in (("route", "label"), ("args", "skill")):
        src = d / f"{name}.pre_decontam.jsonl"
        if not src.exists():
            (d / f"{name}.jsonl").rename(src)
        rows = [json.loads(ln) for ln in src.read_text().splitlines() if ln.strip()]
        kept, drop, by_src, by_rule = [], collections.Counter(), collections.Counter(), collections.Counter()
        short = collections.Counter()
        for r in rows:
            m = idx.match(r["utterance"])
            if m:
                drop[r[lab_key]] += 1
                by_src[m[1].src] += 1
                by_rule[m[0]] += 1
                if m[0] == "short_edit1":
                    short[r[lab_key]] += 1
                pairs.append({"set": name, "label": r[lab_key], "rule": m[0], "train": r["utterance"],
                              "eval": m[1].text, "eval_source": m[1].src})
            else:
                kept.append(r)
        (d / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
        rep["dropped"][name] = dict(sorted(drop.items()))
        rep["dropped_by_eval_source"][name] = dict(sorted(by_src.items()))
        rep.setdefault("dropped_by_rule", {})[name] = dict(by_rule)
        rep.setdefault("short_edit1_by_label", {})[name] = dict(short.most_common())
        rep[f"{name}_in"], rep[f"{name}_kept"] = len(rows), len(kept)
    rep["pairs"] = random.Random(seed).sample(pairs, min(10, len(pairs)))
    (d / "decontam.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    return rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rep = run(a.run, a.seed)
    print(json.dumps({k: v for k, v in rep.items() if k != "pairs"}))
    for p in rep["pairs"]:
        print(p)


if __name__ == "__main__":
    main()
