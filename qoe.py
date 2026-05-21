"""
Restructuring Options Engine
------------------------------
Institutional restructuring analysis: liquidity runway, debt capacity,
option scoring, creditor waterfall, and options paper output.

Follows the methodology used in A&M / FTI / Alvarez & Marsal restructuring
mandates. No pandas dependency. Pure Python.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Liquidity and runway
# ---------------------------------------------------------------------------

def estimate_liquidity_runway(opening_cash: float, monthly_burn: float) -> float | None:
    """
    Months of runway at current burn rate.
    Returns None if burn is zero or positive (no immediate risk).
    """
    if monthly_burn <= 0:
        return None
    return round(opening_cash / monthly_burn, 1)


def compute_liquidity_headroom(
    available_cash: float,
    undrawn_rcf: float,
    minimum_cash_covenant: float,
    short_term_debt_maturity: float,
    next_12m_interest: float,
    next_12m_capex: float,
) -> dict:
    """
    12-month liquidity headroom analysis.
    """
    total_liquidity = available_cash + undrawn_rcf
    total_outflows = minimum_cash_covenant + short_term_debt_maturity + next_12m_interest + next_12m_capex
    headroom = total_liquidity - total_outflows

    return {
        "available_cash": available_cash,
        "undrawn_rcf": undrawn_rcf,
        "total_available_liquidity": total_liquidity,
        "minimum_cash_covenant": minimum_cash_covenant,
        "short_term_debt_maturity": short_term_debt_maturity,
        "next_12m_interest_service": next_12m_interest,
        "next_12m_capex": next_12m_capex,
        "total_outflows": total_outflows,
        "net_headroom": headroom,
        "flag": "adequate" if headroom > 0 else "tight" if headroom > -1_000_000 else "critical",
        "interpretation": _liquidity_comment(headroom),
    }


# ---------------------------------------------------------------------------
# Debt capacity
# ---------------------------------------------------------------------------

def compute_debt_capacity(
    adjusted_ebitda: float,
    max_leverage_turns: float = 4.0,
    min_dscr: float = 1.25,
    interest_rate: float = 0.07,
    existing_debt: float = 0.0,
) -> dict:
    """
    Maximum sustainable debt based on:
    - leverage constraint: Debt ≤ EBITDA × max_turns
    - DSCR constraint: EBITDA ≥ annual_interest × min_dscr
    """
    leverage_capacity = adjusted_ebitda * max_leverage_turns
    # DSCR-implied max: if EBITDA / (D × rate) ≥ min_dscr → D ≤ EBITDA / (rate × min_dscr)
    dscr_capacity = adjusted_ebitda / (interest_rate * min_dscr) if interest_rate > 0 else float("inf")
    gross_capacity = min(leverage_capacity, dscr_capacity)
    incremental = max(0.0, gross_capacity - existing_debt)
    current_leverage = existing_debt / adjusted_ebitda if adjusted_ebitda > 0 else None
    current_dscr = (adjusted_ebitda / (existing_debt * interest_rate)) if (existing_debt > 0 and interest_rate > 0) else None

    return {
        "adjusted_ebitda": adjusted_ebitda,
        "existing_debt": existing_debt,
        "current_leverage_turns": round(current_leverage, 2) if current_leverage is not None else None,
        "current_dscr": round(current_dscr, 2) if current_dscr is not None else None,
        "leverage_cap_gross_debt": round(leverage_capacity, 0),
        "dscr_cap_gross_debt": round(dscr_capacity, 0) if not math.isinf(dscr_capacity) else None,
        "max_gross_debt": round(gross_capacity, 0),
        "incremental_capacity": round(incremental, 0),
        "binding_constraint": "leverage" if leverage_capacity <= dscr_capacity else "dscr",
        "inputs": {
            "max_leverage_turns": max_leverage_turns,
            "min_dscr": min_dscr,
            "interest_rate": interest_rate,
        },
    }


# ---------------------------------------------------------------------------
# Restructuring options
# ---------------------------------------------------------------------------

RESTRUCTURING_OPTIONS = [
    {
        "option": "Consensual debt rescheduling",
        "category": "Out-of-court",
        "liquidity_relief": "medium",
        "execution_risk": "low",
        "creditor_impact": "low",
        "timeline_months": "2–4",
        "suitable_for": "Short liquidity gap; supportive bank group; viable business plan.",
        "description": "Extend maturities, waive covenants, defer amortisation through bilateral bank negotiation. No court involvement. Requires 100% lender consent under most facilities.",
        "key_risks": ["Holdout creditor", "Information requirements", "Management bandwidth"],
    },
    {
        "option": "Amend and Extend (A&E)",
        "category": "Out-of-court",
        "liquidity_relief": "medium",
        "execution_risk": "low",
        "creditor_impact": "low",
        "timeline_months": "2–4",
        "suitable_for": "Facilities approaching maturity with core lender support.",
        "description": "Extend maturity by 1–3 years, typically with margin step-up. Avoids formal process. Requires majority or all-lender consent depending on documentation.",
        "key_risks": ["Margin cost", "Fee burn", "Covenant reset may be required"],
    },
    {
        "option": "New money injection (equity or debt)",
        "category": "Out-of-court",
        "liquidity_relief": "high",
        "execution_risk": "medium",
        "creditor_impact": "low",
        "timeline_months": "3–6",
        "suitable_for": "Liquidity crisis; sponsor with appetite; credible business plan.",
        "description": "Sponsor or third-party provides new cash. Can be structured as equity injection, super-senior facility, or subordinated bridge.",
        "key_risks": ["Sponsor fatigue", "Dilution mechanics", "Intercreditor complexity"],
    },
    {
        "option": "Pre-packaged / pre-arranged restructuring",
        "category": "Formal process",
        "liquidity_relief": "high",
        "execution_risk": "medium",
        "creditor_impact": "medium",
        "timeline_months": "3–6",
        "suitable_for": "Majority creditor support; need to bind minority holdouts; cross-border debt.",
        "description": "Term sheet agreed with majority creditors before filing. Minimises court time and operational disruption. Typically used under UK Restructuring Plan, US pre-pack Chapter 11, or French SFA.",
        "key_risks": ["Minority holdouts", "Employee / customer reaction", "Cross-border enforcement"],
    },
    {
        "option": "Scheme of Arrangement / UK Restructuring Plan",
        "category": "Formal process",
        "liquidity_relief": "high",
        "execution_risk": "medium",
        "creditor_impact": "medium",
        "timeline_months": "4–8",
        "suitable_for": "UK-domiciled group; majority creditor support; cross-class cram-down required.",
        "description": "Court-sanctioned process under Part 26 (Scheme) or Part 26A (Restructuring Plan). Restructuring Plan allows cross-class cram-down on dissenting classes if 'no worse off' test is met.",
        "key_risks": ["Valuation dispute", "Litigation from out-of-money class", "Cost"],
    },
    {
        "option": "Administration / Chapter 11 / Safeguard",
        "category": "Insolvency process",
        "liquidity_relief": "high",
        "execution_risk": "high",
        "creditor_impact": "high",
        "timeline_months": "6–24",
        "suitable_for": "Creditor agreement impossible; immediate liquidity crisis; distressed M&A required.",
        "description": "Statutory moratorium protects the business. Chapter 11 (US) or Administration (UK) allows DIP financing, contract rejection and trading under court protection.",
        "key_risks": ["Trading disruption", "Customer attrition", "DIP cost", "Timeline uncertainty"],
    },
    {
        "option": "Debt-to-equity swap",
        "category": "Balance sheet repair",
        "liquidity_relief": "medium",
        "execution_risk": "medium",
        "creditor_impact": "high",
        "timeline_months": "4–8",
        "suitable_for": "Over-leveraged structure; lenders willing to take equity; viable operating business.",
        "description": "Senior or mezzanine creditors convert all or part of debt claims to equity, reducing leverage and interest burden. Requires creditor consent and shareholder dilution.",
        "key_risks": ["Valuation disagreement", "Creditor as shareholder dynamics", "Existing sponsor write-off"],
    },
    {
        "option": "Operational restructuring (cost programme)",
        "category": "Operational",
        "liquidity_relief": "low",
        "execution_risk": "medium",
        "creditor_impact": "none",
        "timeline_months": "6–18",
        "suitable_for": "EBITDA improvement required before or alongside financial restructuring.",
        "description": "Headcount reduction, site closures, working capital optimisation, procurement savings. Does not directly address debt quantum but improves serviceability and valuation.",
        "key_risks": ["Execution capacity", "Employee / union response", "One-off costs"],
    },
    {
        "option": "Asset disposal / non-core carve-out",
        "category": "Deleveraging",
        "liquidity_relief": "medium",
        "execution_risk": "medium",
        "creditor_impact": "low",
        "timeline_months": "3–9",
        "suitable_for": "Non-core subsidiaries, brands or assets exist; lenders supportive; buyer pool available.",
        "description": "Sell non-core operations or assets; apply proceeds to debt repayment. Reduces leverage and simplifies the group. May trigger mandatory prepayment under facility agreement.",
        "key_risks": ["Valuation realisation", "Carve-out complexity", "TUPE / pension liabilities"],
    },
    {
        "option": "Whole-business / distressed M&A",
        "category": "Exit",
        "liquidity_relief": "high",
        "execution_risk": "high",
        "creditor_impact": "high",
        "timeline_months": "3–9",
        "suitable_for": "Going concern sale more valuable than wind-down; sponsor/management exit required.",
        "description": "Structured sale of the entire business or core assets. Can be achieved in or out of insolvency. Maximises recoveries versus liquidation in viable businesses.",
        "key_risks": ["Timeline vs liquidity", "Information disadvantage vs buyer", "Lease/contract assignment"],
    },
]


def score_options(
    liquidity_months: float | None,
    leverage_turns: float | None,
    creditor_support: str = "unknown",
) -> list[dict]:
    """
    Score and rank restructuring options based on the company's situation.

    liquidity_months: runway from compute_liquidity_headroom
    leverage_turns: current debt / EBITDA
    creditor_support: "strong" | "mixed" | "hostile" | "unknown"
    """
    support_score = {"strong": 2, "mixed": 1, "hostile": 0, "unknown": 1}[creditor_support]
    urgency = "critical" if (liquidity_months is not None and liquidity_months < 6) else "moderate" if (liquidity_months is not None and liquidity_months < 12) else "low"
    over_leveraged = leverage_turns is not None and leverage_turns > 5.0

    scored = []
    for opt in RESTRUCTURING_OPTIONS:
        score = 0

        # Liquidity urgency weighting
        if urgency == "critical":
            score += 20 if opt["liquidity_relief"] == "high" else 10 if opt["liquidity_relief"] == "medium" else 0
        elif urgency == "moderate":
            score += 10 if opt["liquidity_relief"] in ("high", "medium") else 5

        # Execution risk (lower is better when creditor support is weak)
        if support_score >= 2:
            score += 10 if opt["execution_risk"] == "low" else 5
        elif support_score == 0:
            score += 5 if opt["execution_risk"] in ("high",) else 8  # formal processes score higher

        # Leverage context
        if over_leveraged and opt["creditor_impact"] in ("high", "medium"):
            score += 10  # structural solutions needed

        scored.append({**opt, "situation_score": score})

    return sorted(scored, key=lambda x: x["situation_score"], reverse=True)


def build_restructuring_paper(
    project: dict,
    financials: dict,
    opening_cash: float = 0.0,
    monthly_burn: float = 0.0,
    undrawn_rcf: float = 0.0,
    min_cash_covenant: float = 0.0,
    creditor_support: str = "unknown",
) -> dict:
    """
    Master function — builds the full restructuring options paper dict.
    """
    periods = financials.get("periods", [])
    income_statement = financials.get("income_statement", [])
    balance_sheet = financials.get("balance_sheet", [])

    # Get latest period EBITDA and debt
    latest_period = periods[-1] if periods else None
    ebitda = _get_value(income_statement, "ebitda", latest_period) or 0
    debt = _get_value(balance_sheet, "debt", latest_period) or 0
    leverage = round(debt / ebitda, 2) if ebitda > 0 else None

    runway = estimate_liquidity_runway(opening_cash, monthly_burn)
    annual_interest = debt * 0.07  # rough estimate
    liquidity = compute_liquidity_headroom(
        opening_cash, undrawn_rcf, min_cash_covenant,
        short_term_debt_maturity=0,
        next_12m_interest=annual_interest,
        next_12m_capex=0,
    )
    capacity = compute_debt_capacity(
        adjusted_ebitda=ebitda,
        existing_debt=debt,
    )
    ranked_options = score_options(runway, leverage, creditor_support)

    return {
        "project": project.get("company_name", "Target Company"),
        "currency": project.get("currency", "EUR"),
        "analysis_period": latest_period,
        "key_metrics": {
            "ebitda": ebitda,
            "gross_debt": debt,
            "leverage_turns": leverage,
            "liquidity_runway_months": runway,
        },
        "liquidity_headroom": liquidity,
        "debt_capacity": capacity,
        "options_ranked": ranked_options,
        "methodology_note": (
            "Options scored on urgency, creditor support and structural need. "
            "All options require bespoke legal and financial diligence before selection. "
            "This paper is a preliminary analytical framework, not legal advice."
        ),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_value(statement: list[dict], line_name: str, period: str | None) -> float | None:
    if not period:
        return None
    for line in statement:
        if line_name.lower() in str(line.get("name", "")).lower():
            return line.get("values", {}).get(period)
    return None


def _liquidity_comment(headroom: float) -> str:
    if headroom > 5_000_000:
        return "Liquidity is adequate. Headroom is comfortable over the next 12 months."
    if headroom > 0:
        return "Liquidity is tight. Monitor monthly. Manage working capital carefully."
    return "Liquidity is critical. Immediate action required: drawdown, new money or covenant waiver."
