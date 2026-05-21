from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.output_service import build_lender_deck
from app.services.project_service import list_projects


def main() -> None:
    projects = list_projects()
    if not projects:
        raise SystemExit("No project available for deck smoke test.")
    project = projects[0]
    output = build_lender_deck(project["id"])
    path = Path(output["path"])
    if not path.exists():
        raise SystemExit(f"Deck was not created: {path}")
    print(f"OK {path}")


if __name__ == "__main__":
    main()
