"""Deterministic, confirmation-gated edits in the open Premiere Pro project."""

from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path

MEDIA_EXT = {".mp4", ".mov", ".m4v", ".mxf", ".wav", ".mp3", ".png", ".jpg"}
POLL_S = 0.15
NAME_RE = re.compile(r"[A-Za-z0-9 _.,'-]{1,40}\Z")


class ToolError(Exception):
    def __init__(self, say: str, raw: str):
        super().__init__(raw)
        self.say, self.raw = say, raw


class Steps:
    def __init__(self, orch):
        self.orch = orch

    def __call__(self, name):
        return _Step(self.orch, name)


class _Step:
    def __init__(self, orch, name):
        self.orch, self.name = orch, name

    def __enter__(self):
        self.started = time.perf_counter()

    def __exit__(self, *exc):
        self.orch.tracer.stage(
            f"premiere_{self.name}", (time.perf_counter() - self.started) * 1000)


def parse_request(text: str, ctx: dict) -> dict | None:
    app = str(ctx.get("app", "")).casefold()
    raw = str(text or "")
    lower = raw.casefold()
    if not app.startswith("adobe premiere") and "premiere" not in lower:
        return None
    if re.search(r"\b(play|stop|undo)\b|\bgo\s+to\s+(?:the\s+)?(?:start|end)\b",
                 lower):
        return None
    if re.search(r"\b(export|render)\b", lower):
        return {"op": "export"}
    if re.search(r"\bimport\b", lower):
        match = re.search(
            r"\bfrom\s+(?:my\s+|the\s+)?(?:desktop\s+)?(.+?)\s+folder\b",
            raw, re.IGNORECASE)
        return {"op": "import", "folder": match.group(1).strip()
                if match else "Footage"}
    if re.search(r"\bmarker\b", lower):
        args = {"op": "marker"}
        match = re.search(
            r"(?:called|named|titled|labeled)\s+[\"“']?(.+?)[\"”']?[.!?]?$",
            raw, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if NAME_RE.fullmatch(name):
                args["name"] = name
        return args
    if re.search(r"\b(cross ?dissolve|dissolve|transition)\b", lower):
        return {"op": "transition"}
    if re.search(r"\b(speed|faster|slow)\b", lower):
        match = re.search(r"\b(\d{1,4})\s*(?:%|\bpercent\b)", lower)
        percent = int(match.group(1)) if match else None
        if percent is None and re.search(r"\b(?:double|2x)\b", lower):
            percent = 200
        if percent is None and re.search(r"\bhalf\b", lower):
            percent = 50
        return {"op": "speed", "percent": percent} if percent is not None else None
    if re.search(r"\b(cut|split|razor|add an? edit)\b", lower):
        return {"op": "cut"}
    return None


def _as_str(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _keystroke(text: str, mods: tuple[str, ...] = ()) -> str:
    source = f"keystroke {_as_str(text)}"
    return source + (" using {" + ", ".join(f"{mod} down" for mod in mods) + "}"
                     if mods else "")


def _key(code: int, mods: tuple[str, ...] = ()) -> str:
    source = f"key code {int(code)}"
    return source + (" using {" + ", ".join(f"{mod} down" for mod in mods) + "}"
                     if mods else "")


def _menu_click(path: tuple[str, ...]) -> str:
    lines = [f"set menuRef to menu 1 of menu bar item {_as_str(path[0])} of menu bar 1 of p"]
    for index, item in enumerate(path[1:]):
        base = item.removesuffix("...").removesuffix("…")
        names = (base + "...", base + "…") if item.endswith(("...", "…")) else (item,)
        query = " or ".join(f"name is {_as_str(name)}" for name in names)
        lines += [
            "try",
            f" set menuItem to first menu item of menuRef whose {query}",
            "on error",
            ' return "error:missing"',
            "end try",
        ]
        if index < len(path) - 2:
            lines.append("set menuRef to menu 1 of menuItem")
        else:
            lines += [
                'if enabled of menuItem is false then return "error:disabled"',
                "click menuItem",
                'return "ok"',
            ]
    return "\n".join(lines)


def _undo_title() -> str:
    return ('return name of menu item 1 of menu 1 of menu bar item "Edit" '
            "of menu bar 1 of p")


def _focus_timeline() -> str:
    return _menu_click(("Window", "Timeline"))


def _window_info() -> str:
    return (
        "set w to window 1 of p\n"
        "set xy to position of w\n"
        "set wh to size of w\n"
        "return (name of w as text) & tab & (item 1 of xy as text) & tab & "
        "(item 2 of xy as text) & tab & (item 1 of wh as text) & tab & "
        "(item 2 of wh as text)"
    )


def _wrap(body: str) -> str:
    return (
        'tell application "System Events"\n'
        "try\n"
        ' set p to first application process whose bundle identifier starts with '
        '"com.adobe.PremierePro"\n'
        "on error\n"
        ' return "error:not_open"\n'
        "end try\n"
        "set frontmost of p to true\n"
        f"{body}\n"
        "end tell"
    )


async def _rpc(orch, method: str, params: dict, fail_say: str, timeout: float = 30) -> dict:
    started = time.perf_counter()
    try:
        result = await orch.server.rpc(method, params, timeout=timeout)
    except RuntimeError as exc:
        orch.tracer.rpc(method, params, {"error": str(exc)},
                        (time.perf_counter() - started) * 1000)
        raise ToolError(fail_say, str(exc)) from None
    orch.tracer.rpc(method, params, result, (time.perf_counter() - started) * 1000)
    if not isinstance(result, dict) or not result.get("ok", method == "ocr"):
        raise ToolError(fail_say, str(result.get("error") if isinstance(result, dict)
                                       else result))
    return result


async def _script(orch, code: str, fail_say: str = "Premiere couldn't do that") -> str:
    result = await _rpc(
        orch, "act", {"op": "script", "lang": "applescript", "code": code},
        fail_say)
    output = str(result.get("output") or "").strip()
    if output == "error:not_open":
        raise ToolError("Premiere Pro isn't open", output)
    return output


async def _ensure_premiere(orch) -> None:
    await _script(orch, _wrap('return "ready"'), "Premiere Pro isn't open")


async def _window_names(orch) -> list[str]:
    body = (
        "set AppleScript's text item delimiters to linefeed\n"
        "set ns to name of every window of p\n"
        "return ns as text"
    )
    output = await _script(orch, _wrap(body), "Premiere couldn't read its windows")
    return [line.strip() for line in output.splitlines() if line.strip()]


async def _wait_window(orch, name_prefix: str, timeout: float,
                       previous: set[str] | None = None) -> str | None:
    deadline = time.monotonic() + timeout
    prefix = name_prefix.casefold()
    while True:
        names = await _window_names(orch)
        found = next((name for name in names if name.casefold().startswith(prefix)), None)
        if found is None and previous is not None:
            found = next((name for name in names if name not in previous), None)
        if found:
            return found
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        await asyncio.sleep(min(POLL_S, remaining))


async def _click_menu(orch, path: tuple[str, ...], *,
                      missing: str = "Premiere menu item wasn't found",
                      disabled: str = "Premiere menu item is unavailable") -> None:
    output = await _script(orch, _wrap(_menu_click(path)), missing)
    if output == "error:missing":
        raise ToolError(missing, output)
    if output == "error:disabled":
        raise ToolError(disabled, output)
    if output != "ok":
        raise ToolError(missing, output)


async def _focus(orch) -> None:
    await _click_menu(
        orch, ("Window", "Timeline"),
        missing="Couldn't focus the timeline",
        disabled="Couldn't focus the timeline")


async def _read_undo(orch) -> str:
    return await _script(
        orch, _wrap(_undo_title()), "Couldn't read Premiere's undo title")


async def _verify_undo(orch, before: str) -> str:
    after = await _read_undo(orch)
    ok = after != before and after.startswith("Undo")
    orch.tracer.decision({
        "tool": "premiere_edit", "undo_before": before,
        "undo_after": after, "verified": ok,
    })
    if not ok:
        raise ToolError("Premiere didn't apply that", f"{before!r} -> {after!r}")
    return after


async def _window_region(orch) -> list[int]:
    output = await _script(
        orch, _wrap(_window_info()), "Couldn't read Premiere's window frame")
    try:
        _, x, y, width, height = output.split("\t")
        return [int(float(x)), int(float(y)), int(float(width)), int(float(height))]
    except (ValueError, TypeError):
        raise ToolError("Couldn't read Premiere's window frame", output) from None


async def _ocr_window(orch) -> dict:
    return await _rpc(
        orch, "ocr", {"region": await _window_region(orch)},
        "Couldn't read Premiere's window")


def _ocr_text(result: dict) -> str:
    if isinstance(result.get("text"), str):
        return result["text"]
    return "\n".join(str(line.get("text", "")) for line in result.get("lines", [])
                     if isinstance(line, dict))


def _marker_name(value) -> str | None:
    name = str(value or "").strip()
    return name if NAME_RE.fullmatch(name) else None


async def _confirm(orch, args: dict) -> bool:
    mode = os.environ.get("MUSELET_PREMIERE_CONFIRM", "each").casefold()
    if mode != "project":
        mode = "each"
    if mode == "project":
        title = str(orch._ctx.get("window_title") or "Premiere Pro").strip()
        normalized = re.sub(r"\s*[-–—]\s*Adobe Premiere Pro.*$", "", title,
                            flags=re.IGNORECASE)
        normalized = re.sub(r"\s*\*+\s*$", "", normalized).strip()
        stem = Path(normalized).stem or "Premiere project"
        key = normalized.casefold() or stem.casefold()
        confirmed = getattr(orch, "_premiere_confirmed_projects", None)
        if confirmed is None:
            confirmed = orch._premiere_confirmed_projects = set()
        if key in confirmed:
            return True
        summary = " ".join(f"Let Muselet edit {stem}?".split()[:12])
    else:
        summary = await orch._confirm_summary({
            "op": "skill", "name": "premiere_edit", "args": args})
    started = time.perf_counter()
    try:
        yes = await orch.server.ask_confirm(summary)
    except (RuntimeError, TimeoutError):
        yes = False
    orch.tracer.stage("premiere_confirm", (time.perf_counter() - started) * 1000)
    orch.tracer.decision({"tool": "premiere_edit", "confirm": summary, "yes": bool(yes)})
    if yes and mode == "project":
        confirmed.add(key)
    return bool(yes)


def _media_files(folder: str) -> tuple[Path, list[Path]]:
    env_folder = os.environ.get("MUSELET_PREMIERE_FOOTAGE")
    if env_folder and (not folder or folder.casefold() == "footage"):
        root = Path(env_folder).expanduser()
    else:
        root = Path.home() / "Desktop" / (folder or "Footage")
    try:
        files = sorted(
            path for path in root.iterdir()
            if not path.name.startswith(".") and path.is_file()
            and path.suffix.casefold() in MEDIA_EXT)
    except OSError:
        files = []
    return root, files


async def _import(orch, args: dict) -> str:
    folder = str(args.get("folder") or "Footage").strip() or "Footage"
    root, files = _media_files(folder)
    if not files:
        raise ToolError(f"No clips in Desktop/{folder}", str(root))
    previous = set(await _window_names(orch))
    before = await _read_undo(orch)
    await _click_menu(orch, ("File", "Import..."))
    if not await _wait_window(orch, "Import", 3, previous):
        raise ToolError("Import dialog didn't open", "window timeout")
    await _script(orch, _wrap(_keystroke("g", ("command", "shift"))),
                  "Couldn't open the footage folder")
    await asyncio.sleep(0.3)
    await _script(orch, _wrap(_keystroke(str(root))),
                  "Couldn't enter the footage path")
    await _script(orch, _wrap(_key(36)), "Couldn't open the footage folder")
    await asyncio.sleep(0.5)
    await _script(orch, _wrap(_keystroke("a", ("command",))),
                  "Couldn't select the footage")
    await _script(orch, _wrap(_key(36)), "Couldn't import the footage")
    after = await _verify_undo(orch, before)
    ocr = await _ocr_window(orch)
    text = _ocr_text(ocr).casefold()
    verified = any(path.stem.casefold() in text for path in files)
    orch.tracer.decision({
        "tool": "premiere_edit", "import_count": len(files),
        "verified_ocr": verified, "undo_after": after,
    })
    return f"Imported {len(files)} clips"


async def _edit(orch, op: str, args: dict) -> str:
    if op == "import":
        return await _import(orch, args)
    if op == "speed":
        try:
            percent = int(args.get("percent"))
        except (TypeError, ValueError):
            percent = 0
        if not 1 <= percent <= 10000:
            raise ToolError("Speed must be 1 to 10000%", str(args.get("percent")))
    name = _marker_name(args.get("name")) if op == "marker" else None
    await _focus(orch)
    if op == "cut":
        before = await _read_undo(orch)
        await _click_menu(orch, ("Sequence", "Add Edit"))
        await _verify_undo(orch, before)
        return "Cut at the playhead"
    if op == "transition":
        before = await _read_undo(orch)
        await _click_menu(
            orch, ("Sequence", "Apply Video Transition"),
            disabled="Put the playhead on a cut first")
        await _verify_undo(orch, before)
        return "Added a cross dissolve"
    if op == "speed":
        before = await _read_undo(orch)
        await _script(orch, _wrap(_keystroke("d")), "Couldn't select a clip")
        previous = set(await _window_names(orch))
        await _click_menu(
            orch, ("Clip", "Speed/Duration..."),
            disabled="Select a clip first")
        if not await _wait_window(orch, "Clip Speed", 3, previous):
            raise ToolError("Speed dialog didn't open", "window timeout")
        await _script(orch, _wrap(_keystroke("a", ("command",))),
                      "Couldn't edit clip speed")
        await _script(orch, _wrap(_keystroke(str(percent))),
                      "Couldn't edit clip speed")
        await _script(orch, _wrap(_key(36)), "Couldn't set clip speed")
        await _verify_undo(orch, before)
        return f"Speed set to {percent}%"
    if op == "marker":
        before = await _read_undo(orch)
        await _click_menu(orch, ("Markers", "Add Marker"))
        await _verify_undo(orch, before)
        if name:
            before = await _read_undo(orch)
            previous = set(await _window_names(orch))
            await _click_menu(orch, ("Markers", "Edit Marker..."))
            if not await _wait_window(orch, "Marker", 3, previous):
                raise ToolError("Marker dialog didn't open", "window timeout")
            await _script(orch, _wrap(_keystroke("a", ("command",))),
                          "Couldn't edit marker")
            await _script(orch, _wrap(_keystroke(name)), "Couldn't name marker")
            await _script(orch, _wrap(_key(36)), "Couldn't save marker")
            await _verify_undo(orch, before)
            return f"Added marker {name}"
        return "Added a marker"
    raise ToolError("I couldn't parse that Premiere edit", op)


def _desktop_mp4s() -> dict[str, int]:
    desktop = Path.home() / "Desktop"
    try:
        return {path.name: path.stat().st_mtime_ns for path in desktop.iterdir()
                if path.is_file() and path.suffix.casefold() == ".mp4"}
    except OSError as exc:
        raise ToolError("Couldn't check Desktop exports", str(exc)) from None


async def _wait_export(orch, before: dict[str, int]) -> Path | None:
    try:
        timeout = max(0.0, float(os.environ.get(
            "MUSELET_PREMIERE_EXPORT_TIMEOUT", "120")))
    except ValueError:
        timeout = 120.0
    desktop = Path.home() / "Desktop"
    deadline = time.monotonic() + timeout
    previous_sizes: dict[str, int] = {}
    while True:
        try:
            candidates = sorted(
                (path for path in desktop.iterdir()
                 if path.is_file() and path.suffix.casefold() == ".mp4"),
                key=lambda path: path.stat().st_mtime_ns, reverse=True)
        except OSError:
            candidates = []
        for path in candidates:
            try:
                stat = path.stat()
                if stat.st_mtime_ns <= before.get(path.name, -1) or stat.st_size <= 0:
                    continue
                if previous_sizes.get(path.name) == stat.st_size:
                    with path.open("rb") as stream:
                        stream.seek(4)
                        if stream.read(4) == b"ftyp":
                            return path
                previous_sizes[path.name] = stat.st_size
            except OSError:
                continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        await asyncio.sleep(min(1.0, remaining))


def _line_frame(line: dict) -> tuple[float, float] | None:
    frame = line.get("frame")
    if isinstance(frame, dict):
        x, y = frame.get("x"), frame.get("y")
        width = frame.get("width", frame.get("w"))
        height = frame.get("height", frame.get("h"))
    elif isinstance(frame, (list, tuple)) and len(frame) >= 4:
        x, y, width, height = frame[:4]
    else:
        return None
    try:
        return float(x) + float(width) / 2, float(y) + float(height) / 2
    except (TypeError, ValueError):
        return None


async def _export(orch) -> str:
    before = _desktop_mp4s()
    await _focus(orch)
    previous = set(await _window_names(orch))
    await _click_menu(orch, ("File", "Export", "Media..."))
    if not await _wait_window(orch, "Export", 5, previous):
        raise ToolError("Export window didn't open", "window timeout")
    result = await _ocr_window(orch)
    region = await _window_region(orch)
    midpoint = region[0] + region[2] / 2
    buttons = []
    for line in result.get("lines", []):
        if not isinstance(line, dict) or str(line.get("text", "")).strip() != "Export":
            continue
        center = _line_frame(line)
        if center and center[0] >= midpoint:
            buttons.append(center)
    if not buttons:
        raise ToolError("Couldn't find the Export button", "OCR miss")
    x, y = max(buttons, key=lambda center: center[1])
    await _rpc(orch, "act", {"op": "click", "x": int(x), "y": int(y)},
               "Couldn't click Export")
    await orch.server.ui("acting", "Exporting…")
    path = await _wait_export(orch, before)
    if path is None:
        raise ToolError("Export didn't finish", "export timeout")
    orch.tracer.decision({
        "tool": "premiere_edit", "export_path": str(path), "verified": True,
    })
    return f"Exported {path.name}"


async def run(orch, args: dict, utterance: str) -> str:
    started = time.perf_counter()
    steps = Steps(orch)
    op = str(args.get("op") or "")
    try:
        if op not in {"import", "cut", "transition", "speed", "marker", "export"}:
            raise ToolError("I couldn't parse that Premiere edit", op)
        clean_args = dict(args)
        if op == "marker":
            name = _marker_name(clean_args.get("name"))
            if name:
                clean_args["name"] = name
            else:
                clean_args.pop("name", None)
        with steps("confirm"):
            confirmed = await _confirm(orch, clean_args)
        if not confirmed:
            await orch.server.say("Okay, cancelled")
            await orch.server.ui("confused")
            return "cancelled"
        with steps("locate"):
            await _ensure_premiere(orch)
        await orch.server.ui("acting")
        with steps(op):
            reply = await (_export(orch) if op == "export"
                           else _edit(orch, op, clean_args))
        await orch.server.say(" ".join(reply.split()[:12]))
        await orch.server.ui("success")
        return "ok"
    except ToolError as exc:
        orch.tracer.decision({"tool": "premiere_edit", "error": exc.raw})
        await orch.server.say(" ".join(exc.say.split()[:12]))
        await orch.server.ui("confused")
        return "failed"
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        orch.tracer.decision({
            "tool": "premiere_edit",
            "error": f"{type(exc).__name__}: {exc}",
        })
        await orch.server.say("Premiere couldn't finish that")
        await orch.server.ui("confused")
        return "failed"
    finally:
        orch.tracer.stage("premiere_total", (time.perf_counter() - started) * 1000)
