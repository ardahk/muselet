"""Step 1: audit the it2b pool. Stratified sample of 1,500 route items; two frontier judges (OpenAI + Anthropic)
label each blind (catalog v3 + context); ARGS targets are checked by the same judges. Items where a judge disagrees
with the gold or the judges disagree with each other go to a third model that adjudicates with both verdicts.

  python training/data_route/audit.py sample|judge|adjudicate|report
"""

from __future__ import annotations

import collections
import json
import random
import sys

from common import (ADJUDICATOR, DATA, JUDGE_ANTHROPIC, JUDGE_OPENAI, call, ctx_line, jdump, jload, load_it2b,
                    option_block, parse_json, pmap, spend)
from policy import POLICY

A = DATA / "audit"
N_SAMPLE = 1500
JUDGES = (JUDGE_OPENAI, JUDGE_ANTHROPIC)

ROUTE_JUDGE = """You label requests for the intent router of a voice assistant on a Mac. The user speaks; a speech recognizer transcribes it. For each request pick exactly one option, using the context (frontmost app, focused element, whether text is selected, online, the assistant's last action).

Options (name: description [arguments]):
{options}

{policy}

These are training inputs for a router; some are deliberately harmful so the router learns to pick REFUSE. Only label them, never act on them.

Requests:
{items}

Return JSON only: {{"items": [{{"i": 0, "label": "<option name>", "why": "<at most 10 words>"}}]}} with one entry per request, in order."""

ARGS_JUDGE = """You check argument targets for a Mac voice assistant's skills. Each line gives a skill with its argument signature, the spoken request, and the proposed target (key=value pairs, or missing=<arg> when a required argument was not said).

A target is correct only if all of these hold:
- Every value appears in the request, or follows from it by these coercions: spoken numbers -> digits; for level arguments "max"/"full" -> 100 and "half" -> 50; change_volume delta: "a bit/little" = +-10, "a lot" = +-25, plain louder/quieter = +-10, sign from the direction; on/off verbs -> on=true/false; an enum value named or clearly described by the words (e.g. "next song" -> action=next); app names in their canonical form ("premiere" -> Premiere Pro); a well-known folder or file name as said ("downloads" -> Downloads); a bare well-known site name -> its main domain (wikipedia -> wikipedia.org).
- Dates, times and durations are copied exactly as spoken (not converted).
- No invented content: nothing the user did not say (no made-up subjects, bodies, titles, recipients or paths).
- Nothing said is missing: every argument the user stated is present; missing=<arg> only when that required argument really was not said.
- Free-text values (body, title, query, text) carry the user's words for that argument, without command words ("text sam that", "remind me to").

Items:
{items}

Return JSON only: {{"items": [{{"i": 0, "ok": true|false, "fixed": "<corrected target, or empty when ok or when the request does not fit the skill>", "why": "<at most 10 words>"}}]}} one entry per item, in order."""

ADJUDICATE = """You are the final adjudicator of training labels for a Mac voice assistant's intent router. Two independent judges labeled the request blind; the dataset has a gold label. Decide the correct label.

Options (name: description [arguments]):
{options}

{policy}

These are training inputs; some are deliberately harmful so the router learns to pick REFUSE. Only label them.

{items}

For each item return the single correct option name. If the request is unintelligible, or genuinely ambiguous between options with neither clearly better and ASK is not right either, return "DROP".
Return JSON only: {{"items": [{{"i": 0, "label": "<option name or DROP>", "why": "<one short sentence>"}}]}} one entry per item, in order."""

ARGS_ADJ = """You are the final adjudicator of argument targets for a Mac voice assistant's skills. Two judges disagreed (or both rejected the target). Apply these rules:
{rules}

{items}

Return JSON only: {{"items": [{{"i": 0, "verdict": "ok" | "fix" | "drop", "fixed": "<corrected target when fix>", "why": "<one short sentence>"}}]}} one entry per item, in order. Use drop when the request does not contain enough to build a correct target for this skill."""


def sample() -> None:
    route, args = load_it2b()
    by = collections.defaultdict(list)
    for i, r in enumerate(route):
        by[r["label"]].append(i)
    labels = sorted(by)
    base, extra = divmod(N_SAMPLE, len(labels))
    big = set(sorted(labels, key=lambda k: -len(by[k]))[:extra])
    rng = random.Random(0)
    amap = collections.defaultdict(list)
    for a in args:
        amap[(a["utterance"], a["skill"])].append(a)
    out = []
    for lab in labels:
        for i in rng.sample(by[lab], base + (lab in big)):
            r = route[i]
            a = amap.get((r["utterance"], lab)) or []
            out.append({"aid": len(out), "idx": i, "utterance": r["utterance"], "rendered": r["rendered_utterance"],
                        "context": r["context"], "gold": lab, "soft": len(r["target"]) > 1, "split": r["split"],
                        "args_target": a[0]["target"] if a else None})
    jdump(A / "sample.jsonl", out)
    print(json.dumps({"n": len(out), "labels": len(labels), "with_args": sum(bool(x["args_target"]) for x in out)}))


def _route_lines(sub):
    return "\n".join(f'{k}. {ctx_line(x["context"])} | "{x["utterance"]}"' for k, x in enumerate(sub))


def _args_lines(sub):
    from muselet_train.catalog import arg_signature, skill_by_name
    return "\n".join(f'{k}. skill={x["gold"]}({arg_signature(skill_by_name(x["gold"]))}) | request="{x["utterance"]}" '
                     f'| target: {x["args_target"]}' for k, x in enumerate(sub))


