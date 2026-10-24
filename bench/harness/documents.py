"""Document-app inventory and case-scoped cleanup helpers."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Sequence


@dataclass(frozen=True)
class DocumentApp:
    name: str
    bundle_ids: tuple[str, ...]
    aliases: tuple[str, ...]


DOCUMENT_APPS: tuple[DocumentApp, ...] = (
    DocumentApp("TextEdit", ("com.apple.TextEdit",), ("Text Edit",)),
    DocumentApp("Pages", ("com.apple.iWork.Pages", "com.apple.Pages"), ("Apple Pages",)),
    DocumentApp(
        "Numbers",
        ("com.apple.iWork.Numbers", "com.apple.Numbers"),
        ("Apple Numbers", "Numbers Creator Studio"),
    ),
    DocumentApp("Keynote", ("com.apple.iWork.Keynote", "com.apple.Keynote"), ("Apple Keynote",)),
    DocumentApp("Notes", ("com.apple.Notes",), ("Apple Notes",)),
    DocumentApp("Mail", ("com.apple.mail",), ("Apple Mail",)),
    DocumentApp("Messages", ("com.apple.MobileSMS",), ("iMessage",)),
    DocumentApp("Preview", ("com.apple.Preview",), ("Apple Preview",)),
    DocumentApp("Reminders", ("com.apple.reminders",), ("Apple Reminders",)),
    DocumentApp("Script Editor", ("com.apple.ScriptEditor2",), ("AppleScript Editor",)),
    DocumentApp("Word", ("com.microsoft.Word",), ("Microsoft Word",)),
    DocumentApp("Excel", ("com.microsoft.Excel",), ("Microsoft Excel",)),
    DocumentApp("PowerPoint", ("com.microsoft.Powerpoint",), ("Microsoft PowerPoint",)),
    DocumentApp("Outlook", ("com.microsoft.Outlook",), ("Microsoft Outlook",)),
    DocumentApp("Safari", ("com.apple.Safari",), ("Apple Safari",)),
    DocumentApp("Google Chrome", ("com.google.Chrome",), ("Chrome",)),
    DocumentApp("Firefox", ("org.mozilla.firefox",), ("Mozilla Firefox",)),
    DocumentApp("Arc", ("company.thebrowser.Browser",), ()),
    DocumentApp("Slack", ("com.tinyspeck.slackmacgap",), ()),
    DocumentApp("Discord", ("com.hnc.Discord",), ()),
    DocumentApp("WhatsApp", ("net.whatsapp.WhatsApp",), ()),
    DocumentApp("Telegram", ("ru.keepcoder.Telegram",), ()),
    DocumentApp("Signal", ("org.whispersystems.signal-desktop",), ()),
    DocumentApp("Adobe Premiere Pro", ("com.adobe.PremierePro",), ()),
)

_MAY_EDIT_CATEGORIES = {"input", "finance", "docs", "notes", "writing", "mail", "messages"}
_MAY_EDIT_UTTERANCE = re.compile(
    r"\b(type|write|paste|insert|append|delete|erase|clear|edit|fill|replace|rename|"
    r"draft|compose|reply|send|message|email|note|jot|enter|sum|total|spreadsheet|"
    r"cell|document)\b",
    re.IGNORECASE,
)
_SCRIPT_FIELDS = ("precondition", "setup", "check", "forbid", "teardown", "restore")


class DocumentInventoryError(RuntimeError):
    """Raised when the document inventory cannot be trusted."""


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


def _app_for_name_or_bundle(value: str) -> DocumentApp | None:
    normalized = value.strip().casefold()
    for app in DOCUMENT_APPS:
        if normalized in {
            app.name.casefold(),
            *(alias.casefold() for alias in app.aliases),
            *(bundle_id.casefold() for bundle_id in app.bundle_ids),
        }:
            return app
    return None


def may_edit_documents(case: dict) -> bool:
    category = str(case.get("category", case.get("kind", ""))).casefold()
    utterance = str(case.get("utterance", case.get("text", "")))
    return category in _MAY_EDIT_CATEGORIES or bool(_MAY_EDIT_UTTERANCE.search(utterance))


def _mentions_app(text: str, app: DocumentApp) -> bool:
    terms = (app.name, *app.aliases, *app.bundle_ids)
    return any(
        re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE)
        for term in terms
        if term
    )


def document_apps_for_case(case: dict) -> list[DocumentApp]:
    explicit = case.get("document_apps", [])
    if isinstance(explicit, str):
        explicit = [explicit]
    explicit_apps = {
        app
        for value in explicit if isinstance(value, str)
        if (app := _app_for_name_or_bundle(value)) is not None
    } if isinstance(explicit, (list, tuple, set)) else set()

    texts = [
        str(case.get("utterance", case.get("text", ""))),
        *(text for field in _SCRIPT_FIELDS for text in _iter_strings(case.get(field, []))),
    ]
    mentioned = {
        app for app in DOCUMENT_APPS
        if any(_mentions_app(text, app) for text in texts)
    }
    if may_edit_documents(case):
        return list(DOCUMENT_APPS)
    return [app for app in DOCUMENT_APPS if app in explicit_apps or app in mentioned]


def inventory_script(apps: Sequence[DocumentApp]) -> str:
    requested = [
        {"name": app.name, "bundle_ids": list(app.bundle_ids)}
        for app in apps
    ]
    return f"""// muselet-doc-inventory
