from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.output_service import build_lender_deck
from app.services.deck_planning_service import build_deck_blueprint, load_deck_blueprint
from app.services.project_service import get_project
from app.services.template_service import list_pptx_templates


router = APIRouter(prefix="/api", tags=["decks"])


@router.get("/decks/status")
def deck_status():
    return {
        "status": "online",
        "message": "Institutional lender presentation generation is available.",
    }


@router.get("/decks/templates")
def deck_templates():
    return list_pptx_templates()


@router.post("/projects/{project_id}/decks/lender/plan")
def api_plan_lender_deck(project_id: str):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return build_deck_blueprint(project_id, deck_type="lender", force=True)


@router.get("/projects/{project_id}/decks/lender/blueprint")
def api_get_lender_blueprint(project_id: str):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return load_deck_blueprint(project_id, deck_type="lender")


@router.post("/projects/{project_id}/decks/lender/generate")
def api_generate_lender_deck(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    output = build_lender_deck(project_id)
    return {"output": output}


@router.get("/projects/{project_id}/decks/lender/download")
def api_download_lender_deck(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    output = build_lender_deck(project_id)
    return FileResponse(
        output["path"],
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=output["filename"],
    )
