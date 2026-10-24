"""Step 2: targeted generation for the it2 weak labels and the catalog-v3 intents.

Each writer call gets one contrast group (hard-negative labels written side by side), a style mix with realistic ASR
noise, and asks for context + args. Items then pass: schema/norm_args, ARGS grounding (ground.py), two blind route
judges that must both agree with the intended label, and two ARGS judges that must both accept the target.

  python training/data_route/gen.py write|check|judge
"""

from __future__ import annotations

import collections
import json
import random
import re
import sys

from common import DATA, JUDGE_ANTHROPIC, JUDGE_OPENAI, call, jdump, jload, option_block, parse_json, pmap, spend
from policy import POLICY

G = DATA / "gen"
WRITERS = ("claude-sonnet-5-5", "gpt-5.6-sol")
N_PER_CALL = 30

GROUPS = [  # (name, labels, calls, note)
    ("email", ["compose_email", "send_message", "draft_email", "ASK"], 12,
     "minimal pairs across the channel boundary: dictate exact email words to a named person (compose_email), text a "
     "named person (send_message, with or without the message said), ask the assistant to write/draft/reply to an "
     "email (draft_email: new drafts to people/teams, and replies to the email open in Mail with reply=true), and "
     "unknown recipient with no context (ASK). Use Mail/Gmail/Messages/Slack/other apps frontmost; when the words do "
     "not say email or text, the frontmost app decides"),
    ("messaging", ["send_message"], 6,
     "texts and iMessages to NAMED people or relations (first names from many cultures, mom, my sister, my boss, "
     "coach); half with the message said, half without (omit body: target missing=body)"),
    ("writing", ["compose_text", "new_note", "type_text", "draft_email"], 8,
     "writing content: the assistant writes NEW content on a topic (compose_text: lists, templates, outlines, plans, "
     "short paragraphs; target=notes when Notes is meant or nothing is focused, target=document when the user means "
     "the document/field they are in) vs the user dictating exact note words (new_note) vs exact words to type at the "
     "cursor (type_text, needs a focused text field) vs writing an email (draft_email)"),
    ("writing2", ["compose_text", "new_note", "type_text"], 6,
     "second round for compose_text, the thinnest new intent after judging: the assistant writes NEW content (packing "
     "lists, grocery lists, checklists, meeting agendas, outlines, templates, plans, short paragraphs, talking points); "
     "topic carries the user's words including the format word (\"packing list for a road trip\"); target=notes "
     "unless the user means the document/field they are in (target=document, e.g. TextEdit/Pages/Google Docs "
     "frontmost and 'here'/'in this doc'). Contrast with dictated exact note words (new_note) and exact words to "
     "type (type_text)"),
    ("sites", ["open_url", "open_app", "web_search"], 7,
     "bare site names without any URL (go to wikipedia, open gmail, pull up youtube, reddit, google docs, the new york "
     "times, netflix, amazon, github, linkedin; url = main domain such as wikipedia.org, mail.google.com, "
     "docs.google.com, nytimes.com) vs installed Mac apps with similar names (Mail, Notes, Messages, Calendar, Music, "
     "TV, News, Safari, Spotify, Slack) vs searching the web for a topic (web_search)"),
    ("media", ["media_control", "premiere_command", "play_music"], 8,
     "play/pause/resume/skip/previous of whatever is playing (media_control; Music, Spotify, a YouTube video in "
     "Chrome/Safari frontmost) vs Premiere Pro timeline commands with Premiere Pro frontmost (premiere_command: "
     "razor/cut at playhead, add marker, play or stop the timeline, undo, export with optional preset, go to start/end) "
     "vs playing a named song/artist/playlist/genre (play_music). Include play/pause said with Premiere Pro frontmost "
     "(premiere_command) and with Music frontmost (media_control)"),
    ("files", ["open_folder", "open_file", "find_file", "open_app"], 8,
     "open a known folder in Finder (open_folder: Downloads, Desktop, Documents, a project folder, a path) vs open "
     "one specific named file (open_file) vs search for files when the location is unknown (find_file: find, where "
     "is, look for, any pdfs about; kind when a type is said) vs opening an app (open_app). Many near-identical "
     "phrasings that differ only in the deciding word"),
    ("display", ["set_brightness", "dark_mode", "change_volume", "set_volume", "mute", "sleep_display"], 8,
     "screen brightness absolute and relative (set_brightness: brighter, dimmer, full brightness, 40 percent) vs "
     "light/dark appearance (dark_mode) vs volume steps (change_volume) vs absolute volume (set_volume) vs mute vs "
     "turning the display off (sleep_display). Include ambiguous-sounding words: 'too bright' (brightness), 'it's too "
     "dark in here' (brightness), 'dark theme' (dark_mode), 'turn it up' after a volume action"),
]

