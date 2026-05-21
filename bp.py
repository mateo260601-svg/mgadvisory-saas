"""
Documents Routes
-----------------
List, inspect and delete documents uploaded to a project's data room.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.services.extraction_service import list_project_documents
from app.services.project_service import get_project, project_dir, touch_project


router = APIRouter(prefix="/api/projects", tags=["documents"])


@router.get("/{project_id}/documents")
def api_list_documents(project_id: str):
    """List all uploaded documents for a project."""
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    documents = list_project_documents(project_id)
    result = []
    for path in sorted(documents):
        stat = path.stat()
        result.append({
            "filename": path.name,
            "extension": path.suffix.lower(),
            "bytes": stat.st_size,
            "kb": round(stat.st_size / 1024, 1),
            "path": str(path),
        })

    return {
        "project_id": project_id,
        "document_count": len(result),
        "documents": result,
    }


@router.delete("/{project_id}/documents/{filename}")
def api_delete_document(project_id: str, filename: str):
    """Delete a specific document from a project's data room."""
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    # Security: only allow safe filenames
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    doc_path = project_dir(project_id) / "documents" / filename
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    doc_path.unlink()
    touch_project(project_id)

    return {"ok": True, "deleted": filename, "project_id": project_id}
