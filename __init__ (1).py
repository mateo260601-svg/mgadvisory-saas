import json

from app.services.ai_service import plan_deck_from_templates
from app.services.financial_mapping_service import load_normalized_financials
from app.services.project_service import get_project, project_dir
from app.services.template_service import compact_pptx_pattern_library


def build_deck_blueprint(project_id: str, deck_type: str = "lender", force: bool = False) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Project not found")

    output_path = _blueprint_path(project_id, deck_type)
    if output_path.exists() and not force:
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    financials = load_normalized_financials(project_id)
    pattern_library = compact_pptx_pattern_library()
    result = plan_deck_from_templates(project, financials, pattern_library, deck_type=deck_type)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def load_deck_blueprint(project_id: str, deck_type: str = "lender") -> dict:
    output_path = _blueprint_path(project_id, deck_type)
    if output_path.exists():
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return build_deck_blueprint(project_id, deck_type=deck_type, force=False)


def _blueprint_path(project_id: str, deck_type: str):
    return project_dir(project_id) / "decks" / f"{deck_type}_blueprint.json"
