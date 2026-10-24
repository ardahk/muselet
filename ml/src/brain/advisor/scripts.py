"""AppleScript generators (strings only; the app executes them). Every interpolated value is escaped."""

from __future__ import annotations

import html
import re
from decimal import Decimal

from .brief import brief_html, brief_markdown

NUMBERS_ID = "com.apple.Numbers"
NOTES_ID = "com.apple.Notes"
GREEN = (50886, 61423, 52942)    # rgb(198, 239, 206) in Numbers' 16-bit channels
AMBER = (65535, 58853, 39321)    # rgb(255, 229, 153)
HOLDINGS_COLUMNS = "A", "J"      # Account .. Unrealized G/L
NOTE_TITLE = "{household} — annual review prep (Muselet)"   # tag: the only note this tool updates
REVIEW_SHEET = "Muselet Review"
MARKER_TABLE = "Muselet Allocation"                             # marks a Review sheet this tool created


def q(text: str) -> str:
    """AppleScript string literal: escape backslashes and quotes, splice line breaks/tabs, drop other controls."""
    s = str(text).replace("\r\n", "\n").replace("\r", "\n")
    s = "".join(ch for ch in s if ch in "\n\t" or ord(ch) >= 32)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", '" & linefeed & "').replace("\t", '" & tab & "')
    return f'"{s}"'


def _num(x: str | Decimal) -> str:
    d = Decimal(x)
    return format(d, "f")


def _doc(document: str | None, path: str | None = None) -> str:
    if path:
        return "theDoc"
    return f"document {q(document)}" if document else "front document"


def _resolve_doc(path: str, indent: str = "\t", tries: int = 1) -> list[str]:
    """Bind `theDoc` to the open Numbers document whose file is `path` (never by name: every client has a
    portfolio.xlsx). tries > 1 polls every 0.1 s while Numbers is still opening the file."""
    i = indent
    body = [f"{i}set theDoc to missing value",
            f"{i}repeat {int(tries)} times",
            f"{i}\trepeat with d in documents",
            f"{i}\t\ttry",
            f"{i}\t\t\tif POSIX path of ((file of d) as alias) is {q(path)} then set theDoc to contents of d",
            f"{i}\t\tend try",
            f"{i}\tend repeat",
            f"{i}\tif theDoc is not missing value then exit repeat",
            *([f"{i}\tdelay 0.1"] if tries > 1 else []),
            f"{i}end repeat",
            f"{i}if theDoc is missing value then error {q('Numbers has no open document for ' + path)}"]
    return body


def _rgb(c: tuple[int, int, int]) -> str:
    return "{" + ", ".join(str(v) for v in c) + "}"


def numbers_highlight_script(prep: dict, document: str | None = None, sheet: str = "Holdings",
                             path: str | None = None) -> str:
    """Green = harvestable TLH lots, amber = wash-sale-blocked lots. Sheet row = CSV data row + 1 (header)."""
    lines = [f"tell application id {q(NUMBERS_ID)}", *(_resolve_doc(path) if path else []),
             f"\ttell table 1 of sheet {q(sheet)} of {_doc(document, path)}"]
    for e in prep["tlh"]["lots"]:
        r = e["lot"]["row"] + 1
        color = GREEN if e["status"] == "ok" else AMBER
        rng = f"{HOLDINGS_COLUMNS[0]}{r}:{HOLDINGS_COLUMNS[1]}{r}"
        lines.append(f"\t\tset background color of range {q(rng)} to {_rgb(color)} "
                     f"-- {e['lot']['ticker']} {e['lot']['lot_date']} {e['status']}")
    lines += ["\tend tell", "end tell"]
    return "\n".join(lines) + "\n"


def _fill(lines: list[str], table_var: str, rows: list[list], indent: str) -> None:
    for r, row in enumerate(rows, start=1):
        for c, v in enumerate(row, start=1):
            val = q(v) if isinstance(v, str) else _num(v)
            lines.append(f"{indent}set value of cell {c} of row {r} of {table_var} to {val}")


