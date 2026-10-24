"""Merchant -> budget category. Keyword rules first; the injected decision model only for unknown merchants.

Rules are general merchant knowledge (chains, transit, utilities, streaming), matched on whole words of the
normalized description. The most specific phrase wins (more words, then more letters), so `UBER EATS` beats
`UBER`; remaining ties go to `TIE_PRIORITY`. Ambiguous single words (RENT, SHELL) only count when they are the
whole description (`EXACT`). Credits are `Income` only when an income keyword says so; refunds take the
category of the debit they reverse; any other credit (transfers, P2P, rewards) is asked about, never assumed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .statement import Txn, normalize_merchant

INCOME = "Income"
UNCATEGORIZED = "Uncategorized"
CONFIDENCE_THRESHOLD = 0.6
RULE_CONFIDENCE = 1.0

Decide = Callable[[str, list[str]], Mapping[str, float]]

KEYWORDS: dict[str, list[str]] = {
    INCOME: ["PAYROLL", "DIRECT DEP", "DIRECT DEPOSIT", "SALARY", "INTEREST PAYMENT", "TAX REFUND"],
    "Rent": ["RENT PAYMENT", "RENT PMT", "PROPERTY MGMT", "PROPERTY MANAGEMENT", "PROPERTIES", "APARTMENTS", "LEASING", "LANDLORD"],
    "Utilities": ["PGE", "PG E", "COMCAST", "XFINITY", "ATT", "VERIZON", "T MOBILE", "TMOBILE", "SPECTRUM",
                  "EBMUD", "WATER DISTRICT", "EDISON", "ELECTRIC", "SONIC NET", "GOOGLE FI", "MINT MOBILE"],
    "Subscriptions": ["SPOTIFY", "NETFLIX", "HULU", "DISNEY PLUS", "DISNEYPLUS", "HBO MAX", "MAX COM", "ICLOUD",
                      "APPLE COM BILL", "APPLE MUSIC", "APPLE TV", "YOUTUBE PREMIUM", "AMAZON PRIME", "PRIME VIDEO",
                      "AUDIBLE", "CHATGPT", "OPENAI", "ANTHROPIC", "CLAUDE AI", "ADOBE", "DROPBOX", "GITHUB",
                      "NOTION", "PATREON", "NYTIMES", "DUOLINGO", "PELOTON"],
    "Transport": ["UBER", "LYFT", "BART", "CLIPPER", "CALTRAIN", "MUNI", "AMTRAK", "CHEVRON", "SHELL OIL",
                  "SHELL SERVICE", "SHELL STATION", "EXXON", "ARCO", "VALERO", "MOBIL", "COSTCO GAS", "PARKING",
                  "PARKMOBILE", "PAYBYPHONE", "SPOTHERO", "FASTRAK", "BRIDGE TOLL", "TOLL ROAD", "LIME RIDE",
                  "LIME SCOOTER", "WAYMO", "GREYHOUND"],
    "Dining": ["UBER EATS", "DOORDASH", "GRUBHUB", "POSTMATES", "CAVIAR", "STARBUCKS", "PEETS", "BLUE BOTTLE",
               "PHILZ", "DUNKIN", "COFFEE", "CAFE", "CHIPOTLE", "SWEETGREEN", "MCDONALDS", "IN N OUT", "TACO BELL",
               "PANDA EXPRESS", "PANERA", "SHAKE SHACK", "DOMINOS", "PIZZA", "RESTAURANT", "TAQUERIA", "SUSHI",
               "BURGER", "BOBA", "BAKERY", "BAR GRILL"],
    "Groceries": ["TRADER JOES", "SAFEWAY", "WHOLE FOODS", "WHOLEFDS", "KROGER", "SPROUTS", "RALPHS", "LUCKY",
                  "ALDI", "INSTACART", "GROCERY", "GROCERIES", "FARMERS MARKET", "99 RANCH", "H MART", "SMART FINAL",
                  "COSTCO"],
    "Shopping": ["AMAZON", "AMZN", "TARGET", "WALMART", "APPLE STORE", "BEST BUY", "IKEA", "EBAY", "ETSY",
                 "HOME DEPOT", "UNIQLO", "NORDSTROM", "MACYS", "MARSHALLS", "TJ MAXX"],
    "Health": ["CVS", "WALGREENS", "RITE AID", "PHARMACY", "KAISER", "SUTTER HEALTH", "DENTAL", "DENTIST", "CLINIC",
               "MEDICAL", "HOSPITAL", "COPAY", "OPTOMETRY", "LABCORP", "QUEST DIAGNOSTICS"],
}
# Whole-description rules for words that are ambiguous inside longer names (RENT THE RUNWAY, SHELL SHACK).
EXACT: dict[str, str] = {"RENT": "Rent", "SHELL": "Transport"}
TIE_PRIORITY = ("Dining", "Groceries", "Health", "Shopping", "Subscriptions", "Utilities", "Transport", "Rent",
                INCOME)
REFUND_WORDS = ("REFUND", "RETURN", "REVERSAL", "CREDIT ADJ", "CHARGEBACK")


def _phrases(rules: Mapping[str, list[str]]) -> list[tuple[tuple[str, ...], str]]:
    out = [(tuple(normalize_merchant(k).split()), cat) for cat, ks in rules.items() for k in ks]
    return [p for p in out if p[0]]


_RULES = _phrases(KEYWORDS)
_INCOME_RULES = [(p, c) for p, c in _RULES if c == INCOME]


def strip_refund_words(norm: str) -> str:
    toks = norm.split()
    drop = {w for p in REFUND_WORDS for w in p.split()}
    return " ".join(t for t in toks if t not in drop)


def is_refund_text(description: str) -> bool:
    norm = " " + normalize_merchant(description) + " "
    return any(f" {w} " in norm for w in REFUND_WORDS)


def _rank(phrase: tuple[str, ...], cat: str) -> tuple:
    prio = TIE_PRIORITY.index(cat) if cat in TIE_PRIORITY else len(TIE_PRIORITY)
    return (len(phrase), len("".join(phrase)), -prio)


def _longest(toks: tuple[str, ...], table) -> tuple[int, str, tuple[str, ...]] | None:
    """The most specific phrase of `table` found in `toks`: more words, then more letters, then TIE_PRIORITY."""
    best, best_rank = None, None
    for phrase, cat in table:
        n = len(phrase)
        if any(toks[i:i + n] == phrase for i in range(len(toks) - n + 1)):
            r = _rank(phrase, cat)
            if best_rank is None or r > best_rank:
                best, best_rank = (n, cat, phrase), r
    return best


def is_income_text(description: str) -> bool:
    """Payroll-like credits, matched before refund words are stripped ("TAX REFUND" is income)."""
    return _longest(tuple(normalize_merchant(description).split()), _INCOME_RULES) is not None


def rule_match(description: str, user_rules: Mapping[str, str] | None = None) -> tuple[str, str] | None:
    """(category, rule id) for a description: user rules first, then the longest keyword phrase."""
    toks = tuple(strip_refund_words(normalize_merchant(description)).split())
    if user_rules:
        hit = _longest(toks, [(tuple(normalize_merchant(k).split()), c) for k, c in user_rules.items()])
        if hit:
            return hit[1], "user:" + " ".join(hit[2])
    hit = _longest(tuple(normalize_merchant(description).split()), _INCOME_RULES) or _longest(toks, _RULES)
    if hit:
        return hit[1], "keyword:" + " ".join(hit[2])
    whole = " ".join(toks)
    return (EXACT[whole], "exact:" + whole) if whole in EXACT else None


def decision_text(t: Txn) -> str:
    kind = "credit" if t.amount > 0 else "debit"
    return f'Bank transaction "{t.description}", {kind} ${abs(t.amount)}, on {t.date.isoformat()}. Budget category?'


def categorize_with_evidence(
    txns: list[Txn], categories: list[str], decide: Decide | None = None,
    user_rules: Mapping[str, str] | None = None,
) -> tuple[dict[int, tuple[str, float, str]], dict[int, str]]:
    """Like `categorize`, plus {row: rule id} saying why (keyword phrase, refund link, model, ask)."""
    from .detect import find_refunds  # local: detect uses rule_match

    out: dict[int, tuple[str, float, str]] = {}
    why: dict[int, str] = {}
    refunds = set(find_refunds(txns))
    cache: dict[tuple[str, bool], tuple[str, float, str, str]] = {}
    for t in txns:
        credit = t.amount > 0 and t.row not in refunds
        # Debits and refunds pick a spending category; other credits may also be Income.
        options = ([INCOME] if credit else []) + [c for c in categories if c != INCOME]
        hit = rule_match(t.description, user_rules)
        if hit and (hit[0] == INCOME and credit or hit[0] != INCOME and (hit[0] in options or not categories)):
            out[t.row] = (hit[0], RULE_CONFIDENCE, "rule")
            why[t.row] = hit[1]
            continue
        key = (strip_refund_words(normalize_merchant(t.description)), credit)
        if key not in cache:
            if decide is None or not categories:
                rule = "ask:credit_not_income_or_refund" if credit else "ask:no_rule_no_model"
                cache[key] = (UNCATEGORIZED, 0.0, "ask", rule)
            else:
                probs = {o: float(p) for o, p in decide(decision_text(t), options).items() if o in options}
                top = max(options, key=lambda o: probs.get(o, 0.0))
                p = probs.get(top, 0.0)
                if p >= CONFIDENCE_THRESHOLD:
                    cache[key] = (top, p, "model", f"model:p={p:.2f}")
                else:
                    cache[key] = (top, p, "ask", f"ask:model_p={p:.2f}<{CONFIDENCE_THRESHOLD}")
        cat, p, src, rule = cache[key]
        out[t.row] = (cat, p, src)
        why[t.row] = rule
    _link_refunds(txns, refunds, out, why)
    return out, why


def _link_refunds(txns, refunds, out, why) -> None:
    """A refund inherits the category of the debit it reverses when its own text gave no rule."""
    from .detect import reversed_debit

    for r in sorted(refunds):
        if out[r][2] == "rule":
            continue
        orig = reversed_debit(txns, r)
        if orig is not None and out[orig][2] in ("rule", "model"):
            out[r] = out[orig]
            why[r] = f"refund_of:row{orig}"


def categorize(
    txns: list[Txn], categories: list[str], decide: Decide | None = None,
    user_rules: Mapping[str, str] | None = None,
) -> dict[int, tuple[str, float, str]]:
    """row -> (category, confidence, source) with source "rule" | "model" | "ask".

    `decide(text, options) -> {option: prob}` is the on-device decision model; it is called once per unknown
    merchant (for credits that are neither income keywords nor refunds, the options include Income).
    Below `CONFIDENCE_THRESHOLD` the row is "ask": escalate to the user instead of guessing (the
    category is then the model's best guess, or `Uncategorized` without a model). `user_rules` are
    merchant -> category answers the user already gave; they act as rules.
    """
    return categorize_with_evidence(txns, categories, decide, user_rules)[0]


def rule_category(description: str, user_rules: Mapping[str, str] | None = None) -> str | None:
    hit = rule_match(description, user_rules)
    return hit[0] if hit else None

