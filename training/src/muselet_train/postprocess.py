"""Validate generated items, attach sampled contexts, build ROUTE items and ARGS targets (SPEC 1.3).

  python -m muselet_train.postprocess --run sample2
Reads /data/gen/<run>/gen_items.jsonl (+ raw_g3_retry.jsonl if present), writes route.jsonl, args.jsonl,
rejects.jsonl and stats.json in the same directory.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
from dataclasses import asdict

from muselet_train.catalog import option_names, skill_by_name, skills
from muselet_train.contexts import sample_context
from muselet_train.gen import DATA, _load, _parse_json

UNITS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
         "fifteen sixteen seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words_to_int(s: str) -> int | None:
    s = s.lower().replace("-", " ").replace("percent", "").replace("%", "").strip()
    if re.fullmatch(r"[+-]?\d+", s):
        return int(s)
    toks, n = s.split(), None
    for t in toks:
        if t in UNITS:
            n = (n or 0) + UNITS.index(t)
        elif t in TENS:
            n = (n or 0) + 10 * TENS.index(t)
        elif t == "hundred":
            n = (n or 1) * 100
        elif t in ("and",):
            continue
        else:
            return None
    return n


def level_value(v, text: str) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).lower().strip()
    if s in ("max", "maximum", "full", "all the way up", "100%"):
        return 100
    if s == "half":
        return 50
    return words_to_int(s)


def change_volume_delta(v, text: str) -> int | None:
    t = text.lower()
    down = bool(re.search(r"\b(down|quiet|lower|decrease|reduce|soft|less|drop|cut)", t))
    n = level_value(v, text)
    spoken = {words_to_int(w) for w in re.findall(r"[a-z]+(?:[ -][a-z]+)?|\d+", t)}
    if n is not None and n != 0 and abs(n) in spoken:
        return -abs(n) if down else abs(n)
    sign = -1 if down else 1
    if re.search(r"\b(a lot|way|much|loads|tons|significantly|quite a bit|really|substantially|a ton)\b", t):
        return 25 * sign
    return 10 * sign


def fmt_args(args: dict) -> str:
    out = []
    for k, v in args.items():
        if isinstance(v, bool):
            v = "true" if v else "false"
        v = str(v)
        out.append(f'{k}="{v}"' if re.search(r"\s", v) else f"{k}={v}")
    return " ".join(out)


def norm_args(skill: str, raw: dict, text: str) -> tuple[dict | None, str]:
    spec = {a["name"]: a for a in skill_by_name(skill).args}
    if not isinstance(raw, dict):
        return None, "args_not_dict"
    if set(raw) - set(spec):
        return None, f"unknown_arg:{sorted(set(raw) - set(spec))}"
    out = {}
    for name, a in spec.items():
        if name not in raw or raw[name] in (None, ""):
            if a["required"]:
                return None, f"missing_required:{name}"
            continue
        v = raw[name]
        t = a["type"]
        if t == "int":
            v = change_volume_delta(v, text) if skill == "change_volume" else level_value(v, text)
            if v is None or not a.get("min", -1e9) <= v <= a.get("max", 1e9):
                return None, f"bad_int:{name}={raw[name]!r}"
        elif t == "bool":
            if isinstance(v, str):
                v = {"true": True, "on": True, "yes": True, "false": False, "off": False, "no": False}.get(v.lower())
            if not isinstance(v, bool):
                return None, f"bad_bool:{name}"
        elif t == "enum":
            if str(v).lower() not in a["values"]:
                return None, f"bad_enum:{name}={v!r}"
            v = str(v).lower()
        else:
            v = str(v).strip()
        out[name] = v
    return out, "ok"


def words(s: str) -> int:
    return len(s.split())


def build(run: str, seed: int = 0) -> None:
    rng = random.Random(seed)
    d = DATA / run
    gen = _load(run, "gen_items.jsonl")
    for x in _load(run, "raw_g3_retry.jsonl"):
        j = _parse_json(x["text"])
        if j and x["stop"] in ("stop", "end_turn"):
            gen += [{"src": x["id"], "k": k, "kind": "g3", "label": None, "style": None,
                     "model": x["model"], "raw": it} for k, it in enumerate(j.get("items", []))]
    names = set(option_names())
    skill_names = {s.name for s in skills()}
    route, args, rej = [], [], []
    why = collections.Counter()

    def reject(x, reason):
        why[(x["label"] or "g3", reason.split(":")[0])] += 1
        rej.append({**x, "reason": reason})

    def add(text, label, ctx, src, extra=None):
        route.append({"utterance": text, "label": label, "context": asdict(ctx), "src": src,
                      **(extra or {})})

    for x in gen:
        r, kind = x["raw"], x["kind"]
        text = (r.get("text") or "").strip() if isinstance(r, dict) else ""
        if not text:
            reject(x, "no_text")
            continue
        if kind == "g1":
            if not 2 <= words(text) <= 20:
                reject(x, "length")
                continue
            a, status = norm_args(x["label"], r.get("args") or {}, text)
            if a is None:
                reject(x, status)
                continue
            ctx = sample_context(rng)
            add(text, x["label"], ctx, x["src"], {"args": a})
            args.append({"skill": x["label"], "utterance": text, "context": asdict(ctx),
                         "target": fmt_args(a), "src": x["src"]})
        elif kind == "g2":
            if not 2 <= words(text) <= 30:
                reject(x, "length")
                continue
            ns = str(r.get("nearest_skill") or "none").strip()
            if x["label"] == "ASK" and ns not in skill_names:
                reject(x, f"ask_nearest_skill_invalid:{ns}")
                continue
            ctx = sample_context(rng)
            add(text, x["label"], ctx, x["src"], {"nearest_skill": ns, "why": r.get("why")})
            if x["label"] == "ASK":
                req = [a["name"] for a in skill_by_name(ns).args if a["required"]]
                if len(req) == 1:  # unambiguous missing arg; multi-arg skills need per-item resolution
                    args.append({"skill": ns, "utterance": text, "context": asdict(ctx),
                                 "target": f"missing={req[0]}", "src": x["src"]})
        else:
            pair = []
            for side in ("a", "b"):
                s = r.get(side) or {}
                lab = str(s.get("label", "")).split(":")[0].split("(")[0].strip()
                if lab not in names:
                    break
                pair.append((s, lab))
            if len(pair) != 2 or pair[0][1] == pair[1][1] or not 1 <= words(text) <= 20:
                reject({**x, "label": "g3"}, "g3_invalid_pair")
                continue
            for s, lab in pair:
                ctx = sample_context(rng, app=str(s.get("app", "")).strip() or None,
                                     selection=str(s.get("selection", "no")).lower() == "yes")
                add(text, lab, ctx, x["src"], {"g3": True})
    for name, rows in (("route", route), ("args", args), ("rejects", rej)):
        (d / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    stats = {"route_by_label": collections.Counter(r["label"] for r in route),
             "args": len(args), "rejects": {f"{k[0]}|{k[1]}": v for k, v in why.items()}}
    (d / "stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    build(ap.parse_args().run)
