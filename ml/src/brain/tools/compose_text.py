"""Brain tool for short, model-generated text drafts."""

from __future__ import annotations

import re


SYSTEM = (
    "You write short text that a voice assistant puts into a note or a text "
    "field. Output only the text itself, at most 150 words, with no preamble "
    "and no closing remarks. If the request asks for a template, use short "
    "headings or labeled blanks the user can fill in. If it asks for a list, "
    "put one item per line starting with \"- \". Plain text only; no markdown "
    "except \"- \" bullets."
)


def _cap_words(text: str) -> str:
    lines = text.strip().splitlines()
    kept: list[str] = []
    count = 0
    for line in lines:
        words = line.split()
        if count + len(words) <= 150:
            kept.append(line)
            count += len(words)
            continue
        if not kept:
            kept.append(" ".join(words[:150]))
        break
    return "\n".join(kept).strip()


def _title(topic: str, text: str) -> str:
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if first and not first.startswith("-") and len(first.split()) <= 6:
        return first
    return " ".join(str(topic).title().split()[:6])


async def run(orch, args, utterance) -> str:
    planner = getattr(orch, "planner_escalate", None) or \
        getattr(orch, "planner", None)
    if planner is None:
        await orch.server.say("I can't write that yet")
        await orch._end_ui("confused")
        return "failed"
    topic = str(args.get("topic") or "").strip()
    user = f"Topic: {topic}\nRequest: {utterance}"
    try:
        from ..planner import worker
        text = await worker().submit_async(
            planner.generate, SYSTEM, user, max_tokens=320)
    except Exception:
        await orch.server.say("I can't write that yet")
        await orch._end_ui("confused")
        return "failed"
    text = re.sub(r"<think>.*?</think>", "", str(text or ""),
                  flags=re.IGNORECASE | re.DOTALL).strip()
    text = _cap_words(text)
    if not text:
        await orch.server.say("I can't write that yet")
        await orch._end_ui("confused")
        return "failed"
    title = _title(topic, text)
    trace = orch.tracer.current or {"decisions": []}
    target = str(args.get("target") or "note").strip().lower()
    target = {"notes": "note", "document": "focused"}.get(target, target)   # catalog v3 (it3) values
    if target == "focused":
        outcome = await orch._run_skill(
            "type_text", {"text": text}, utterance, trace)
        if outcome == "ok":
            await orch.server.say("Wrote it")
            await orch._end_ui("success")
            return "ok"
        if getattr(orch, "_last_action_error", None) == "no_text_target":
            orch._pending_task = {"goal": utterance, "t": __import__(
                "time").time()}
            await orch.server.say("Click where it should go, then say continue.")
            await orch.server.ui("listening")
            return "awaiting_user"
        return outcome
    outcome = await orch._run_skill(
        "new_note", {"title": title, "body": text}, utterance, trace)
    if outcome != "ok":
        await orch.server.say("That didn't work")
        await orch._end_ui("confused")
        return "failed"
    try:
        result = await orch.server.rpc(
            "verify", {"expect": f'appears "{title}"'}, timeout=15)
        if not result.get("ok", False):
            raise RuntimeError("note not found")
    except Exception:
        await orch.server.say("That didn't work")
        await orch._end_ui("confused")
        return "failed"
    await orch.server.say("Wrote it in Notes")
    await orch._end_ui("success")
    return "ok"