STYLE_MIX = """Style mix (spread evenly across the items): terse commands; polite full sentences; questions; indirect needs; very short (2-4 words); and about 40% realistic speech-recognizer transcripts: lowercase, no punctuation, fillers (um, uh, like, so), restarts ("open the, uh, open downloads"), self-corrections ("text sam, no, text alex"), homophones (to/two/too, for/four, there/their, right/write), numbers spelled out."""

WRITE = """You write TRAINING data for the intent router of a voice assistant on a Mac. The user speaks; a speech recognizer transcribes it. The router sees the transcript plus context and picks one option; for skills a second step extracts arguments.

Options (name: description [arguments]):
{options}

{policy}

Write {n} items for this contrast group: {labels}.
Focus: {note}
{style}

Context per item: "app" = frontmost app (vary widely: Finder, Safari, Google Chrome, Mail, Messages, Notes, Calendar, Music, Spotify, Premiere Pro, TextEdit, Pages, Slack, System Settings, Terminal, Numbers, Preview, Zoom, Xcode, ...), "focused" = focused element as role "label" (e.g. textarea "Message body", textfield "Search", row "Inbox", group "Timeline: Sequence 01", webarea "YouTube") or "none", "selection" = true when text is selected (vary it). Context must be consistent with the label (premiere_command needs Premiere Pro frontmost; type_text needs a focused textfield/textarea).

Arguments ("args", only for skills; {{}} for MULTI_STEP/ASK/REFUSE/ANSWER): use the exact argument names. Every value must be copied from the words (free-text values carry the user's words without the command words), or follow from them by: spoken numbers -> digits; max/full -> 100, half -> 50; change_volume delta a bit/little = +-10, a lot = +-25, plain louder/quieter = +-10; on/off -> true/false; enum values named by the words; canonical app names (premiere -> Premiere Pro); bare site name -> its main domain. Dates, times and durations exactly as spoken. Never invent subjects, bodies, recipients or paths. If a required argument was not said, set "missing" to its name and omit it.

Make every item different (vary names, topics, apps, wording, length); avoid the catalog example phrasings. Seed for variety: {seed}.

Return JSON only: {{"items": [{{"label": "...", "utterance": "...", "app": "...", "focused": "...", "selection": false, "args": {{}}, "missing": null}}]}}"""

TOPICS = ["school", "work deadlines", "family", "travel", "sports", "cooking", "a startup", "a hackathon", "music gigs",
          "the gym", "a wedding", "moving apartments", "a podcast", "freelance clients", "a book club", "taxes",
          "a dentist visit", "gardening", "a road trip", "video editing", "a birthday party", "research papers"]


