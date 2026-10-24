"""Official tax constants used by the advisor engine. Every number cites its source.

Federal, tax year 2026: IRS Rev. Proc. 2025-32, section 4.01, Table 1 (Married Individuals Filing Joint
Returns and Surviving Spouses), https://www.irs.gov/pub/irs-drop/rp-25-32.pdf (page 10); the same
figures appear in IRS news release IR-2025-103 (Oct. 9, 2025). IRMAA is intentionally not modelled.
"""

from decimal import Decimal

REV_PROC_2026 = "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf"
IR_2025_103 = ("https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-"
               "including-amendments-from-the-one-big-beautiful-bill")

# Upper edge of each bracket (taxable income); the 37% bracket has no upper edge.
BRACKET_TOPS = {
    (2026, "married_filing_jointly"): {
        "10%": Decimal("24800"),
        "12%": Decimal("100800"),
        "22%": Decimal("211400"),
        "24%": Decimal("403550"),
        "32%": Decimal("512450"),
        "35%": Decimal("768700"),
    },
}
SOURCES = {(2026, "married_filing_jointly"): REV_PROC_2026}

# Wash-sale window: IRS Publication 550, "Wash Sales" (30 days before or after the sale; includes
# acquisitions in your IRA or Roth IRA). https://www.irs.gov/publications/p550
WASH_SALE_DAYS = 30
PUB_550 = "https://www.irs.gov/publications/p550"
