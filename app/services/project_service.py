"""
Project Service
----------------
CRUD operations for projects stored as JSON files under data/projects/.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from app.config import PROJECTS_DIR
from app.schemas.project_schema import ProjectCreate, ProjectUpdate


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def project_metadata_path(project_id: str) -> Path:
    return project_dir(project_id) / "project.json"


def create_project(payload: ProjectCreate, owner_email: str | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    project_id = uuid4().hex[:12]
    directory = project_dir(project_id)
    (directory / "documents").mkdir(parents=True, exist_ok=True)
    (directory / "normalized").mkdir(parents=True, exist_ok=True)
    (directory / "decks").mkdir(parents=True, exist_ok=True)

    project = {
        "id": project_id,
        "company_name": payload.company_name.strip(),
        "project_type": payload.project_type.strip(),
        "currency": payload.currency.strip().upper(),
        "fiscal_year_end": payload.fiscal_year_end.strip(),
        "industry": payload.industry.strip(),
        "country": payload.country.strip(),
        "description": payload.description.strip(),
        "notes": payload.notes.strip(),
        "owner_email": (owner_email or "license:local-demo").strip().lower(),
        "created_at": now,
        "updated_at": now,
        "status": "active",
    }
    _write_json(project_metadata_path(project_id), project)
    return project


def list_projects(owner_email: str | None = None) -> list[dict]:
    projects = []
    if not PROJECTS_DIR.exists():
        return projects
    for path in sorted(PROJECTS_DIR.glob("*/project.json")):
        try:
            project = _read_json(path)
            owner = str(project.get("owner_email", "")).strip().lower()
            if owner_email and not owner:
                project["owner_email"] = owner_email.strip().lower()
                _write_json(path, project)
                owner = project["owner_email"]
            if owner_email and owner and owner != owner_email.strip().lower():
                continue
            projects.append(project)
        except Exception:
            continue
    return sorted(projects, key=lambda item: item.get("created_at", ""), reverse=True)


def get_project(project_id: str) -> dict | None:
    path = project_metadata_path(project_id)
    if not path.exists():
        return None
    try:
        return _read_json(path)
    except Exception:
        return None


def update_project(project_id: str, payload: ProjectUpdate) -> dict | None:
    project = get_project(project_id)
    if not project:
        return None

    updates = payload.model_dump(exclude_none=True)
    if "currency" in updates:
        updates["currency"] = updates["currency"].strip().upper()
    if "company_name" in updates:
        updates["company_name"] = updates["company_name"].strip()

    project.update(updates)
    project["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(project_metadata_path(project_id), project)
    return project


def archive_project(project_id: str) -> dict | None:
    """Soft-delete: mark status as 'archived'."""
    project = get_project(project_id)
    if not project:
        return None
    project["status"] = "archived"
    project["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(project_metadata_path(project_id), project)
    return project


def touch_project(project_id: str) -> None:
    project = get_project(project_id)
    if not project:
        return
    project["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(project_metadata_path(project_id), project)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
