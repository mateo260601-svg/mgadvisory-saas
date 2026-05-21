"""
Restructuring Routes
---------------------
Endpoints for the restructuring options paper:
liquidity runway, debt capacity, and ranked options.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.engines.restructuring_engine import (
    build_restructuring_paper,
    compute_debt_capacity,
    compute_liquidity_headroom,
    estimate_liquidity_runway,
    score_options,
    RESTRUCTURING_OPTIONS,
)
from app.services.financial_mapping_service import load_normalized_financials
from app.services.project_service import get_project


router = APIRouter(prefix="/api/restructuring", tags=["restructuring"])


class LiquidityRequest(BaseModel):
    opening_cash: float = Field(default=0.0, ge=0)
    monthly_burn: float = Field(default=0.0, ge=0)
    undrawn_rcf: float = Field(default=0.0, ge=0)
    min_cash_covenant: float = Field(default=0.0, ge=0)
    next_12m_interest: float = Field(default=0.0, ge=0)
    next_12m_capex: float = Field(default=0.0, ge=0)


class OptionsRequest(BaseModel):
    opening_cash: float = 0.0
    monthly_burn: float = 0.0
    undrawn_rcf: float = 0.0
    min_cash_covenant: float = 0.0
    creditor_support: str = "unknown"


@router.get("/status")
def restructuring_status():
    return {
        "status": "online",
        "message": "Restructuring options engine is available.",
        "options_count": len(RESTRUCTURING_OPTIONS),
    }


@router.get("/options-library")
def options_library():
    """Return the full library of restructuring options."""
    return {"options": RESTRUCTURING_OPTIONS}


@router.post("/liquidity-analysis")
def api_liquidity(body: LiquidityRequest):
    """Standalone liquidity runway and headroom analysis."""
    runway = estimate_liquidity_runway(body.opening_cash, body.monthly_burn)
    headroom = compute_liquidity_headroom(
        body.opening_cash,
        body.undrawn_rcf,
        body.min_cash_covenant,
        short_term_debt_maturity=0,
        next_12m_interest=body.next_12m_interest,
        next_12m_capex=body.next_12m_capex,
    )
    return {"runway_months": runway, "headroom": headroom}


@router.post("/debt-capacity")
def api_debt_capacity(
    adjusted_ebitda: float,
    existing_debt: float = 0.0,
    max_leverage: float = 4.0,
    min_dscr: float = 1.25,
    interest_rate: float = 0.07,
):
    """Standalone debt capacity calculation."""
    return compute_debt_capacity(adjusted_ebitda, max_leverage, min_dscr, interest_rate, existing_debt)


@router.post("/projects/{project_id}/paper")
def api_restructuring_paper(project_id: str, body: OptionsRequest | None = None):
    """Generate the full restructuring options paper for a project."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    financials = load_normalized_financials(project_id)
    opts = body or OptionsRequest()

    return build_restructuring_paper(
        project,
        financials,
        opening_cash=opts.opening_cash,
        monthly_burn=opts.monthly_burn,
        undrawn_rcf=opts.undrawn_rcf,
        min_cash_covenant=opts.min_cash_covenant,
        creditor_support=opts.creditor_support,
    )
