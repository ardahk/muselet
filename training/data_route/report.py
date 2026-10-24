"""Write REPORT.md from the audit, fix, generation and build artifacts under DATA_ROUTE_DIR.

  MUSELET_CATALOG=.../catalog_v3.json uv run --project ~/repos/dp/training python report.py
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

from audit import JUDGES, _rl, final_args, final_route
from common import ADJUDICATOR, DATA, jload, spend

V3_SHIFT = {("compose_email", "draft_email")}


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "-"


def route_audit():
    items = jload(DATA / "audit" / "judged.jsonl")
    by = collections.defaultdict(list)
    for x in items:
        by[x["gold"]].append(x)
    agree = sum(_rl(x, JUDGES[0]) == _rl(x, JUDGES[1]) for x in items)
    gold = [sum(_rl(x, m) == x["gold"] for x in items) for m in JUDGES]
    rows, tot, shift = [], 0, 0
    for lab in sorted(by, key=lambda k: -sum(final_route(x) != k for x in by[k]) / len(by[k])):
        xs = by[lab]
        wrong = [x for x in xs if final_route(x) != lab and (lab, final_route(x)) not in V3_SHIFT]
        sh = [x for x in xs if (lab, final_route(x)) in V3_SHIFT]
        tot += len(wrong)
        shift += len(sh)
        to = collections.Counter(final_route(x) for x in wrong).most_common(3)
        ex = "; ".join(f'"{x["utterance"][:70]}" -> {final_route(x)}' for x in wrong[:2])
        rows.append(f"| {lab} | {len(xs)} | {len(wrong)} | {pct(len(wrong), len(xs))} | "
                    f"{', '.join(f'{k} {v}' for k, v in to)}{f' (+{len(sh)} v3 draft_email)' if sh else ''} | {ex} |")
    head = (f"{len(items)} items, {len(by)} labels. Judge-judge agreement {pct(agree, len(items))}; "
            f"agreement with gold: {JUDGES[0]} {pct(gold[0], len(items))}, {JUDGES[1]} {pct(gold[1], len(items))}. "
            f"Route noise **{tot}/{len(items)} = {pct(tot, len(items))}** "
            f"(+{shift} compose_email -> draft_email catalog-v3 policy shifts, applied but not counted as noise).\n\n"
            "| label | n | wrong | rate | final labels | examples |\n|---|---|---|---|---|---|\n")
    return head + "\n".join(rows)


def args_audit():
    items = [x for x in jload(DATA / "audit" / "judged.jsonl") if x["args_target"]]
    by = collections.defaultdict(collections.Counter)
    ex = collections.defaultdict(list)
    for x in items:
        v = final_args(x)
        by[x["gold"]][v] += 1
        if v in ("fix", "drop", "unresolved") and len(ex[x["gold"]]) < 1:
            fx = (x.get("a:adj") or {}).get("fixed")
            ex[x["gold"]].append(f'"{x["utterance"][:60]}" `{x["args_target"]}` -> {v}{f" `{fx}`" if fx else ""}')
    tot = collections.Counter()
    for c in by.values():
        tot.update(c)
    bad = tot["fix"] + tot["drop"] + tot["unresolved"]
    rows = [f"| {s} | {sum(c.values())} | {c['fix']} | {c['drop'] + c['unresolved']} | "
            f"{pct(sum(c.values()) - c['ok'], sum(c.values()))} | {'; '.join(ex[s])} |"
            for s, c in sorted(by.items(), key=lambda kv: -(sum(kv[1].values()) - kv[1]["ok"]) / sum(kv[1].values()))]
    return (f"{len(items)} sampled rows with an ARGS target. Wrong **{bad}/{len(items)} = {pct(bad, len(items))}** "
            f"({tot['fix']} fixable, {tot['drop'] + tot['unresolved']} drop).\n\n"
            "| skill | n | fix | drop | rate | example |\n|---|---|---|---|---|---|\n" + "\n".join(rows))


def full_pool(changes):
    fx = jload(DATA / "fix" / "judged.jsonl")
    n = collections.Counter(x["gold"] for x in fx)
    r3 = [c for c in changes if c["rule"] == "R3"]
    rel = collections.Counter(c["label"] for c in r3)
    to = collections.defaultdict(collections.Counter)
    for c in r3:
        to[c["label"]][c.get("new") or "DROP"] += 1
    rows = [f"| {lab} | {n[lab]} | {rel[lab]} | {pct(rel[lab], n[lab])} | "
            f"{', '.join(f'{k} {v}' for k, v in to[lab].most_common(4))} |" for lab in sorted(n, key=lambda k: -rel[k] / n[k])]
    return (f"{len(fx)} rows (every non-sampled row of the 10 labels), same two judges + {ADJUDICATOR} "
            f"adjudicator. {len(r3)} changed ({pct(len(r3), len(fx))}).\n\n"
            "| label | rows | changed | rate | new labels |\n|---|---|---|---|---|\n" + "\n".join(rows))


def main() -> None:
    meta = json.loads((DATA / "export" / "it3cand" / "meta.json").read_text())
    changes = jload(DATA / "build" / "changes.jsonl")
    ex = collections.defaultdict(list)
    for c in changes:
        if len(ex[c["rule"]]) < 2:
            ex[c["rule"]].append(c)
    it2 = json.loads((Path.home() / "data" / "it2b" / "meta.json").read_text())
    base = collections.Counter()
    import gzip
    with gzip.open(Path.home() / "data" / "it2b" / "route.jsonl.gz", "rt") as f:
        for line in f:
            base[json.loads(line)["label"]] += 1
    gen_rows = jload(DATA / "gen" / "checked.jsonl")
    gen = collections.Counter(r["label"] for r in gen_rows)
    labels = "\n".join(f"| {k} | {base.get(k, 0)} | {v} | {v - base.get(k, 0):+d} |"
                       for k, v in meta["route_by_label"].items())
    sk = "\n".join(f"| {k} | {v} |" for k, v in meta["args_by_skill"].items())
    sp = spend()
    total = sum(v["usd"] for v in sp.values())
    spend_rows = "\n".join(f"| {m} | {v['calls']} | {v['input']:,} | {v['output']:,} | ${v['usd']:.2f} |"
                           for m, v in sp.items())
    g = meta["gate"]
    gu = {r["utterance"] for r in gen_rows}
    src = collections.Counter(("gen" if c["utterance"] in gu else "it2b", c["overlap"]) for c in changes if c["rule"] == "D")
    out = TEMPLATE.format(
        route=meta["route"], args=meta["args"], split=meta["route_by_split"], asplit=meta["args_by_split"],
        it2_route=it2.get("route", sum(base.values())), route_audit=route_audit(), args_audit=args_audit(),
        full_pool=full_pool(changes), changes="\n".join(f"| {k} | {v} |" for k, v in meta["changes"].items()),
        ex="\n".join(f"- {r}: " + " / ".join(json.dumps(c, ensure_ascii=False) for c in cs) for r, cs in sorted(ex.items())),
        gen_checked=sum(gen.values()), gen_kept=sum(v for k, v in meta["route_by_source"].items() if k != "it2b"),
        by_source=json.dumps(meta["route_by_source"]), gen_rej=json.dumps(meta["gen_rejected"]),
        labels=labels, skills=sk, eval_items="\n".join(f"| {k} | {v} |" for k, v in g["eval_items"].items()),
        before=json.dumps(g["before"]["by_rule"]), before_eval=json.dumps(g["before"]["by_eval"]),
        before_total=g["before"]["total"],
        by_src=", ".join(f"{k[0]} {k[1]} {v}" for k, v in sorted(src.items())), after=g["after"]["total"], spend_rows=spend_rows, total=f"{total:.2f}")
    (Path(__file__).parent / "REPORT.md").write_text(out)
    print(f"REPORT.md written; spend ${total:.2f}")


TEMPLATE = """# data-route: it3 router + ARGS pool (`jonsnov/muselet-route-datums-it3cand`)

