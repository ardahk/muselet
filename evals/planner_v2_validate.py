"""Validate evals/planner_scenarios_v2.jsonl with the v1 grader (evals/planner_offline.grade, runtime-equivalent).

Checks, all automatic:
  schema       same fields as planner_offline.sc() + category/split/gold/wrong; ids unique; regexes compile
  gold         every gold reply passes the grader (runtime and strict), uses only refs in the observation
  wrong        every scenario has >= 1 plausible wrong reply and every one of them fails
  generic      an empty reply, `wait 300`, and (unless a gold reply is `done`) `done "Done"` all fail
  realism      observation lint against HandsKit's serializer (roles, value/checked placement, ordering, header)
  split        each category is split exactly 50/50 into v2-tune / v2-holdout
  overlap      no v2 goal+observation equals a v1 scenario's; no goal is shared between v2-tune and v2-holdout

  python3 evals/planner_v2_validate.py [--file evals/planner_scenarios_v2.jsonl] [--json out.json]
Exit code 1 when any check fails.
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import planner_offline as po  # noqa: E402
from planner_v2_lib import BLIND_HINT, CHECK_ROLES, ROLES_INTERACTIVE, ROLES_LABELED, VALUE_ROLES  # noqa: E402

FIELDS = ["id", "tags", "goal", "observation", "last_batch", "script_output", "accept_first", "reject_any",
          "confirm_before"]
HEAD = re.compile(r'^app: [^|]+ \| window: "(?:[^"\\]|\\.)*"( \| focused: #(\d+))?$')
LINE = re.compile(r'^#(\d+) ([a-z]+) "((?:[^"\\]|\\.)*)"( value="(?:[^"\\]|\\.)*")?( checked| unchecked)?'
                  r'( selected)?( disabled)?$')


def lint_obs(obs: str) -> list[str]:
    errs, lines = [], obs.split("\n")
    m = HEAD.match(lines[0])
    if not m:
        return [f"bad header {lines[0]!r}"]
    refs, seen_labeled = [], False
    body = lines[1:]
    if body and body[-1] == BLIND_HINT:
        body = body[:-1]
    for ln in body:
        lm = LINE.match(ln)
        if not lm:
            errs.append(f"bad line {ln!r}")
            continue
        ref, role, label, val, chk = int(lm[1]), lm[2], lm[3], lm[4], lm[5]
        refs.append(ref)
        if role not in ROLES_INTERACTIVE + ROLES_LABELED:
            errs.append(f"role {role!r} not in kRoleMap")
        if role in VALUE_ROLES and not val:
            errs.append(f"{role} without value: {ln!r}")
        if val and role not in VALUE_ROLES:
            errs.append(f"value on {role}: {ln!r}")
        if role in CHECK_ROLES and not chk:
            errs.append(f"{role} without checked/unchecked: {ln!r}")
        if chk and role not in CHECK_ROLES:
            errs.append(f"checked on {role}: {ln!r}")
        if role in ROLES_LABELED:
            seen_labeled = True
            if not label:
                errs.append(f"unlabeled {role}")
            if role == "text" and len(re.sub(r"\\(.)", r"\1", label)) > 80:
                errs.append(f"text label > 80 chars: {ln!r}")
        elif seen_labeled:
            errs.append(f"interactive after text/image: {ln!r}")
    if len(set(refs)) != len(refs):
        errs.append("duplicate refs")
    if m[2] and int(m[2]) not in refs:
        errs.append("focused ref not in observation")
    return errs


CATALOG = {k["name"]: k for k in json.loads((HERE.parent / "skills/catalog.json").read_text())["skills"]}
ARG = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')


def skill_errs(lines) -> list[str]:
    """skill lines must match skills/catalog.json: known name, known args, required args, enum values"""
    errs = []
    for ln in lines:
        if not ln.startswith("skill "):
            continue
        name = ln.split()[1]
        sk = CATALOG.get(name)
        if not sk:
            errs.append(f"unknown skill {name}")
            continue
        got = {k: v.strip('"') for k, v in ARG.findall(ln[len("skill " + name):])}
        spec = {a["name"]: a for a in sk.get("args", [])}
        errs += [f"{name}: unknown arg {k}" for k in got if k not in spec]
        errs += [f"{name}: missing {k}" for k, a in spec.items() if a.get("required") and k not in got]
        errs += [f"{name}: {k}={got[k]} not in enum" for k, a in spec.items()
                 if k in got and a.get("values") and got[k] not in a["values"]]
    return errs


def refs_used(lines) -> set[int]:
    out = set()
    for ln in lines:
        if ln.startswith(("press", "type", "scroll", "expect")):
            out |= {int(x) for x in re.findall(r"#(\d+)\b", ln.split('"')[0] if ln.startswith("type") else ln)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(HERE / "planner_scenarios_v2.jsonl"))
    ap.add_argument("--json")
    a = ap.parse_args()
    rows = [json.loads(x) for x in Path(a.file).read_text().splitlines() if x.strip()]
    problems = collections.defaultdict(list)
    stats = collections.Counter()
    ids = collections.Counter(r["id"] for r in rows)
    for i, n in ids.items():
        if n > 1:
            problems[i].append("duplicate id")
    v1 = {(s["goal"].lower().strip(), s["observation"]) for s in po.TUNE + po.HOLDOUT + po.HOLDOUT2}
    v1_goals = {s["goal"].lower().strip() for s in po.TUNE + po.HOLDOUT + po.HOLDOUT2}
    goals_by_split = collections.defaultdict(set)
    for r in rows:
        p = problems[r["id"]]
        for f in FIELDS + ["category", "split", "gold", "wrong"]:
            if f not in r:
                p.append(f"missing field {f}")
        if p:
            continue
        for pat in r["accept_first"] + r["reject_any"] + r["confirm_before"]:
            try:
                re.compile(pat)
            except re.error as e:
                p.append(f"bad regex {pat!r}: {e}")
        p += [f"obs: {e}" for e in lint_obs(r["observation"])]
        obs_refs = {int(x) for x in re.findall(r"^#(\d+) ", r["observation"], re.M)}
        for ln in r["last_batch"] or []:
            if "stale_ref" in ln and (bad := {int(x) for x in re.findall(r"#(\d+)", ln.split(" -> ")[0])} & obs_refs):
                p.append(f"stale_ref {sorted(bad)} is still in the observation")
        if not r["gold"]:
            p.append("no gold reply")
        for g in r["gold"]:
            res = po.grade(r, g)
            stats["gold"] += 1
            if not (res["pass"] and res["strict_pass"]):
                p.append(f"gold fails: {g} -> {res}")
            p += [f"gold: {e}" for e in skill_errs(g)]
            if bad := refs_used(g) - obs_refs:
                p.append(f"gold uses refs not in observation: {sorted(bad)}")
        if not r["wrong"]:
            p.append("no wrong reply")
        for w in r["wrong"]:
            stats["wrong"] += 1
            if po.grade(r, w)["pass"]:
                p.append(f"wrong reply passes: {w}")
        generic = [[], ["Let me look at the screen first."]]
        if not any(g and g[0].startswith("wait") for g in r["gold"]):
            generic.append(["wait 300"])
        if not any(g and g[0].startswith("done") for g in r["gold"]):
            generic.append(['done "Done"'])
        for w in generic:
            stats["generic"] += 1
            if po.grade(r, w)["pass"]:
                p.append(f"generic reply passes: {w}")
        key = (r["goal"].lower().strip(), r["observation"])
        if key in v1:
            p.append("goal+observation duplicates a v1 scenario")
        if r["goal"].lower().strip() in v1_goals:
            stats["goal_shared_with_v1"] += 1
        goals_by_split[r["split"]].add(r["goal"].lower().strip())
    shared = goals_by_split["v2-tune"] & goals_by_split["v2-holdout"]
    for r in rows:
        if r["goal"].lower().strip() in shared:
            problems[r["id"]].append("goal shared between v2-tune and v2-holdout")
    cats = collections.defaultdict(collections.Counter)
    for r in rows:
        cats[r["category"]][r["split"]] += 1
    split_errs = [f"{c}: {dict(n)}" for c, n in cats.items() if n["v2-tune"] != n["v2-holdout"]]
    bad = {k: v for k, v in problems.items() if v}
    for k, v in bad.items():
        for e in v:
            print(f"FAIL {k}: {e}")
    for e in split_errs:
        print(f"FAIL split: {e}")
    summary = {"scenarios": len(rows), "failing_scenarios": len(bad), "split_errors": split_errs,
               "gold_replies": stats["gold"], "wrong_replies": stats["wrong"], "generic_negatives": stats["generic"],
               "goals_also_in_v1": stats["goal_shared_with_v1"],
               "by_category": {c: dict(n) for c, n in sorted(cats.items())},
               "by_app": dict(collections.Counter(r["observation"].split(" | ")[0][5:] for r in rows).most_common())}
    print(json.dumps(summary, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps({"summary": summary, "problems": bad}, indent=1))
    sys.exit(1 if bad or split_errs else 0)


if __name__ == "__main__":
    main()
