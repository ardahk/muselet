"""Filter teacher replies into demos, chat datums and the retrieval bank.

Per state, each teacher reply is turned into planner lines exactly like the bench Runner / runtime stream
(strip, skip blank lines, a multi-line `script ... \"\"\"...\"\"\"` block is one element, BatchCutter: <= 5 actions,
stop after done/ask/confirm-style terminators) and graded with evals/planner_offline.grade (runtime + strict).
Keep a state only if BOTH teachers pass runtime and strict and neither reply clobbers text (`type #N` into a
textfield/textarea/combobox whose current value is non-empty must start with that value, unless the goal asks to
replace/clear). The kept target is the shorter passing reply (characters), ties -> anthropic.

  python3 training/planner_demos/keep.py --dir ~/data/planner_demos [--replies replies.jsonl] [--out built]
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render  # noqa: E402
import states_lib  # noqa: E402,F401  (puts evals/ on sys.path)
import planner_offline as po  # noqa: E402

PLACEHOLDERS = {"New Event", "Double-click to edit", "New Reminder", "Untitled", "New Note"}
REPLACE_WORDS = re.compile(r"\b(replace|clear|overwrite|instead of|change (it|the text) to|rewrite)\b", re.I)


def to_lines(text: str) -> list[str]:
    cutter = render.P.BatchCutter()
    lines, script, in_script = [], [], False
    for raw in (text or "").split("\n"):
        if in_script:
            script.append(raw)
            if '"""' not in raw:
                continue
            in_script, line, script = False, "\n".join(script).strip(), []
        else:
            line = raw.strip()
            if not line:
                continue
            if re.match(r"^script\b", line) and line.count('"""') % 2:
                in_script, script = True, [line]
                continue
        o = cutter.push(line)
        if o is not None:
            lines.append(o)
        if cutter.done:
            break
    if in_script and script:
        lines.append("\n".join(script).strip())
    return lines


def clobbers(state: dict, lines: list[str]) -> bool:
    if REPLACE_WORDS.search(state["goal"]):
        return False
    vals = {int(m[1]): m[2] for m in re.finditer(r'^#(\d+) (?:textfield|textarea|combobox) "(?:[^"\\]|\\.)*" value="((?:[^"\\]|\\.)*)"',
                                                   state["observation"], re.M)}
    for ln in lines:
        m = re.match(r'^type #(\d+) "((?:[^"\\]|\\.)*)"', ln)
        if m and vals.get(int(m[1])) and vals[int(m[1])] not in PLACEHOLDERS and not m[2].startswith(vals[int(m[1])]):
            label = re.search(rf'^#{m[1]} \w+ "((?:[^"\\]|\\.)*)"', state["observation"], re.M)[1]
            if re.search(r"search|address|smart search|url|to:|cc:|subject", label, re.I):
                continue          # replacing a search / address / header field is normal
            return True
    return False


def judge(state: dict, text: str | None) -> dict:
    if not text:
        return {"pass": False, "why": "empty_or_error", "lines": []}
    lines = to_lines(text)
    g = po.grade(state, lines)
    why = None
    if not g["valid"]:
        why = "invalid_dsl"
    elif not g["first_ok"]:
        why = "wrong_first_action"
    elif g["rejected"]:
        why = "rejected_line"
    elif not g["confirm_ok"]:
        why = "no_confirm"
    elif not g["strict_pass"]:
        why = "strict_fail"
    elif clobbers(state, lines):
        why = "clobbers_text"
    return {"pass": why is None, "why": why, "lines": lines, "first": g["first"]}


def bank_tokenizer():
    """the student's tokenizer (Qwen3.5-4B, as served: mlx-community/Qwen3.5-4B-4bit)"""
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer
    return Tokenizer.from_file(hf_hub_download("mlx-community/Qwen3.5-4B-4bit", "tokenizer.json"))


