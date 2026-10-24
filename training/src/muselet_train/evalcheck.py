"""Hard contamination gate: training utterances vs every route_v1 / live_t1 / evals/external utterance.

Rules (any one is an overlap): normalized exact match; a shared word 13-gram; token edit distance <= 1 when
either side has 5 tokens or fewer. Normalization = decontam.norm (lowercase, strip punctuation, collapse spaces;
CJK characters are kept and count as one token each). Eval items that normalize to nothing are never matched.

  python -m muselet_train.evalcheck --datums jonsnov/muselet-route-datums-main@2bd81d8 --out /data/diag/evalcheck_main
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
from pathlib import Path

from muselet_train.decontam import SHORT, norm, tok_edit_le1

REPO = Path(__file__).resolve().parents[3]
EVALS = {"route_v1": REPO / "evals/route_v1.jsonl", "live_t1": REPO / "evals/live_t1.jsonl",
         "route_v2": REPO / "evals/route_v2.jsonl"}
EXTERNAL = REPO / "evals/external/utterances.jsonl"
N = 13


def eval_items() -> list[tuple[str, int, str]]:
    out = []
    for name, p in EVALS.items():
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text().splitlines()):
            if line.strip():
                out.append((name, i, json.loads(line)["utterance"]))
    for i, line in enumerate(EXTERNAL.read_text().splitlines()):
        if line.strip():
            r = json.loads(line)
            out.append((f"external/{r.get('source', 'external')}", i, r["text"]))
    return out


def _grams(t: list[str]) -> set[tuple[str, ...]]:
    return {tuple(t[i:i + N]) for i in range(len(t) - N + 1)}


def overlaps(texts: list[str], evals: list[tuple[str, int, str]]) -> list[dict]:
    """(train text, eval item, rule) for every overlapping pair."""
    ev = [(name, i, u, norm(u).split()) for name, i, u in evals if norm(u)]
    exact = collections.defaultdict(list)
    grams = collections.defaultdict(list)
    by_len = collections.defaultdict(list)
    for e in ev:
        exact[" ".join(e[3])].append(e)
        for g in _grams(e[3]):
            grams[g].append(e)
        by_len[len(e[3])].append(e)
    hits = []
    for t in dict.fromkeys(texts):
        tk = norm(t).split()
        if not tk:
            continue
        found = {}
        for e in exact.get(" ".join(tk), []):
            found.setdefault(e[:2], (e, "exact"))
        for g in _grams(tk):
            for e in grams.get(g, []):
                found.setdefault(e[:2], (e, "ngram13"))
        for L in (len(tk) - 1, len(tk), len(tk) + 1):
            for e in by_len.get(L, []):
                if min(len(tk), len(e[3])) <= SHORT and tok_edit_le1(tk, e[3]):
                    found.setdefault(e[:2], (e, "short_edit1"))
        hits += [{"train": t, "eval": e[0], "eval_idx": e[1], "eval_utterance": e[2], "rule": r}
                 for e, r in found.values()]
    return hits


def check_rows(route: list[dict], args: list[dict]) -> dict:
    """route rows: utterance (+ rendered_utterance, the ASR-noised text actually trained); args rows: utterance."""
    evals = eval_items()
    rep, pairs = {"evals": dict(collections.Counter(e[0] for e in evals)),
                  "evals_empty_after_norm": dict(collections.Counter(e[0] for e in evals if not norm(e[2])))}, []
    for kind, rows in (("route", route), ("args", args)):
        for split in ("train", "val"):
            sub = [r for r in rows if r.get("split", "train") == split]
            texts = [r["utterance"] for r in sub] + [r["rendered_utterance"] for r in sub if r.get("rendered_utterance")]
            h = overlaps(texts, evals)
            for x in h:
                x |= {"kind": kind, "split": split}
            pairs += h
            rep[f"{kind}_{split}"] = {"rows": len(sub), "pairs": len(h),
                                      "by_rule": dict(collections.Counter(x["rule"] for x in h)),
                                      "by_eval": dict(collections.Counter(x["eval"] for x in h))}
    aff = sorted({(x["eval"], x["eval_idx"], x["eval_utterance"]) for x in pairs})
    rep["affected"] = {k: [{"idx": i, "utterance": u} for e, i, u in aff if e == k] for k in rep["evals"]}
    rep["affected_counts"] = {k: len(v) for k, v in rep["affected"].items()}
    return rep | {"pairs": pairs}


def _load(spec: str) -> tuple[list[dict], list[dict]]:
    if not Path(spec).exists():
        from huggingface_hub import snapshot_download
        repo, _, rev = spec.partition("@")
        spec = snapshot_download(repo, repo_type="dataset", revision=rev or None)
    rd = [json.loads(x) for x in gzip.open(Path(spec) / "route.jsonl.gz", "rt")]
    ad = [json.loads(x) for x in gzip.open(Path(spec) / "args.jsonl.gz", "rt")]
    return rd, ad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datums", required=True, help="local dir or HF dataset repo[@revision] from datums_export")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rep = check_rows(*_load(a.datums))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pairs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in rep.pop("pairs")))
    (out / "report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "affected"}))


if __name__ == "__main__":
    main()