def write() -> None:
    from muselet_train.catalog import skill_by_name  # noqa: F401  (catalog env check)
    opts = option_block()
    rng = random.Random(3)
    reqs = []
    for name, labels, calls, note in GROUPS:
        for j in range(calls):
            reqs.append({"id": f"{name}-{j}", "group": name, "labels": labels, "writer": WRITERS[j % 2],
                         "prompt": WRITE.format(options=opts, policy=POLICY, n=N_PER_CALL, labels=", ".join(labels),
                                                note=note, style=STYLE_MIX,
                                                seed=f"{', '.join(rng.sample(TOPICS, 3))}; call {j}")})
    done = {r["id"] for r in jload(G / "raw.jsonl")}
    todo = [r for r in reqs if r["id"] not in done]

    def run(r):
        out = parse_json(call(r["writer"], r["prompt"], "gen_write", effort="low"))
        if out:
            with (G / "raw.jsonl").open("a") as f:
                f.write(json.dumps({"id": r["id"], "group": r["group"], "labels": r["labels"], "writer": r["writer"],
                                    "items": out.get("items") or []}, ensure_ascii=False) + "\n")
        return bool(out)
    G.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"requests": len(todo), "ok": sum(pmap(run, todo, conc=8)), "spend": spend()}))


def _focus_ok(f) -> bool:
    import re
    return f == "none" or bool(re.fullmatch(r'[a-z]+ "[^"]+"', f or ""))


def check() -> None:
    from muselet_train.catalog import skill_by_name
    from muselet_train.contexts import LAST_ACTIONS
    from muselet_train.decontam import norm
    from muselet_train.postprocess import fmt_args, norm_args
    from ground import grounded

    rng = random.Random(4)
    specials = {"MULTI_STEP", "ASK", "REFUSE", "ANSWER"}
    rows, why, seen = [], collections.Counter(), set()
    for r in jload(G / "raw.jsonl"):
        for x in r["items"]:
            if not isinstance(x, dict) or not isinstance(x.get("utterance"), str):
                why["bad_item"] += 1
                continue
            lab, u = x.get("label"), x["utterance"].strip()
            if lab not in r["labels"]:
                why["label_outside_group"] += 1
                continue
            if norm(u) in seen or not norm(u):
                why["dup"] += 1
                continue
            focused = x.get("focused") or "none"
            if not _focus_ok(focused):
                why["bad_focused"] += 1
                continue
            ctx = {"app": str(x.get("app") or "Finder"), "focused": focused, "selection": bool(x.get("selection")),
                   "online": True, "last_action": rng.choice(LAST_ACTIONS) if rng.random() < 0.1 else None}
            if lab == "premiere_command" and ctx["app"] != "Premiere Pro" or \
               lab == "type_text" and not focused.startswith(("textfield", "textarea")):
                why["context_inconsistent"] += 1
                continue
            target = None
            if lab not in specials:
                spec = {a["name"]: a for a in skill_by_name(lab).args}
                miss = x.get("missing")
                raw = {k: v for k, v in (x.get("args") or {}).items() if v not in (None, "")}
                if miss:
                    if miss not in spec or not spec[miss]["required"] or miss in raw:
                        why["bad_missing"] += 1
                        continue
                    target = f"missing={miss}"
                    a, err = norm_args(lab, {**raw, miss: "x"} if spec[miss]["type"] not in ("int", "bool", "enum")
                                       else raw, u)
                    if a is not None:
                        a.pop(miss, None)
                    elif not err.startswith("missing_required"):
                        why[f"args:{err.split(':')[0]}"] += 1
                        continue
                else:
                    a, err = norm_args(lab, raw, u)
                    if a is None:
                        why[f"args:{err.split(':')[0]}"] += 1
                        continue
                    g = grounded(lab, a, u, spec)
                    if g:
                        why[f"ungrounded:{g.split(':')[0]}"] += 1
                        continue
                    target = fmt_args(a) if a else ""
                if lab == "draft_email" and not miss and not a:
                    target = ""
            seen.add(norm(u))
            rows.append({"gid": len(rows), "group": r["group"], "writer": r["writer"], "label": lab, "utterance": u,
                         "context": ctx, "args_target": target})
    jdump(G / "checked.jsonl", rows)
    print(json.dumps({"kept": len(rows), "by_label": collections.Counter(x["label"] for x in rows), "dropped": why}))


