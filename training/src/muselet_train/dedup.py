"""Dedup, eval hygiene and 97/3 split (SPEC 1.5).

  python -m muselet_train.dedup --run R [--in route.jsonl]
Exact dedupe on normalized text (per label); MinHash near-dup (Jaccard >= 0.8) groups; drop items with
8-gram Jaccard >= 0.6 vs evals/ and HobbyLM data/frozen tests. Utterances are mostly < 8 words, so
8-grams are character 8-grams of the normalized text.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import re
from pathlib import Path

from datasketch import MinHash, MinHashLSH

from muselet_train.gen import DATA, _load

REPO = Path(__file__).resolve().parents[3]
HOBBY = Path("/data/evals/hobbylm/data/frozen")
NEAR, EVAL_J, VAL = 0.8, 0.6, 0.03


def norm(t: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", t.lower()).split())


def grams(t: str, n: int) -> set[str]:
    t = norm(t)
    return {t[i:i + n] for i in range(max(1, len(t) - n + 1))}


def minhash(t: str) -> MinHash:
    m = MinHash(num_perm=128, seed=1)
    for g in grams(t, 5):
        m.update(g.encode())
    return m


def eval_texts() -> list[str]:
    out = [json.loads(l)["utterance"] for p in sorted((REPO / "evals").glob("**/*.jsonl"))
           for l in p.read_text().splitlines() if l.strip()]
    for p in sorted(HOBBY.glob("*.tsv")):
        out += [row[2] for row in csv.reader(p.open(), delimiter="\t") if len(row) > 2]
    for p in sorted(HOBBY.glob("*.json")):
        def walk(x):
            if isinstance(x, str) and len(x.split()) >= 2:
                out.append(x)
            elif isinstance(x, dict):
                [walk(v) for v in x.values()]
            elif isinstance(x, list):
                [walk(v) for v in x]
        walk(json.loads(p.read_text()))
    return out


def run(run_name: str, infile: str, seed: int) -> None:
    rows = _load(run_name, infile)
    stats = collections.Counter()
    seen, kept = set(), []
    for r in rows:
        k = (norm(r["utterance"]), r["label"], json.dumps(r["context"], sort_keys=True))
        if k in seen or (norm(r["utterance"]), r["label"]) in seen:
            stats["exact_dup"] += 1
            continue
        seen.update({k, (norm(r["utterance"]), r["label"])})
        kept.append(r)
    ev = [grams(t, 8) for t in eval_texts()]
    ev_lsh = MinHashLSH(threshold=0.5, num_perm=128)
    ev_mh = []
    for i, g in enumerate(ev):
        m = MinHash(num_perm=128, seed=2)
        for x in g:
            m.update(x.encode())
        ev_lsh.insert(f"e{i}", m)
        ev_mh.append(m)
    clean = []
    for r in kept:
        g = grams(r["utterance"], 8)
        m = MinHash(num_perm=128, seed=2)
        for x in g:
            m.update(x.encode())
        hits = [int(h[1:]) for h in ev_lsh.query(m)]
        if any(len(g & ev[h]) / len(g | ev[h]) >= EVAL_J for h in hits):
            stats["eval_overlap"] += 1
            continue
        clean.append(r)
    lsh = MinHashLSH(threshold=NEAR, num_perm=128)
    parent = list(range(len(clean)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, r in enumerate(clean):
        m = minhash(r["utterance"])
        for h in lsh.query(m):
            parent[find(i)] = find(int(h))
        lsh.insert(str(i), m)
    groups = collections.defaultdict(list)
    for i in range(len(clean)):
        groups[find(i)].append(i)
    stats["near_dup_groups_gt1"] = sum(len(g) > 1 for g in groups.values())
    rng = random.Random(seed)
    by_label = collections.defaultdict(list)
    for g in groups.values():
        by_label[collections.Counter(clean[i]["label"] for i in g).most_common(1)[0][0]].append(g)
    split = {}
    for lab, gs in sorted(by_label.items()):
        rng.shuffle(gs)
        n = sum(len(g) for g in gs)
        nval = 0
        for g in gs:
            s = "val" if nval < round(VAL * n) else "train"
            nval += len(g) if s == "val" else 0
            for i in g:
                split[i] = s
    d = DATA / run_name
    for s in ("train", "val"):
        (d / f"route_{s}.jsonl").write_text("".join(
            json.dumps({**clean[i], "split": s}, ensure_ascii=False) + "\n" for i in sorted(split) if split[i] == s))
    counts = collections.defaultdict(collections.Counter)
    for i, s in split.items():
        counts[clean[i]["label"]][s] += 1
    rep = {"input": len(rows), **stats, "kept": len(clean),
           "per_label": {k: dict(v) for k, v in sorted(counts.items())}}
    (d / "split_stats.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_label"}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--in", dest="infile", default="route.jsonl")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    run(a.run, a.infile, a.seed)


if __name__ == "__main__":
    main()
