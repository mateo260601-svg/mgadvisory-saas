DEBT_INSTRUMENT_LIBRARY = {
    "Super Senior RCF": {"category": "Senior Bank Debt", "ranking": 0, "default_rate": 0.045, "amortization": "Revolver", "secured": True, "pik": False},
    "RCF": {"category": "Senior Bank Debt", "ranking": 1, "default_rate": 0.050, "amortization": "Revolver", "secured": True, "pik": False},
    "Overdraft": {"category": "Senior Bank Debt", "ranking": 1, "default_rate": 0.080, "amortization": "Revolver", "secured": True, "pik": False},
    "Senior Term Loan A": {"category": "Senior Bank Debt", "ranking": 1, "default_rate": 0.055, "amortization": "Linear", "secured": True, "pik": False},
    "Senior Term Loan B": {"category": "Senior Bank Debt", "ranking": 1, "default_rate": 0.065, "amortization": "Bullet", "secured": True, "pik": False},
    "Senior Term Loan C": {"category": "Senior Bank Debt", "ranking": 1, "default_rate": 0.070, "amortization": "Bullet", "secured": True, "pik": False},
    "Delayed Draw Term Loan": {"category": "Senior Bank Debt", "ranking": 1, "default_rate": 0.068, "amortization": "Bullet", "secured": True, "pik": False},
    "Capex Facility": {"category": "Senior Bank Debt", "ranking": 1, "default_rate": 0.060, "amortization": "Linear", "secured": True, "pik": False},
    "Acquisition Facility": {"category": "Senior Bank Debt", "ranking": 1, "default_rate": 0.065, "amortization": "Bullet", "secured": True, "pik": False},
    "Accordion Facility": {"category": "Senior Bank Debt", "ranking": 1, "default_rate": 0.070, "amortization": "Bullet", "secured": True, "pik": False},
    "Asset Based Lending": {"category": "Borrowing Base", "ranking": 1, "default_rate": 0.055, "amortization": "Borrowing Base", "secured": True, "pik": False},
    "Borrowing Base Facility": {"category": "Borrowing Base", "ranking": 1, "default_rate": 0.055, "amortization": "Borrowing Base", "secured": True, "pik": False},
    "Receivables Facility": {"category": "Borrowing Base", "ranking": 1, "default_rate": 0.050, "amortization": "Borrowing Base", "secured": True, "pik": False},
    "Inventory Facility": {"category": "Borrowing Base", "ranking": 1, "default_rate": 0.060, "amortization": "Borrowing Base", "secured": True, "pik": False},
    "Factoring Recourse": {"category": "Borrowing Base", "ranking": 1, "default_rate": 0.060, "amortization": "Borrowing Base", "secured": True, "pik": False},
    "Factoring Non-Recourse": {"category": "Borrowing Base", "ranking": 1, "default_rate": 0.070, "amortization": "Borrowing Base", "secured": True, "pik": False},
    "Securitisation": {"category": "Borrowing Base", "ranking": 1, "default_rate": 0.052, "amortization": "Borrowing Base", "secured": True, "pik": False},
    "Supply Chain Finance": {"category": "Working Capital Finance", "ranking": 2, "default_rate": 0.045, "amortization": "Operational Run-Off", "secured": False, "pik": False},
    "Reverse Factoring": {"category": "Working Capital Finance", "ranking": 2, "default_rate": 0.045, "amortization": "Operational Run-Off", "secured": False, "pik": False},
    "Unitranche": {"category": "Private Credit", "ranking": 2, "default_rate": 0.085, "amortization": "Bullet", "secured": True, "pik": False},
    "First Out Unitranche": {"category": "Private Credit", "ranking": 1, "default_rate": 0.070, "amortization": "Bullet", "secured": True, "pik": False},
    "Last Out Unitranche": {"category": "Private Credit", "ranking": 2, "default_rate": 0.100, "amortization": "Bullet", "secured": True, "pik": False},
    "Second Lien": {"category": "Junior Secured", "ranking": 2, "default_rate": 0.095, "amortization": "Bullet", "secured": True, "pik": False},
    "Mezzanine Cash Pay": {"category": "Mezzanine", "ranking": 3, "default_rate": 0.110, "amortization": "Bullet", "secured": False, "pik": False},
    "Mezzanine PIK": {"category": "Mezzanine", "ranking": 3, "default_rate": 0.120, "amortization": "PIK", "secured": False, "pik": True},
    "Mezzanine Toggle": {"category": "Mezzanine", "ranking": 3, "default_rate": 0.115, "amortization": "PIK Toggle", "secured": False, "pik": True},
    "HoldCo PIK": {"category": "HoldCo Debt", "ranking": 5, "default_rate": 0.125, "amortization": "PIK", "secured": False, "pik": True},
    "OpCo PIK": {"category": "PIK Debt", "ranking": 4, "default_rate": 0.115, "amortization": "PIK", "secured": False, "pik": True},
    "High Yield Bond": {"category": "Bonds", "ranking": 3, "default_rate": 0.095, "amortization": "Bullet", "secured": False, "pik": False},
    "Senior Secured Notes": {"category": "Bonds", "ranking": 2, "default_rate": 0.075, "amortization": "Bullet", "secured": True, "pik": False},
    "Senior Unsecured Notes": {"category": "Bonds", "ranking": 3, "default_rate": 0.085, "amortization": "Bullet", "secured": False, "pik": False},
    "Fixed Rate Bond": {"category": "Bonds", "ranking": 2, "default_rate": 0.075, "amortization": "Bullet", "secured": False, "pik": False},
    "Floating Rate Bond": {"category": "Bonds", "ranking": 2, "default_rate": 0.070, "amortization": "Bullet", "secured": False, "pik": False},
    "Private Placement": {"category": "Bonds", "ranking": 2, "default_rate": 0.070, "amortization": "Linear", "secured": False, "pik": False},
    "Convertible Note": {"category": "Hybrid", "ranking": 4, "default_rate": 0.080, "amortization": "PIK", "secured": False, "pik": True},
    "Preferred Equity": {"category": "Hybrid", "ranking": 6, "default_rate": 0.110, "amortization": "PIK", "secured": False, "pik": True},
    "Redeemable Preferred Equity": {"category": "Hybrid", "ranking": 6, "default_rate": 0.120, "amortization": "PIK", "secured": False, "pik": True},
    "Warrant-Linked Debt": {"category": "Hybrid", "ranking": 4, "default_rate": 0.085, "amortization": "Bullet", "secured": False, "pik": False},
    "Shareholder Loan Cash Pay": {"category": "Shareholder", "ranking": 5, "default_rate": 0.080, "amortization": "Bullet", "secured": False, "pik": False},
    "Shareholder Loan PIK": {"category": "Shareholder", "ranking": 5, "default_rate": 0.100, "amortization": "PIK", "secured": False, "pik": True},
    "Shareholder Current Account": {"category": "Shareholder", "ranking": 5, "default_rate": 0.030, "amortization": "Bullet", "secured": False, "pik": False},
    "Vendor Loan": {"category": "Vendor / Seller", "ranking": 4, "default_rate": 0.060, "amortization": "Bullet", "secured": False, "pik": False},
    "Seller Note": {"category": "Vendor / Seller", "ranking": 4, "default_rate": 0.060, "amortization": "Bullet", "secured": False, "pik": False},
    "Earn-Out Deferred Consideration": {"category": "Vendor / Seller", "ranking": 5, "default_rate": 0.000, "amortization": "Bullet", "secured": False, "pik": False},
    "Contingent Consideration": {"category": "Vendor / Seller", "ranking": 5, "default_rate": 0.000, "amortization": "Bullet", "secured": False, "pik": False},
    "Management Loan": {"category": "Management", "ranking": 5, "default_rate": 0.050, "amortization": "Bullet", "secured": False, "pik": False},
    "Bridge Loan": {"category": "Bridge", "ranking": 1, "default_rate": 0.090, "amortization": "Bullet", "secured": True, "pik": False},
    "Super Senior Bridge": {"category": "Bridge", "ranking": 0, "default_rate": 0.100, "amortization": "Bullet", "secured": True, "pik": False},
    "DIP Financing": {"category": "Restructuring", "ranking": 0, "default_rate": 0.120, "amortization": "Bullet", "secured": True, "pik": False},
    "Rescue Financing": {"category": "Restructuring", "ranking": 0, "default_rate": 0.140, "amortization": "Cash Sweep", "secured": True, "pik": False},
    "Tax Debt Payment Plan": {"category": "Restructuring", "ranking": 2, "default_rate": 0.040, "amortization": "Linear", "secured": False, "pik": False},
    "Social Security Debt Plan": {"category": "Restructuring", "ranking": 2, "default_rate": 0.040, "amortization": "Linear", "secured": False, "pik": False},
    "Supplier Payment Plan": {"category": "Restructuring", "ranking": 2, "default_rate": 0.000, "amortization": "Operational Run-Off", "secured": False, "pik": False},
    "Customer Advance": {"category": "Restructuring", "ranking": 2, "default_rate": 0.000, "amortization": "Operational Run-Off", "secured": False, "pik": False},
    "Cramdown Debt": {"category": "Restructuring", "ranking": 3, "default_rate": 0.080, "amortization": "Sculpted", "secured": False, "pik": False},
    "Project Finance": {"category": "Project Finance", "ranking": 1, "default_rate": 0.065, "amortization": "Debt Sculpting", "secured": True, "pik": False},
    "Export Credit Agency Facility": {"category": "Project Finance", "ranking": 1, "default_rate": 0.045, "amortization": "Linear", "secured": True, "pik": False},
    "State Guaranteed Loan": {"category": "Project Finance", "ranking": 1, "default_rate": 0.035, "amortization": "Linear", "secured": True, "pik": False},
    "Green Loan": {"category": "Project Finance", "ranking": 1, "default_rate": 0.055, "amortization": "Linear", "secured": True, "pik": False},
    "Sustainability Linked Loan": {"category": "Project Finance", "ranking": 1, "default_rate": 0.055, "amortization": "Linear", "secured": True, "pik": False},
    "Mortgage Debt": {"category": "Asset Finance", "ranking": 1, "default_rate": 0.050, "amortization": "Annuity", "secured": True, "pik": False},
    "Equipment Loan": {"category": "Asset Finance", "ranking": 1, "default_rate": 0.060, "amortization": "Linear", "secured": True, "pik": False},
    "Finance Lease": {"category": "Lease", "ranking": 1, "default_rate": 0.065, "amortization": "Annuity", "secured": True, "pik": False},
    "Operating Lease IFRS16": {"category": "Lease", "ranking": 1, "default_rate": 0.060, "amortization": "Annuity", "secured": True, "pik": False},
    "Sale & Leaseback": {"category": "Lease", "ranking": 1, "default_rate": 0.065, "amortization": "Annuity", "secured": True, "pik": False},
    "Venture Debt": {"category": "Growth Debt", "ranking": 2, "default_rate": 0.100, "amortization": "Interest Only Then Linear", "secured": True, "pik": False},
    "Growth Debt": {"category": "Growth Debt", "ranking": 2, "default_rate": 0.095, "amortization": "Interest Only Then Linear", "secured": True, "pik": False},
    "Revenue Based Financing": {"category": "Growth Debt", "ranking": 3, "default_rate": 0.080, "amortization": "Revenue Share", "secured": False, "pik": False},
    "Royalty Financing": {"category": "Growth Debt", "ranking": 3, "default_rate": 0.080, "amortization": "Revenue Share", "secured": False, "pik": False},
    "Local Bank Debt": {"category": "Local Debt", "ranking": 2, "default_rate": 0.070, "amortization": "Linear", "secured": True, "pik": False},
    "FX Debt": {"category": "FX Debt", "ranking": 2, "default_rate": 0.070, "amortization": "Bullet", "secured": True, "pik": False},
    "Hedged Floating Debt": {"category": "Hedged Debt", "ranking": 1, "default_rate": 0.060, "amortization": "Linear", "secured": True, "pik": False},
    "Swap Liability": {"category": "Hedge", "ranking": 2, "default_rate": 0.000, "amortization": "Operational Run-Off", "secured": False, "pik": False},
    "Call Premium Liability": {"category": "Fees / Premium", "ranking": 3, "default_rate": 0.000, "amortization": "Bullet", "secured": False, "pik": False},
    "Exit Fee Liability": {"category": "Fees / Premium", "ranking": 3, "default_rate": 0.000, "amortization": "Bullet", "secured": False, "pik": False},
}