def judge() -> None:
    from audit import ARGS_JUDGE, ROUTE_JUDGE, _args_lines, _batched, _route_lines
    items = jload(G / "judged.jsonl")
    have = {x["gid"] for x in items}
    items += [x for x in jload(G / "checked.jsonl") if x["gid"] not in have]
    for x in items:
        x["gold"] = x["label"]
    opts = option_block()
    for m in (JUDGE_OPENAI, JUDGE_ANTHROPIC):
        _batched(items, f"r:{m}", m, lambda s: ROUTE_JUDGE.format(options=opts, policy=POLICY, items=_route_lines(s)),
                 "label", "gen_route", batches=(25, 5))
        jdump(G / "judged.jsonl", items)
        ai = [x for x in items if x["args_target"]]
        _batched(ai, f"a:{m}", m, lambda s: ARGS_JUDGE.replace("\n\nItems:", "\n" + CONVENTIONS + "\n\nItems:").format(
            items=_args_lines(s)), "ok", "gen_args", batches=(25, 5))
        jdump(G / "judged.jsonl", items)
    print(json.dumps(spend()))


CONVENTIONS = """- Cloud A's catalog-v3 target conventions (correct by definition): send_message with a named recipient and no message is exactly missing=body (one key, the recipient is not repeated); compose_text target is notes when the user names Notes or no document, document when they mean the document/field they are in ("here", "this doc"), even when the word is not said; open_folder path is the folder name without the words the/my/folder, well-known folders capitalized (Downloads, Desktop)."""


def folder_path(p: str) -> str:
    """R7: open_folder path canonical form (the/my and a trailing 'folder' dropped, well-known folders capitalized)."""
    q = re.sub(r"^(the|my)\s+", "", p.strip(), flags=re.I)
    q = re.sub(r"\s+folder$", "", q, flags=re.I)
    if q.lower() in ("", "that", "this", "it", "the"):
        return p
    return WELL_KNOWN.get(q.lower(), q)


WELL_KNOWN = {k.lower(): k for k in ("Downloads", "Desktop", "Documents", "Pictures", "Music", "Movies",
                                       "Applications", "Public", "Library")}


def rejudge_args() -> None:
    """Second ARGS pass for generated items both route judges accepted but an ARGS judge rejected, after R7 and
    with cloud A's v3 target conventions added to the rules (the first pass did not state them)."""
    from audit import ARGS_JUDGE, _args_lines, _batched
    from muselet_train.postprocess import fmt_args
    items = jload(G / "judged.jsonl")
    keys = [f"a:{m}" for m in (JUDGE_OPENAI, JUDGE_ANTHROPIC)]
    s = []
    for x in items:
        if x["args_target"] and "args_pass1" not in x and [(x.get(f"r:{m}") or {}).get("label") for m in
                (JUDGE_OPENAI, JUDGE_ANTHROPIC)] == [x["label"]] * 2 and \
                not all((x.get(k) or {}).get("ok") is True for k in keys):
            x["args_pass1"] = {"target": x["args_target"], **{k: x.pop(k, None) for k in keys}}
            if x["label"] == "open_folder" and x["args_target"].startswith("path="):
                import shlex
                x["args_target"] = fmt_args({"path": folder_path(shlex.split(x["args_target"])[0][5:])})
            s.append(x)
    prompt = ARGS_JUDGE.replace("\n\nItems:", "\n" + CONVENTIONS + "\n\nItems:")
    for m in (JUDGE_OPENAI, JUDGE_ANTHROPIC):
        _batched(s, f"a:{m}", m, lambda b: prompt.format(items=_args_lines(b)), "ok", "gen_args_pass2", batches=(25, 5))
    jdump(G / "judged.jsonl", items)
    print(json.dumps({"rejudged": len(s), "ok": sum(all((x.get(k) or {}).get("ok") is True for k in keys) for x in s)}))


if __name__ == "__main__":
    {"write": write, "check": check, "judge": judge, "rejudge_args": rejudge_args}[sys.argv[1]]()
