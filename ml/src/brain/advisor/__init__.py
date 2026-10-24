"""Advisor mode: deterministic, on-device meeting prep for a client household."""

from .brief import brief_html, brief_markdown
from .core import (
                   Household,
                   allocation,
                   cash_excess,
                   donation_candidates,
                   load_household,
                   parse_ics,
                   prep,
                   rebalance_trades,
                   roth_room,
                   strip_evidence,
                   tlh_candidates,
                   totals,
)
from .scripts import (
    notes_brief_script,
    numbers_highlight_script,
    numbers_review_script,
    numbers_wait_script,
)

__all__ = ["Household", "allocation", "brief_html", "brief_markdown", "cash_excess", "donation_candidates",
           "load_household", "notes_brief_script", "numbers_highlight_script", "numbers_review_script",
           "numbers_wait_script", "parse_ics", "prep",
           "rebalance_trades", "roth_room", "strip_evidence", "tlh_candidates", "totals"]
