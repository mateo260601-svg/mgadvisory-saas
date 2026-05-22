"""
Projects Routes
----------------
CRUD endpoints for projects: create, list, get, update, archive.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.routes.auth import account_from_request
from app.schemas.project_schema import ProjectCreate, ProjectUpdate
from app.services.project_service import (
    archive_project,
    create_project,
    get_project,
    list_projects,
    update_project,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def api_list_projects(request: Request):
    return {"projects": list_projects(account_from_request(request))}


@router.post("")
def api_create_project(payload: ProjectCreate, request: Request):
    project = create_project(payload, account_from_request(request))
    return {"project": project}


@router.get("/{project_id}")
def api_get_project(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": project}


@router.patch("/{project_id}")
def api_update_project(project_id: str, payload: ProjectUpdate):
    """Partially update a project (any field can be omitted)."""
    updated = update_project(project_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": updated}


@router.post("/{project_id}/archive")
def api_archive_project(project_id: str):
    """Soft-archive a project (does not delete files)."""
    archived = archive_project(project_id)
    if not archived:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True, "project": archived}