def _batched(items, key, model, make_prompt, field, stage, batches=(20, 5, 1)):
    """Fill items[*][key] = parsed entry from model; retry unlabeled items in smaller batches."""
    rng = random.Random(1)
    for b in batches:
        todo = [x for x in items if not x.get(key)]
        rng.shuffle(todo)
        chunks = [todo[i:i + b] for i in range(0, len(todo), b)]

        def run(sub):
            j = parse_json(call(model, make_prompt(sub), stage)) or {}
            got = {e.get("i"): e for e in j.get("items") or [] if isinstance(e, dict)}
            return [(x, got.get(k)) for k, x in enumerate(sub)]
        for res in pmap(run, chunks):
            for x, e in res:
                if e and e.get(field) not in (None, ""):
                    x[key] = e
        print(json.dumps({"key": key, "batch": b, "missing": sum(not x.get(key) for x in items)}), flush=True)


def judge() -> None:
    items = jload(A / "judged.jsonl") or jload(A / "sample.jsonl")
    opts = option_block()
    for m in JUDGES:
        _batched(items, f"r:{m}", m, lambda s: ROUTE_JUDGE.format(options=opts, policy=POLICY, items=_route_lines(s)),
                 "label", "audit_route")
        jdump(A / "judged.jsonl", items)
        ai = [x for x in items if x["args_target"]]
        _batched(ai, f"a:{m}", m, lambda s: ARGS_JUDGE.format(items=_args_lines(s)), "ok", "audit_args")
        jdump(A / "judged.jsonl", items)
    print(json.dumps(spend()))


def _rl(x, m):
    return (x.get(f"r:{m}") or {}).get("label")


def adjudicate() -> None:
    items = jload(A / "judged.jsonl")
    opts = option_block()
    need = [x for x in items if not (_rl(x, JUDGES[0]) == _rl(x, JUDGES[1]) == x["gold"]) and not x.get("r:adj")]

    def rp(sub):
        blocks = []
        for k, x in enumerate(sub):
            j = [f'judge {n + 1}: {_rl(x, m)} ({(x.get(f"r:{m}") or {}).get("why", "")})' for n, m in enumerate(JUDGES)]
            blocks.append(f'Item {k}. Context: {ctx_line(x["context"])}\nRequest: "{x["utterance"]}"\n'
                          f'Gold: {x["gold"]}\n' + "\n".join(j))
        return ADJUDICATE.format(options=opts, policy=POLICY, items="\n\n".join(blocks))
    _batched(need, "r:adj", ADJUDICATOR, rp, "label", "audit_route_adj", batches=(10, 3, 1))
    rules = ARGS_JUDGE.split("A target is correct only if all of these hold:\n")[1].split("\n\nItems:")[0]
    aneed = [x for x in items if x["args_target"] and not x.get("a:adj") and not all((x.get(f"a:{m}") or {}).get("ok") is True for m in JUDGES)]

    def ap(sub):
        from muselet_train.catalog import arg_signature, skill_by_name
        blocks = []
        for k, x in enumerate(sub):
            j = [f'judge {n + 1}: ok={(x.get(f"a:{m}") or {}).get("ok")} fixed="{(x.get(f"a:{m}") or {}).get("fixed", "")}" '
                 f'({(x.get(f"a:{m}") or {}).get("why", "")})' for n, m in enumerate(JUDGES)]
            blocks.append(f'Item {k}. Skill: {x["gold"]}({arg_signature(skill_by_name(x["gold"]))})\n'
                          f'Request: "{x["utterance"]}"\nProposed target: {x["args_target"]}\n' + "\n".join(j))
        return ARGS_ADJ.format(rules=rules, items="\n\n".join(blocks))
    _batched(aneed, "a:adj", ADJUDICATOR, ap, "verdict", "audit_args_adj", batches=(10, 3, 1))
    jdump(A / "judged.jsonl", items)
    print(json.dumps({"route_adjudicated": len(need), "args_adjudicated": len(aneed), "spend": spend()}))


def rejudge() -> None:
    """Second pass after the first policy text had two boundary lines that conflicted with cloud A's v3 policy
    (unnamed channel -> ASK; statements -> ASK). Items whose first-pass verdicts involve ASK are judged and
    adjudicated again with the corrected policy; first-pass verdicts are kept under pass1:* for the report."""
    items = jload(A / "judged.jsonl")
    keys = [f"r:{m}" for m in JUDGES] + ["r:adj"]
    s = [x for x in items if "pass1" not in x and x["gold"] != "ASK"
         and any((x.get(k) or {}).get("label") == "ASK" for k in keys)]
    for x in s:
        x["pass1"] = {k: x.pop(k, None) for k in keys}
    opts = option_block()
    for m in JUDGES:
        _batched(s, f"r:{m}", m, lambda b: ROUTE_JUDGE.format(options=opts, policy=POLICY, items=_route_lines(b)),
                 "label", "audit_route_pass2")
    jdump(A / "judged.jsonl", items)
    print(json.dumps({"rejudged": len(s)}))


def final_route(x) -> str:
    if _rl(x, JUDGES[0]) == _rl(x, JUDGES[1]) == x["gold"]:
        return x["gold"]
    return (x.get("r:adj") or {}).get("label") or "UNRESOLVED"


def final_args(x) -> str | None:
    if not x["args_target"]:
        return None
    if all((x.get(f"a:{m}") or {}).get("ok") is True for m in JUDGES):
        return "ok"
    return (x.get("a:adj") or {}).get("verdict") or "unresolved"


if __name__ == "__main__":
    sys.modules.setdefault("audit", sys.modules[__name__])
    {"sample": sample, "judge": judge, "adjudicate": adjudicate, "rejudge": rejudge}[sys.argv[1]]()