ObjC.import('Foundation');
const requested = {json.dumps(requested, ensure_ascii=False)};
const systemEvents = Application("System Events");
const inventory = {{}};
function readScriptValue(read, row) {{
  try {{ return read(); }}
  catch (error) {{ row.scripting_unavailable = true; return null; }}
}}
for (const appInfo of requested) {{
  for (const bundleId of appInfo.bundle_ids) {{
    let processes;
    try {{
      processes = systemEvents.processes.whose({{bundleIdentifier: bundleId}})();
    }} catch (error) {{
      inventory[bundleId] = {{
        name: appInfo.name, running: false, ax_windows: [], windows: [], documents: [],
        scripting_unavailable: false, inventory_error: String(error)
      }};
      continue;
    }}
    const row = {{
      name: appInfo.name, running: processes.length > 0, ax_windows: [], windows: [],
      documents: [], scripting_unavailable: false
    }};
    if (processes.length > 0) {{
      try {{
        const names = processes[0].windows.name();
        row.ax_windows = (Array.isArray(names) ? names : [names]).map(name => String(name));
      }} catch (error) {{
        row.system_events_error = String(error);
      }}
      const app = Application(bundleId);
      try {{
        row.windows = app.windows().map(window => ({{
          id: readScriptValue(() => window.id(), row),
          name: readScriptValue(() => window.name(), row)
        }}));
      }} catch (error) {{
        row.scripting_unavailable = true;
      }}
      try {{
        row.documents = app.documents().map(document => ({{
          name: readScriptValue(() => document.name(), row),
          path: readScriptValue(() => document.path(), row)
        }}));
      }} catch (error) {{
        row.scripting_unavailable = true;
      }}
    }}
    inventory[bundleId] = row;
  }}
}}
JSON.stringify(inventory);
"""


RunScript = Callable[[str, str], Awaitable[dict[str, Any]]]


async def take_inventory(run_script: RunScript, apps: Sequence[DocumentApp]) -> dict[str, dict]:
    if not apps:
        return {}
    try:
        result = await run_script("jxa", inventory_script(apps))
    except Exception as exc:
        raise DocumentInventoryError(f"document inventory script failed: {exc}") from exc
    output = result.get("output") if isinstance(result, dict) else None
    try:
        inventory = json.loads(output) if isinstance(output, str) else None
    except (TypeError, json.JSONDecodeError) as exc:
        raise DocumentInventoryError("document inventory output was not valid JSON") from exc
    if not isinstance(inventory, dict):
        raise DocumentInventoryError("document inventory output was not an object")

    expected_bundles = {bundle_id for app in apps for bundle_id in app.bundle_ids}
    missing = expected_bundles - inventory.keys()
    if missing:
        raise DocumentInventoryError(
            f"document inventory omitted bundle ids: {', '.join(sorted(missing))}"
        )
    for bundle_id in expected_bundles:
        row = inventory[bundle_id]
        if not isinstance(row, dict):
            raise DocumentInventoryError(f"document inventory row for {bundle_id} was invalid")
        if row.get("inventory_error"):
            raise DocumentInventoryError(
                f"System Events could not inspect {bundle_id}: {row['inventory_error']}"
            )
        if row.get("running") and row.get("system_events_error"):
            raise DocumentInventoryError(
                f"System Events could not read windows for {bundle_id}: "
                f"{row['system_events_error']}"
            )
        if not isinstance(row.get("running"), bool):
            raise DocumentInventoryError(f"document inventory running status for {bundle_id} was invalid")
        if any(not isinstance(row.get(key), list) for key in ("ax_windows", "windows", "documents")):
            raise DocumentInventoryError(f"document inventory items for {bundle_id} were invalid")
    return inventory


async def osascript_run_script(
    language: str,
    script: str,
    *,
    timeout: float = 15,
) -> dict[str, Any]:
    if language != "jxa":
        raise ValueError("document inventory adapter only accepts JXA")
    process = await asyncio.create_subprocess_exec(
        "osascript",
        "-l",
        "JavaScript",
        "-e",
        script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise DocumentInventoryError(
            f"osascript document inventory timed out after {timeout:g}s"
        ) from exc
    output = stdout.decode("utf-8", errors="replace").strip()
    error = stderr.decode("utf-8", errors="replace").strip()
    if process.returncode:
        raise DocumentInventoryError(
            f"osascript document inventory exited {process.returncode}: {error}"
        )
    return {"output": output, "stderr": error, "returncode": process.returncode}


def foreign_items(baseline: dict) -> list[str]:
    items = []
    for bundle_id, row in baseline.items():
        if not isinstance(row, dict) or not row.get("running"):
            continue
        app_name = str(row.get("name") or bundle_id)
        items.extend(
            f'{app_name} AX window: {name}'
            for name in row.get("ax_windows", [])
        )
        items.extend(
            f'{app_name} window: {window.get("name") or window.get("id") or "unknown"}'
            for window in row.get("windows", [])
            if isinstance(window, dict)
        )
        items.extend(
            f'{app_name} document: {document.get("name") or "unknown"}'
            for document in row.get("documents", [])
            if isinstance(document, dict)
        )
    return list(dict.fromkeys(items))


def _item_identity(item: dict, kind: str):
    if kind == "window":
        return ("id", str(item["id"])) if item.get("id") is not None else None
    if item.get("name") is not None and item.get("path") is not None:
        return ("document", str(item["name"]), str(item["path"]))
    return None


def created_items(baseline: dict, *later: dict) -> dict:
    created: dict[str, dict] = {}
    bundle_ids = set(baseline)
    for snapshot in later:
        if isinstance(snapshot, dict):
            bundle_ids.update(snapshot)
    for bundle_id in sorted(bundle_ids):
        base_row = baseline.get(bundle_id, {})
        if not isinstance(base_row, dict):
            base_row = {}
        row = {
            "name": base_row.get("name"),
            "windows": [],
            "documents": [],
            "unidentified": [],
        }
        baseline_windows = base_row.get("windows", [])
        baseline_documents = base_row.get("documents", [])
        baseline_ax_windows = set(base_row.get("ax_windows", []))
        known_windows = {
            identity for item in baseline_windows if isinstance(item, dict)
            if (identity := _item_identity(item, "window")) is not None
        }
        known_documents = {
            identity for item in baseline_documents if isinstance(item, dict)
            if (identity := _item_identity(item, "document")) is not None
        }
        baseline_unidentified = {
            (kind, json.dumps(item, sort_keys=True, default=str))
            for kind, values in (("window", baseline_windows), ("document", baseline_documents))
            for item in values if isinstance(item, dict) and _item_identity(item, kind) is None
        }
        seen_windows: set[tuple] = set()
        seen_documents: set[tuple] = set()
        seen_unidentified: set[tuple[str, str]] = set()
        for snapshot in later:
            if not isinstance(snapshot, dict):
                continue
            later_row = snapshot.get(bundle_id, {})
            if not isinstance(later_row, dict):
                continue
            later_windows = [
                item for item in later_row.get("windows", [])
                if isinstance(item, dict)
            ]
            known_scripted_names = {
                str(item.get("name"))
                for item in later_windows
                if item.get("name") is not None
            }
            for name in later_row.get("ax_windows", []):
                if (
                    name not in baseline_ax_windows
                    and str(name) not in known_scripted_names
                ):
                    marker = ("ax_window", json.dumps({"name": name}, sort_keys=True, default=str))
                    if marker not in seen_unidentified:
                        row["unidentified"].append({
                            "type": "ax_window",
                            "item": {"name": name},
                        })
                        seen_unidentified.add(marker)
            for item in later_windows:
                identity = _item_identity(item, "window")
                if identity is None:
                    marker = ("window", json.dumps(item, sort_keys=True, default=str))
                    if marker not in baseline_unidentified and marker not in seen_unidentified:
                        row["unidentified"].append({"type": "window", "item": item})
                        seen_unidentified.add(marker)
                elif identity not in known_windows and identity not in seen_windows:
                    row["windows"].append(item)
                    seen_windows.add(identity)
            for item in later_row.get("documents", []):
                if not isinstance(item, dict):
                    continue
                identity = _item_identity(item, "document")
                if identity is None:
                    marker = ("document", json.dumps(item, sort_keys=True, default=str))
                    if marker not in baseline_unidentified and marker not in seen_unidentified:
                        row["unidentified"].append({"type": "document", "item": item})
                        seen_unidentified.add(marker)
                elif identity not in known_documents and identity not in seen_documents:
                    row["documents"].append(item)
                    seen_documents.add(identity)
        if row["windows"] or row["documents"] or row["unidentified"]:
            created[bundle_id] = row
    return created


def unclosable_items(created: dict) -> list[dict]:
    items = []
    for bundle_id, row in created.items():
        has_created_window_id = any(
            isinstance(window, dict) and window.get("id") is not None
            for window in row.get("windows", [])
        )
        for window in row.get("windows", []):
            if not isinstance(window, dict) or window.get("id") is None:
                items.append({"bundle_id": bundle_id, "type": "window", "item": window})
        for document in row.get("documents", []):
            if (
                not isinstance(document, dict)
                or document.get("name") is None
                or document.get("path") is None
            ) and not has_created_window_id:
                items.append({"bundle_id": bundle_id, "type": "document", "item": document})
        for item in row.get("unidentified", []):
            if has_created_window_id and item.get("type") == "document":
                continue
            items.append({"bundle_id": bundle_id, **item})
    return items


def close_created_script(created: dict) -> str | None:
    closable = {}
    for bundle_id, row in created.items():
        windows = [
            {"id": item["id"]}
            for item in row.get("windows", [])
            if isinstance(item, dict) and item.get("id") is not None
        ]
        documents = [
            {"name": item["name"], "path": item["path"]}
            for item in row.get("documents", [])
            if (
                isinstance(item, dict)
                and item.get("name") is not None
                and item.get("path") is not None
            )
        ]
        if windows or documents:
            closable[bundle_id] = {"windows": windows, "documents": documents}
    if not closable:
        return None
    return f"""const created = {json.dumps(closable, ensure_ascii=False)};
