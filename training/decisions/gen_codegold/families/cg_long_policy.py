from __future__ import annotations

import random
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..common import finish_record, key_for_value, round_bands, score_level_for

FAMILY = "cg_long_policy"
SCHEMAS = {
    "travel_medical_reimbursement": {
        "title": "Overseas Emergency Care Reimbursement Schedule",
        "covered": "urgent hospital treatment",
        "exception": "emergency evacuation",
        "other": "elective wellness service",
        "definition": "a treatment record is the dated provider invoice paired with the traveller's itinerary",
        "evidence": "the hospital discharge summary and carrier itinerary",
        "record": "Hospital discharge summary",
        "fact": "The itinerary records the destination and return leg separately from the treatment receipt.",
        "topics": ("ward billing", "carrier itineraries", "provider remittances", "regional care desks"),
        "documents": ("discharge packet", "travel voucher", "clinic ledger", "care review sheet"),
        "offices": ("Global Care Desk", "Claims Annex", "Traveller Services"),
    },
    "employee_relocation_allowance": {
        "title": "Employee Household Relocation Allowance",
        "covered": "household-goods transport",
        "exception": "accessible moving support",
        "other": "temporary storage",
        "definition": "a move date is the handover date on the signed destination lease, not the booking date",
        "evidence": "the destination lease and carrier bill of lading",
        "record": "Carrier bill of lading",
        "fact": "The lease handover date and the carrier pickup date are recorded on separate documents.",
        "topics": ("lease handovers", "carrier inventories", "destination receipts", "move coordinators"),
        "documents": ("handover file", "packing inventory", "carrier ledger", "relocation worksheet"),
        "offices": ("Mobility Office", "People Services", "Relocation Registry"),
    },
    "research_grant_expense": {
        "title": "Laboratory Research Grant Expense Schedule",
        "covered": "laboratory reagents",
        "exception": "urgent equipment repair",
        "other": "conference hospitality",
        "definition": "a grant-period expense is dated by the receiving laboratory's signed goods receipt",
        "evidence": "the laboratory goods receipt and custodian's invoice",
        "record": "Laboratory goods receipt",
        "fact": "The custodian's receipt date may differ from the vendor's invoice date.",
        "topics": ("reagent custody", "laboratory receipts", "grant ledgers", "equipment service"),
        "documents": ("custodian packet", "vendor invoice", "bench register", "grant worksheet"),
        "offices": ("Research Finance", "Laboratory Registry", "Grant Services"),
    },
    "equipment_lease_return": {
        "title": "Leased Equipment Return Adjustment Schedule",
        "covered": "documented wear repair",
        "exception": "safety recall replacement",
        "other": "missing accessory replacement",
        "definition": "a return condition is measured at the signed inspection, not at the courier collection",
        "evidence": "the signed inspection sheet and return waybill",
        "record": "Signed return inspection",
        "fact": "The inspection sheet lists condition findings while the waybill establishes collection timing.",
        "topics": ("inspection findings", "return waybills", "service estimates", "asset registries"),
        "documents": ("inspection packet", "service estimate", "asset ledger", "return worksheet"),
        "offices": ("Asset Review Desk", "Lease Registry", "Equipment Services"),
    },
    "student_fee_withdrawal": {
        "title": "Student Term-Fee Withdrawal Schedule",
        "covered": "tuition withdrawal before census",
        "exception": "medical withdrawal",
        "other": "housing deposit",
        "definition": "a withdrawal date is the timestamp on the registrar's signed status letter",
        "evidence": "the registrar's letter and term-fee receipt",
        "record": "Registrar status letter",
        "fact": "The registrar letter identifies the effective withdrawal date independently of the payment receipt.",
        "topics": ("registrar letters", "term calendars", "fee receipts", "student accounts"),
        "documents": ("status packet", "term receipt", "registrar ledger", "account worksheet"),
        "offices": ("Student Accounts", "Registrar Annex", "Fee Review Office"),
    },
    "parental_leave_pay": {
        "title": "Parental Leave Salary Supplement Schedule",
        "covered": "bonding leave wages",
        "exception": "hospitalization leave",
        "other": "caregiver travel",
        "definition": "the leave start is the first approved day on the signed personnel letter",
        "evidence": "the personnel letter and the child's birth registration",
        "record": "Signed personnel leave letter",
        "fact": "The personnel letter supplies the approved start date; the registration establishes the family event.",
        "topics": ("personnel letters", "leave calendars", "payroll records", "family registrations"),
        "documents": ("leave packet", "payroll ledger", "registration copy", "benefit worksheet"),
        "offices": ("People Operations", "Leave Registry", "Payroll Review"),
    },
    "public_service_accessibility_grant": {
        "title": "Public-Service Access Retrofit Grant",
        "covered": "door-control installation",
        "exception": "urgent ramp repair",
        "other": "general renovation",
        "definition": "a completed retrofit is dated by the inspector's signed acceptance certificate",
        "evidence": "the signed acceptance certificate and contractor's invoice",
        "record": "Inspector acceptance certificate",
        "fact": "The contractor invoice records the charge while the inspector certificate establishes completion.",
        "topics": ("inspection certificates", "contractor invoices", "access plans", "grant registers"),
        "documents": ("acceptance packet", "contractor ledger", "access plan", "grant worksheet"),
        "offices": ("Civic Access Desk", "Works Registry", "Grant Review Office"),
    },
}

