from fastapi import APIRouter, HTTPException

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ai_service import claude_status, chat_with_claude, extract_financials_from_chat, generate_project_brief
from app.services.bp_assumption_service import load_bp_assumptions, save_bp_assumptions
from app.services.financial_mapping_service import (
    load_normalized_financials,
    merge_ai_extraction_into_financials,
    normalize_project_financials,
    save_normalized_financials,
)
from app.services.project_service import get_project


router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@router.get("/status")
def ai_status():
    return claude_status()


@router.post("/projects/{project_id}/brief")
def ai_project_brief(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    financials = load_normalized_financials(project_id)
    return generate_project_brief(project, financials)


@router.post("/projects/{project_id}/extract-historicals")
def ai_extract_historicals(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    normalized = normalize_project_financials(project_id, use_ai=True)
    return {
        "ok": True,
        "project_id": project_id,
        "normalized": normalized,
        "extraction": normalized.get("extraction", {}),
    }


@router.get("/projects/{project_id}/financials")
def ai_project_financials(project_id: str):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return load_normalized_financials(project_id)


@router.post("/projects/{project_id}/chat")
def ai_chat(project_id: str, payload: ChatRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    financials = load_normalized_financials(project_id)
    return chat_with_claude(project, financials, payload.message, payload.history)


@router.post("/projects/{project_id}/chat/apply")
def ai_chat_apply(project_id: str, payload: ChatRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    current = load_normalized_financials(project_id)
    ai_result = extract_financials_from_chat(project, current, payload.message, payload.history)
    merged = merge_ai_extraction_into_financials(current, ai_result)
    save_normalized_financials(project_id, merged)
    assumptions = _apply_extraction_to_bp_assumptions(project_id, project, ai_result.get("extraction") or {})
    return {
        "ok": True,
        "project_id": project_id,
        "source": ai_result.get("source"),
        "configured": ai_result.get("configured"),
        "extraction": merged.get("extraction", {}),
        "normalized": merged,
        "assumptions": assumptions,
    }


def _apply_extraction_to_bp_assumptions(project_id: str, project: dict, extraction: dict) -> dict:
    assumptions = load_bp_assumptions(project_id, project)
    historical_lines = []
    for line in extraction.get("historical_detail", []) or []:
        values = line.get("values") or {}
        periods = sorted(values)
        latest_period = periods[-1] if periods else None
        historical_lines.append(
            {
                "model_line": line.get("model_line") or line.get("category") or "",
                "detail_line": line.get("detail_line") or line.get("model_line") or "",
                "fy2022": values.get("FY2022", 0) or 0,
                "fy2023": values.get("FY2023", 0) or 0,
                "fy2024": values.get("FY2024", 0) or 0,
                "fy2025": values.get("FY2025", 0) or 0,
                "latest_actual": values.get(latest_period, 0) if latest_period else 0,
            }
        )
    if historical_lines:
        assumptions["historical_actuals"] = historical_lines[:24]

    bp_assumptions = extraction.get("bp_assumptions") or {}
    for key in ["revenue_streams", "cost_items", "debt_tranches"]:
        if bp_assumptions.get(key):
            assumptions[key] = bp_assumptions[key]
    assumptions.setdefault("model", {})["historical_source"] = "Claude chat"
    return save_bp_assumptions(project_id, assumptions)