def numbers_review_script(prep: dict, document: str | None = None, sheet: str = REVIEW_SHEET,
                          path: str | None = None) -> str:
    """Add sheet `sheet` with the allocation and trades tables. Never deletes user content: an existing sheet of
    that name is replaced only if it carries this tool's marker table; otherwise the new sheet gets a number."""
    alloc = [["Asset class", "Value", "Current %", "Target %", "Drift (pp)", "Post-trade %"]]
    post = prep["rebalance"]["post_trade_pct"]
    for c in prep["allocation"]["classes"]:
        alloc.append([c["asset_class"], Decimal(c["value"]), Decimal(c["current_pct"]), Decimal(c["target_pct"]),
                      Decimal(c["drift_pp"]), Decimal(post[c["asset_class"]])])
    for g in prep["allocation"]["groups"]:
        alloc.append([f"{g['group']} total", Decimal(g["value"]), Decimal(g["current_pct"]), Decimal(g["target_pct"]),
                      Decimal(g["drift_pp"]),
                      sum((Decimal(post[k]) for k in g["classes"]), Decimal(0))])
    trades = [["Account", "Side", "Ticker", "Asset class", "Amount", "Note"]]
    for t in prep["rebalance"]["trades"]:
        note = f"instead of {t['instead_of']} (wash sale)" if t.get("instead_of") else ""
        trades.append([t["account"], t["side"], t["ticker"], t["asset_class"], Decimal(t["amount"]), note])
    if len(trades) == 1:
        trades.append(["No trades: allocation within band", "", "", "", Decimal(0), ""])

    lines = [f"tell application id {q(NUMBERS_ID)}", *(_resolve_doc(path) if path else []),
             f"\ttell {_doc(document, path)}",
             f"\t\tset nm to {q(sheet)}",
             "\t\tif exists sheet nm then",
             f"\t\t\tif exists table {q(MARKER_TABLE)} of sheet nm then",
             "\t\t\t\tdelete sheet nm",
             "\t\t\telse",
             "\t\t\t\tset i to 2",
             "\t\t\t\trepeat while exists sheet (nm & \" \" & i)",
             "\t\t\t\t\tset i to i + 1",
             "\t\t\t\tend repeat",
             "\t\t\t\tset nm to nm & \" \" & i",
             "\t\t\tend if",
             "\t\tend if",
             "\t\tset s to make new sheet with properties {name:nm}",
             "\t\ttell s",
             "\t\t\tset t1 to table 1",
             f"\t\t\tset name of t1 to {q(MARKER_TABLE)}",
             f"\t\t\tset column count of t1 to {len(alloc[0])}",
             f"\t\t\tset row count of t1 to {len(alloc)}"]
    _fill(lines, "t1", alloc, "\t\t\t")
    lines += [f"\t\t\tset format of range {q(f'B2:B{len(alloc)}')} of t1 to currency",
              f"\t\t\tset t2 to make new table with properties {{name:{q('Muselet Trades')}, "
              f"column count:{len(trades[0])}, row count:{len(trades)}}}",
              "\t\t\tset {x0, y0} to position of t1",
              "\t\t\tset position of t2 to {x0, y0 + (height of t1) + 40}"]
    _fill(lines, "t2", trades, "\t\t\t")
    lines += [f"\t\t\tset format of range {q(f'E2:E{len(trades)}')} of t2 to currency",
              "\t\tend tell",
              "\t\tset active sheet to s",
              "\tend tell",
              "end tell"]
    return "\n".join(lines) + "\n"


def notes_brief_script(prep: dict, phrasing: dict | None = None, folder: str = "Clients",
                       title: str | None = None, reveal: bool = False) -> str:
    """Write the brief to the note titled `title` (tagged "(Muselet)") in `folder`: update it if this tool made it
    before, else create it. Never deletes notes. Notes names a note after its first line, so the tag is the h1."""
    title = title or NOTE_TITLE.format(household=prep["household"])
    body = re.sub(r"^<h1>.*?</h1>", "", brief_html(brief_markdown(prep, phrasing)), count=1)
    body = f"<h1>{html.escape(title, quote=True)}</h1>" + body
    return "\n".join([
        f"tell application id {q(NOTES_ID)}",
        "\tset acct to default account",
        f"\tif not (exists folder {q(folder)} of acct) then make new folder at acct with properties {{name:{q(folder)}}}",
        f"\tset f to folder {q(folder)} of acct",
        f"\tset hits to (every note of f whose name is {q(title)})",
        "\tif (count of hits) > 0 then",
        "\t\tset n to item 1 of hits",
        f"\t\tset body of n to {q(body)}",
        "\telse",
        f"\t\tset n to make new note at f with properties {{name:{q(title)}, body:{q(body)}}}",
        "\tend if",
        *(["\tactivate", "\tshow n"] if reveal else []),
        "end tell",
    ]) + "\n"


CALENDAR_ID = "com.apple.iCal"


def calendar_lookup_script(name: str, days: int = 30) -> str:
    """Bring Calendar forward, find the earliest event in [today, today + days) whose title contains `name`,
    show its day and return "summary<LF>start ISO<LF>end ISO" (empty string when there is none)."""
    return "\n".join([
        f"tell application id {q(CALENDAR_ID)}",
        "\tactivate",
        "\tset d0 to (current date) - (time of (current date))",
        f"\tset d1 to d0 + {int(days)} * days",
        "\tset best to missing value",
        "\trepeat with c in calendars",
        f"\t\trepeat with e in (every event of c whose summary contains {q(name)} and "
        "start date is greater than or equal to d0 and start date is less than d1)",
        "\t\t\tif best is missing value then",
        "\t\t\t\tset best to contents of e",
        "\t\t\telse if start date of e < start date of best then",
        "\t\t\t\tset best to contents of e",
        "\t\t\tend if",
        "\t\tend repeat",
        "\tend repeat",
        "\tif best is missing value then return \"\"",
        "\tset s to start date of best",
        "\tswitch view to day view",
        "\tview calendar at s",
        "\treturn (summary of best) & linefeed & (s as «class isot» as string) & linefeed & "
        "((end date of best) as «class isot» as string)",
        "end tell",
    ]) + "\n"


def numbers_wait_script(path: str, tries: int = 100) -> str:
    """Wait (polling, <= tries x 0.1 s) until Numbers has the document whose file is `path` open."""
    return "\n".join([f"tell application id {q(NUMBERS_ID)}", *_resolve_doc(path, tries=tries),
                      "\treturn POSIX path of ((file of theDoc) as alias)", "end tell"]) + "\n"
