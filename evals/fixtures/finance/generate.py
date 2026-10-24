"""Deterministic generator for the October 2026 finance demo/eval fixtures.

Persona: Alex Rivera, student/freelancer in Berkeley.
Run: python3 evals/fixtures/finance/generate.py   (Python 3.12, stdlib + openpyxl + pillow)
All truth files are computed from the generated CSV, never by hand.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import random
import zipfile
from pathlib import Path

from openpyxl import Workbook
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
YEAR, MONTH, DAYS = 2026, 10, 31
N_ROWS = 120
OPENING_CENTS = 312055

rng = random.Random(1337)

SAMPLED = {
    "Groceries": (["TRADER JOE'S", "SAFEWAY", "BERKELEY BOWL"], -9500, -1200),
    "Dining": (["CHIPOTLE", "SWEETGREEN", "BLUE BOTTLE COFFEE", "DOORDASH"], -4200, -450),
    "Transport": (["BART CLIPPER", "UBER TRIP", "LYFT RIDE", "CHEVRON"], -5800, -250),
    "Shopping": (["AMAZON MKTP", "TARGET", "APPLE STORE"], -12000, -800),
    "Health": (["CVS PHARMACY", "KAISER COPAY"], -4500, -1000),
}
WEIGHTS = {"Groceries": 25, "Dining": 35, "Transport": 25, "Shopping": 10, "Health": 5}

CATEGORY_OF = {
    "PAYROLL ACME LABS": "Income",
    "VENMO FROM SAM": "Income",
    "RENT OAKLAND PROPERTIES": "Rent",
    "PG&E": "Utilities",
    "COMCAST XFINITY": "Utilities",
    "SPOTIFY": "Subscriptions",
    "NETFLIX": "Subscriptions",
    "APPLE ICLOUD": "Subscriptions",
    "OPENAI CHATGPT": "Subscriptions",
    "AMAZON MKTP REFUND": "Shopping",
}
for _cat, (_merchants, _lo, _hi) in SAMPLED.items():
    for _m in _merchants:
        CATEGORY_OF[_m] = _cat

BUDGET = [
    ("Rent", 1650), ("Groceries", 400), ("Dining", 250), ("Transport", 150),
    ("Shopping", 200), ("Subscriptions", 60), ("Utilities", 180), ("Health", 80),
]


def day(d: int) -> str:
    return dt.date(YEAR, MONTH, d).isoformat()


def rand_day() -> str:
    return day(rng.randint(1, DAYS))


def money(cents: int) -> str:
    return f"{cents / 100:.2f}"


def build_rows() -> list[dict]:
    """Rows as dicts with integer cents; returned sorted (stable) by date."""
    fixed: list[tuple[str, str, int]] = [
        (day(1), "PAYROLL ACME LABS", 240000),
        (day(1), "RENT OAKLAND PROPERTIES", -165000),
        (day(15), "PAYROLL ACME LABS", 240000),
        (rand_day(), "VENMO FROM SAM", 4500),
        (rand_day(), "PG&E", rng.randint(-11000, -6000)),
        (rand_day(), "COMCAST XFINITY", -7999),
        (rand_day(), "SPOTIFY", -1199),
        (rand_day(), "NETFLIX", -1549),
        (rand_day(), "APPLE ICLOUD", -299),
        (rand_day(), "OPENAI CHATGPT", -2000),
        (day(9), "UBER TRIP", -2347),
        (day(9), "UBER TRIP", -2347),
        (day(21), "AMAZON MKTP", -6499),
        (day(21), "AMAZON MKTP", -6499),
        (day(24), "APPLE STORE", -129900),
        (day(28), "AMAZON MKTP REFUND", 6499),
    ]
    seen = {(d, m, a) for d, m, a in fixed}

    def sample(cat: str, merchant: str | None = None) -> tuple[str, str, int]:
        merchants, lo, hi = SAMPLED[cat]
        while True:
            row = (rand_day(), merchant or rng.choice(merchants), rng.randint(lo, hi))
            if row not in seen:  # no accidental exact duplicates
                seen.add(row)
                return row

    random_rows = [sample(cat, m) for cat, (ms, _, _) in SAMPLED.items() for m in ms]
    cats, weights = list(WEIGHTS), list(WEIGHTS.values())
    while len(fixed) + len(random_rows) < N_ROWS:
        random_rows.append(sample(rng.choices(cats, weights)[0]))

    rows = sorted(fixed + random_rows, key=lambda r: r[0])
    bal = OPENING_CENTS
    out = []
    for i, (d, m, a) in enumerate(rows, 1):
        bal += a
        out.append({"row": i, "date": d, "desc": m, "cents": a, "bal": bal, "category": CATEGORY_OF[m]})
    return out


def write_statement(rows: list[dict]) -> Path:
    path = OUT / "bank_statement_oct2026.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Date", "Description", "Amount", "Balance"])
        for r in rows:
            w.writerow([r["date"], r["desc"], money(r["cents"]), money(r["bal"])])
    return path


def read_statement(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        rows = []
        for i, r in enumerate(csv.DictReader(f), 1):
            rows.append({
                "row": i, "date": r["Date"], "desc": r["Description"],
                "cents": round(float(r["Amount"]) * 100), "bal": round(float(r["Balance"]) * 100),
                "category": CATEGORY_OF[r["Description"]],
            })
    return rows


def statement_truth(rows: list[dict]) -> dict:
    groups: dict[tuple, list[int]] = {}
    for r in rows:
        groups.setdefault((r["date"], r["desc"], r["cents"]), []).append(r["row"])
    duplicates = [g for g in groups.values() if len(g) > 1]
    assert len(duplicates) == 2 and all(len(g) == 2 for g in duplicates), duplicates

    outliers = [r["row"] for r in rows if r["desc"] == "APPLE STORE" and r["cents"] == -129900]
    refunds = [r["row"] for r in rows if r["desc"] == "AMAZON MKTP REFUND"]
    assert len(outliers) == 1 and len(refunds) == 1
    # Outlier is the only debit below the sampled ranges' minimum except rent.
    assert all(r["cents"] >= -12000 for r in rows if r["category"] not in ("Rent", "Income") and r["row"] not in outliers)

    spend: dict[str, int] = {c: 0 for c, _ in BUDGET}
    income = 0
    for r in rows:
        if r["category"] == "Income":
            income += r["cents"]
        else:
            spend[r["category"]] -= r["cents"]  # debits add, refunds subtract
    total_spend = sum(spend.values())
    closing = rows[-1]["bal"]
    assert closing == OPENING_CENTS + income - total_spend
    return {
        "rows": [{"row": r["row"], "category": r["category"]} for r in rows],
        "duplicates": duplicates,
        "outliers": outliers,
        "refunds": refunds,
        "category_spend": {c: round(v / 100, 2) for c, v in spend.items()},
        "total_income": round(income / 100, 2),
        "total_spend": round(total_spend / 100, 2),
        "net": round((income - total_spend) / 100, 2),
        "opening_balance": round(OPENING_CENTS / 100, 2),
        "closing_balance": round(closing / 100, 2),
    }


def write_budget(truth: dict) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Budget"
    ws.append(["Category", "Budget", "Actual", "Remaining"])
    for cat, b in BUDGET:
        ws.append([cat, b, None, None])
    ws.column_dimensions["A"].width = 16
    fixed_time = dt.datetime(2026, 10, 1, 9, 0, 0)
    wb.properties.creator = "Alex Rivera"
    wb.properties.created = fixed_time
    buf = io.BytesIO()
    wb.save(buf)
    # openpyxl stamps `modified` with now(); rewrite the zip with fixed metadata so output is byte-stable.
    src = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    stamp = fixed_time.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    with zipfile.ZipFile(OUT / "budget_oct2026.xlsx", "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                start = data.index(b"<dcterms:modified")
                start = data.index(b">", start) + 1
                end = data.index(b"</dcterms:modified>", start)
                data = data[:start] + stamp + data[end:]
            zi = zipfile.ZipInfo(info.filename, date_time=(2026, 10, 1, 9, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(zi, data)

    actual = {c: truth["category_spend"][c] for c, _ in BUDGET}
    remaining = {c: round(b - actual[c], 2) for c, b in BUDGET}
    (OUT / "budget_oct2026.truth.json").write_text(json.dumps({
        "sheet": "Budget",
        "categories": [c for c, _ in BUDGET],
        "budget": dict(BUDGET),
        "actual": actual,
        "remaining": remaining,
        "over_budget": [c for c, _ in BUDGET if remaining[c] < 0],
    }, indent=2) + "\n")


ADDRESSES = {
    "TRADER JOE'S": "1885 University Ave, Berkeley, CA 94703",
    "SAFEWAY": "1444 Shattuck Pl, Berkeley, CA 94709",
    "BERKELEY BOWL": "2020 Oregon St, Berkeley, CA 94703",
    "CHIPOTLE": "2311 Telegraph Ave, Berkeley, CA 94704",
    "SWEETGREEN": "1890 Shattuck Ave, Berkeley, CA 94704",
    "BLUE BOTTLE COFFEE": "2118 University Ave, Berkeley, CA 94704",
    "TARGET": "2187 Shattuck Ave, Berkeley, CA 94704",
    "CVS PHARMACY": "2300 Shattuck Ave, Berkeley, CA 94704",
    "CHEVRON": "1800 University Ave, Berkeley, CA 94703",
    "PHILZ COFFEE": "1600 Shattuck Ave, Berkeley, CA 94709",
}
ITEMS = {
    "TRADER JOE'S": ["BANANAS", "MANDARIN CHICKEN", "OAT MILK", "EVERYTHING BAGELS", "DARK CHOC PB CUPS", "FROZEN GYOZA"],
    "SAFEWAY": ["LARGE EGGS 12CT", "WHOLE MILK GAL", "SOURDOUGH LOAF", "CHICKEN THIGHS", "APPLES GALA", "PASTA SAUCE"],
    "BERKELEY BOWL": ["AVOCADO", "HEIRLOOM TOMATO", "TOFU FIRM", "BULK GRANOLA", "KALE BUNCH", "GREEK YOGURT"],
    "CHIPOTLE": ["BURRITO BOWL", "CHIPS & GUAC", "SPARKLING WATER", "TACOS (3)"],
    "SWEETGREEN": ["HARVEST BOWL", "KALE CAESAR", "SPICY CASHEW", "LEMONADE"],
    "BLUE BOTTLE COFFEE": ["NEW ORLEANS ICED", "OAT LATTE", "CROISSANT", "DRIP COFFEE"],
    "TARGET": ["USB-C CABLE", "NOTEBOOK 3PK", "DISH SOAP", "SOCKS 6PK", "DESK LAMP"],
    "CVS PHARMACY": ["IBUPROFEN 100CT", "TOOTHPASTE", "VITAMIN D3", "BAND-AIDS"],
    "CHEVRON": ["UNLEADED 87", "CAR WASH", "WATER 1L"],
    "PHILZ COFFEE": ["MINT MOJITO ICED", "TESORA", "PHILTERED SOUL"],
}
TAX_RATE = 0.1025


def transpose_total(cents: int) -> int:
    """Swap two adjacent differing digits of the amount (rightmost pair first)."""
    s = f"{cents:d}"
    for i in range(len(s) - 1, 0, -1):
        if s[i] != s[i - 1]:
            t = s[: i - 1] + s[i] + s[i - 1] + s[i + 1:]
            if t[0] != "0":
                return int(t)
    raise ValueError(cents)


def split_items(merchant: str, total: int) -> tuple[list[tuple[str, int]], int, int]:
    tax = round(total - total / (1 + TAX_RATE))
    subtotal = total - tax
    n = rng.randint(2, 4)
    names = rng.sample(ITEMS[merchant], min(n, len(ITEMS[merchant])))
    n = len(names)
    cuts = sorted(rng.sample(range(1, subtotal), n - 1))
    parts = [b - a for a, b in zip([0] + cuts, cuts + [subtotal])]
    return list(zip(names, parts)), subtotal, tax


def load_font(size: int) -> ImageFont.ImageFont:
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/Library/Fonts/Courier New.ttf",
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def render_receipt(path: Path, merchant: str, date: str, items, subtotal: int, tax: int, total: int) -> None:
    img = Image.new("RGB", (600, 900), "white")
    draw = ImageDraw.Draw(img)
    big, font = load_font(30), load_font(20)
    y = 50

    def center(text: str, f, dy: int) -> None:
        nonlocal y
        w = draw.textlength(text, font=f)
        draw.text(((600 - w) / 2, y), text, fill="black", font=f)
        y += dy

    def lr(left: str, right: str, f=font, dy: int = 34) -> None:
        nonlocal y
        draw.text((50, y), left, fill="black", font=f)
        draw.text((550 - draw.textlength(right, font=f), y), right, fill="black", font=f)
        y += dy

    center(merchant, big, 50)
    center(ADDRESSES[merchant], load_font(16), 40)
    d = dt.date.fromisoformat(date)
    center(f"{d.strftime('%m/%d/%Y')}  {rng.randint(8, 21):02d}:{rng.randint(0, 59):02d}", font, 60)
    rule = "-" * 44
    center(rule, font, 40)
    for name, c in items:
        lr(name, money(c))
    center(rule, font, 40)
    lr("SUBTOTAL", money(subtotal))
    lr(f"TAX {TAX_RATE * 100:.2f}%", money(tax))
    y += 10
    lr("TOTAL", money(total), big, 60)
    center("VISA **** 4417", font, 40)
    center("THANK YOU!", font, 40)
    img.save(path, optimize=False)


def write_receipts(rows: list[dict]) -> None:
    rdir = OUT / "receipts"
    rdir.mkdir(exist_ok=True)
    md_count: dict[tuple, int] = {}
    for r in rows:
        md_count[(r["desc"], r["date"])] = md_count.get((r["desc"], r["date"]), 0) + 1
    # Candidates: debit rows at receipt-printing merchants, unique merchant+date, not anomaly rows.
    cands = [r for r in rows if r["desc"] in ADDRESSES and r["cents"] < 0 and md_count[(r["desc"], r["date"])] == 1]
    picks = rng.sample(cands, 7)
    picks.sort(key=lambda r: r["row"])
    while len(str(-picks[6]["cents"])) < 3 or len(set(str(-picks[6]["cents"]))) < 2:
        picks[6] = rng.choice([c for c in cands if c not in picks])

    truth = {}
    specs = []
    for i, r in enumerate(picks[:6], 1):
        specs.append((i, r["desc"], r["date"], -r["cents"], r["row"], "matched"))
    r7 = picks[6]
    specs.append((7, r7["desc"], r7["date"], transpose_total(-r7["cents"]), r7["row"], "amount_mismatch"))
    philz_total = rng.randint(450, 1400)
    specs.append((8, "PHILZ COFFEE", rand_day(), philz_total, None, "no_match"))

    for i, merchant, date, total, row, status in specs:
        items, subtotal, tax = split_items(merchant, total)
        name = f"receipt_{i:02d}.png"
        render_receipt(rdir / name, merchant, date, items, subtotal, tax, total)
        entry = {"match_row": row, "status": status, "total": round(total / 100, 2), "merchant": merchant, "date": date}
        if status == "amount_mismatch":
            entry["statement_amount"] = round(-r7["cents"] / 100, 2)
        truth[name] = entry
    assert all(r["desc"] != "PHILZ COFFEE" for r in rows)
    (OUT / "receipts.truth.json").write_text(json.dumps(truth, indent=2) + "\n")


def main() -> None:
    rows = build_rows()
    assert len(rows) == N_ROWS
    path = write_statement(rows)
    rows = read_statement(path)  # truth is computed from the CSV as written
    truth = statement_truth(rows)
    (OUT / "bank_statement_oct2026.truth.json").write_text(json.dumps(truth, indent=2) + "\n")
    write_budget(truth)
    write_receipts(rows)
    print(json.dumps({k: truth[k] for k in ("duplicates", "outliers", "refunds", "category_spend",
                                             "total_income", "total_spend", "net", "closing_balance")}, indent=1))


if __name__ == "__main__":
    main()
