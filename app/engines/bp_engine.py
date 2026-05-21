"""
Business Plan Engine
---------------------
Forecast period generation, revenue bridge, EBITDA build,
working capital cycle, and scenario helpers.

No pandas. Pure Python stdlib.
"""

from __future__ import annotations

from datetime import date


# ---------------------------------------------------------------------------
# Period / date utilities
# ---------------------------------------------------------------------------

def forecast_periods(last_historical_year: str, years: int = 5) -> list[str]:
    """Return FY forecast period labels after the last historical year."""
    year = _extract_year(last_historical_year) or 2025
    return [f"FY{year + i}" for i in range(1, years + 1)]


def monthly_period_labels(start_year: int, start_month: int, n_months: int = 60) -> list[str]:
    """Generate 'YYYY-MM' labels for n_months starting from start_year/start_month."""
    labels = []
    y, m = start_year, start_month
    for _ in range(n_months):
        labels.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return labels


# ---------------------------------------------------------------------------
# Revenue forecasting
# ---------------------------------------------------------------------------

def build_revenue_forecast(
    historical_revenues: dict[str, float],
    growth_rates: dict[str, float],
    forecast_periods_list: list[str],
) -> dict[str, float]:
    """
    Build revenue forecast given explicit growth rates per period.
    growth_rates can be partial; missing periods use the last known rate.
    """
    all_periods = sorted(historical_revenues.keys())
    last_rev = historical_revenues[all_periods[-1]] if all_periods else 1_000_000
    last_rate = 0.05

    forecast: dict[str, float] = {}
    for period in forecast_periods_list:
        rate = growth_rates.get(period, last_rate)
        last_rate = rate
        last_rev = last_rev * (1 + rate)
        forecast[period] = round(last_rev, 0)

    return forecast


# ---------------------------------------------------------------------------
# EBITDA bridge
# ---------------------------------------------------------------------------

def build_ebitda_bridge(
    base_ebitda: float,
    revenue_delta: float,
    gross_margin_pct: float,
    opex_delta: float = 0.0,
    one_off_items: list[dict] | None = None,
) -> dict:
    """
    Waterfall: base EBITDA → revenue contribution → opex savings → one-offs → adjusted.
    """
    revenue_contribution = revenue_delta * gross_margin_pct
    bridge = [
        {"label": "Base EBITDA", "amount": base_ebitda, "cumulative": base_ebitda},
        {"label": "Revenue contribution", "amount": revenue_contribution, "cumulative": base_ebitda + revenue_contribution},
    ]
    running = base_ebitda + revenue_contribution

    if opex_delta:
        running += opex_delta
        bridge.append({"label": "Opex change", "amount": opex_delta, "cumulative": running})

    for item in (one_off_items or []):
        amount = item.get("amount", 0)
        running += amount
        bridge.append({"label": item.get("label", "Adjustment"), "amount": amount, "cumulative": running})

    bridge.append({"label": "Adjusted EBITDA", "amount": 0, "cumulative": running})

    return {
        "bridge_steps": bridge,
        "adjusted_ebitda": running,
        "gross_margin_pct": gross_margin_pct,
    }


# ---------------------------------------------------------------------------
# Working capital cycle in forecast
# ---------------------------------------------------------------------------

def forecast_working_capital(
    revenue_forecast: dict[str, float],
    dso_days: float = 60.0,
    dpo_days: float = 45.0,
    dio_days: float = 30.0,
    cogs_pct: float = 0.5,
) -> dict[str, dict]:
    """
    Compute NWC items for each forecast period using DSO/DPO/DIO assumptions.
    """
    result = {}
    for period, rev in revenue_forecast.items():
        cogs = rev * cogs_pct
        receivables = rev / 365 * dso_days
        payables = cogs / 365 * dpo_days
        inventory = cogs / 365 * dio_days
        nwc = receivables + inventory - payables
        result[period] = {
            "revenue": round(rev, 0),
            "receivables": round(receivables, 0),
            "payables": round(payables, 0),
            "inventory": round(inventory, 0),
            "net_working_capital": round(nwc, 0),
        }
    return result


# ---------------------------------------------------------------------------
# Scenario helpers
# ---------------------------------------------------------------------------

SCENARIOS = {
    "Base": {"revenue_growth_delta": 0.0, "margin_delta": 0.0},
    "Upside": {"revenue_growth_delta": 0.03, "margin_delta": 0.02},
    "Downside": {"revenue_growth_delta": -0.03, "margin_delta": -0.02},
    "Stress": {"revenue_growth_delta": -0.08, "margin_delta": -0.05},
    "Management": {"revenue_growth_delta": 0.05, "margin_delta": 0.02},
}


def apply_scenario(
    base_revenues: dict[str, float],
    base_margin: float,
    scenario_name: str,
) -> dict:
    """Apply a named scenario delta to base revenues and margin."""
    scenario = SCENARIOS.get(scenario_name, SCENARIOS["Base"])
    rev_delta = scenario["revenue_growth_delta"]
    margin_delta = scenario["margin_delta"]

    adjusted_revenues = {p: round(v * (1 + rev_delta), 0) for p, v in base_revenues.items()}
    adjusted_margin = base_margin + margin_delta

    return {
        "scenario": scenario_name,
        "revenues": adjusted_revenues,
        "ebitda_margin_pct": round(adjusted_margin, 4),
        "ebitda": {p: round(v * adjusted_margin, 0) for p, v in adjusted_revenues.items()},
    }


def available_scenarios() -> list[str]:
    return list(SCENARIOS.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_year(period: str) -> int | None:
    digits = "".join(c for c in period if c.isdigit())
    if len(digits) >= 4:
        return int(digits[-4:])
    return None