Base: `jonsnov/muselet-route-datums-it2b@8df540b` ({it2_route} route rows). Output: **{route} route rows**
({split}), **{args} ARGS rows** ({asplit}), catalog v3 (cloud A's `training/artifacts/catalog_v3.json`, 39 skills +
MULTI_STEP/ASK/REFUSE/ANSWER), same datum format as it2b (rendered with cloud A's `route_render` / `datums.noisy`);
Uploaded revision `84595279452d9c43573012f78555e25376316cf8` (private).
`provenance.jsonl.gz` maps every row to `it2b` or `gen:<group>`. Every change is one line in
`build/changes.jsonl` (uploaded as `changes.jsonl.gz`). No Tinker runs were started.

Code (`training/data_route/`): `audit.py` (sample, judges, adjudication), `fix.py` (full-pool re-judge),
`gen.py` (targeted generation + checks + judges), `ground.py` (deterministic ARGS grounding), `build.py`
(rules, gate, export, upload), `report.py` (this file). Judges: `gpt-5.6-sol` (OpenAI) and `claude-opus-5-5`
(Anthropic), blind to gold, with the v3 option descriptions, cloud A's v3 policy plus `policy.py` boundaries, and
the full context (app, focused, selection, online, last_action). Adjudicator `gpt-5.5` sees gold and both verdicts.

## 1. Audit of it2b (1,500 items, stratified by label, seed 0)

### Route labels
{route_audit}

Method note: the first pass used two policy lines that conflicted with cloud A's v3 policy (unclear channel -> ASK,
statements -> ASK) and measured 12.1%. They were corrected and the 190 affected items re-judged and re-adjudicated;
first-pass verdicts are kept in `audit/judged.jsonl` under `pass1:*`.

