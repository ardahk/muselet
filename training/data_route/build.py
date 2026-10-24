"""Steps 1c-4: apply the audit rules to the it2b pool, add the accepted generated items, run the evalcheck gate and
export it2b-format datums (catalog v3 renderer). Every change is logged to $DATA/build/changes.jsonl.

Rules
  R1 context  web_search/open_url rows with online=false -> online=true (the gold needs the web).
  R2 audited  the 1,500 audited rows take the adjudicated label (DROP -> drop); their ARGS take the adjudicated
              fix/drop.
  R3 re-judge rows of the high-noise labels (fix.py) take the adjudicated label when a judge disagreed; unresolved
              -> drop.
  R4 ground   ARGS rows whose values are not in the utterance (ground.py) are dropped (route row kept).
  R5 volume   change_volume delta: one spoken number -> |delta| = that number; "a bit/a little/slightly" -> 10,
              "a lot" -> 25 (documented coercions); the sign is kept.
  R6 relabel  ARGS rows whose route label changed are dropped (they belong to the old skill).
  R7 folder  open_folder path: the/my and a trailing "folder" dropped, well-known folders capitalized.
  G  gen      generated items are kept only if both route judges pick the intended label and both ARGS judges
              accept the target.
  D  gate     any route or ARGS row whose utterance or rendered (ASR-noised) text overlaps an eval item under
              evalcheck rules is dropped; the final gate must report 0.

  MUSELET_CATALOG=.../catalog_v3.json python training/data_route/build.py [--upload]
"""

from __future__ import annotations

import collections
import gzip
import hashlib
import json
import re
import shlex
import subprocess
import sys
import zlib
from pathlib import Path

from audit import JUDGES, _rl, final_args, final_route
from common import DATA, jdump, jload, load_it2b
from gen import folder_path
from ground import grounded

B = DATA / "build"
OUT = DATA / "export" / "it3cand"
REPO_ID = "jonsnov/muselet-route-datums-it3cand"
SPECIALS = {"MULTI_STEP", "ASK", "REFUSE", "ANSWER"}
log: list[dict] = []


def change(rule, kind, utt, **kw):
    log.append({"rule": rule, "kind": kind, "utterance": utt, **kw})


def parse_target(t: str) -> dict | None:
    try:
        return dict(p.split("=", 1) for p in shlex.split(t))
    except ValueError:
        return None


def adj_fixed(skill: str, fixed: str, utt: str) -> str | None:
    from muselet_train.catalog import skill_by_name
    from muselet_train.postprocess import fmt_args, norm_args
    fixed = (fixed or "").strip()
    if re.fullmatch(r"missing=\w+", fixed):
        return fixed
    kv = parse_target(fixed)
    if not kv:
        return None
    a, err = norm_args(skill, kv, utt)
    if a is None or grounded(skill, a, utt, {x["name"]: x for x in skill_by_name(skill).args}):
        return None
    return fmt_args(a)


