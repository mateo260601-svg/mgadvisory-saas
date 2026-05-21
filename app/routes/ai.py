from fastapi import APIRouter, HTTPException

from app.services.ai_service import claude_status, generate_project_brief
from app.services.financial_mapping_service import load_normalized_financials, normalize_project_financials
from app.services.project_service import get_project


router = APIRouter(prefix="/api/ai", tags=["ai"])


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
