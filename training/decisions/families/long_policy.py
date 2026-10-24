from __future__ import annotations

import calendar
import random
from datetime import date, timedelta

from .core import NAMES, choose_domain, question_specs, record


def eligible(*, active: bool, amount: float, filed: date, start: date, end: date,
             exception: bool, region: str) -> bool:
    return active and start <= filed <= end and amount <= 5000 and (region == "north" or exception)


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    reviewer = rng.choice(NAMES)
    year = rng.choice((2025, 2026, 2027))
    filed = date(year, rng.randint(1, 12), 1)
    filed = filed.replace(day=rng.randint(1, calendar.monthrange(year, filed.month)[1]))
    region = rng.choice(("north", "south"))
    signed_exception = bool(rng.randrange(2))
    active = bool(rng.randrange(2))
    amount = float(rng.choice((3200, 4800, 5000, 5200)))
    claim = f"CLM-{rng.randint(20000, 99999)}"
    account = f"AC-{rng.randint(1000, 9999)}"
    exception_date = filed - timedelta(days=rng.randint(1, 14)) if signed_exception else None
    start, end = date(year, 1, 1), date(year, 12, 31)
    allowed = eligible(active=active, amount=amount, filed=filed, start=start, end=end,
                       exception=signed_exception, region=region)
    evidence = [
        f"Intake register: {claim} was accepted at 09:14 on {filed.isoformat()}; the accepted timestamp, rather than the reviewer-opened date, controls the filing window.",
        f"Account directory entry {account} reports status {'active' if active else 'suspended'} on {filed.isoformat()}; the status snapshot is retained with the claim record.",
        f"The submitted eligible amount for {claim} is ${amount:.2f}; the receipt ledger and the claim form show the same amount before any reimbursement adjustment.",
        f"Regional assignment for {account} is {region}; the service address and the intake register agree on that region.",
        f"Exception register review: {'signed approval was entered on ' + exception_date.isoformat() + ', before intake' if signed_exception else 'no signed regional exception was present before intake'}.",
        f"Identity review by {reviewer}: the account identifier on the claim matches {account}; no duplicate submission was found in the same filing year.",
        f"Document control logged the claim packet under {claim} after checking that the date, amount, and region fields were legible.",
        f"Routing history shows that {reviewer} opened the review after intake; opening time does not replace the timestamp recorded for {claim}.",
    ]
    rules = [
        f"Section 1 — Effective dates. This edition applies to claims accepted from {start.isoformat()} through {end.isoformat()}, inclusive. A claim outside that window is assessed under the edition in force on its accepted intake date; a reviewer cannot extend the policy year by opening a late file.",
        "Section 2 — Account definition. An active account is one whose registry status is active at the accepted filing timestamp. A suspended or closed account does not qualify, even when its balance is current or the customer has an older approval on file.",
        "Section 3 — Eligible region. The ordinary route is available to North-region claims. The region is read from the service address attached to the account, not from the reviewer’s office, the mailing address on an invoice, or the location from which a document was uploaded.",
        "Section 4 — Regional exception. A South-region claim may use the ordinary route only when a signed regional exception is recorded before the accepted filing timestamp. A verbal assurance, a later signature, or an unsigned draft is not a qualifying exception.",
        "Section 5 — Amount ceiling. The eligible amount must be no more than $5,000.00; an amount exactly equal to $5,000.00 is permitted. The ceiling applies to the eligible claim amount before reimbursement is calculated, and rounding a larger claim down is not authorized.",
        "Section 6 — Conjunctive test. The active-account, effective-date, amount, and region requirements apply to the same claim. Passing three requirements does not compensate for the fourth, and a reviewer must record every failed requirement rather than selecting the most favorable one.",
        "Section 7 — Scope of exception. A signed regional exception changes only the region test. It does not reactivate a suspended account, move an intake date into the effective window, increase the amount ceiling, or waive any other requirement in this edition.",
        "Section 8 — Timestamp precedence. The intake service records the accepted timestamp after the required fields are submitted. A case-management screen may show a later review time, but that display is an audit event and cannot be substituted for the accepted filing date.",
        "Section 9 — Amount evidence. Use the eligible amount stated on the submitted claim and corroborated by its receipt ledger. Shipping, tax, or a proposed reimbursement adjustment is not added unless the policy identifies it as part of the eligible amount; no such adjustment changes the $5,000.00 ceiling.",
        "Section 10 — Duplicate control. A second upload of the same claim number is not a new filing and does not restart the effective-date window. If separate claims exist, each has its own accepted timestamp and amount test; reviewers must not combine amounts across unrelated claim numbers.",
        "Section 11 — Record retention. Preserve the account-status snapshot, intake timestamp, regional evidence, and any signed exception with the disposition. A missing supporting document may be requested, but a request for evidence is not itself proof that an eligibility condition has been met.",
        "Section 12 — Review sequence. Confirm the intake record first, then the account status, region, exception register, and eligible amount. This sequence is an audit aid only; it does not create a priority rule or permit a reviewer to stop before checking all conditions.",
        "Section 13 — Referral versus denial. A claim with a correctable documentation gap may be referred for review. A failed eligibility condition is not converted into approval by choosing a referral code, and the current decision must still reflect whether every substantive requirement is satisfied.",
        "Section 14 — Trap threshold. The operations dashboard displays a separate expedited-review marker for amounts of $4,800.00 or more. That marker changes queue order only; it neither raises the eligible amount ceiling nor establishes that an account is active.",
        "Section 15 — Exception audit. The exception register stores the signer, region, claim reference, and signature timestamp. An entry is effective only when all required fields are present and its timestamp precedes the accepted filing time; a blank or later-dated entry has no waiver effect.",
        "Section 16 — Decision record. The reviewer must cite the controlling policy edition and the evidence used for each condition. A prior-year approval, a neighboring account’s status, or a manager’s informal comment cannot override the written requirements in this controlled copy.",
    ]
    audit_notes = [
        f"Case conference note: {reviewer} verified that the accepted timestamp in the intake service is the same timestamp copied into the audit trail for {claim}; the portal's later display time records review activity only.",
        f"Registry reconciliation for {account} was completed against the filing-date snapshot. A current-day status lookup is retained as context, but it cannot replace the historical status that applied when {claim} was accepted.",
        f"The amount worksheet separates the requested eligible amount from the proposed payment. The reviewer records the original ${amount:.2f} figure first, because payment calculations happen after the eligibility ceiling has been tested.",
        f"Regional review links the service address to {region} before considering any exception. The uploaded invoice carries a mailing address for correspondence; it is not the address used to determine this claim's policy region.",
        f"Exception handling requires a claim-specific signed entry. A general regional bulletin or an exception granted to another account cannot be copied into {claim}'s file, even if the underlying service is similar.",
        f"The document register records when each attachment arrived. A file added after intake may explain a fact, but it does not alter the accepted date or retroactively create a signature that was absent at filing.",
        f"During quality review, a second analyst checks the conjunction rather than repeating the first reviewer’s conclusion. Each criterion is tied to its own source record so that one favorable fact cannot conceal another failed test.",
        f"The queue marker for ${amount:.2f} is operational metadata. Dispatchers may prioritize marked work, but the eligibility reviewer must apply Section 5 independently and may not treat a fast-lane marker as an approval.",
        f"If evidence conflicts, the reviewer records both sources and identifies which one controls under the policy. A silent overwrite is not permitted; unresolved factual conflicts go to supervisory review without changing the substantive threshold.",
        f"Final notices identify the controlling edition and distinguish a missing-document referral from an eligibility denial. They do not describe an exception as valid unless the signer, claim reference, region, and pre-intake timestamp are all present.",
        f"Appeal intake preserves the original decision snapshot alongside any later material. New evidence can support a reconsideration, but an appeal does not rewrite the historical filing date used for this edition's effective window.",
        f"Duplicate detection uses the claim reference and account together. Similar amounts or the same reviewer do not prove that two packets are duplicates; each distinct accepted claim must be assessed on its own records.",
        f"An amended submission retains the original intake event and receives a linked amendment event. Review staff cannot choose whichever event produces a favorable year or region; the amendment rule applies only where the controlled edition permits it.",
        f"Supervisors may correct a transcription error when the underlying source is clear, and the correction is logged with the source citation. They cannot waive the account, date, region, or amount tests through a free-text note.",
        f"Policy owners review exception usage quarterly for consistency across service regions. That audit may update a later edition, but it does not change the written rule that governed {claim} on its accepted date.",
        f"Disposition coding is checked after the substantive review. An expedited queue code, an unresolved evidence flag, and an eligibility result are separate fields; none of these administrative labels substitutes for the four-part test.",
    ]
    rng.shuffle(evidence)
    rng.shuffle(rules)
    rng.shuffle(audit_notes)
    layout = rng.choice(("controlled policy copy", "case review memorandum", "claims portal export", "review email"))
    if layout == "controlled policy copy":
        heading = f"CLAIMS ELIGIBILITY STANDARD / {domain.upper()} / CONTROLLED COPY"
    elif layout == "case review memorandum":
        heading = f"CASE REVIEW MEMORANDUM\nTo: Eligibility panel\nFrom: {reviewer}\nSubject: {claim}"
    elif layout == "claims portal export":
        heading = f"PORTAL EXPORT — {claim}\nQueue: {domain}\nReviewer: {reviewer}\nStatus: eligibility review"
    else:
        heading = f"Subject: Decision needed for {claim}\nFrom: {reviewer}\nTo: Eligibility review"
    state = (
        f"{heading}\n\nCASE DOSSIER\nClaim: {claim}; account: {account}; accepted filing: {filed.isoformat()}.\n"
        f"Region: {region}; account active on filing date: {str(active).lower()}; eligible amount: ${amount:.2f}.\n"
        f"Signed regional exception: {str(signed_exception).lower()}"
        + (f", recorded {exception_date.isoformat()}." if exception_date else " (none recorded before filing).")
        + "\n\nEVIDENCE TRAIL\n" + "\n\n".join(evidence)
        + "\n\nPOLICY EXCERPT\n" + "\n\n".join(rules)
        + "\n\nAUDIT APPENDIX\n" + "\n\n".join(audit_notes)
        + f"\n\nDisposition requested by {reviewer}: determine whether {claim} satisfies every applicable condition."
    )
    disposition_options = {
        "eligible": "The claim meets every applicable policy requirement.",
        "ineligible": "The claim fails at least one applicable policy requirement.",
    }
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            specs.append((kind, f"What is the policy disposition for claim {claim}?",
                          "eligible" if allowed else "ineligible", disposition_options, None))
        elif kind == "noul":
            specs.append((kind, f"Does claim {claim} satisfy every substantive eligibility condition?",
                          "true" if allowed else "false",
                          {"false": "The claim fails at least one applicable policy requirement.",
                           "true": "The claim meets every applicable policy requirement."},
                          None))
        else:
            score = "0" if not active else "2" if allowed else "1"
            specs.append((kind, f"What policy disposition tier applies to claim {claim}?",
                          score, None,
                          [f"Claim {claim} fails the active-account requirement.",
                           f"Claim {claim} passes the account test but fails a different eligibility test.",
                           f"Claim {claim} meets every substantive eligibility requirement."]))
    return record(
        rng, "long_policy", domain, state, specs,
        intermediate_values=(
            f"filing-window test for {claim}",
            f"regional exception test for {claim}",
            f"account-status test for {claim}",
        ),
    )