def volume_fix(utt: str, target: str) -> str | None:
    from muselet_train.asr import W2D
    m = re.fullmatch(r"delta=(-?\d+)", target)
    if not m:
        return None
    d = int(m.group(1))
    sign = -1 if d < 0 else 1
    toks = re.findall(r"[a-z]+|\d+", utt.lower())
    nums = [int(t) for t in toks if t.isdigit()] + [W2D[t] for t in toks if t in W2D and t not in ("one", "zero")]
    tens = re.findall(r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[\s-](one|two|three|four|five|six|seven|eight|nine)\b", utt.lower())
    if tens:
        return None  # compound spoken numbers: leave to the judges
    if len(set(nums)) == 1:
        n = nums[0]
        return None if n == abs(d) or not 1 <= n <= 100 else f"delta={sign * n}"
    if not nums and not re.search(r"\blot\b|\bmuch\b", utt.lower()) and \
            re.search(r"\ba (bit|little|touch|tad)\b|\bslightly\b", utt.lower()) and abs(d) != 10:
        return f"delta={sign * 10}"
    return None


def route_pool(route):
    audit = {x["idx"]: x for x in jload(DATA / "audit" / "judged.jsonl")}
    fixj = {x["idx"]: x for x in jload(DATA / "fix" / "judged.jsonl")}
    out, label_of = [], {}
    for i, r in enumerate(route):
        r = dict(r)
        u = r["utterance"]
        if r["label"] in ("web_search", "open_url") and r["context"].get("online") is False:
            r["context"] = {**r["context"], "online": True}
            change("R1", "context_online", u, label=r["label"])
        new = r["label"]
        if i in audit:
            new = final_route(audit[i])
            rule = "R2"
        elif i in fixj:
            x = fixj[i]
            new = x["gold"] if _rl(x, JUDGES[0]) == _rl(x, JUDGES[1]) == x["gold"] else \
                (x.get("r:adj") or {}).get("label") or "UNRESOLVED"
            rule = "R3"
        if new != r["label"]:
            if new in ("DROP", "UNRESOLVED") or new is None:
                change(rule, "route_drop", u, label=r["label"], verdict=new)
                label_of[u] = None
                continue
            change(rule, "route_relabel", u, label=r["label"], new=new)
            r["label"], r["target"] = new, {new: 1.0}
        label_of[u] = r["label"]
        out.append({k: r[k] for k in ("utterance", "context", "label", "split", "target")})
    return out, label_of


def args_pool(args, label_of, orig_of):
    from muselet_train.catalog import skill_by_name
    audit = {(x["utterance"], x["gold"]): x for x in jload(DATA / "audit" / "judged.jsonl") if x["args_target"]}
    out = []
    for a in args:
        u, s, t = a["utterance"], a["skill"], a["target"]
        if u in orig_of and s not in orig_of[u]:
            change("R6b", "args_drop_inconsistent", u, skill=s, target=t, route=sorted(orig_of[u]))
            continue
        if u in orig_of and label_of.get(u) != s:
            change("R6", "args_drop_relabel", u, skill=s, target=t, route=label_of.get(u))
            continue
        x = audit.get((u, s))
        if x and x["args_target"] == t:
            v = final_args(x)
            if v in ("drop", "unresolved"):
                change("R2", "args_drop", u, skill=s, target=t, why=(x.get("a:adj") or {}).get("why"))
                continue
            if v == "fix":
                f = adj_fixed(s, (x.get("a:adj") or {}).get("fixed"), u)
                if not f:
                    change("R2", "args_drop_badfix", u, skill=s, target=t, fixed=(x.get("a:adj") or {}).get("fixed"))
                    continue
                change("R2", "args_fix", u, skill=s, target=t, new=f)
                t = f
        if t and not t.startswith("missing="):
            kv = parse_target(t)
            spec = {y["name"]: y for y in skill_by_name(s).args}
            g = "unparsable" if kv is None or set(kv) - set(spec) else grounded(s, kv, u, spec)
            if g:
                change("R4", "args_drop_ungrounded", u, skill=s, target=t, why=g)
                continue
        if s == "open_folder" and t.startswith("path="):
            from muselet_train.postprocess import fmt_args
            f = fmt_args({"path": folder_path(parse_target(t)["path"])})
            if f != t:
                change("R7", "args_fix", u, skill=s, target=t, new=f)
                t = f
        if s == "change_volume":
            f = volume_fix(u, t)
            if f:
                change("R5", "args_fix", u, skill=s, target=t, new=f)
                t = f
        out.append({"skill": s, "utterance": u, "context": a["context"], "target": t, "split": a["split"]})
    return out


def gen_pool(seen: set):
    from muselet_train.decontam import norm
    route, args = [], []
    why = collections.Counter()
    for x in jload(DATA / "gen" / "judged.jsonl"):
        labs = [_rl(x, m) for m in JUDGES]
        if labs != [x["label"]] * 2:
            why[f"route_judges:{x['label']}->{'/'.join(map(str, labs))}"] += 1
            continue
        if x["args_target"] and not all((x.get(f"a:{m}") or {}).get("ok") is True for m in JUDGES):
            why["args_judges"] += 1
            continue
        if norm(x["utterance"]) in seen:
            why["dup_of_pool"] += 1
            continue
        seen.add(norm(x["utterance"]))
        split = "val" if zlib.crc32(x["utterance"].encode()) % 20 == 0 else "train"
        route.append({"utterance": x["utterance"], "context": x["context"], "label": x["label"], "split": split,
                      "target": {x["label"]: 1.0}, "source": f"gen:{x['group']}"})
        if x["args_target"] is not None and x["label"] not in SPECIALS:
            args.append({"skill": x["label"], "utterance": x["utterance"], "context": x["context"],
                         "target": x["args_target"], "split": split, "source": f"gen:{x['group']}"})
    return route, args, why


def gate(route, args):
    from muselet_train import datums as D
    from muselet_train.evalcheck import eval_items, overlaps
    ev = eval_items()
    memory_path = Path(__file__).resolve().parents[2] / "evals" / "memory_followups.jsonl"
    for line in memory_path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            ev.extend(("memory_followups", turn["utterance"]) for turn in row["turns"])
    texts = [r["utterance"] for r in route] + [D.noisy(r["utterance"], "r:" + r["utterance"], r["split"]) for r in route] \
        + [a["utterance"] for a in args]
    hits = overlaps(texts, ev)
    return hits, collections.Counter(e[0].split("/")[0] if not e[0].startswith("external") else e[0] for e in ev)


def main() -> None:
    from muselet_train import datums as D
    from muselet_train.catalog import CATALOG_PATH, skill_by_name
    from muselet_train.decontam import norm
    from muselet_train.route_render import STUDENT_MODEL, RouteContext, args_messages, render_route

    route0, args0 = load_it2b()
    route, label_of = route_pool(route0)
    orig_of = collections.defaultdict(set)
    for r in route0:
        orig_of[r["utterance"]].add(r["label"])
    args = args_pool(args0, label_of, orig_of)
    seen = {norm(r["utterance"]) for r in route}
    groute, gargs, gwhy = gen_pool(seen)
    route += groute
    args += gargs
    hits, ev_counts = gate(route, args)
    bad = {h["train"] for h in hits}
    for h in hits:
        change("D", "gate_drop", h["train"], eval=h["eval"], eval_utterance=h["eval_utterance"], overlap=h["rule"])

    def contaminated(u, split):
        return u in bad or D.noisy(u, "r:" + u, split) in bad
    gone = {r["utterance"] for r in route if contaminated(r["utterance"], r["split"])}
    route = [r for r in route if r["utterance"] not in gone]
    args = [a for a in args if a["utterance"] not in bad and a["utterance"] not in gone]
    hits2, _ = gate(route, args)
    by_rule = collections.Counter(h["rule"] for h in hits)
    by_eval = collections.Counter(h["eval"] for h in hits)
    gate_report = {"eval_items": dict(ev_counts), "before": {"total": len(hits), "by_rule": dict(by_rule),
                   "by_eval": dict(by_eval)}, "after": {"total": len(hits2),
                   "by_rule": dict(collections.Counter(h["rule"] for h in hits2))}}
    assert not hits2, hits2[:5]

    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / "route.jsonl.gz", "wt") as f:
        for r in route:
            text = D.noisy(r["utterance"], "r:" + r["utterance"], r["split"])
            rend = render_route(RouteContext(**r["context"]), text)
            ids = dict(rend.label_tokens)
            f.write(json.dumps({"utterance": r["utterance"], "rendered_utterance": text, "context": r["context"],
                                "label": r["label"], "split": r["split"], "target": r["target"],
                                "target_ids": {str(ids[k]): v for k, v in r["target"].items()},
                                "tokens": rend.tokens, "choice_pos": rend.choice_pos}, ensure_ascii=False) + "\n")
    with gzip.open(OUT / "args.jsonl.gz", "wt") as f:
        for r in args:
            msgs = args_messages(skill_by_name(r["skill"]), RouteContext(**r["context"]), r["utterance"], r["target"])
            f.write(json.dumps({"skill": r["skill"], "utterance": r["utterance"], "context": r["context"],
                                "target": r["target"], "split": r["split"], "messages": msgs}, ensure_ascii=False) + "\n")
    with gzip.open(OUT / "provenance.jsonl.gz", "wt") as f:
        for kind, rows in (("route", route), ("args", args)):
            for i, r in enumerate(rows):
                f.write(json.dumps({"file": kind, "row": i, "source": r.get("source", "it2b")}) + "\n")
    cat = CATALOG_PATH.read_bytes()
    commit = subprocess.run(["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True).stdout.strip()
    meta = {"name": "it3cand", "base": "jonsnov/muselet-route-datums-it2b@8df540b", "student": STUDENT_MODEL,
            "catalog_version": json.loads(cat)["version"], "catalog_sha256": hashlib.sha256(cat).hexdigest(),
            "route": len(route), "args": len(args),
            "route_by_split": {s: sum(r["split"] == s for r in route) for s in ("train", "val")},
            "args_by_split": {s: sum(r["split"] == s for r in args) for s in ("train", "val")},
            "route_by_label": dict(collections.Counter(r["label"] for r in route).most_common()),
            "args_by_skill": dict(collections.Counter(r["skill"] for r in args).most_common()),
            "route_by_source": dict(collections.Counter(r.get("source", "it2b") for r in route)),
            "changes": dict(collections.Counter(f'{c["rule"]}:{c["kind"]}' for c in log)),
            "gen_rejected": dict(gwhy), "gate": gate_report, "code_commit": commit}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    (OUT / "README.md").write_text(README.format(**meta))
    jdump(B / "changes.jsonl", log)
    with gzip.open(OUT / "changes.jsonl.gz", "wt") as f:
        for c in log:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(json.dumps({k: meta[k] for k in ("route", "args", "route_by_split", "changes", "gate")}, indent=1))
    if "--upload" in sys.argv:
        from huggingface_hub import HfApi
        api = HfApi()
        api.create_repo(REPO_ID, repo_type="dataset", private=True, exist_ok=True)
        info = api.upload_folder(folder_path=str(OUT), repo_id=REPO_ID, repo_type="dataset",
                                 commit_message="route datums it3cand (audited it2b + targeted generation)")
        print(json.dumps({"repo": REPO_ID, "revision": info.oid}))


README = """# muselet route datums: it3cand

Candidate route + ARGS pool for iteration 3: `jonsnov/muselet-route-datums-it2b@8df540b` after the data-route audit
rules, plus judged targeted generation. Built by `training/data_route/build.py` (see `training/data_route/REPORT.md`).

- Same row format as it2b (`route.jsonl.gz`, `args.jsonl.gz`); `provenance.jsonl.gz` maps each row to its source
  (`it2b` or `gen:<group>`).
- Renderer: `muselet_train.route_render.render_route`, catalog v{catalog_version} (sha256 `{catalog_sha256}`),
  so `target_ids` cover 43 choice ids (39 skills + MULTI_STEP/ASK/REFUSE/ANSWER). ASR noise on train route items
  (`datums.noisy`), as in it2b.
- ARGS rows: chat messages; weight only the answer tokens + `<|im_end|>` (`datums._answer_only`).
- Route {route} rows, ARGS {args} rows; evalcheck gate 0 overlaps (route_v1, live_t1, route_v2, evals/external).
"""


if __name__ == "__main__":
    main()
