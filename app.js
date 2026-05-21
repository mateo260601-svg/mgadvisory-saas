from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.output_service import build_bp_model
from app.services.project_service import get_project


router = APIRouter(prefix="/api/projects", tags=["business-plan"])


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

