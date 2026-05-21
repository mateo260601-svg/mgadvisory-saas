import json

from app.config import BASE_DIR


PPTX_TEMPLATE_DIR = BASE_DIR / "templates" / "pptx"
PPTX_MANIFEST_PATH = PPTX_TEMPLATE_DIR / "template_manifest.json"


def list_pptx_templates() -> dict:
    templates = []
    for path in sorted(PPTX_TEMPLATE_DIR.glob("*.pptx")) if PPTX_TEMPLATE_DIR.exists() else []:
        templates.append(
            {
                "filename": path.name,
                "bytes": path.stat().st_size,
                "role": _template_role(path.name),
            }
        )

    manifest = {}
    if PPTX_MANIFEST_PATH.exists():
        try:
            manifest = json.loads(PPTX_MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            manifest = {"error": "Manifest could not be read"}

    return {
        "template_dir": str(PPTX_TEMPLATE_DIR),
        "templates": templates,
        "manifest_available": bool(manifest),
        "manifest": manifest,
    }


def load_pptx_template_manifest() -> dict:
    if not PPTX_MANIFEST_PATH.exists():
        return {"templates": [], "usage_principles": []}
    try:
        return json.loads(PPTX_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"templates": [], "usage_principles": [], "error": "Manifest could not be read"}


def compact_pptx_pattern_library(limit_per_template: int = 40) -> dict:
    manifest = load_pptx_template_manifest()
    compact = {
        "usage_principles": manifest.get("usage_principles", []),
        "templates": [],
    }
    for template in manifest.get("templates", []):
        slides = []
        for slide in template.get("slides", [])[:limit_per_template]:
            preview = slide.get("text_preview", "")
            layout = slide.get("layout", "")
            slides.append(
                {
                    "template_file": template.get("file"),
                    "slide_number": slide.get("slide"),
                    "layout": layout,
                    "pattern_type": _infer_pattern_type(layout, preview),
                    "text_preview": preview[:220],
                    "shape_count": slide.get("shape_count"),
                }
            )
        compact["templates"].append(
            {
                "file": template.get("file"),
                "slide_count": template.get("slide_count"),
                "patterns": slides,
            }
        )
    return compact


def _template_role(filename: str) -> str:
    if "book_schemas" in filename:
        return "slide_pattern_library"
    if "im_draft" in filename:
        return "im_narrative_reference"
    return "reference"


def _infer_pattern_type(layout: str, preview: str) -> str:
    text = f"{layout} {preview}".lower()
    if "divider" in text or "section" in text:
        return "section_divider"
    if "timeline" in text or "next steps" in text or "process" in text:
        return "timeline_or_process"
    if "chart" in text or "%" in text or "ebitda" in text or "revenue" in text:
        return "chart_or_financial_analysis"
    if "contents" in text or "agenda" in text or "index" in text:
        return "agenda_or_contents"
    if "investment highlights" in text or "why acquire" in text:
        return "investment_highlights"
    if "market" in text or "strategic" in text:
        return "market_or_strategy"
    if "title" in text:
        return "title_or_cover"
    return "general_content"
