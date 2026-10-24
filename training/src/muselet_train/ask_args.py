"""ASK ARGS for nearest skills with >= 2 required args (lead decision, step-3 gate).

Run the ARGS prompt (ARGS_SYSTEM + ARGS_USER) on the utterance with nearest_skill; missing = required
args not extracted (or named in missing=...); target = missing=<first missing arg in catalog order>; nothing missing -> drop.
  python -m muselet_train.ask_args --run R
Reads route.jsonl / args.jsonl, appends to args.jsonl, writes ask_args_dropped.jsonl.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re

from muselet_train.catalog import options
from muselet_train.gen import DATA, GEN_ANTHROPIC, _load
from muselet_train.route_render import ARGS_SYSTEM, RouteContext, args_messages

KV = re.compile(r'(\w+)=("[^"]*"|\S+)')


def required(opt) -> list[str]:
    return [a["name"] for a in opt.args if a.get("required")]


def label_one(client, opt, r: dict, tries: int = 3) -> tuple[dict, dict]:
    msgs = args_messages(opt, RouteContext(**r["context"]), r["utterance"])
    for _ in range(tries):
        m = client.messages.create(model=GEN_ANTHROPIC, max_tokens=200, system=ARGS_SYSTEM,
                                   messages=[{"role": "user", "content": msgs[1]["content"]}])
        lines = "".join(x.text for x in m.content if x.type == "text").strip().splitlines()
        if lines:
            break
    if not lines:
        return {"line": "", "missing": None, "model": m.model}, {"input": m.usage.input_tokens,
                                                                 "output": m.usage.output_tokens}
    line = lines[0]
    got = {k: v for k, v in KV.findall(line)}
    if "missing" in got:  # the ARGS prompt answers only missing=<arg>; trust the args it names
        named = {x.strip() for x in got["missing"].strip('"').split(",")}
        miss = [a for a in required(opt) if a in named]
    else:
        miss = [a for a in required(opt) if a not in got or got[a] in ('""', "")]
    return {"line": line, "missing": miss, "model": m.model}, {"input": m.usage.input_tokens,
                                                               "output": m.usage.output_tokens}


def main() -> None:
    import anthropic

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    opts = {o.name: o for o in options()}
    todo = [r for r in _load(a.run, "route.jsonl")
            if r["label"] == "ASK" and r.get("nearest_skill") in opts
            and len(required(opts[r["nearest_skill"]])) >= 2]
    client = anthropic.Anthropic()
    usage = {"calls": 0, "input": 0, "output": 0}
    new, dropped, errors = [], [], []
    with cf.ThreadPoolExecutor(16) as ex:
        for r, (res, u) in zip(todo, ex.map(lambda r: label_one(client, opts[r["nearest_skill"]], r), todo)):
            usage["calls"] += 1
            usage["input"] += u["input"]
            usage["output"] += u["output"]
            if res["missing"] is None:
                errors.append({**r, "labeler_line": ""})
            elif res["missing"]:
                new.append({"skill": r["nearest_skill"], "context": r["context"], "utterance": r["utterance"],
                            "target": f"missing={res['missing'][0]}", "src": r["src"], "kind": "ask_args",
                            "labeler": res["model"], "labeler_line": res["line"]})
            else:
                dropped.append({**r, "labeler_line": res["line"]})
    with open(DATA / a.run / "args.jsonl", "a") as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in new)
    (DATA / a.run / "ask_args_dropped.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in dropped))
    (DATA / a.run / "ask_args_usage.json").write_text(json.dumps({GEN_ANTHROPIC: usage}))
    print(json.dumps({"candidates": len(todo), "args_added": len(new), "dropped_not_ask": len(dropped),
                      "empty_reply": len(errors),
                      "usage": usage}))


if __name__ == "__main__":
    main()
