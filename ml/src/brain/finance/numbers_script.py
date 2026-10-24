"""AppleScript source for Apple Numbers. Each function returns one script = one `osascript` run.

Bulk reads fetch every cell value in a single Apple Event and build TSV locally; bulk writes are one
script with a loop (no UI clicks). All strings are escaped with `q`. Statement rows are 1-based and
offset by `header_rows` to get the table row.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

APP = 'tell application id "com.apple.Numbers"'

RED = (65535, 49087, 49087)
ORANGE = (65535, 52428, 30840)
WEEKEND = (61166, 61166, 65535)
RESOLVED = (52428, 65535, 52428)  # a duplicate that was already refunded, and its refund
RS = "character id 30"  # record separator between tables in one multi-table read


def q(s) -> str:
    """AppleScript string literal."""
    s = str(s).replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\r\n", "\n").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return f'"{s}"'


def lit(v) -> str:
    """AppleScript literal for a cell value: numbers stay numeric, None clears the cell."""
    if v is None:
        return '""'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, Decimal)):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    return q(v)


def lst(values: Sequence) -> str:
    return "{" + ", ".join(lit(v) for v in values) + "}"


def _ref(kind: str, v) -> str:
    return f"{kind} {v}" if isinstance(v, int) else f"{kind} {q(v)}"


def _doc(document) -> str:
    return "document 1" if document is None else _ref("document", document)


def _sheet(sheet, document) -> str:
    return f"{'active sheet' if sheet is None else _ref('sheet', sheet)} of {_doc(document)}"


def _table(table, sheet, document) -> str:
    return f"{_ref('table', 1 if table is None else table)} of {_sheet(sheet, document)}"


def _col(column) -> str:
    return _ref("column", column)


def _wrap(target: str, body: list[str], after: list[str] = ()) -> str:
    lines = [APP, f"\ttell {target}"] + ["\t\t" + b for b in body] + ["\tend tell", "end tell"] + list(after)
    return "\n".join(lines) + "\n"


def read_table_tsv(cell_range: str | None = None, *, table=None, sheet=None, document=None,
                   formatted: bool = True) -> str:
    """Return the range (default: the whole table) as TSV text, rows joined by linefeed."""
    prop = "formatted value" if formatted else "value"
    rng = "cell range" if cell_range is None else f"range {q(cell_range)}"
    return _wrap(_table(table, sheet, document), [
        f"set r to {rng}",
        "set ncols to count of columns of r",
        f"set vals to {prop} of cells of r",
    ], [
        "set out to {}",
        "set rowVals to {}",
        "repeat with v in vals",
        "\tset v to contents of v",
        '\tif v is missing value then set v to ""',
        "\tset end of rowVals to (v as text)",
        "\tif (count of rowVals) = ncols then",
        "\t\tset end of out to rowVals",
        "\t\tset rowVals to {}",
        "\tend if",
        "end repeat",
        "set lines_ to {}",
        "set AppleScript's text item delimiters to tab",
        "repeat with rv in out",
        "\tset end of lines_ to ((contents of rv) as text)",
        "end repeat",
        "set AppleScript's text item delimiters to linefeed",
        "set tsv to lines_ as text",
        'set AppleScript\'s text item delimiters to ""',
        "return tsv",
    ])


def write_column(column, values: Sequence, *, start_row: int = 2, table=None, sheet=None, document=None) -> str:
    """Write `values` down one column starting at table row `start_row` (1-based, header is row 1)."""
    return _wrap(_table(table, sheet, document), [
        f"set vals to {lst(values)}",
        "repeat with i from 1 to count of vals",
        f"\tset value of cell (i + {start_row - 1}) of {_col(column)} to item i of vals",
        "end repeat",
    ])


def write_budget(actual: Mapping[str, Decimal], remaining: Mapping[str, Decimal], *, category_column="A",
                 budget_column="B", actual_column="C", remaining_column="D", remaining_formula: bool = False,
                 notes: Mapping[str, str] | None = None, note_column="E", table=None, sheet=None,
                 document=None) -> str:
    """Fill Actual and Remaining by looking up each category's row by name (row order may differ).

    With `notes` ({category: text}), also write a Note column (header "Note"; categories without a note get
    an empty cell), e.g. "Needs review" while some rows are still uncategorized.
    """
    return _wrap(_table(table, sheet, document), budget_body(
        actual, remaining, category_column=category_column, budget_column=budget_column,
        actual_column=actual_column, remaining_column=remaining_column, remaining_formula=remaining_formula,
        notes=notes, note_column=note_column))


def budget_body(actual, remaining, *, category_column="A", budget_column="B", actual_column="C",
                remaining_column="D", remaining_formula=False, notes=None, note_column="E") -> list[str]:
    names = list(actual)
    rem = (f'("={budget_column}" & r & "-{actual_column}" & r)' if remaining_formula else "item k of rems")
    note_lines = []
    head = []
    if notes is not None:
        head = [f"set notes to {lst([notes.get(n, '') for n in names])}",
                f"set value of cell 1 of {_col(note_column)} to {q('Note')}"]
        note_lines = [f"\t\t\t\tset value of cell r of {_col(note_column)} to item k of notes"]
    return [
        f"set names to {lst(names)}",
        f"set acts to {lst([actual[n] for n in names])}",
        f"set rems to {lst([remaining[n] for n in names])}",
        *head,
        f"set cats to value of cells of {_col(category_column)}",
        "set written to 0",
        "repeat with r from 1 to count of cats",
        "\tset c to item r of cats",
        "\tif c is not missing value then",
        "\t\trepeat with k from 1 to count of names",
        "\t\t\tif (c as text) is (item k of names) then",
        f"\t\t\t\tset value of cell r of {_col(actual_column)} to item k of acts",
        f"\t\t\t\tset value of cell r of {_col(remaining_column)} to {rem}",
        *note_lines,
        "\t\t\t\tset written to written + 1",
        "\t\t\tend if",
        "\t\tend repeat",
        "\tend if",
        "end repeat",
        "return written",
    ]


def color_rows(colors: Mapping[int, tuple[int, int, int]], *, header_rows: int = 1, table=None, sheet=None,
               document=None) -> str:
    """Set the background color of statement rows ({row: (r, g, b)} with 16-bit channels)."""
    return _wrap(_table(table, sheet, document), color_body(colors, header_rows=header_rows))


def color_body(colors: Mapping[int, tuple[int, int, int]], *, header_rows: int = 1) -> list[str]:
    groups: dict[tuple, list[int]] = {}
    for row, rgb in sorted(colors.items()):
        groups.setdefault(tuple(rgb), []).append(row + header_rows)
    body = []
    for rgb, rows in groups.items():
        body += [
            f"repeat with r in {lst(rows)}",
            f"\tset background color of row (contents of r) to {lst(rgb)}",
            "end repeat",
        ]
    return body


def highlight_colors(duplicates: Sequence[Sequence[int]] = (), outliers: Sequence[int] = (),
                     weekend: Sequence[int] = (), resolved: Sequence[int] = ()) -> dict[int, tuple[int, int, int]]:
    """Open duplicates red, outliers orange, refunded duplicates + their refund green, weekend light."""
    colors: dict[int, tuple[int, int, int]] = {r: WEEKEND for r in weekend}
    colors |= {r: RESOLVED for r in resolved}
    colors |= {r: ORANGE for r in outliers}
    colors |= {r: RED for pair in duplicates for r in pair if r not in resolved}
    return colors


def highlight_flags(duplicates: Sequence[Sequence[int]] = (), outliers: Sequence[int] = (),
                    weekend: Sequence[int] = (), resolved: Sequence[int] = (), **kw) -> str:
    """Duplicates red, outliers orange, weekend charges light; stronger flags win on overlap."""
    return color_rows(highlight_colors(duplicates, outliers, weekend, resolved), **kw)


def col_letter(n: int) -> str:
    """1 -> A, 27 -> AA."""
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def category_body(column: int, values: Sequence, *, header: str = "Category", header_rows: int = 1) -> list[str]:
    """Grow the table to `column` columns if needed, then write the header and one value per statement row."""
    letter = col_letter(column)
    return [
        f"if column count < {column} then set column count to {column}",
        f"set value of cell {header_rows} of column {q(letter)} to {q(header)}",
        f"set vals to {lst(values)}",
        "repeat with i from 1 to count of vals",
        f"\tset value of cell (i + {header_rows}) of column {q(letter)} to item i of vals",
        "end repeat",
    ]


def multi(blocks: Sequence[tuple[str, list[str]]]) -> str:
    """One script that runs several `tell <target>` blocks (e.g. statement and budget documents)."""
    lines = [APP]
    for target, body in blocks:
        lines += [f"\ttell {target}"] + ["\t\t" + b for b in body] + ["\tend tell"]
    return "\n".join(lines + ["end tell"]) + "\n"


def list_documents() -> str:
    """One line per open document, front first: `name<TAB>sheet|sheet|...` (empty text when none)."""
    return "\n".join([
        "set out to {}",
        APP,
        "\trepeat with d in documents",
        "\t\tset AppleScript's text item delimiters to \"|\"",
        "\t\tset sheetNames to (name of every sheet of d) as text",
        "\t\tset end of out to (name of d) & tab & sheetNames",
        "\tend repeat",
        "end tell",
        "set AppleScript's text item delimiters to linefeed",
        "set res to out as text",
        "set AppleScript's text item delimiters to \"\"",
        "return res",
    ]) + "\n"


ISO_HANDLERS = [
    "on cellText(v, f)",
    "\tif v is missing value then return \"\"",
    "\tif class of v is date then",
    "\t\tset m to (month of v) as integer",
    "\t\tset d to day of v",
    ("\t\treturn ((year of v) as text) & \"-\" & (text -2 thru -1 of (\"0\" & m)) & \"-\" & "
    "(text -2 thru -1 of (\"0\" & d))"),
    "\tend if",
    "\tif f is missing value then return (v as text)",
    "\treturn f as text",
    "end cellText",
    "",
    "on tableTSV(vals, fvals, nc)",
    "\tset out to {}",
    "\tset rowVals to {}",
    "\trepeat with i from 1 to count of vals",
    "\t\tset end of rowVals to my cellText(item i of vals, item i of fvals)",
    "\t\tif (count of rowVals) = nc then",
    "\t\t\tset AppleScript's text item delimiters to tab",
    "\t\t\tset end of out to rowVals as text",
    "\t\t\tset rowVals to {}",
    "\t\tend if",
    "\tend repeat",
    "\tset AppleScript's text item delimiters to linefeed",
    "\tset s to out as text",
    "\tset AppleScript's text item delimiters to \"\"",
    "\treturn s",
    "end tableTSV",
    "",
]


def read_tables(targets: Sequence[str]) -> str:
    """Read whole tables (each a `table ... of sheet ... of document ...` specifier) in one script.

    The range is bounded by `row count` x `column count`, so the last row is never dropped. Dates are
    coerced to ISO `YYYY-MM-DD` inside AppleScript; every other cell uses its formatted (displayed) value, so
    amounts arrive as text, not binary reals. Tables are joined by ASCII 30, rows by LF, cells by TAB.
    """
    lines = list(ISO_HANDLERS) + ["set results to {}", APP]
    for t in targets:
        lines += [
            f"\ttell {t}",
            "\t\tset nr to row count",
            "\t\tset nc to column count",
            "\t\tset rng to range (\"A1:\" & (name of cell nc of row nr))",
            "\t\tset vals to value of every cell of rng",
            "\t\tset fvals to formatted value of every cell of rng",
            "\tend tell",
            "\tset end of results to my tableTSV(vals, fvals, nc)",
        ]
    lines += ["end tell", f"set AppleScript's text item delimiters to ({RS})", "set res to results as text",
              "set AppleScript's text item delimiters to \"\"", "return res"]
    return "\n".join(lines) + "\n"


def table_ref(table=None, sheet=None, document=None) -> str:
    """`table 1 of sheet 1 of document "x"`-style specifier (sheet None = first sheet, not the active one)."""
    return f"{_ref('table', 1 if table is None else table)} of {_ref('sheet', 1 if sheet is None else sheet)} of " \
           f"{_doc(document)}"


def add_summary_table(rows: Sequence[Sequence], *, name: str = "Muselet Summary", sheet=None,
                      document=None) -> str:
    """Replace (or create) a table `name` on the sheet holding `rows` (first row is the header)."""
    ncols = max((len(r) for r in rows), default=1)
    grid = "{" + ", ".join(lst(list(r) + [None] * (ncols - len(r))) for r in rows) + "}"
    return _wrap(_sheet(sheet, document), [
        f"if exists table {q(name)} then delete table {q(name)}",
        (f"set t to make new table with properties {{name:{q(name)}, row count:{max(len(rows), 1)}, "
        f"column count:{ncols}, header row count:1, header column count:0}}"),
        f"set grid to {grid}",
        "tell t",
        "\trepeat with i from 1 to count of grid",
        "\t\tset rowVals to item i of grid",
        "\t\trepeat with j from 1 to count of rowVals",
        "\t\t\tset value of cell j of row i to item j of rowVals",
        "\t\tend repeat",
        "\tend repeat",
        "end tell",
    ])


def summary_rows(report: Mapping) -> list[list]:
    """Two-column summary (Item, Value) from an `analyze` report."""
    st, b = report["statement"], report["budget"]
    rows: list[list] = [["Item", "Value"],
                        ["Income", st["total_income"]], ["Spend", st["total_spend"]], ["Net", st["net"]],
                        ["Over budget", ", ".join(b["over_budget"]) or "none"],
                        ["Duplicate charges", "; ".join(
                            f"rows {d['rows'][0]} & {d['rows'][1]}"
                            + (f" (refunded, row {d['refund_row']})" if d["status"] == "refunded" else "")
                            for d in report["duplicate_status"]) or "none"],
                        ["Outliers", ", ".join(f"row {r}" for r in report["outliers"]) or "none"],
                        ["Refunds", ", ".join(f"row {r}" for r in report["refunds"]) or "none"],
                        ["Weekend charges", len(report.get("weekend_charges", []))]]
    if b.get("pending"):
        rows.append(["Needs review", f"{len(b['pending']['rows'])} rows"])
    rec = report.get("receipts") or {}
    for status in ("matched", "amount_mismatch", "no_match"):
        ids = [k for k, e in rec.items() if e["status"] == status]
        if rec:
            rows.append([f"Receipts {status.replace('_', ' ')}", len(ids)])
    return rows
