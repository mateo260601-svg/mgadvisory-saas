from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.bp_assumption_service import load_bp_assumptions, save_bp_assumptions
from app.services.output_service import build_bp_model
from app.services.project_service import create_project
from app.schemas.project_schema import ProjectCreate


def main() -> None:
    project = create_project(
        ProjectCreate(
            company_name="SMOKE BP BUILDER",
            project_type="Restructuring",
            currency="EUR",
            fiscal_year_end="December",
        )
    )
    assumptions = load_bp_assumptions(project["id"], project)
    assumptions["model"]["opening_cash"] = 250000
    assumptions["revenue_streams"][0]["name"] = "Smoke revenue stream"
    assumptions["debt_tranches"][0]["term_months"] = 72
    save_bp_assumptions(project["id"], assumptions)

    output = build_bp_model(project["id"])
    path = Path(output["path"])
    if not path.exists():
        raise SystemExit(f"Workbook was not created: {path}")
    print(f"OK {path}")


if __name__ == "__main__":
    main()
