"""Statement and budget loading. Money is `Decimal` quantized to cents; rows are 1-based."""

from __future__ import annotations

import csv
import datetime as dt
import io
import itertools
import json
import re
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Txn:
    row: int
    date: dt.date
    description: str
    amount: Decimal
    balance: Decimal

    @property
    def is_debit(self) -> bool:
        return self.amount < 0


def parse_money(text) -> Decimal:
    """'$1,650.00', '(23.47)', '-23.47', '1 299,00'-free US formats -> Decimal cents."""
    if isinstance(text, Decimal):
        return text.quantize(CENT)
    if isinstance(text, (int, float)):
        return Decimal(str(text)).quantize(CENT)
    s = str(text).strip().replace("\u2212", "-")
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[\s$,()]", "", s)
    if s.endswith("-"):
        neg, s = True, s[:-1]
    try:
        v = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"not a money amount: {text!r}") from None
    return (-v if neg else v).quantize(CENT)


def parse_date(text) -> dt.date:
    if isinstance(text, dt.datetime):
        return text.date()
    if isinstance(text, dt.date):
        return text
    s = str(text).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%b %d, %Y", "%d %b %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"not a date: {text!r}")


def _header_index(header: list[str], *names: str) -> int:
    norm = [h.strip().lower() for h in header]
    for n in names:
        if n in norm:
            return norm.index(n)
    raise ValueError(f"missing column {names[0]!r} in header {header!r}")


def load_statement(csv_text: str) -> list[Txn]:
    """Parse a `Date,Description,Amount,Balance` CSV (or TSV read from Numbers). Debits are negative."""
    text = csv_text.lstrip("\ufeff")
    dialect = "excel-tab" if "\t" in text.split("\n", 1)[0] else "excel"
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        return []
    header = rows[0]
    di = _header_index(header, "date", "posted", "posting date", "transaction date")
    si = _header_index(header, "description", "merchant", "payee", "name")
    ai = _header_index(header, "amount")
    bi = _header_index(header, "balance", "running balance")
    return [
        Txn(i, parse_date(r[di]), r[si].strip(), parse_money(r[ai]), parse_money(r[bi]))
        for i, r in enumerate(rows[1:], 1)
    ]


def opening_balance(txns: list[Txn]) -> Decimal:
    return txns[0].balance - txns[0].amount if txns else Decimal("0.00")


def balance_breaks(txns: list[Txn]) -> list[int]:
    """Rows whose running balance does not equal the previous balance plus the amount."""
    return [b.row for a, b in itertools.pairwise(txns) if a.balance + b.amount != b.balance]


def _xlsx_rows(path: Path) -> list[list[str]]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        sheet = min(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        out = []
        for row in ElementTree.fromstring(z.read(sheet)).iter(f"{{{ns['m']}}}row"):
            cells: dict[int, str] = {}
            for c in row.findall("m:c", ns):
                col = 0
                for ch in re.match(r"[A-Z]+", c.get("r")).group():
                    col = col * 26 + ord(ch) - 64
                v = c.find("m:v", ns)
                is_ = c.find("m:is", ns)
                if c.get("t") == "s" and v is not None:
                    cells[col - 1] = shared[int(v.text)]
                elif is_ is not None:
                    cells[col - 1] = "".join(t.text or "" for t in is_.iter(f"{{{ns['m']}}}t"))
                elif v is not None:
                    cells[col - 1] = v.text or ""
            out.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
        return out


def load_budget(path_or_rows) -> dict[str, Decimal]:
    """`Category,Budget` table -> {category: budget}, in table order.

    Accepts: CSV/TSV text (as exported from Numbers; extra columns and title rows are ignored), a list of
    rows (lists/tuples, optionally with a header, or dicts with Category/Budget keys), a mapping, or a path
    to a .csv/.tsv, .xlsx, or budget truth .json (`{"budget": {...}}`).
    """
    src = path_or_rows
    if isinstance(src, Path) or (isinstance(src, str) and "\n" not in src and Path(src).suffix
                                 and Path(src).exists()):
        p = Path(src)
        if p.suffix.lower() == ".xlsx":
            return load_budget(_xlsx_rows(p))
        if p.suffix.lower() == ".json":
            data = json.loads(p.read_text())
            return load_budget(data.get("budget", data))
        src = p.read_text()
    if isinstance(src, dict):
        return {str(k).strip(): parse_money(v) for k, v in src.items()}
    if isinstance(src, str):
        text = src.lstrip("\ufeff")
        dialect = "excel-tab" if "\t" in text else "excel"
        src = list(csv.reader(io.StringIO(text), dialect))
    rows = list(src)
    if rows and isinstance(rows[0], dict):
        rows = [[r.get("Category", r.get("category", "")), r.get("Budget", r.get("budget", ""))] for r in rows]
    start = 0
    for i, r in enumerate(rows):
        cells = [str(c).strip().lower() for c in r]
        if "category" in cells and "budget" in cells:
            ci, bi, start = cells.index("category"), cells.index("budget"), i + 1
            break
    else:
        ci, bi = 0, 1
    out: dict[str, Decimal] = {}
    for r in rows[start:]:
        if len(r) <= max(ci, bi):
            continue
        name, val = str(r[ci]).strip(), str(r[bi]).strip()
        if not name or not val:
            continue
        try:
            out[name] = parse_money(val)
        except ValueError:
            continue  # title or total rows
    return out


_STRIP_PREFIX = re.compile(r"^(?:SQ|TST|POS|PURCHASE|DEBIT CARD|DEBIT|CHECKCARD|PP|PAYPAL)\s*\*?\s+")


def normalize_merchant(text: str) -> str:
    """Uppercase, drop apostrophes/ampersands, card-processor prefixes, store numbers and punctuation."""
    s = text.upper().replace("'", "").replace("\u2019", "").replace("&", "")
    s = re.sub(r"[^A-Z0-9#*]+", " ", s).strip()
    s = _STRIP_PREFIX.sub("", s)
    s = re.sub(r"\*", " ", s)
    tokens = [t for t in s.split() if not re.fullmatch(r"#?\d+|#\w*|STORE\d+|NO\d+", t)]
    return " ".join(tokens)
