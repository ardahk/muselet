"""AppleScript generators (strings only; the app executes them). Every interpolated value is escaped."""

from __future__ import annotations

from decimal import Decimal

from .brief import brief_html, brief_markdown

NUMBERS_ID = "com.apple.Numbers"
NOTES_ID = "com.apple.Notes"
GREEN = (50886, 61423, 52942)    # rgb(198, 239, 206) in Numbers' 16-bit channels
AMBER = (65535, 58853, 39321)    # rgb(255, 229, 153)
HOLDINGS_COLUMNS = "A", "J"      # Account .. Unrealized G/L
NOTE_TITLE = "{household} — annual review prep"


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


def _doc(document: str | None) -> str:
    return f"document {q(document)}" if document else "front document"


def _rgb(c: tuple[int, int, int]) -> str:
    return "{" + ", ".join(str(v) for v in c) + "}"


def numbers_highlight_script(prep: dict, document: str | None = None, sheet: str = "Holdings") -> str:
    """Green = harvestable TLH lots, amber = wash-sale-blocked lots. Sheet row = CSV data row + 1 (header)."""
    lines = [f"tell application id {q(NUMBERS_ID)}",
             f"\ttell table 1 of sheet {q(sheet)} of {_doc(document)}"]
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


def numbers_review_script(prep: dict, document: str | None = None, sheet: str = "Review") -> str:
    """Replace sheet `sheet` with an Allocation table and a Trades table."""
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

    lines = [f"tell application id {q(NUMBERS_ID)}",
             f"\ttell {_doc(document)}",
             f"\t\tif exists sheet {q(sheet)} then delete sheet {q(sheet)}",
             f"\t\tset s to make new sheet with properties {{name:{q(sheet)}}}",
             "\t\ttell s",
             "\t\t\tset t1 to table 1",
             f"\t\t\tset name of t1 to {q('Allocation')}",
             f"\t\t\tset column count of t1 to {len(alloc[0])}",
             f"\t\t\tset row count of t1 to {len(alloc)}"]
    _fill(lines, "t1", alloc, "\t\t\t")
    lines += [f"\t\t\tset format of range {q(f'B2:B{len(alloc)}')} of t1 to currency",
              f"\t\t\tset t2 to make new table with properties {{name:{q('Trades')}, "
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
    """Create (or replace) the prep note in `folder` of the default Notes account; `reveal` brings it on screen."""
    title = title or NOTE_TITLE.format(household=prep["household"])
    body = brief_html(brief_markdown(prep, phrasing))
    return "\n".join([
        f"tell application id {q(NOTES_ID)}",
        "\tset acct to default account",
        f"\tif not (exists folder {q(folder)} of acct) then make new folder at acct with properties {{name:{q(folder)}}}",
        f"\tset f to folder {q(folder)} of acct",
        f"\trepeat with n in (get every note of f whose name is {q(title)})",
        "\t\tdelete n",
        "\tend repeat",
        f"\t{'set n to ' if reveal else ''}make new note at f with properties {{name:{q(title)}, body:{q(body)}}}",
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


def numbers_wait_script(prefix: str = "portfolio", tries: int = 100) -> str:
    """Wait (polling, <= tries x 0.1 s) until Numbers has a document whose name starts with `prefix`; return its name."""
    return "\n".join([
        f"tell application id {q(NUMBERS_ID)}",
        f"\trepeat {int(tries)} times",
        f"\t\tif (count of (every document whose name starts with {q(prefix)})) > 0 then exit repeat",
        "\t\tdelay 0.1",
        "\tend repeat",
        f"\treturn name of first document whose name starts with {q(prefix)}",
        "end tell",
    ]) + "\n"
