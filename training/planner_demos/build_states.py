"""Build + validate the synthetic demo states and the v2-tune sources -> <out>/states.jsonl.

Every synthetic state must pass the v2 checks (evals/planner_v2_validate.py): every gold reply passes the v1 grader
runtime + strict, every wrong reply and the generic negatives fail, gold refs exist, gold skill lines match the
catalog (plus the orchestrator's code args open_folder.view / set_brightness.delta), observation lint. Invalid
states are counted per family and dropped (a non-zero count is a generator bug to fix). Then the decontamination
gate (gate.py) runs on every state, v2-tune included, and duplicate (goal, observation) pairs are dropped.

  python3 training/planner_demos/build_states.py [--out ~/data/planner_demos] [--seed 7]
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import states_lib  # noqa: E402
from gate import Gate  # noqa: E402

import planner_offline as po  # noqa: E402  (evals/ is on sys.path via states_lib)
import planner_v2_validate as V  # noqa: E402

CODE_ARGS = {"open_folder": {"view"}, "set_brightness": {"delta"}}


def skill_errs(lines):
    out = []
    for e in V.skill_errs(lines):
        m = re.match(r"(\w+): unknown arg (\w+)", e)
        if m and m[2] in CODE_ARGS.get(m[1], ()):
            continue
        out.append(e)
    return out


def check(s: dict) -> list[str]:
    errs = [f"obs: {e}" for e in V.lint_obs(s["observation"])]
    obs_refs = {int(x) for x in re.findall(r"^#(\d+) ", s["observation"], re.M)}
    for pat in s["accept_first"] + s["reject_any"] + s["confirm_before"]:
        try:
            re.compile(pat)
        except re.error as e:
            errs.append(f"regex {pat!r}: {e}")
    if errs:
        return errs
    if not s["gold"] or not s["wrong"]:
        errs.append("missing gold or wrong")
    for g in s["gold"]:
        r = po.grade(s, g)
        if not (r["pass"] and r["strict_pass"]):
            errs.append(f"gold fails: {g} {r}")
        errs += [f"gold skill: {e}" for e in skill_errs(g)]
        if bad := V.refs_used(g) - obs_refs:
            errs.append(f"gold refs not in obs {sorted(bad)}")
    for w in s["wrong"]:
        if po.grade(s, w)["pass"]:
            errs.append(f"wrong passes: {w}")
    neg = [[], ["Let me look at the screen first."]]
    if not any(g and g[0].startswith("done") for g in s["gold"]):
        neg.append(['done "Done"'])
    if not any(g and g[0].startswith("wait") for g in s["gold"]):
        neg.append(["wait 300"])
    for w in neg:
        if po.grade(s, w)["pass"]:
            errs.append(f"generic passes: {w}")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path.home() / "data" / "planner_demos")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--parts", default="states_a,states_b")
    ap.add_argument("--show-errors", type=int, default=3)
    a = ap.parse_args()
    import importlib
    fams = []
    for p in a.parts.split(","):
        if (HERE / f"{p}.py").exists():
            fams += importlib.import_module(p).FAMILIES
    for k, fn in enumerate(fams):
        fn(random.Random(a.seed * 1000 + k))
    syn = list(states_lib.STATES)
    v2 = [json.loads(x) for x in (V.HERE / "planner_scenarios_v2.jsonl").read_text().splitlines() if x.strip()]
    tune = [dict(r, family="v2_tune", source="v2-tune") for r in v2 if r["split"] == "v2-tune"]
    rep = {"generated": collections.Counter(s["family"] for s in syn), "invalid": collections.Counter(),
           "gate_dropped": collections.Counter(), "gate_by_rule": collections.Counter(), "gate_by_eval": collections.Counter(),
           "dup_dropped": collections.Counter()}
    shown = collections.Counter()
    ok = []
    for s in syn:
        errs = check(s)
        if errs:
            rep["invalid"][s["family"]] += 1
            if shown[s["family"]] < a.show_errors:
                shown[s["family"]] += 1
                print(f"INVALID {s['id']}: {errs[:2]}")
            continue
        ok.append(s)
    gate = Gate()
    seen, kept, gate_hits = set(), [], []
    for s in tune + ok:
        hits = gate.hits(s["goal"], s["observation"])
        if hits:
            rep["gate_dropped"][s["family"]] += 1
            for h in hits:
                rep["gate_by_rule"][h["rule"]] += 1
                rep["gate_by_eval"][h["eval"]] += 1
            gate_hits.append({"id": s["id"], "goal": s["goal"], "hits": hits[:3]})
            continue
        key = (s["goal"], s["observation"], json.dumps(s["last_batch"]), s["script_output"])
        if key in seen:
            rep["dup_dropped"][s["family"]] += 1
            continue
        seen.add(key)
        kept.append(s)
    assert not any(gate.hits(s["goal"], s["observation"]) for s in kept)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "states.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in kept))
    (a.out / "gate_hits.jsonl").write_text("".join(json.dumps(h, ensure_ascii=False) + "\n" for h in gate_hits))
    rep["kept"] = collections.Counter(s["family"] for s in kept)
    rep["kept_by_category"] = collections.Counter(s["category"] for s in kept)
    rep["kept_total"] = len(kept)
    rep["gate_eval_items"] = dict(gate.counts)
    (a.out / "states_report.json").write_text(json.dumps(rep, indent=1, default=dict))
    print(json.dumps({k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in rep.items() if k != "gate_eval_items"}, indent=1))


if __name__ == "__main__":
    main()
