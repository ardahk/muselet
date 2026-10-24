"""A1 adjudication with claude-sonnet-5-5 via Message Batches (SPEC 1.4).

  python -m muselet_train.adjudicate submit --run R [--in teacher.jsonl] [--all-labels ASK]
  python -m muselet_train.adjudicate collect --run R
By default only items with needs_adjudication; --all-labels X adjudicates every item with label X.
"""

from __future__ import annotations

import argparse
import json
import time

from muselet_train.catalog import options
from muselet_train.gen import DATA, _load, _parse_json
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


def submit(run: str, infile: str, all_labels: list[str]) -> None:
    import anthropic

    rows = _load(run, infile)
    todo = [(i, r) for i, r in enumerate(rows) if r["needs_adjudication"] or r["label"] in all_labels]
    b = anthropic.Anthropic().messages.batches.create(requests=[
        {"custom_id": f"a{i}", "params": {"model": ADJUDICATOR, "max_tokens": 400,
                                           "messages": [{"role": "user", "content": a1_prompt(r)}]}}
        for i, r in todo])
    (DATA / run / "adjudication_batch.json").write_text(json.dumps({"id": b.id, "in": infile}))
    print("submitted", b.id, len(todo))


def collect(run: str, wait: bool) -> None:
    import anthropic

    c = anthropic.Anthropic()
    meta = json.loads((DATA / run / "adjudication_batch.json").read_text())
    while True:
        b = c.messages.batches.retrieve(meta["id"])
        print(b.processing_status, b.request_counts)
        if b.processing_status == "ended":
            break
        if not wait:
            return
        time.sleep(30)
    rows = _load(run, meta["in"])
    usage = {"calls": 0, "input": 0, "output": 0}
    for res in c.messages.batches.results(meta["id"]):
        r = rows[int(res.custom_id[1:])]
        if res.result.type != "succeeded":
            r["adjudication"] = {"error": res.result.type}
            continue
        m = res.result.message
        usage["calls"] += 1
        usage["input"] += m.usage.input_tokens
        usage["output"] += m.usage.output_tokens
        j = _parse_json("".join(x.text for x in m.content if x.type == "text")) or {}
        r["adjudication"] = {"model": m.model, **j}
    (DATA / run / meta["in"].replace(".jsonl", "_adj.jsonl")).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    (DATA / run / "adjudication_usage.json").write_text(json.dumps({ADJUDICATOR: usage}))
    print(json.dumps(usage))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["submit", "collect"])
    ap.add_argument("--run", required=True)
    ap.add_argument("--in", dest="infile", default="teacher.jsonl")
    ap.add_argument("--all-labels", nargs="*", default=[])
    ap.add_argument("--wait", action="store_true")
    a = ap.parse_args()
    submit(a.run, a.infile, a.all_labels) if a.cmd == "submit" else collect(a.run, a.wait)


if __name__ == "__main__":
    main()
