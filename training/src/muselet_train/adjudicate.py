"""A1 adjudication with claude-sonnet-5-5, synchronous calls (lead: no Batch APIs), SPEC 1.4.

  python -m muselet_train.adjudicate --run R [--in teacher.jsonl] [--all-labels ASK] [--differs]
Selected: needs_adjudication items whose label is ASK, REFUSE or has > 10% teacher disagreement;
--all-labels X adds every item with label X; --differs takes every item whose teacher argmax != label.
"""

from __future__ import annotations

import argparse
import json
import collections
import concurrent.futures as cf

from muselet_train.catalog import options
from muselet_train.gen import DATA, _call, _load, _parse_json
from muselet_train.prompts import A1
from muselet_train.route_render import RouteContext

ADJUDICATOR = "claude-sonnet-5-5"


def context_line(ctx: dict) -> str:
    return RouteContext(**ctx).line()


def a1_prompt(r: dict) -> str:
    opts = "\n".join(f"- {o.name}: {o.description}" for o in options())
    return A1.format(all_options_with_descriptions=opts, context_line=context_line(r["context"]),
                     utterance=r["utterance"], intended_label=r["label"],
                     teacher_argmax=r["teacher_argmax"], p=f"{r['teacher_p']:.2f}")


ALWAYS = ("ASK", "REFUSE")
DISAGREE = 0.10


def select(rows: list[dict], all_labels: list[str], differs: bool) -> list[int]:
    n, bad = collections.Counter(), collections.Counter()
    for r in rows:
        n[r["label"]] += 1
        bad[r["label"]] += r["teacher_argmax"] != r["label"]
    hot = {k for k in n if bad[k] / n[k] > DISAGREE} | set(ALWAYS)
    return [i for i, r in enumerate(rows)
            if r["label"] in all_labels
            or (differs and r["teacher_argmax"] != r["label"])
            or (r["needs_adjudication"] and r["label"] in hot)]


def run(run: str, infile: str, all_labels: list[str], differs: bool, concurrency: int = 16) -> None:
    rows = _load(run, infile)
    todo = select(rows, all_labels, differs)
    usage = {"calls": 0, "input": 0, "output": 0}
    reqs = [{"id": f"a{i}", "provider": "anthropic", "model": ADJUDICATOR, "prompt": a1_prompt(rows[i])}
            for i in todo]
    with cf.ThreadPoolExecutor(concurrency) as ex:
        for i, (res, u) in zip(todo, ex.map(_call, reqs), strict=True):
            usage["calls"] += 1
            usage["input"] += u["input"]
            usage["output"] += u["output"]
            j = _parse_json(res.get("text") or "") or {}
            rows[i]["adjudication"] = {"model": res.get("model"), **j} if j else {"error": res.get("error", "bad_json")}
    out = infile.replace(".jsonl", "_adj.jsonl")
    (DATA / run / out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    (DATA / run / out.replace(".jsonl", "_usage.json")).write_text(json.dumps({ADJUDICATOR: usage}))
    adj = [rows[i] for i in todo]
    by = collections.defaultdict(collections.Counter)
    for r in adj:
        a = r["adjudication"]
        by[r["label"]][a.get("verdict", "error") + ("" if a.get("verdict") != "relabel" else ":" + str(a.get("label")))] += 1
    print(json.dumps({"adjudicated": len(todo), "usage": usage, "by_label": by}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--in", dest="infile", default="teacher.jsonl")
    ap.add_argument("--all-labels", nargs="*", default=[])
    ap.add_argument("--differs", action="store_true")
    a = ap.parse_args()
    run(a.run, a.infile, a.all_labels, a.differs)


if __name__ == "__main__":
    main()
