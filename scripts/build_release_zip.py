from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
ZIP_NAME = "MG_Strategic_Finance_AI_GitHub_READY.zip"

INCLUDE_ROOT_FILES = {
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "Procfile",
    "RAILWAY_SETUP.md",
    "README.md",
    "railway.json",
    "requirements.txt",
    "runtime.txt",
}
INCLUDE_DIRS = {"app", "frontend", "templates", "scripts"}
INCLUDE_PLACEHOLDERS = {"data/.gitkeep", "outputs/.gitkeep"}
SKIP_PARTS = {"__pycache__", ".git", ".venv", "venv", "env"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".xlsx", ".pptx", ".pdf", ".docx", ".log"}


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    parts = set(path.relative_to(ROOT).parts)
    if path.name == ZIP_NAME:
        return False
    if parts & SKIP_PARTS:
        return False
    if rel in INCLUDE_PLACEHOLDERS:
        return True
    if path.name in INCLUDE_ROOT_FILES and path.parent == ROOT:
        return True
    if path.parts[len(ROOT.parts)] in INCLUDE_DIRS:
        return path.suffix.lower() not in SKIP_SUFFIXES
    return False


def main() -> None:
    output_path = ROOT / ZIP_NAME
    if output_path.exists():
        output_path.unlink()
    with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and should_include(path):
                archive.write(path, path.relative_to(ROOT).as_posix())
    print(output_path)


if __name__ == "__main__":
    main()
