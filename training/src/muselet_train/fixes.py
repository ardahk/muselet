"""Training-review fixes applied when assembling a combined run (lead decisions training-3/6/7, ASK gate).

- concatenate the decontaminated source runs (route/args/requests) into one run directory;
- add the 2% ASK re-run items the A1 adjudicator kept as ASK (`a1_ask_keep`);
- drop G3 context pairs;
- constrain contexts for context-dependent labels (contexts.constrain), on route and ARGS rows;
- drop ARGS items whose string/path/contact values are not grounded in the utterance.
Writes route.jsonl, args.jsonl, requests.jsonl and fixes.json; run dedup afterwards.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
from dataclasses import asdict

from muselet_train.catalog import skill_by_name
from muselet_train.contexts import constrain
from muselet_train.decontam import norm
from muselet_train.gen import DATA, _load
from muselet_train.route_render import RouteContext

GROUNDED_TYPES = ("string", "path", "contact")
NUM = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}
NUM |= {w: str(10 * i) for i, w in enumerate("x x x thirty forty fifty sixty seventy eighty ninety".split()) if i >= 3}
NUM["hundred"] = "100"
ARG_RX = re.compile(r'(\w+)=("([^"]*)"|\S+)')


def parse_target(t: str) -> dict[str, str]:
    return {m.group(1): m.group(3) if m.group(3) is not None else m.group(2) for m in ARG_RX.finditer(t)}


def _words(s: str) -> list[str]:
    return [w.strip("'") for w in norm(re.sub(r"[/._~\-]", " ", s)).split() if w.strip("'")]


def _toks(s: str) -> set[str]:
    out = set()
    for w in _words(s):
        out |= {w, w.removesuffix("'s"), NUM.get(w, w)}
        out |= {k for k, v in NUM.items() if v == w}
    return out


def ungrounded(row: dict) -> list[str]:
    """Names of string/path/contact args whose value tokens are not all present in the utterance
    (case-insensitive; spoken number words == digits; path separators/extensions split into words)."""
    if row["target"].startswith("missing="):
        return []
    types = {a["name"]: a["type"] for a in skill_by_name(row["skill"]).args}
    have = _toks(row["utterance"])
    bad = []
    for k, v in parse_target(row["target"]).items():
        if types.get(k) in GROUNDED_TYPES:
            want = set(_words(v))
            if not want or not all(w in have or NUM.get(w, w) in have or w.removesuffix("'s") in have for w in want):
                bad.append(k)
    return bad


def is_g3(r: dict) -> bool:
    return bool(r.get("g3")) or str(r.get("src", "")).startswith("g3")


def build(out_run: str, sources: list[str], ask_run: str | None, seed: int) -> dict:
    rng = random.Random(seed)
    route = [r for s in sources for r in _load(s, "route.jsonl")]
    args = [r for s in sources for r in _load(s, "args.jsonl")]
    reqs = [r for s in sources for r in _load(s, "requests.jsonl")]
    rep: dict = {"sources": sources, "in": {"route": len(route), "args": len(args)}}
    if ask_run:
        keep = {(r["utterance"], r["src"]) for r in _load(ask_run, "teacher_adj.jsonl")
                if (r.get("adjudication") or {}).get("verdict") == "keep"}
        add = [{**r, "a1_ask_keep": True} for r in _load(ask_run, "route.jsonl") if (r["utterance"], r["src"]) in keep]
        utts = {r["utterance"] for r in add}
        add_args = [r for r in _load(ask_run, "args.jsonl") if r["utterance"] in utts]
        route, args = route + add, args + add_args
        reqs += _load(ask_run, "requests.jsonl")
        rep["ask_a1_kept_added"] = {"route": len(add), "args": len(add_args)}
    g3 = collections.Counter(r["label"] for r in route if is_g3(r))
    route = [r for r in route if not is_g3(r)]
    args = [r for r in args if not is_g3(r)]
    rep["g3_dropped_route_by_label"] = dict(g3.most_common())
    changed, ctx_of = collections.Counter(), {}
    for r in route:
        c = constrain(r["label"], RouteContext(**r["context"]), rng)
        if asdict(c) != r["context"]:
            changed[r["label"]] += 1
            r["context"] = asdict(c)
            ctx_of[(r["utterance"], r["src"], r["label"])] = r["context"]
    for r in args:
        if (r["utterance"], r["src"], r["skill"]) in ctx_of:
            r["context"] = ctx_of[(r["utterance"], r["src"], r["skill"])]
    rep["context_constrained_by_label"] = dict(changed)
    bad = collections.Counter()
    kept, examples = [], []
    for r in args:
        b = ungrounded(r)
        if b:
            bad[r["skill"]] += 1
            examples.append({"skill": r["skill"], "utterance": r["utterance"], "target": r["target"], "args": b})
        else:
            kept.append(r)
    rep["args_ungrounded_dropped"] = sum(bad.values())
    rep["args_ungrounded_by_skill"] = dict(bad.most_common())
    rep["args_ungrounded_examples"] = rng.sample(examples, min(15, len(examples)))
    rep["out"] = {"route": len(route), "args": len(kept)}
    d = DATA / out_run
    d.mkdir(parents=True, exist_ok=True)
    for name, rows in (("route", route), ("args", kept), ("requests", reqs)):
        (d / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    (d / "fixes.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    return rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--from", dest="sources", nargs="+", required=True)
    ap.add_argument("--ask-run")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rep = build(a.out, a.sources, a.ask_run, a.seed)
    print(json.dumps({k: v for k, v in rep.items() if k != "args_ungrounded_examples"}, indent=1))


if __name__ == "__main__":
    main()