def first_op(lines):
    acts = [ln for ln in lines if not re.match(r"^(#|expect\b)", ln)]
    return acts[0].split()[0] if acts else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path.home() / "data" / "planner_demos")
    ap.add_argument("--replies", default="replies.jsonl")
    ap.add_argument("--out", default="built")
    a = ap.parse_args()
    states = {s["id"]: s for s in map(json.loads, (a.dir / "states.jsonl").read_text().splitlines())}
    rep = collections.defaultdict(dict)
    for r in map(json.loads, (a.dir / a.replies).read_text().splitlines()):
        if r["id"] in states and (r["teacher"] not in rep[r["id"]] or not r.get("error")):
            rep[r["id"]][r["teacher"]] = r
    stats = {"states_answered": 0, "teacher_pass": collections.Counter(), "teacher_fail_why": collections.defaultdict(collections.Counter),
             "both_pass": 0, "same_first_op_when_both_pass": 0, "same_first_line_when_both_pass": 0,
             "kept_by_family": collections.Counter(), "kept_by_category": collections.Counter(), "kept_by_app": collections.Counter(),
             "drop_why": collections.Counter(), "target_teacher": collections.Counter(), "by_family": {}}
    fam = collections.defaultdict(lambda: collections.Counter())
    kept = []
    for sid, rs in rep.items():
        if set(rs) != {"openai", "anthropic"}:
            continue
        s = states[sid]
        stats["states_answered"] += 1
        j = {t: judge(s, rs[t].get("text")) for t in ("openai", "anthropic")}
        fam[s["family"]]["n"] += 1
        for t, x in j.items():
            if x["pass"]:
                stats["teacher_pass"][t] += 1
                fam[s["family"]][f"{t}_pass"] += 1
            else:
                stats["teacher_fail_why"][t][x["why"]] += 1
        if not all(x["pass"] for x in j.values()):
            stats["drop_why"]["openai_fail" if not j["openai"]["pass"] and j["anthropic"]["pass"] else
                              "anthropic_fail" if j["openai"]["pass"] else "both_fail"] += 1
            continue
        stats["both_pass"] += 1
        stats["same_first_op_when_both_pass"] += first_op(j["openai"]["lines"]) == first_op(j["anthropic"]["lines"])
        stats["same_first_line_when_both_pass"] += j["openai"]["first"] == j["anthropic"]["first"]
        t = min(("anthropic", "openai"), key=lambda t: len("\n".join(j[t]["lines"])))
        target = "\n".join(j[t]["lines"])
        msgs = render.messages(s)
        app = s["observation"].split(" | ")[0][5:]
        kept.append({"id": sid, "family": s["family"], "category": s["category"], "source": s["source"], "app": app,
                     "messages": msgs + [{"role": "assistant", "content": target}], "completion": target,
                     "target_teacher": t, "target_model": rs[t]["model"],
                     "other_reply": "\n".join(j["anthropic" if t == "openai" else "openai"]["lines"]),
                     "state": {k: s[k] for k in ("goal", "observation", "last_batch", "script_output", "accept_first",
                                                 "reject_any", "confirm_before", "tags", "category")}})
        stats["kept_by_family"][s["family"]] += 1
        stats["kept_by_category"][s["category"]] += 1
        stats["kept_by_app"][app] += 1
        stats["target_teacher"][t] += 1
    stats["by_family"] = {f: dict(c) for f, c in sorted(fam.items())}
    tok = bank_tokenizer()
    bank, too_long = [], 0
    for k in kept:
        st_ = k["state"]
        header = st_["observation"].split("\n")[0]
        text = f'Goal: "{st_["goal"]}"\n{header}\n' + (f"Last batch: {len(st_['last_batch'])} lines\n" if st_["last_batch"] else "") + \
            f"```\n{k['completion']}\n```"
        n = len(tok.encode(text).ids)
        if n >= 400:
            too_long += 1
            continue
        bank.append({"id": k["id"], "goal": st_["goal"], "app": k["app"], "category": k["category"], "family": k["family"],
                     "header": header, "batch": k["completion"], "text": text, "tokens": n})
    stats["bank"] = len(bank)
    stats["bank_too_long"] = too_long
    stats["kept"] = len(kept)
    out = a.dir / a.out
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out / "demos.jsonl.gz", "wt") as f:
        for k in kept:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    with gzip.open(out / "bank.jsonl.gz", "wt") as f:
        for b in bank:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
    (out / "keep_stats.json").write_text(json.dumps(stats, indent=1, default=dict))
    print(json.dumps({k: v for k, v in stats.items() if k not in ("by_family",)}, indent=1, default=dict))


if __name__ == "__main__":
    main()
