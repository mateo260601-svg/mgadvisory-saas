from pathlib import Path
import re

from fastapi import HTTPException, UploadFile

from app.config import ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_BYTES
from app.services.project_service import project_dir, touch_project


async def save_upload(project_id: str, file: UploadFile) -> dict:
    original_name = file.filename or "uploaded_file"
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")

    safe_name = _safe_filename(original_name)
    target_dir = project_dir(project_id) / "documents"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = _dedupe_path(target_dir / safe_name)

    size = 0
    with target_path.open("wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large")
            buffer.write(chunk)

    touch_project(project_id)
    return {
        "filename": target_path.name,
        "original_filename": original_name,
        "path": str(target_path),
        "bytes": size,
        "extension": extension,
    }


def list_project_documents(project_id: str) -> list[Path]:
    documents_dir = project_dir(project_id) / "documents"
    if not documents_dir.exists():
        return []
    return [path for path in documents_dir.iterdir() if path.is_file()]


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename.strip())
    return cleaned[:140] or "uploaded_file"


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 1000):
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise HTTPException(status_code=500, detail="Could not allocate upload filename")

