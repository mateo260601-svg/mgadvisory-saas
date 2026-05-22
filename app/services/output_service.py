from app.builders.excel_builder import build_business_plan_workbook
from app.builders.pptx_builder import build_lender_presentation
from app.config import OUTPUTS_DIR
from app.services.deck_planning_service import load_deck_blueprint
from app.services.financial_mapping_service import load_normalized_financials
from app.services.bp_assumption_service import load_bp_assumptions
from app.services.project_service import get_project


def build_bp_model(project_id: str) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Project not found")

    financials = load_normalized_financials(project_id)
    filename = f"{project['company_name'].replace(' ', '_')}_{project_id}_BP_Model.xlsx"
    output_path = OUTPUTS_DIR / filename
    assumptions = load_bp_assumptions(project_id, project)
    build_business_plan_workbook(project, financials, output_path, assumptions=assumptions)
    return {"filename": filename, "path": str(output_path)}


def build_lender_deck(project_id: str) -> dict:
    return build_presentation_deck(project_id, deck_type="lender", label="Lender_Presentation")


def build_im_deck(project_id: str) -> dict:
    return build_presentation_deck(project_id, deck_type="im", label="IM_MA_Deck")


def build_presentation_deck(project_id: str, deck_type: str, label: str) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Project not found")

    financials = load_normalized_financials(project_id)
    assumptions = load_bp_assumptions(project_id, project)
    blueprint = load_deck_blueprint(project_id, deck_type=deck_type)
    filename = f"{project['company_name'].replace(' ', '_')}_{project_id}_{label}.pptx"
    output_path = OUTPUTS_DIR / filename
    build_lender_presentation(project, financials, output_path, blueprint=blueprint, assumptions=assumptions)
    return {"filename": filename, "path": str(output_path)}
