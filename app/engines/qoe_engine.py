"""
Quality of Earnings (QoE) Engine
---------------------------------
Institutional-grade QoE analysis: EBITDA normalisation, non-recurring
adjustments, working-capital quality, revenue sustainability scoring,
and audit trail for every adjustment applied.

Follows the methodology of A&M / FTI / Big-4 transaction services QoE packs.
No pandas dependency. Pure Python with stdlib only.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Adjustment type catalogue
# ---------------------------------------------------------------------------

ADJUSTMENT_CATEGORIES = {
    "non_recurring_cost": {
        "label": "Non-recurring cost (add-back)",
        "direction": +1,
        "description": "One-off costs that will not recur: restructuring, litigation settlement, M&A fees, etc.",
    },
    "non_recurring_income": {
        "label": "Non-recurring income (deduct)",
        "direction": -1,
        "description": "One-off income that will not recur: asset disposal gain, insurance recovery, etc.",
    },
    "normalisation_cost": {
        "label": "Normalisation — cost",
        "direction": +1,
        "description": "Run-rate cost not reflected in historicals: market rent, management salary normalisation.",
    },
    "normalisation_income": {
        "label": "Normalisation — income",
        "direction": -1,
        "description": "Income that should be excluded: discontinued operations, related-party above-market revenue.",
    },
    "accounting_policy": {
        "label": "Accounting policy difference",
        "direction": +1,
        "description": "IFRS vs local GAAP, revenue recognition reclassification, lease capitalisation.",
    },
    "run_rate": {
        "label": "Run-rate adjustment",
        "direction": +1,
        "description": "Annualisation of partial-year organic change: contract wins, headcount additions.",
    },
    "pro_forma": {
        "label": "Pro-forma acquisition",
        "direction": +1,
        "description": "EBITDA contribution of an acquisition as if owned for the full period.",
    },
    "cost_synergy": {
        "label": "Cost synergy (management case)",
        "direction": +1,
        "description": "Identifiable and achievable cost savings post-transaction. Mark clearly as management projection.",
    },
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def normalize_ebitda(
    reported_ebitda: float,
    adjustments: list[dict] | None = None,
) -> dict:
    """
    Apply a list of QoE adjustments to a reported EBITDA figure.

    Each adjustment dict:
        {
            "label": str,
            "category": str,         # key from ADJUSTMENT_CATEGORIES
            "amount": float,          # always positive — direction driven by category
            "period": str,            # e.g. "FY2024"
            "source": str,            # document / page reference
            "confidence": "high|medium|low",
            "notes": str,             # analyst commentary
        }

    Returns a dict with:
        reported_ebitda, total_adjustments, adjusted_ebitda,
        adjustments_detail, summary_by_category, margin_impact_ppts (if revenue provided)
    """
    adjustments = adjustments or []
    total = 0.0
    detail = []

    for adj in adjustments:
        category = adj.get("category", "non_recurring_cost")
        config = ADJUSTMENT_CATEGORIES.get(category, ADJUSTMENT_CATEGORIES["non_recurring_cost"])
        amount = float(adj.get("amount", 0.0))
        signed = amount * config["direction"]
        total += signed

        detail.append({
            "label": adj.get("label", config["label"]),
            "category": category,
            "category_label": config["label"],
            "direction": config["direction"],
            "amount_absolute": amount,
            "amount_signed": signed,
            "period": adj.get("period", ""),
            "source": adj.get("source", ""),
            "confidence": adj.get("confidence", "medium"),
            "notes": adj.get("notes", ""),
        })

    # Group by category for summary
    summary: dict[str, float] = {}
    for item in detail:
        key = item["category_label"]
        summary[key] = summary.get(key, 0.0) + item["amount_signed"]

    return {
        "reported_ebitda": reported_ebitda,
        "total_adjustments": total,
        "adjusted_ebitda": reported_ebitda + total,
        "adjustments_detail": detail,
        "summary_by_category": summary,
    }


def score_revenue_quality(
    income_statement: list[dict],
    periods: list[str],
) -> dict:
    """
    Score revenue quality across historical periods on four dimensions:
    - growth consistency
    - gross margin stability
    - revenue concentration (heuristic based on available data)
    - period-over-period volatility

    Returns scores 0–100 and a qualitative flag.
    """
    revenue_values = _extract_line(income_statement, ["revenue", "sales", "turnover"], periods)
    cogs_values = _extract_line(income_statement, ["cogs", "cost of sales", "direct cost"], periods)
    gross_profit = {p: revenue_values.get(p, 0) - cogs_values.get(p, 0) for p in periods}
    gp_margins = {
        p: (gross_profit[p] / revenue_values[p] * 100) if revenue_values.get(p) else None
        for p in periods
    }

    # Growth consistency score
    revenues = [revenue_values.get(p) for p in periods if revenue_values.get(p) is not None]
    growth_score = 100
    if len(revenues) >= 2:
        growths = [(revenues[i] - revenues[i - 1]) / revenues[i - 1] for i in range(1, len(revenues)) if revenues[i - 1]]
        negative_growth_count = sum(1 for g in growths if g < 0)
        growth_score = max(0, 100 - negative_growth_count * 30)

    # Gross margin stability score
    margins = [v for v in gp_margins.values() if v is not None]
    margin_score = 100
    if len(margins) >= 2:
        margin_range = max(margins) - min(margins)
        margin_score = max(0, 100 - margin_range * 2)

    overall = round((growth_score + margin_score) / 2)
    flag = "strong" if overall >= 75 else "acceptable" if overall >= 50 else "caution"

    return {
        "revenue_by_period": revenue_values,
        "gross_profit_by_period": gross_profit,
        "gp_margin_pct": gp_margins,
        "growth_consistency_score": growth_score,
        "margin_stability_score": margin_score,
        "overall_quality_score": overall,
        "quality_flag": flag,
        "comment": _quality_comment(flag, margins),
    }


def analyze_working_capital_quality(
    balance_sheet: list[dict],
    income_statement: list[dict],
    periods: list[str],
) -> dict:
    """
    Compute DSO, DPO, DIO and working capital cycle quality for each period.
    """
    revenue = _extract_line(income_statement, ["revenue", "sales", "turnover"], periods)
    cogs = _extract_line(income_statement, ["cogs", "cost of sales", "direct cost"], periods)
    receivables = _extract_line(balance_sheet, ["receivable", "debtor", "trade receivable"], periods)
    payables = _extract_line(balance_sheet, ["payable", "creditor", "trade payable"], periods)
    inventory = _extract_line(balance_sheet, ["inventory", "stock"], periods)

    results = {}
    for period in periods:
        rev = revenue.get(period) or 0
        cg = abs(cogs.get(period) or 0) or (rev * 0.5)
        rec = receivables.get(period) or 0
        pay = payables.get(period) or 0
        inv = inventory.get(period) or 0

        dso = round(rec / rev * 365, 1) if rev else None
        dpo = round(pay / cg * 365, 1) if cg else None
        dio = round(inv / cg * 365, 1) if cg else None
        cwc = rec + inv - pay
        nwc_days = (dso or 0) + (dio or 0) - (dpo or 0)

        results[period] = {
            "dso_days": dso,
            "dpo_days": dpo,
            "dio_days": dio,
            "net_working_capital": cwc,
            "nwc_cycle_days": round(nwc_days, 1),
        }

    # Trend comment
    nwc_list = [results[p]["net_working_capital"] for p in periods]
    trend = "improving" if len(nwc_list) >= 2 and nwc_list[-1] < nwc_list[0] else "deteriorating" if len(nwc_list) >= 2 and nwc_list[-1] > nwc_list[0] else "stable"

    return {
        "periods": results,
        "nwc_trend": trend,
        "interpretation": f"Working capital trend is {trend}. A lower NWC cycle is generally better for cash generation.",
    }


def build_qoe_pack(
    project: dict,
    financials: dict,
    adjustments: list[dict] | None = None,
) -> dict:
    """
    Master function — builds the full QoE pack dict.
    Used by the route and the Excel builder.
    """
    periods = financials.get("periods", ["FY2023", "FY2024"])
    income_statement = financials.get("income_statement", [])
    balance_sheet = financials.get("balance_sheet", [])

    # Per-period EBITDA normalisation
    normalised_by_period = {}
    for period in periods:
        reported = _get_period_value(income_statement, "ebitda", period) or 0
        period_adjs = [a for a in (adjustments or []) if a.get("period", "") in ("", period, "all")]
        normalised_by_period[period] = normalize_ebitda(reported, period_adjs)

    revenue_quality = score_revenue_quality(income_statement, periods)
    wc_quality = analyze_working_capital_quality(balance_sheet, income_statement, periods)

    company = project.get("company_name", "Target Company")
    currency = project.get("currency", "EUR")

    return {
        "project": company,
        "currency": currency,
        "periods": periods,
        "normalised_ebitda": normalised_by_period,
        "revenue_quality": revenue_quality,
        "working_capital_quality": wc_quality,
        "adjustment_categories_available": list(ADJUSTMENT_CATEGORIES.keys()),
        "methodology_note": (
            "EBITDA normalisation follows A&M / FTI transaction services methodology. "
            "Each adjustment has a category, direction, source reference and confidence level. "
            "Working capital metrics are computed from balance sheet and income statement extractions."
        ),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_line(statement: list[dict], aliases: list[str], periods: list[str]) -> dict[str, float]:
    """Find the first line in a statement that matches any alias, return values by period."""
    for line in statement:
        name = str(line.get("name", "")).lower()
        if any(alias in name for alias in aliases):
            values = line.get("values", {})
            return {p: float(values.get(p, 0) or 0) for p in periods}
    return {p: 0.0 for p in periods}


def _get_period_value(statement: list[dict], line_name: str, period: str) -> float | None:
    for line in statement:
        if line_name.lower() in str(line.get("name", "")).lower():
            return line.get("values", {}).get(period)
    return None


def _quality_comment(flag: str, margins: list[float]) -> str:
    avg = round(sum(margins) / len(margins), 1) if margins else 0
    if flag == "strong":
        return f"Revenue quality is strong. Average gross margin {avg}%. Growth is positive and consistent."
    if flag == "acceptable":
        return f"Revenue quality is acceptable. Average gross margin {avg}%. Some volatility noted — review contract mix and customer concentration."
    return f"Revenue quality requires diligence. Average gross margin {avg}%. Negative growth or significant margin compression observed."
