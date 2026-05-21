from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.output_service import build_bp_model
from app.services.bp_assumption_service import default_bp_assumptions, load_bp_assumptions, save_bp_assumptions
from app.services.project_service import get_project


router = APIRouter(prefix="/api/projects", tags=["business-plan"])


class BpAssumptionPayload(BaseModel):
    assumptions: dict[str, Any]


@router.get("/{project_id}/bp/assumptions")
def api_get_bp_assumptions(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"assumptions": load_bp_assumptions(project_id, project)}


@router.put("/{project_id}/bp/assumptions")
def api_save_bp_assumptions(project_id: str, payload: BpAssumptionPayload):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    assumptions = save_bp_assumptions(project_id, payload.assumptions)
    return {"assumptions": assumptions}


@router.post("/{project_id}/bp/assumptions/reset")
def api_reset_bp_assumptions(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    assumptions = save_bp_assumptions(project_id, default_bp_assumptions(project))
    return {"assumptions": assumptions}


@router.post("/{project_id}/bp/generate")
def api_generate_bp(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    output = build_bp_model(project_id)
    return {"output": output}


@router.get("/{project_id}/bp/download")
def api_download_bp(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    output = build_bp_model(project_id)
    return FileResponse(
        output["path"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=output["filename"],
    )
