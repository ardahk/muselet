"""Strict check of MULTI_STEP -> finance_review relabels (iteration 2 diagnosis: A1 relabeled generic
spreadsheet work such as averages, sorting or highlighting). finance_review is kept only for the four catalog
tasks; datums.route_items reverts the rest to MULTI_STEP (one-hot).
  python -m muselet_train.finance_check --run R
Reads teacher_*_adj.jsonl in the run dir; writes finance_check.jsonl / finance_check.json.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json

from muselet_train.adjudicate import ADJUDICATOR
from muselet_train.catalog import skill_by_name
from muselet_train.gen import DATA, _load, _parse_json

PROMPT = """A macOS voice assistant has a skill finance_review: {description}
Request: "{utterance}"
Does the request plainly ask for exactly one of these on the user's own budget spreadsheet or bank/card statement: categorize transactions, find duplicate charges, reconcile receipts against the statement, or list over-budget categories? Other spreadsheet work (averages, totals, sorting, charts, summaries, highlighting by amount, formulas, comparisons) does not count.
Return JSON: {{"fits": true | false, "task": "categorize" | "duplicates" | "receipts" | "over_budget" | "none", "reason": "<one sentence>"}}"""


def main() -> None:
    import anthropic

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    d = DATA / a.run
    seen, todo = set(), []
    for p in sorted(d.glob("teacher_*_adj.jsonl")):
        for r in _load(a.run, p.name):
            k = (r["utterance"], r["src"])
            if (r["label"] == "MULTI_STEP" and (r.get("adjudication") or {}).get("label") == "finance_review"
                    and k not in seen):
                seen.add(k)
                todo.append(r)
    desc = skill_by_name("finance_review").description
    client = anthropic.Anthropic()
    usage = collections.Counter()

    def one(r):
        for _ in range(3):
            m = client.messages.create(model=ADJUDICATOR, max_tokens=200, messages=[
                {"role": "user", "content": PROMPT.format(description=desc, utterance=r["utterance"])}])
            usage["calls"] += 1
            usage["input"] += m.usage.input_tokens
            usage["output"] += m.usage.output_tokens
            j = _parse_json("".join(x.text for x in m.content if x.type == "text"))
            if j and isinstance(j.get("fits"), bool):
                return {"utterance": r["utterance"], "src": r["src"], **j}
        return {"utterance": r["utterance"], "src": r["src"], "fits": None, "task": "error"}

    with cf.ThreadPoolExecutor(16) as ex:
        out = list(ex.map(one, todo))
    (d / "finance_check.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out))
    rep = {"candidates": len(out), "fits": dict(collections.Counter(str(x["fits"]) for x in out)),
           "task": dict(collections.Counter(x["task"] for x in out)), "usage": {ADJUDICATOR: dict(usage)},
           "reverted_examples": [x["utterance"] for x in out if x["fits"] is False][:20],
           "kept_examples": [x["utterance"] for x in out if x["fits"]][:20]}
    (d / "finance_check.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in rep.items() if "examples" not in k}))


if __name__ == "__main__":
    main()