OUTCOMES = {
    "not_covered": "outside the scheduled period",
    "late": "received after the filing window",
    "not_eligible": "outside the qualifying activity",
    "exception_authorized": "within the signed exception",
    "full": "payable in full",
    "partial": "payable in part",
}

_FILLER = (
    "The {topic} index at {office} keeps the {document} beside its dated source, so a reviewer can trace each entry back to the original record. The index supports retrieval only; it cannot replace the date or wording on the signed evidence.",
    "When a clerk closes a {topic} task, the {document} remains linked to the case chronology rather than being copied into a summary field. This practice preserves the distinction between an administrative note and a document that proves an event.",
    "The {office} archive groups {topic} material by receipt month and custodian. A later correction is retained with the earlier version, allowing the reviewer to see which record was available when the file first reached the desk.",
    "For {topic}, staff compare the face of the {document} with its attached source before recording a completion date. A routing stamp shows where the packet travelled, but it does not alter the underlying event date.",
    "The {document} is indexed under {topic} after the responsible office confirms that the page belongs to this file. Indexing prevents misplaced pages; it is not evidence that the expense meets a schedule definition.",
    "At {office}, the {topic} register records the name of the receiving custodian and the date the packet entered local custody. Those details help retrieve the source without changing the receipt date stated by the issuing party.",
    "A reviewer using the {document} should retain its heading, signature, and date together. The {topic} archive does not infer a missing signature from a payment trace or from a later administrative acknowledgement.",
    "The {office} desk keeps separate folders for {topic} correspondence and source records. Correspondence can explain why a document was sent, while the signed source remains the evidence used to establish the event described.",
    "When two {topic} copies differ, the registry preserves both and records the page sequence supplied by the sender. Staff do not choose a date merely because one copy is easier to read or was uploaded first.",
    "A {document} may arrive with supporting pages from another office. The {office} clerk records the bundle as received, while the case reviewer checks each dated page against the rule that governs the particular claim.",
    "The {topic} retention ledger lists the case reference, storage location, and scheduled review month. These administrative entries help reproduce the file later and have no independent effect on the amount calculated under the schedule.",
    "For archival transfer, {office} staff check that the {document} is readable and that its attachments remain in order. A transfer receipt confirms custody only; it does not establish that the underlying request was timely.",
    "The local {topic} procedure asks staff to keep calculations with the source invoice and to preserve the rounding convention used. A second reviewer can then repeat the arithmetic without relying on an earlier conclusion.",
    "A contact note in the {topic} folder may explain a delay in communication, but the schedule measures the filing period from the receipt date printed in the case record. The note is retained for context, not substituted for that date.",
    "The {office} quality check samples {topic} files for missing pages and inconsistent references. A sampling mark triggers document retrieval when needed; it does not approve an expense or override a policy condition.",
    "The {document} is stored with the case chronology so that later reviewers can distinguish the date an event occurred from the date the office learned about it. Both dates remain visible in the archive.",
    "The {topic} register uses a stable case reference across paper and electronic copies. If a clerk corrects a transcription, the source image and correction history are retained together for a complete audit trail.",
    "Before a {topic} file is transferred to {office}, the sender lists the documents enclosed and the recipient records any missing page. The transfer list helps locate evidence but cannot fill a gap in the source record.",
    "A supervisor reviewing {topic} work checks that the file contains the source named by the schedule and that calculations can be repeated from the printed figures. Administrative completeness is separate from substantive eligibility.",
    "The archive copy of a {document} retains the issuing party's wording even when staff add an index label. Labels make retrieval faster, but the reviewer relies on the dated document rather than an internal description.",
)
_FILLER_TAILS = (
    "The receiving officer initials the custody ledger after checking the packet count.",
    "This keeps the source chronology distinct from the office's handling chronology.",
    "Any later search begins with the case reference printed on the original page.",
    "A copied page remains linked to its issuing record rather than standing alone.",
    "The registry preserves the original sequence even when attachments are reordered.",
    "The reconciliation log is retained as an administrative aid for the next review.",
    "Staff can retrieve the earlier version without treating it as the controlling copy.",
    "The storage label identifies a location and does not express a substantive finding.",
    "A receipt for the packet records custody, not the merits of the request.",
    "The desk keeps the sender's cover sheet alongside the dated supporting material.",
    "A later audit can therefore reproduce the file as it appeared at intake.",
    "The archive note remains separate from the evidence used in the calculation.",
    "This procedure applies to document handling and does not alter the schedule terms.",
    "The reviewer records any missing attachment before moving the file to the next desk.",
    "The index is updated only after the source page has been returned to its folder.",
    "A corrected transcription is stored with the image from which it was prepared.",
    "The custodian's initials make the transfer traceable without changing the source date.",
    "The retained copy supports retrieval when the original is requested for inspection.",
    "Staff preserve both versions when a sender supplies a corrected page later.",
    "No administrative marker substitutes for a signed document required by the schedule.",
)


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


