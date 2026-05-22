from __future__ import annotations

import json
from typing import Any

from app.services.project_service import project_dir, touch_project


def default_bp_assumptions(project: dict | None = None) -> dict:
    currency = (project or {}).get("currency", "EUR")
    return {
        "model": {
            "currency": currency,
            "scenario": "Base",
            "model_start_date": "2026-01-31",
            "actuals_end_date": "2025-12-31",
            "historical_source": "Claude extraction",
            "forecast_months": 60,
            "tax_rate": 0.25,
            "opening_cash": 120000,
            "opening_debt": 500000,
            "minimum_cash": 50000,
        },
        "revenue_streams": [
            {"name": "Core product", "type": "Product", "volume": 100, "price": 1000, "volume_growth": 0.01, "price_growth": 0.002},
            {"name": "Services", "type": "Service", "volume": 80, "price": 850, "volume_growth": 0.008, "price_growth": 0.002},
            {"name": "Recurring revenue", "type": "Recurring", "volume": 60, "price": 700, "volume_growth": 0.012, "price_growth": 0.001},
            {"name": "Projects", "type": "Project", "volume": 40, "price": 600, "volume_growth": 0.006, "price_growth": 0.001},
            {"name": "Other", "type": "Other", "volume": 25, "price": 500, "volume_growth": 0.004, "price_growth": 0.001},
        ],
        "historical_actuals": [
            {"model_line": "Revenue", "detail_line": "Product revenue", "fy2022": 0, "fy2023": 0, "fy2024": 0, "fy2025": 0, "latest_actual": 0},
            {"model_line": "Revenue", "detail_line": "Service revenue", "fy2022": 0, "fy2023": 0, "fy2024": 0, "fy2025": 0, "latest_actual": 0},
            {"model_line": "COGS", "detail_line": "Materials", "fy2022": 0, "fy2023": 0, "fy2024": 0, "fy2025": 0, "latest_actual": 0},
            {"model_line": "Payroll", "detail_line": "Management payroll", "fy2022": 0, "fy2023": 0, "fy2024": 0, "fy2025": 0, "latest_actual": 0},
            {"model_line": "Opex", "detail_line": "Rent", "fy2022": 0, "fy2023": 0, "fy2024": 0, "fy2025": 0, "latest_actual": 0},
            {"model_line": "Cash", "detail_line": "Cash at bank", "fy2022": 0, "fy2023": 0, "fy2024": 0, "fy2025": 0, "latest_actual": 0},
            {"model_line": "Closing Debt", "detail_line": "Senior term loan A", "fy2022": 0, "fy2023": 0, "fy2024": 0, "fy2025": 0, "latest_actual": 0},
        ],
        "cost_base": {
            "cogs_percent": 0.35,
            "fulfilment_cost_per_unit": 100,
            "opex_fixed_monthly": 80000,
            "opex_percent_revenue": 0.04,
            "rent_monthly": 12000,
            "professional_fees_monthly": 8000,
            "it_monthly": 5000,
        },
        "cost_items": [
            {"name": "Rent", "driver": "Fixed", "monthly_fixed": 12000, "percent_revenue": 0, "cost_per_fte": 0},
            {"name": "Marketing", "driver": "% Revenue", "monthly_fixed": 0, "percent_revenue": 0.03, "cost_per_fte": 0},
            {"name": "IT & software", "driver": "Per FTE", "monthly_fixed": 5000, "percent_revenue": 0, "cost_per_fte": 120},
            {"name": "Professional fees", "driver": "Fixed", "monthly_fixed": 8000, "percent_revenue": 0, "cost_per_fte": 0},
            {"name": "Travel & commercial", "driver": "% Revenue", "monthly_fixed": 0, "percent_revenue": 0.01, "cost_per_fte": 0},
            {"name": "Other SG&A", "driver": "Fixed", "monthly_fixed": 10000, "percent_revenue": 0, "cost_per_fte": 0},
        ],
        "headcount": [
            {"department": "Management", "opening_fte": 2, "avg_salary_month": 10000, "hiring_every_months": 12, "new_hires": 1},
            {"department": "Sales", "opening_fte": 4, "avg_salary_month": 5000, "hiring_every_months": 6, "new_hires": 1},
            {"department": "Operations", "opening_fte": 8, "avg_salary_month": 4200, "hiring_every_months": 6, "new_hires": 2},
            {"department": "Finance", "opening_fte": 2, "avg_salary_month": 4800, "hiring_every_months": 12, "new_hires": 1},
            {"department": "IT", "opening_fte": 2, "avg_salary_month": 5200, "hiring_every_months": 12, "new_hires": 1},
            {"department": "Admin", "opening_fte": 3, "avg_salary_month": 3500, "hiring_every_months": 12, "new_hires": 1},
        ],
        "working_capital": {
            "dso": 60,
            "dio": 45,
            "dpo": 55,
        },
        "capex": {
            "maintenance_percent_revenue": 0.015,
            "growth_capex_monthly": 15000,
            "depreciation_years": 7,
        },
        "debt_tranches": [
            {
                "name": "Senior Term Loan A",
                "debt_type": "Senior Term Loan",
                "borrower": "OpCo",
                "start_date": "2026-01-31",
                "opening_balance": 500000,
                "commitment": 500000,
                "term_months": 60,
                "moratorium_months": 6,
                "interest_cap_months": 0,
                "margin": 0.045,
                "base_rate": 0.035,
                "amortization": "Linear",
                "bullet_percent": 0.20,
                "cash_sweep_percent": 0.25,
                "interest_type": "Cash",
                "cash_pay_frequency": "Monthly",
                "cash_pay_percent": 1.0,
                "pik": False,
                "minimum_cash": 50000,
            }
        ],
        "covenants": {
            "max_net_debt_ebitda": 3.5,
            "min_interest_cover": 2.0,
            "min_liquidity": 50000,
        },
    }


def load_bp_assumptions(project_id: str, project: dict | None = None) -> dict:
    path = _assumptions_path(project_id)
    if not path.exists():
        assumptions = default_bp_assumptions(project)
        save_bp_assumptions(project_id, assumptions)
        return assumptions
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        current = {}
    return _deep_merge(default_bp_assumptions(project), current)


def save_bp_assumptions(project_id: str, payload: dict[str, Any]) -> dict:
    clean = _deep_merge(default_bp_assumptions(), payload or {})
    path = _assumptions_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    touch_project(project_id)
    return clean


def _assumptions_path(project_id: str):
    return project_dir(project_id) / "bp" / "assumptions.json"


def _deep_merge(base: dict, updates: dict) -> dict:
    merged = dict(base)
    for key, value in (updates or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
