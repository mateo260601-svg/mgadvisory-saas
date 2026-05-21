from app.builders.excel_builder import build_business_plan_workbook
from app.builders.pptx_builder import build_lender_presentation
from app.config import OUTPUTS_DIR
from app.services.deck_planning_service import load_deck_blueprint
from app.services.financial_mapping_service import load_normalized_financials
from app.services.project_service import get_project


def build_bp_model(project_id: str) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Project not found")

    financials = load_normalized_financials(project_id)
    filename = f"{project['company_name'].replace(' ', '_')}_{project_id}_BP_Model.xlsx"
    output_path = OUTPUTS_DIR / filename
    build_business_plan_workbook(project, financials, output_path)
    return {"filename": filename, "path": str(output_path)}


def build_lender_deck(project_id: str) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Project not found")

    financials = load_normalized_financials(project_id)
    blueprint = load_deck_blueprint(project_id, deck_type="lender")
    filename = f"{project['company_name'].replace(' ', '_')}_{project_id}_Lender_Presentation.pptx"
    output_path = OUTPUTS_DIR / filename
    build_lender_presentation(project, financials, output_path, blueprint=blueprint)
    return {"filename": filename, "path": str(output_path)}