def _date(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def _calculation(requested, cap, sublimit, rate, deductible):
    subtotal = min(requested, cap, sublimit)
    gross = (subtotal * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return max(Decimal("0.00"), gross - deductible).quantize(Decimal("0.01"))


def _derive(case, policy):
    event = _date(case["event_date"])
    received = _date(case["received_date"])
    start = _date(policy["period_start"])
    end = _date(policy["period_end"])
    amended = event >= _date(policy["endorsement_date"])
    cap = policy["amended_cap"] if amended else policy["prior_cap"]
    signed = _date(case["exception_signed"]) if case["exception_signed"] is not None else None
    exception_ok = (
        signed is not None
        and signed <= event
        and case["category"] == policy["exception_category"]
        and case["exception_scope"] == policy["exception_category"]
    )
    in_period = start <= event <= end
    timely = received <= event + timedelta(days=policy["filing_days"])
    early = received <= event + timedelta(days=max(1, policy["filing_days"] // 2))
    eligible = case["category"] == policy["covered_category"] or exception_ok
    amount = Decimal("0.00")
    if in_period and timely and eligible:
        amount = _calculation(
            case["requested"], cap, case["sublimit"], case["rate"], case["deductible"]
        )
    if not in_period:
        outcome = "not_covered"
    elif not timely:
        outcome = "late"
    elif not eligible:
        outcome = "not_eligible"
    elif exception_ok:
        outcome = "exception_authorized"
    elif amount == case["requested"]:
        outcome = "full"
    else:
        outcome = "partial"
    return {
        "in_period": in_period, "timely": timely, "amended": amended,
        "early": early, "standard_category": case["category"] == policy["covered_category"],
        "letter_present": signed is not None, "exception_ok": exception_ok, "eligible": eligible,
        "amount": amount, "outcome": outcome,
    }


def _render(schema, case, policy, rng):
    config = SCHEMAS[schema]
    state = (
        f"SCHEDULE TITLE: {config['title']}\n"
        f"Edition reference: {policy['edition']}\n\n"
        "DEFINITIONS\n"
        f"Covered record: {config['definition']}.\n"
        f"Document source: Eligibility is read from {config['evidence']}.\n\n"
        "OPERATIVE RULES\n"
        f"Rule 1 — Period: The schedule applies to events from {policy['period_start']} through "
        f"{policy['period_end']}, inclusive.\n"
        f"Rule 2 — Qualifying activity: The documented item must be exactly “{config['covered']}”. "
        f"The description is taken from the case file, not from a later payment label.\n"
        f"Rule 3 — Filing: The office must receive the request no later than "
        f"{policy['filing_days']} calendar days after the event date.\n"
        f"Rule 4 — Special authorization: A signed letter may authorize “{config['exception']}” "
        "when signed on or before the event. It does not extend the period or filing deadline.\n"
        f"Rule 5 — Amount: Apply the reimbursement share to the lowest of the claimed amount, "
        "the applicable per-case cap, and the per-item limit; then subtract the deductible and "
        "round half up to cents. Amounts cannot fall below zero.\n"
        "Rule 6 — Decision order: First test Rule 1, then Rule 3, then the activity in Rules 2 "
        "and 4. If those gates pass, calculate under Rule 5. The first failed gate controls the "
        "disposition; a later amount calculation cannot cure it.\n\n"
        "CASE DOSSIER\n"
        f"Case reference: {case['reference']}\n"
        f"{config['record']}: Event date: {case['event_date']}.\n"
        f"Item description: {case['category']}.\n"
        f"Claimed amount: {_money(case['requested'])}\n"
        f"Request received by office: {case['received_date']}\n"
        f"Case evidence: {config['fact']}\n"
        f"Per-item limit: {_money(case['sublimit'])}\n"
        f"Reimbursement share: {case['rate'] * 100:.2f}%\n"
        f"Deductible: {_money(case['deductible'])}\n"
    )
    if case["exception_signed"] is None:
        state += "Signed case letter: The authorization register contains no signed exception for this file.\n"
    else:
        state += (
            f"Signed case letter: Registry copy {case['letter_ref']} signed "
            f"{case['exception_signed'].isoformat()}; authorized activity: "
            f"{case['exception_scope']}.\n"
        )
    state += (
        "\nEFFECTIVE-DATED ENDORSEMENT REGISTER\n"
        f"Rider {policy['rider']} was signed by the schedule owner.\n"
        f"Effective date: {policy['endorsement_date']}.\n"
        f"Prior per-case cap: {_money(policy['prior_cap'])}.\n"
        f"Revised per-case cap: {_money(policy['amended_cap'])}.\n"
        "The revised cap applies only to events on or after the effective date; earlier events "
        "remain under the prior schedule.\n\n"
        "ADMINISTRATIVE REFERENCE NOTES\n"
    )
    forms = [(index, template) for index, template in enumerate(_FILLER)] * 2
    rng.shuffle(forms)
    for index, template in forms:
        entry = template.format(
            topic=rng.choice(config["topics"]),
            office=rng.choice(config["offices"]),
            document=rng.choice(config["documents"]),
        )
        entry += " " + _FILLER_TAILS[index]
        state += entry + "\n\n"
        if len(state) // 4 >= policy["target_tokens"]:
            break
    return state.rstrip()


def _parse_state(state):
    title_match = re.search(r"^SCHEDULE TITLE: (.+)$", state, re.MULTILINE)
    schema = next(
        (key for key, config in SCHEMAS.items() if title_match and config["title"] == title_match.group(1)),
        None,
    )
    if schema is None:
        raise ValueError("unrecognized schedule title")
    config = SCHEMAS[schema]
    def one(pattern):
        match = re.search(pattern, state, re.MULTILINE)
        if not match:
            raise ValueError(f"missing rendered field: {pattern}")
        return match.group(1)
    def money(pattern):
        return Decimal(one(pattern).replace("$", "").replace(",", ""))
    event = date.fromisoformat(one(r"^" + re.escape(config["record"]) + r": Event date: (\d{4}-\d{2}-\d{2})\.$"))
    category = one(r"^Item description: (.+)\.$")
    received = date.fromisoformat(one(r"^Request received by office: (\d{4}-\d{2}-\d{2})$"))
    case = {
        "reference": one(r"^Case reference: (.+)$"),
        "event_date": event.isoformat(),
        "category": category,
        "received_date": received.isoformat(),
        "requested": money(r"^Claimed amount: (\$[\d,]+\.\d{2})$"),
        "sublimit": money(r"^Per-item limit: (\$[\d,]+\.\d{2})$"),
        "rate": Decimal(one(r"^Reimbursement share: ([\d.]+)%$")) / 100,
        "deductible": money(r"^Deductible: (\$[\d,]+\.\d{2})$"),
        "exception_signed": None,
        "exception_scope": None,
    }
    letter = re.search(
        r"^Signed case letter: Registry copy (\S+) signed (\d{4}-\d{2}-\d{2}); "
        r"authorized activity: (.+)\.$", state, re.MULTILINE,
    )
    if letter:
        case["letter_ref"] = letter.group(1)
        case["exception_signed"] = date.fromisoformat(letter.group(2))
        case["exception_scope"] = letter.group(3)
    policy = {
        "period_start": date.fromisoformat(one(r"^Rule 1 — Period: The schedule applies to events from (\d{4}-\d{2}-\d{2})")),
        "period_end": date.fromisoformat(one(r"^Rule 1 — Period: The schedule applies to events from \d{4}-\d{2}-\d{2} through (\d{4}-\d{2}-\d{2})")),
        "filing_days": int(one(r"^Rule 3 — Filing: The office must receive the request no later than (\d+) calendar days")),
        "endorsement_date": date.fromisoformat(one(r"^Effective date: (\d{4}-\d{2}-\d{2})\.?$")),
        "prior_cap": money(r"^Prior per-case cap: (\$[\d,]+\.\d{2})\.?$"),
        "amended_cap": money(r"^Revised per-case cap: (\$[\d,]+\.\d{2})\.?$"),
        "covered_category": one(r"^Rule 2 — Qualifying activity: The documented item must be exactly “(.+?)”\."),
        "exception_category": one(r"^Rule 4 — Special authorization: A signed letter may authorize “(.+?)” "),
    }
    facts = {
        "case": {
            "event_date": case["event_date"], "received_date": case["received_date"],
            "category": case["category"], "requested_amount": str(case["requested"]),
            "sublimit": str(case["sublimit"]), "deductible": str(case["deductible"]),
        },
        "policy": {
            "coverage_start": policy["period_start"].isoformat(),
            "coverage_end": policy["period_end"].isoformat(),
            "amendment_effective": policy["endorsement_date"].isoformat(),
            "prior_cap": str(policy["prior_cap"]), "amended_cap": str(policy["amended_cap"]),
        },
    }
    return schema, config, case, policy, facts


def verify_rendered(record: dict) -> bool:
    try:
        schema, config, case, policy, _ = _parse_state(record["state"])
        policy["covered_category"] = config["covered"]
        policy["exception_category"] = config["exception"]
        derived = _derive(case, policy)
        for qid, question in record["questions"].items():
            instruction = question["instructions"]
            if instruction == "Which disposition follows from the schedule?":
                wanted = key_for_value("disposition", derived["outcome"])
            elif instruction == "Which band contains the reimbursable amount?":
                wanted = score_level_for(derived["amount"], question["criteria"])
            elif instruction == "Does the effective-dated rider apply to this event?":
                wanted = "true" if derived["amended"] else "false"
            elif instruction == "Was the request received during the first half of the filing window?":
                wanted = "true" if derived["early"] else "false"
            elif instruction == "Is the documented item the standard qualifying activity?":
                wanted = "true" if derived["standard_category"] else "false"
            elif instruction == "Is a signed case letter present in the file?":
                wanted = "true" if derived["letter_present"] else "false"
            else:
                return False
            if record["gold"][qid] != wanted:
                return False
        note_match = re.search(
            r"Mira \(claims\): I have \$([\d,]+\.\d{2}) as the reimbursable amount for this file, "
            r"so the payment can be prepared\.",
            record["state"],
        )
        note_meta = record["_meta"]["staff_note"]
        if bool(note_match) != note_meta["included"]:
            return False
        if note_match:
            stated = Decimal(note_match.group(1).replace(",", ""))
            if note_meta["correct"] is not (stated == derived["amount"]):
                return False
        return True
    except (ValueError, KeyError, InvalidOperation, IndexError, AttributeError, TypeError):
        return False


def generate(rng: random.Random, n_questions: int) -> dict:
    if not 2 <= n_questions <= 5:
        raise ValueError("n_questions must be between 2 and 5")
    schema = rng.choice(list(SCHEMAS))
    config = SCHEMAS[schema]
    mode = rng.choice(("not_covered", "late", "not_eligible", "exception_authorized", "full", "partial"))
    event = date(2027, rng.randint(1, 12), rng.randint(3, 24))
    if mode == "not_covered":
        event = date(2026, 12, rng.randint(10, 24))
    requested = Decimal(rng.randrange(70_000, 800_001)) / 100
    sublimit = requested + Decimal(rng.randrange(150, 1_001, 25))
    rate = Decimal(rng.choice(("0.75", "0.80", "0.90", "1.00")))
    deductible = Decimal(rng.randrange(0, 121, 10))
    prior_cap = requested + Decimal(rng.randrange(100, 701, 25))
    amended_cap = requested + Decimal(rng.randrange(250, 1_001, 25))
    if mode == "full":
        prior_cap = requested - Decimal("100.00")
        amended_cap = requested + Decimal("500.00")
        sublimit, rate, deductible = requested + Decimal("700.00"), Decimal("1.00"), Decimal("0")
    elif mode == "partial":
        prior_cap, amended_cap = requested - Decimal("150.00"), requested - Decimal("50.00")
        sublimit, rate, deductible = requested + Decimal("500.00"), Decimal("1.00"), Decimal("20.00")
    elif mode == "exception_authorized":
        prior_cap, amended_cap = requested - Decimal("100.00"), requested + Decimal("300.00")
        rate, deductible = Decimal("0.90"), Decimal("25.00")
    period_start, period_end = date(2027, 1, 1), date(2027, 12, 31)
    filing_days = rng.randint(8, 24)
    received = event + timedelta(days=rng.randint(1, filing_days))
    category = config["covered"]
    exception_signed = None
    exception_scope = None
    if mode == "late":
        received = event + timedelta(days=filing_days + rng.randint(1, 12))
    elif mode == "not_eligible":
        category = config["other"]
    elif mode == "exception_authorized":
        category = config["exception"]
        exception_scope = config["exception"]
        exception_signed = event - timedelta(days=rng.randint(1, 20))
    if mode in {"late", "not_eligible"}:
        exception_signed = event + timedelta(days=1) if mode == "late" else event - timedelta(days=1)
        exception_scope = config["exception"]
    endorsement_date = event - timedelta(days=5) if mode == "full" else event + timedelta(days=rng.randint(-40, 40))
    if mode == "not_covered":
        endorsement_date = date(2027, 7, 1)
    case = {
        "reference": f"CP-{rng.randint(100000, 999999)}",
        "event_date": event.isoformat(),
        "category": category,
        "received_date": received.isoformat(),
        "requested": requested,
        "sublimit": sublimit,
        "rate": rate,
        "deductible": deductible,
        "exception_signed": exception_signed,
        "exception_scope": exception_scope,
        "letter_ref": f"EX-{rng.randint(1000, 9999)}",
    }
    policy = {
        "edition": f"{rng.randint(2024, 2027)}.{rng.randint(1, 4)}",
        "period_start": period_start,
        "period_end": period_end,
        "filing_days": filing_days,
        "endorsement_date": endorsement_date,
        "prior_cap": prior_cap,
        "amended_cap": amended_cap,
        "covered_category": config["covered"],
        "exception_category": config["exception"],
        "rider": f"R-{rng.randint(1000, 9999)}",
        "target_tokens": rng.randint(2_250, 3_650),
    }
    derived = _derive(case, policy)
    state = _render(schema, case, policy, rng)
    note = None
    correct_note = False
    mistake = None
    if rng.random() < 0.65:
        correct_note = rng.random() < 0.30
        if correct_note:
            note_amount = derived["amount"]
        elif mode == "full":
            note_amount = _calculation(requested, prior_cap, sublimit, rate, deductible)
            mistake = "used the superseded per-case cap"
        elif mode == "partial":
            note_amount = min(requested, derived["amount"] + deductible)
            mistake = "failed to subtract the deductible"
        elif mode == "exception_authorized":
            note_amount = Decimal("0.00")
            mistake = "overlooked the signed exception"
        else:
            note_amount = _calculation(requested, amended_cap, sublimit, rate, deductible)
            if note_amount == derived["amount"]:
                note_amount = requested
            mistake = "treated the item as qualifying without applying the disposition gate"
        note = (
            f"Mira (claims): I have {_money(note_amount)} as the reimbursable amount for this file, "
            "so the payment can be prepared.",
            correct_note,
        )
    pool = [
        ("choice", "Which disposition follows from the schedule?",
         key_for_value("disposition", derived["outcome"]),
         {key_for_value("disposition", outcome): f"The file receives the {label} disposition."
          for outcome, label in OUTCOMES.items()}),
        ("noul", "Does the effective-dated rider apply to this event?",
         "true" if derived["amended"] else "false",
         {"false": "The effective-dated rider applies to this event: No.",
          "true": "The effective-dated rider applies to this event: Yes."}),
        ("noul", "Was the request received during the first half of the filing window?",
         "true" if derived["early"] else "false",
         {"false": "The request arrived during the first half of the filing window: No.",
          "true": "The request arrived during the first half of the filing window: Yes."}),
        ("noul", "Is the documented item the standard qualifying activity?",
         "true" if derived["standard_category"] else "false",
         {"false": "The documented item is the standard qualifying activity: No.",
          "true": "The documented item is the standard qualifying activity: Yes."}),
        ("noul", "Is a signed case letter present in the file?",
         "true" if derived["letter_present"] else "false",
         {"false": "A signed case letter is present in the file: No.",
          "true": "A signed case letter is present in the file: Yes."}),
    ]
    if derived["amount"] > 0:
        band_edges, band_gold = round_bands(
            derived["amount"], "$", [Decimal("10"), Decimal("25"), Decimal("50"), Decimal("100")],
            rng, metric="The reimbursable amount",
        )
        pool.append((
            "score", "Which band contains the reimbursable amount?",
            str(band_gold), band_edges,
        ))
    selected = rng.sample(pool, n_questions)
    specs = [(kind, instruction, answer, criteria) for kind, instruction, answer, criteria in selected]
    record = finish_record(
        rng, FAMILY, schema, state, specs,
        facts={
            "schema": schema, "case": {
                "event_date": case["event_date"], "received_date": case["received_date"],
                "category": case["category"], "requested_amount": str(requested),
                "sublimit": str(sublimit), "deductible": str(deductible),
            },
            "policy": {"effective_date": endorsement_date.isoformat()},
            "outcome": derived["outcome"], "amount": str(derived["amount"]),
        },
        traps=["period_boundary", "filing_window", "activity_definition", "signed_exception",
               "effective_endorsement", "marginal_calculation"],
        note=note,
        approx_tokens=len(state) // 4,
    )
    record["_meta"]["note_mistake"] = mistake
    record["_meta"]["outcome"] = derived["outcome"]
    record["_meta"]["schema"] = schema
    record["_meta"]["approx_tokens"] = len(record["state"]) // 4
    return record
