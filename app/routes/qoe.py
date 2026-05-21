"""
QoE (Quality of Earnings) Routes
----------------------------------
Endpoints for the QoE pack: EBITDA normalisation, revenue quality,
working capital quality, and full QoE pack generation.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from app.engines.qoe_engine import (
    ADJUSTMENT_CATEGORIES,
    build_qoe_pack,
    normalize_ebitda,
    score_revenue_quality,
    analyze_working_capital_quality,
)
from app.services.financial_mapping_service import load_normalized_financials
from app.services.project_service import get_project


router = APIRouter(prefix="/api/qoe", tags=["qoe"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class QoEAdjustment(BaseModel):
    label: str = ""
    category: str = "non_recurring_cost"
    amount: float = Field(..., ge=0)
    period: str = ""
    source: str = ""
    confidence: str = "medium"
    notes: str = ""


class QoePackRequest(BaseModel):
    adjustments: list[QoEAdjustment] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status")
def qoe_status():
    return {
        "status": "online",
        "message": "QoE pack engine is available.",
        "capabilities": [
            "EBITDA normalisation with audit trail",
            "Revenue quality scoring",
            "Working capital quality analysis",
            "Full QoE pack per project",
        ],
    }


@router.get("/adjustment-categories")
def adjustment_categories():
    """Return the full catalogue of QoE adjustment types."""
    return {"categories": ADJUSTMENT_CATEGORIES}


@router.post("/normalize-ebitda")
def api_normalize_ebitda(
    reported_ebitda: float,
    adjustments: list[QoEAdjustment] | None = None,
):
    """
    Quick standalone EBITDA normalisation — no project needed.
    """
    adj_dicts = [a.model_dump() for a in (adjustments or [])]
    return normalize_ebitda(reported_ebitda, adj_dicts)


@router.get("/projects/{project_id}/revenue-quality")
def api_revenue_quality(project_id: str):
    """Revenue quality scoring for a project's extracted financials."""
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    financials = load_normalized_financials(project_id)
    periods = financials.get("periods", [])
    income_statement = financials.get("income_statement", [])
    if not periods or not income_statement:
        raise HTTPException(status_code=422, detail="No normalised financials available. Upload source documents first.")
    return score_revenue_quality(income_statement, periods)


@router.get("/projects/{project_id}/working-capital-quality")
def api_wc_quality(project_id: str):
    """Working capital quality (DSO/DPO/DIO) for a project."""
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    financials = load_normalized_financials(project_id)
    periods = financials.get("periods", [])
    if not periods:
        raise HTTPException(status_code=422, detail="No normalised financials available.")
    return analyze_working_capital_quality(
        financials.get("balance_sheet", []),
        financials.get("income_statement", []),
        periods,
    )


@router.post("/projects/{project_id}/pack")
def api_qoe_pack(project_id: str, body: QoePackRequest | None = None):
    """
    Generate the full QoE pack for a project.
    Optionally supply an adjustments list in the request body.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    financials = load_normalized_financials(project_id)
    adjustments = [a.model_dump() for a in (body.adjustments if body else [])]
    return build_qoe_pack(project, financials, adjustments)
