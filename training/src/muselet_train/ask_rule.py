"""Rule-based ASK validation (lead decision, iteration 2; replaces Sonnet-agreement for ASK).

An ASK route item stays ASK only when the ARGS labeler (ARGS_SYSTEM + ARGS_USER on nearest_skill) finds a
required argument missing AND the request names no concrete value for it; otherwise it is a complete request
and becomes nearest_skill ("please open Downloads" stays open_folder). No nearest skill / empty reply -> drop.
  python -m muselet_train.ask_rule --run R
Writes ask_rule.jsonl / ask_rule.json (counts, 20 examples per verdict); rewrites args.jsonl so missing= targets
exist exactly for rule-ASK items (original kept as args.pre_ask_rule.jsonl). datums.route_items reads it.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json
import random

from muselet_train.ask_args import KV, label_one, required
from muselet_train.catalog import options
from muselet_train.gen import DATA, GEN_ANTHROPIC, _load


def verdict(req: list[str], line: str, missing: list[str] | None) -> str:
    """'ask' iff some required arg is missing and none of the missing args carries a value in the line."""
    if not req:
        return "concrete"
    if missing is None:
        return "error"
    got = {k: v.strip('"').strip() for k, v in KV.findall(line)}
    return "ask" if missing and not any(got.get(a) for a in missing) else "concrete"


def main() -> None:
    import anthropic

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    opts = {o.name: o for o in options()}
    asks = [r for r in _load(a.run, "route.jsonl") if r["label"] == "ASK"]
    client = anthropic.Anthropic()
    usage = {"calls": 0, "input": 0, "output": 0}

    def one(r):
        ns = r.get("nearest_skill")
        if ns not in opts:
            return {"verdict": "no_skill", "missing": None, "line": ""}
        req = required(opts[ns])
        if not req:
            return {"verdict": "concrete", "missing": [], "line": ""}
        res, u = label_one(client, opts[ns], r)
        usage["calls"] += 1
        usage["input"] += u["input"]
        usage["output"] += u["output"]
        return {"verdict": verdict(req, res["line"], res["missing"]), "missing": res["missing"], "line": res["line"]}

    with cf.ThreadPoolExecutor(16) as ex:
        res = list(ex.map(one, asks))
    out = [{"utterance": r["utterance"], "src": r["src"], "nearest_skill": r.get("nearest_skill"),
            "context": r["context"], **v} for r, v in zip(asks, res)]
    d = DATA / a.run
    (d / "ask_rule.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out))

    is_ask = {x["utterance"] for x in out if x["verdict"] == "ask"}
    ask_utts = {x["utterance"] for x in out}
    args = _load(a.run, "args.jsonl")
    (d / "args.pre_ask_rule.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in args))
    keep = [x for x in args if not (x["target"].startswith("missing=") and x["utterance"] in ask_utts
                                    and x["utterance"] not in is_ask)]
    have = {x["utterance"] for x in keep if x["target"].startswith("missing=")}
    added = [{"skill": x["nearest_skill"], "context": x["context"], "utterance": x["utterance"],
              "target": f"missing={x['missing'][0]}", "src": x["src"], "kind": "ask_rule",
              "labeler": GEN_ANTHROPIC, "labeler_line": x["line"]}
             for x in out if x["verdict"] == "ask" and x["utterance"] not in have]
    (d / "args.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in keep + added))

    rng = random.Random(a.seed)
    ex = {v: rng.sample([x for x in out if x["verdict"] == v], min(20, sum(x["verdict"] == v for x in out)))
          for v in ("ask", "concrete")}
    rep = {"ask_items": len(out), "verdicts": dict(collections.Counter(x["verdict"] for x in out)),
           "concrete_to": dict(collections.Counter(x["nearest_skill"] for x in out if x["verdict"] == "concrete")),
           "args_missing_removed": len(args) - len(keep), "args_missing_added": len(added),
           "usage": {GEN_ANTHROPIC: usage},
           "examples": {v: [{k: x[k] for k in ("utterance", "nearest_skill", "missing", "line")} for x in xs]
                        for v, xs in ex.items()}}
    (d / "ask_rule.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in rep.items() if k != "examples"}))


if __name__ == "__main__":
    main()