AMORTIZATION_TYPES = [
    "Bullet",
    "Linear",
    "Annuity",
    "Cash Sweep",
    "Excess Cash Flow Sweep",
    "Revolver",
    "Borrowing Base",
    "Interest Only Then Linear",
    "PIK",
    "PIK Toggle",
    "Revenue Share",
    "Operational Run-Off",
    "Debt Sculpting",
    "Sculpted",
]

RATE_BASIS = ["Fixed", "Floating", "EURIBOR", "SOFR", "SONIA", "Base + Margin", "Hedged"]
CURRENCIES = ["EUR", "USD", "GBP", "CHF", "CAD", "AUD", "Local"]
CASES = ["Base", "Downside", "Upside", "Bank Case", "IC Case", "Restructuring Case"]


def debt_type_options() -> list[str]:
    return list(DEBT_INSTRUMENT_LIBRARY.keys())


def debt_library_payload() -> dict:
    return {
        "debt_types": debt_type_options(),
        "amortization_types": AMORTIZATION_TYPES,
        "rate_basis": RATE_BASIS,
        "currencies": CURRENCIES,
        "case_list": CASES,
        "library": DEBT_INSTRUMENT_LIBRARY,
    }


def default_debt_stack() -> list[dict]:
    return [
        _facility("Super Senior RCF", commitment=30000, opening_balance=0),
        _facility("Senior Term Loan B", commitment=130000, opening_balance=130000),
        _facility("Mezzanine PIK", commitment=40000, opening_balance=40000),
    ]


def _facility(debt_type: str, commitment: float, opening_balance: float) -> dict:
    meta = DEBT_INSTRUMENT_LIBRARY[debt_type]
    return {
        "instrument": debt_type,
        "debt_type": debt_type,
        "category": meta["category"],
        "commitment": commitment,
        "opening_balance": opening_balance,
        "rate": meta["default_rate"],
        "amortization": meta["amortization"],
        "ranking": meta["ranking"],
        "secured": meta["secured"],
        "pik": meta["pik"],
    }


def annual_debt_metrics(opening_debt: float, all_in_rate: float, amortization_pct: float) -> dict:
    interest = opening_debt * all_in_rate
    amortization = opening_debt * amortization_pct
    closing_debt = max(opening_debt - amortization, 0)
    return {
        "opening_debt": opening_debt,
        "interest": interest,
        "amortization": amortization,
        "closing_debt": closing_debt,
    }