### ARGS
{args_audit}

### Full-pool re-judge (rule R3)
Labels with >= 13% audit noise or flagged weak by the lead.

{full_pool}

## 2. Rules applied (never silent; counts from `meta.json`)

- R1 context: `web_search` / `open_url` rows with `online=false` -> `online=true` (the label needs the web).
- R2 audited rows: final label = gold when both judges agree with it, else the adjudicator's label; DROP/unresolved
  removed. ARGS take the adjudicator's verdict (fix -> its fixed target after `norm_args`, drop -> removed).
- R3 full-pool re-judge of the 10 labels above, same decision rule as R2.
- R4 ARGS grounding (`ground.py`): drop an ARGS row whose values neither appear in the utterance nor follow by the
  documented coercions (spoken numbers, max/half, a bit/a lot deltas, on/off, enum words, canonical app names,
  site name -> domain, unit spellings). The route row stays.
- R5 `change_volume`: delta re-derived from the spoken amount and direction (incl. self-corrections).
- R6 ARGS of a route row whose label changed (R2/R3) or was dropped are removed. R6b: 562 it2b ARGS rows whose skill
  is not the route label of the same utterance (e.g. "mute it" with `set_volume` ARGS) are removed.
  ARGS-only rows (no route row in it2b) are kept and go through R4/R5/R7.
- R7 `open_folder` path: the/my and a trailing "folder" dropped, well-known folders capitalized (path=desktop ->
  Desktop).
- G generated rows kept only if both judges pick the intended label and both ARGS judges accept the target.
- D decontamination gate (below); hits are dropped from route and ARGS.

| rule:kind | rows |
|---|---|
{changes}

Examples:
{ex}

## 3. Targeted generation

Groups (`gen.py`): email (compose_email / send_message / draft_email / ASK minimal pairs across the channel
boundary), messaging (named people, with and without a body), writing + writing2 (compose_text / new_note /
type_text / draft_email), sites (bare site names -> open_url vs Mac apps vs web_search), media (media_control vs
premiere_command vs play_music), files (open_folder vs open_file vs find_file vs open_app), display
(set_brightness vs dark_mode vs change_volume / set_volume / mute / sleep_display). Writers `claude-sonnet-5-5`
and `gpt-5.6-sol`; style mix with ~40% ASR-style transcripts (lowercase, no punctuation, fillers, restarts,
self-corrections, homophones, spelled numbers); contexts vary frontmost app, focused element and selection.

Checks before judging: label in group, context consistency (premiere_command needs Premiere Pro, type_text a
focused text field), `norm_args`, `ground.py`, required/missing arguments, normalized dedup. {gen_checked} passed;
{gen_kept} kept after the judges, dedup against the pool and the gate. Second ARGS pass: the first ARGS judge prompt
did not state cloud A's v3 target conventions (send_message `missing=body`, compose_text `target=notes` default),
so items rejected only on ARGS were re-judged once with them stated (`gen.py rejudge_args`).

Rows by source: `{by_source}`

Rejected: `{gen_rej}`

## 4. Decontamination gate

cloud A's `muselet_train.evalcheck.overlaps` (normalized exact, shared 13-gram, token edit <= 1 when either side
has <= 5 tokens; `decontam.norm`, CJK characters one token each) over every route utterance, its rendered noisy
form, and every ARGS utterance, against:

| eval set | items |
|---|---|
{eval_items}

Before: {before_total} hits, by rule {before}, by eval {before_eval}. By source: {by_src} (the 6 it2b hits are token-edit-1
near-duplicates of route_v1 / HobbyLM sealed-r3 / live_t1 short items). All dropped (rule D).
**After: {after} on every rule and every set.**

## 5. Counts

| route label | it2b | it3cand | delta |
|---|---|---|---|
{labels}

| ARGS skill | rows |
|---|---|
{skills}

## 6. API spend

| model | calls | input tok | output tok | USD |
|---|---|---|---|---|
{spend_rows}

**Total ${total}** of the $80 budget (prices in `common.py`, USD per M tokens, conservative list prices).
"""

if __name__ == "__main__":
    main()
