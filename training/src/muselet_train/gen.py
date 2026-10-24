"""Synthetic generation via Anthropic Message Batches (~70%) and OpenAI Batch API (~30%).

  python -m muselet_train.gen build  --run sample2 --fraction 0.02
  python -m muselet_train.gen submit --run sample2
  python -m muselet_train.gen poll   --run sample2
  python -m muselet_train.gen collect --run sample2
Artifacts live in /data/gen/<run>/ (requests, batch ids, raw results, parsed items, usage).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import time
from pathlib import Path

from muselet_train.catalog import Option, arg_signature, skills
from muselet_train.prompts import (
    CATEGORIES, G1, G2, G2_NEAR_MISS, G2_NEAR_MISS_ASK, G3, MAC_APPS, MULTI_STEP_FOCUS, STYLES,
)

GEN_ANTHROPIC = "claude-haiku-5-5"
GEN_OPENAI = "gpt-5.4-nano"
DATA = Path("/data/gen")
G1_N, G1_TARGET = 40, 800
G2_N = 40
G3_N, G3_TARGET = 30, 1500
MAX_TOKENS = 8000


def skill_list() -> str:
    return "\n".join(f"- {s.name}: {s.description}" for s in skills())


def enum_values(opt: Option) -> str:
    e = [f"{a['name']}: {'|'.join(a['values'])}" for a in opt.args if a["type"] == "enum"]
    return "; ".join(e) if e else "n/a"


def g1_prompt(opt: Option, style: str, n: int = G1_N) -> str:
    return G1.format(
        name=opt.name, description=opt.description,
        arg_signature=arg_signature(opt) or "none",
        examples="; ".join(f'"{e}"' for e in opt.examples),
        n=n, app_list=", ".join(MAC_APPS), enum_values=enum_values(opt), style=style,
    )


def g2_prompt(cat: str, style: str, n: int = G2_N) -> str:
    c = CATEGORIES[cat]
    near = G2_NEAR_MISS_ASK if cat == "ASK" else G2_NEAR_MISS.format(category_name=cat)
    return G2.format(skill_list_with_descriptions=skill_list(), n=n, category_name=cat, near_miss=near,
                     category_definition=c["definition"], category_examples=c["examples"],
                     style=style)


def g3_prompt(n: int = G3_N) -> str:
    return G3.format(n=n, skill_list_with_descriptions=skill_list())


def build(run: str, fraction: float, seed: int = 0, skip: tuple[str, ...] = ()) -> list[dict]:
    rng = random.Random(seed)
    reqs: list[dict] = []
    for opt in skills():
        calls = max(1, math.ceil(G1_TARGET * fraction / G1_N))
        for j in range(calls):
            style = STYLES[(len(reqs) + j) % len(STYLES)]
            reqs.append({"id": f"g1-{opt.name}-{j}", "kind": "g1", "label": opt.name,
                         "style": style, "prompt": g1_prompt(opt, style)})
    for cat, c in CATEGORIES.items():
        calls = max(1, math.ceil(c["target"] * fraction / G2_N))
        for j in range(calls):
            style = STYLES[j % len(STYLES)]
            if cat == "MULTI_STEP":
                focus = _quota_pick(j, calls)
                style = f"{style}; focus: {focus}"
            reqs.append({"id": f"g2-{cat}-{j}", "kind": "g2", "label": cat, "style": style,
                         "prompt": g2_prompt(cat, style)})
    calls = max(1, math.ceil(G3_TARGET * fraction / G3_N))
    for j in range(calls):
        reqs.append({"id": f"g3-{j}", "kind": "g3", "label": None, "style": None,
                     "prompt": g3_prompt()})
    reqs = [r for r in reqs if r["label"] not in skip]
    # ~30% of calls to OpenAI (cross-family diversity), deterministic
    order = list(range(len(reqs)))
    rng.shuffle(order)
    n_oa = round(0.3 * len(reqs))
    for k, i in enumerate(order):
        reqs[i]["provider"] = "openai" if k < n_oa else "anthropic"
        reqs[i]["model"] = GEN_OPENAI if k < n_oa else GEN_ANTHROPIC
    # claude-haiku-5-5 loops on G3 until max_tokens (2/2 attempts in the 2% sample); gpt-5.4-nano is reliable
    for r in reqs:
        if r["kind"] == "g3":
            r["provider"], r["model"] = "openai", GEN_OPENAI
    d = DATA / run
    d.mkdir(parents=True, exist_ok=True)
    (d / "requests.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reqs))
    print(f"{len(reqs)} requests ({n_oa} openai) -> {d}/requests.jsonl")
    return reqs


V2_SKILLS = ("bluetooth", "lock_screen", "empty_trash", "finance_review", "advisor_prep")
V2_G2_CALLS = 2  # per (category, new skill)


def build_v2(run: str, seed: int = 0) -> list[dict]:
    """Catalog v2 additions: G1 for the 5 new skills, plus G2 near-misses aimed at each of them."""
    rng = random.Random(seed)
    reqs: list[dict] = []
    for opt in skills():
        if opt.name not in V2_SKILLS:
            continue
        for j in range(math.ceil(G1_TARGET / G1_N)):
            style = STYLES[j % len(STYLES)]
            reqs.append({"id": f"g1-{opt.name}-{j}", "kind": "g1", "label": opt.name,
                         "style": style, "prompt": g1_prompt(opt, style)})
    for cat in CATEGORIES:
        for name in V2_SKILLS:
            for j in range(V2_G2_CALLS):
                style = f"{STYLES[j % len(STYLES)]}; near-misses should resemble the {name} skill"
                reqs.append({"id": f"g2-{cat}-{name}-{j}", "kind": "g2", "label": cat, "style": style,
                             "prompt": g2_prompt(cat, style)})
    for r in reqs:
        oa = rng.random() < 0.3
        r["provider"], r["model"] = ("openai", GEN_OPENAI) if oa else ("anthropic", GEN_ANTHROPIC)
    d = DATA / run
    d.mkdir(parents=True, exist_ok=True)
    (d / "requests.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reqs))
    print(f"{len(reqs)} requests -> {d}/requests.jsonl")
    return reqs


# iteration 2 (lead-approved): targeted top-ups for the labels the main run got wrong; notes go in the {style}
# slot so the prompt text stays exact.
IT2_G1 = [
    ("dark_mode", 10, "indirect needs about glare, night-time, eye strain or wanting everything darker or lighter, "
                      "where switching the system appearance (dark/light mode) is the fix"),
    ("set_brightness", 5, "indirect needs about the screen itself being too bright or too dim"),
    ("sleep_display", 4, "the user wants the screen turned off right now, not dimmed and not dark mode"),
    ("open_app", 10, "many verbs: fire up, pull up, bring up, get me into, launch, start, boot up, open up"),
    ("find_file", 8, "the user lost or can't locate a file and wants it found, without asking to open it"),
    ("open_file", 4, "the user names a specific file and wants it opened"),
    ("create_reminder", 6, "'don't let me forget' / 'remind me' with a time; personal to-dos, not meetings"),
    ("create_event", 4, "meetings, appointments and calendar entries with a time, not to-do reminders"),
    ("media_control", 8, "generic playback commands (play, pause, toggle, resume, skip) for music or video in any app"),
    ("premiere_command", 3, "playback commands for the Premiere Pro timeline (play, stop, play from playhead)"),
]
IT2_POLITE = "polite full sentence that names every required value explicitly"
IT2_ASK_CALLS = 20
IT2_ASK_STYLE = ("very short (2-4 words): name one skill's action but give none of the details it needs, "
                 "or point at something unclear like 'it', 'him', 'the one from earlier'")


def build_it2(run: str, seed: int = 0) -> list[dict]:
    """Iteration-2 top-ups: indirect/contrast G1 for weak labels, polite-complete G1 for every skill with a
    required argument (hard negatives for ASK), and terse ASK G2 (validated later by ask_rule)."""
    rng = random.Random(seed)
    by = {o.name: o for o in skills()}
    reqs: list[dict] = []
    for name, calls, note in IT2_G1:
        for j in range(calls):
            reqs.append({"id": f"g1-{name}-it2-{j}", "kind": "g1", "label": name, "style": f"{STYLES[j % len(STYLES)]}; {note}",
                         "prompt": g1_prompt(by[name], f"{STYLES[j % len(STYLES)]}; {note}")})
    for o in skills():
        if any(a.get("required") for a in o.args):
            reqs.append({"id": f"g1-{o.name}-it2polite", "kind": "g1", "label": o.name, "style": IT2_POLITE,
                         "prompt": g1_prompt(o, IT2_POLITE)})
    for j in range(IT2_ASK_CALLS):
        reqs.append({"id": f"g2-ASK-it2-{j}", "kind": "g2", "label": "ASK", "style": IT2_ASK_STYLE,
                     "prompt": g2_prompt("ASK", IT2_ASK_STYLE)})
    for r in reqs:
        oa = rng.random() < 0.3
        r["provider"], r["model"] = ("openai", GEN_OPENAI) if oa else ("anthropic", GEN_ANTHROPIC)
    d = DATA / run
    d.mkdir(parents=True, exist_ok=True)
    (d / "requests.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reqs))
    print(f"{len(reqs)} requests -> {d}/requests.jsonl")
    return reqs


def _quota_pick(j: int, calls: int) -> str:
    """Deterministic largest-remainder allocation of MULTI_STEP focus domains over calls."""
    alloc: list[str] = []
    for name, share in MULTI_STEP_FOCUS:
        alloc += [name] * max(1, round(share * calls))
    return alloc[j % len(alloc)]


def _load(run: str, name: str) -> list[dict]:
    p = DATA / run / name
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def submit(run: str) -> None:
    import anthropic
    import openai

    d = DATA / run
    reqs = _load(run, "requests.jsonl")
    batches = {}
    an = [r for r in reqs if r["provider"] == "anthropic"]
    oa = [r for r in reqs if r["provider"] == "openai"]
    if an:
        b = anthropic.Anthropic().messages.batches.create(requests=[
            {"custom_id": r["id"], "params": {
                "model": r["model"], "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": r["prompt"]}]}}
            for r in an])
        batches["anthropic"] = b.id
    if oa:
        lines = [json.dumps({"custom_id": r["id"], "method": "POST", "url": "/v1/chat/completions",
                             "body": {"model": r["model"], "max_completion_tokens": MAX_TOKENS,
                                      "reasoning_effort": "low",
                                      "response_format": {"type": "json_object"},
                                      "messages": [{"role": "user", "content": r["prompt"]}]}})
                 for r in oa]
        f = d / "openai_input.jsonl"
        f.write_text("\n".join(lines) + "\n")
        client = openai.OpenAI()
        up = client.files.create(file=f.open("rb"), purpose="batch")
        b = client.batches.create(input_file_id=up.id, endpoint="/v1/chat/completions",
                                  completion_window="24h")
        batches["openai"] = b.id
    (d / "batches.json").write_text(json.dumps(batches, indent=1))
    print("submitted", batches)


def poll(run: str, wait: bool = False, interval: int = 30) -> bool:
    import anthropic
    import openai

    batches = json.loads((DATA / run / "batches.json").read_text())
    while True:
        done = True
        if "anthropic" in batches:
            b = anthropic.Anthropic().messages.batches.retrieve(batches["anthropic"])
            print("anthropic", b.processing_status, b.request_counts)
            done &= b.processing_status == "ended"
        if "openai" in batches:
            b = openai.OpenAI().batches.retrieve(batches["openai"])
            print("openai", b.status, b.request_counts)
            done &= b.status in ("completed", "failed", "expired", "cancelled")
        if done or not wait:
            return done
        time.sleep(interval)


def _parse_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def collect(run: str) -> None:
    import anthropic
    import openai

    d = DATA / run
    batches = json.loads((d / "batches.json").read_text())
    reqs = {r["id"]: r for r in _load(run, "requests.jsonl")}
    raw = []
    usage = {}
    if "anthropic" in batches:
        for res in anthropic.Anthropic().messages.batches.results(batches["anthropic"]):
            r = reqs[res.custom_id]
            if res.result.type != "succeeded":
                raw.append({"id": res.custom_id, "error": res.result.type})
                continue
            m = res.result.message
            text = "".join(c.text for c in m.content if c.type == "text")
            u = usage.setdefault(r["model"], {"calls": 0, "input": 0, "output": 0})
            u["calls"] += 1
            u["input"] += m.usage.input_tokens
            u["output"] += m.usage.output_tokens
            raw.append({"id": res.custom_id, "model": m.model, "text": text,
                        "stop": m.stop_reason})
    if "openai" in batches:
        client = openai.OpenAI()
        b = client.batches.retrieve(batches["openai"])
        if b.output_file_id:
            for line in client.files.content(b.output_file_id).text.splitlines():
                o = json.loads(line)
                r = reqs[o["custom_id"]]
                body = (o.get("response") or {}).get("body") or {}
                if not body.get("choices"):
                    raw.append({"id": o["custom_id"], "error": str(o.get("error"))[:300]})
                    continue
                u = usage.setdefault(r["model"], {"calls": 0, "input": 0, "output": 0})
                u["calls"] += 1
                u["input"] += body["usage"]["prompt_tokens"]
                u["output"] += body["usage"]["completion_tokens"]
                raw.append({"id": o["custom_id"], "model": body.get("model"),
                            "text": body["choices"][0]["message"]["content"],
                            "stop": body["choices"][0].get("finish_reason")})
        if b.error_file_id:
            for line in client.files.content(b.error_file_id).text.splitlines():
                o = json.loads(line)
                raw.append({"id": o["custom_id"], "error": str(o.get("error") or o)[:300]})
    (d / "raw.jsonl").write_text("".join(json.dumps(x) + "\n" for x in raw))
    (d / "usage.json").write_text(json.dumps(usage, indent=1))
    parse(run)


def _ok(x: dict) -> bool:
    j = _parse_json(x.get("text") or "") if "error" not in x else None
    return bool(j) and isinstance(j.get("items"), list)


def _call(r: dict, tries: int = 8) -> tuple[dict, dict]:
    import anthropic
    import openai

    for k in range(tries):
        try:
            if r["provider"] == "anthropic":
                m = anthropic.Anthropic(max_retries=0).messages.create(
                    model=r["model"], max_tokens=MAX_TOKENS,
                    messages=[{"role": "user", "content": r["prompt"]}])
                return ({"id": r["id"], "model": m.model, "stop": m.stop_reason,
                         "text": "".join(c.text for c in m.content if c.type == "text")},
                        {"input": m.usage.input_tokens, "output": m.usage.output_tokens})
            o = openai.OpenAI(max_retries=0).chat.completions.create(
                model=r["model"], max_completion_tokens=MAX_TOKENS, reasoning_effort="low",
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": r["prompt"]}])
            return ({"id": r["id"], "model": o.model, "stop": o.choices[0].finish_reason,
                     "text": o.choices[0].message.content},
                    {"input": o.usage.prompt_tokens, "output": o.usage.completion_tokens})
        except (anthropic.RateLimitError, openai.RateLimitError, anthropic.InternalServerError,
                anthropic.APIConnectionError, openai.APIConnectionError, openai.InternalServerError):
            time.sleep(min(60, 2 ** k + random.random()))
    return {"id": r["id"], "error": "retries_exhausted"}, {"input": 0, "output": 0}


def sync(run: str, concurrency: int = 16, attempts: int = 2) -> None:
    """Synchronous calls (no Batch API) for every request without a valid JSON result."""
    import concurrent.futures as cf

    d = DATA / run
    reqs = _load(run, "requests.jsonl")
    raw = {x["id"]: x for x in _load(run, "raw.jsonl")} if (d / "raw.jsonl").exists() else {}
    up = d / "usage_sync.json"
    usage = json.loads(up.read_text()) if up.exists() else {}
    for _ in range(attempts):
        todo = [r for r in reqs if not _ok(raw.get(r["id"], {}))]
        print("sync todo", len(todo), flush=True)
        if not todo:
            break
        with cf.ThreadPoolExecutor(concurrency) as ex:
            for n, (x, u) in enumerate(ex.map(_call, todo), 1):
                raw[x["id"]] = x
                m = next(r["model"] for r in todo if r["id"] == x["id"])
                t = usage.setdefault(m, {"calls": 0, "input": 0, "output": 0})
                t["calls"] += 1
                t["input"] += u["input"]
                t["output"] += u["output"]
                if n % 50 == 0:
                    print(n, "/", len(todo), flush=True)
                    (d / "raw.jsonl").write_text("".join(json.dumps(v) + "\n" for v in raw.values()))
                    up.write_text(json.dumps(usage, indent=1))
        (d / "raw.jsonl").write_text("".join(json.dumps(v) + "\n" for v in raw.values()))
        up.write_text(json.dumps(usage, indent=1))
    parse(run)


def parse(run: str) -> None:
    d = DATA / run
    reqs = {r["id"]: r for r in _load(run, "requests.jsonl")}
    raw = _load(run, "raw.jsonl")
    items = []
    stats = {"calls": len(raw), "errors": 0, "bad_json": 0}
    for x in raw:
        if "error" in x:
            stats["errors"] += 1
            continue
        j = _parse_json(x["text"])
        if not j or not isinstance(j.get("items"), list):
            stats["bad_json"] += 1
            continue
        r = reqs[x["id"]]
        for k, it in enumerate(j["items"]):
            if isinstance(it, dict):
                items.append({"src": x["id"], "k": k, "kind": r["kind"], "label": r["label"],
                              "style": r["style"], "model": x["model"], "raw": it})
    (d / "gen_items.jsonl").write_text("".join(json.dumps(x) + "\n" for x in items))
    print(json.dumps({"stats": stats, "items": len(items)}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "build_v2", "build_it2", "submit", "poll", "collect", "sync"])
    ap.add_argument("--run", required=True)
    ap.add_argument("--fraction", type=float, default=1.0)
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--skip", nargs="*", default=[])
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.run, a.fraction, skip=tuple(a.skip))
    elif a.cmd == "build_v2":
        build_v2(a.run)
    elif a.cmd == "build_it2":
        build_it2(a.run)
    elif a.cmd == "sync":
        sync(a.run)
    elif a.cmd == "submit":
        submit(a.run)
    elif a.cmd == "poll":
        poll(a.run, a.wait)
    else:
        collect(a.run)


if __name__ == "__main__":
    main()