for (const bundleId of Object.keys(created)) {{
  const app = Application(bundleId);
  for (const windowInfo of created[bundleId].windows) {{
    try {{ app.windows.byId(windowInfo.id).close({{saving: "no"}}); }} catch (error) {{}}
  }}
  for (const documentInfo of created[bundleId].documents) {{
    try {{
      app.documents.whose({{name: documentInfo.name, path: documentInfo.path}})()
        .forEach(document => document.close({{saving: "no"}}));
    }} catch (error) {{}}
  }}
}}
"""


_CLOSE_TARGET = re.compile(
    r"\bclose\s+(?:\(\s*)?(?:(?:every|front)\s+)?(?:documents?|windows?)\b",
    re.IGNORECASE,
)
_DOCUMENT_CLOSE_TARGET = re.compile(
    r"\bclose\s+(?:\(\s*)?(?:(?:every|front|first|last|the)\s+)?(?:documents?|windows?)\b",
    re.IGNORECASE,
)
_FILTERED_CLOSE = re.compile(r"\bwhose\s+(?:path|url|id|name)\b", re.IGNORECASE)
_JXA_CLOSE_EVERY = re.compile(
    r"\.\s*(?:documents|windows)\s*\(\s*\)\s*\.\s*forEach\s*\(",
    re.IGNORECASE,
)


def is_broad_close(script: str) -> bool:
    for match in _CLOSE_TARGET.finditer(script):
        tail = script[match.end():]
        delimiters = [position for position in (tail.find(")"), tail.find(";"), tail.find("\n")) if position >= 0]
        scope = tail[:min(delimiters)] if delimiters else tail
        if not _FILTERED_CLOSE.search(scope):
            return True
    for match in _JXA_CLOSE_EVERY.finditer(script):
        tail = script[match.end():]
        terminators = [position for position in (tail.find(";"), tail.find("\n")) if position >= 0]
        scope = tail[:min(terminators)] if terminators else tail
        if re.search(r"(?:\.close\s*\(|\bclose\s*\()", scope, re.IGNORECASE):
            return True
    return False


_JXA_DOCUMENT_CLOSE = re.compile(
    r"\.\s*(?:documents|windows)\b[\s\S]*?(?:\.\s*close\s*\(|\bclose\s*\()"
    r"|\b(?:document|window)\s*\.\s*close\s*\(",
    re.IGNORECASE,
)


def is_document_close(script: str) -> bool:
    return bool(
        _DOCUMENT_CLOSE_TARGET.search(script)
        or _JXA_DOCUMENT_CLOSE.search(script)
    )


_QUIT_TARGET_PATTERNS = (
    re.compile(r"\bquit\s+app(?:lication)?\s+['\"]([^'\"]+)['\"]", re.IGNORECASE),
    re.compile(
        r"\btell\s+application(?:\s+id)?\s+['\"]([^'\"]+)['\"][\s\S]{0,200}?\bquit\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bApplication\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\.quit\s*\(", re.IGNORECASE),
)


def quit_target(script: str) -> DocumentApp | None:
    for pattern in _QUIT_TARGET_PATTERNS:
        match = pattern.search(script)
        if not match:
            continue
        target = match.group(1).strip()
        app = _app_for_name_or_bundle(target)
        if app is not None:
            return app
        for candidate in DOCUMENT_APPS:
            if target.casefold().startswith(candidate.name.casefold() + " "):
                return candidate
    return None
