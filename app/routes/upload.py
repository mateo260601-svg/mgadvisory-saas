from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.extraction_service import save_upload
from app.services.financial_mapping_service import normalize_project_financials
from app.services.project_service import get_project


router = APIRouter(prefix="/api/projects", tags=["upload"])


@router.post("/{project_id}/upload")
async def api_upload_file(project_id: str, file: UploadFile = File(...)):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    saved = await save_upload(project_id, file)
    normalized = normalize_project_financials(project_id)
    return {"file": saved, "normalized": normalized}

