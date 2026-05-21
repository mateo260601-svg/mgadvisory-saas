"""
Application configuration.
All values can be overridden via environment variables (Railway > Variables).
"""

from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR))).resolve()
DATA_DIR = STORAGE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = BASE_DIR / "templates"

APP_NAME = "MG Advisory Finance OS"

# --- Auth ---
DEFAULT_LICENSE_KEY = "MG-ADVISORY-DEMO-2026"
LICENSE_KEY = os.getenv("MG_LICENSE_KEY", DEFAULT_LICENSE_KEY)
APP_SECRET = os.getenv("APP_SECRET", "change-me-in-production")

# --- Google OAuth (all optional) ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")
GOOGLE_ALLOWED_DOMAINS = {
    domain.strip().lower()
    for domain in os.getenv("GOOGLE_ALLOWED_DOMAINS", "").split(",")
    if domain.strip()
}

# --- Claude / Anthropic (optional) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# --- Upload limits ---
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".xlsx", ".xlsm", ".csv"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def ensure_runtime_directories() -> None:
    """Create all required runtime directories at startup."""
    for directory in [PROJECTS_DIR, OUTPUTS_DIR, TEMPLATES_DIR / "pptx"]:
        directory.mkdir(parents=True, exist_ok=True)
