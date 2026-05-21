"""
MG Advisory Finance OS — FastAPI application entry point.

Stability contract:
  - Every route module is loaded inside a try/except.
    If one module fails to import (missing dep, syntax error, etc.)
    the server still starts and serves all other routes.
  - Heavy dependencies (openpyxl, python-pptx, pypdf) are lazy-loaded
    inside builder/service functions, never at module level here.
  - .env is loaded when available (local dev); Railway uses real env vars.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Load .env when present (local dev). Silently ignored if python-dotenv
# is unavailable or .env does not exist — no startup crash.
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except Exception:
    pass

from app.config import APP_NAME, FRONTEND_DIR, ensure_runtime_directories

logger = logging.getLogger("mg_advisory")

# ---------------------------------------------------------------------------
# Route modules to register. Order matters for OpenAPI grouping.
# ---------------------------------------------------------------------------
_ROUTE_MODULES = [
    ("app.routes.auth",           "router"),
    ("app.routes.projects",       "router"),
    ("app.routes.documents",      "router"),
    ("app.routes.upload",         "router"),
    ("app.routes.bp",             "router"),
    ("app.routes.debt",           "router"),
    ("app.routes.qoe",            "router"),
    ("app.routes.restructuring",  "router"),
    ("app.routes.decks",          "router"),
    ("app.routes.ai",             "router"),
]


def create_app() -> FastAPI:
    ensure_runtime_directories()

    app = FastAPI(
        title=APP_NAME,
        version="1.1.0",
        description=(
            "Institutional finance SaaS: business plan modelling, "
            "debt analytics, QoE packs, and transaction outputs."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_routes(app)

    # Serve frontend static files
    if FRONTEND_DIR.exists():
        app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

    @app.get("/", include_in_schema=False)
    def index():
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return JSONResponse({"message": APP_NAME, "status": "running", "docs": "/docs"})

    @app.get("/health")
    def health():
        """Railway health check endpoint."""
        return {"status": "ok", "app": APP_NAME, "version": "1.1.0"}

    return app


def _register_routes(app: FastAPI) -> None:
    failed = []
    for module_path, router_name in _ROUTE_MODULES:
        try:
            module = __import__(module_path, fromlist=[router_name])
            app.include_router(getattr(module, router_name))
        except Exception as exc:
            logger.warning("Route module %s failed to load: %s", module_path, exc)
            failed.append({"module": module_path, "error": str(exc)})

    if failed:
        # Expose a degraded-mode status endpoint listing which modules failed
        @app.get("/system/degraded-modules", include_in_schema=False)
        def degraded_modules():
            return {"degraded": failed}


app = create_app()
