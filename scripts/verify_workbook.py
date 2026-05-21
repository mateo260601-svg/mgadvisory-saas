from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import load_workbook

from app.config import OUTPUTS_DIR


def main() -> None:
    workbooks = sorted(Path(OUTPUTS_DIR).glob("*_BP_Model.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not workbooks:
        raise SystemExit("No BP workbook found in outputs.")

    path = workbooks[0]
    wb = load_workbook(path, data_only=False)
    required = [
        "Control Panel",
        "Historical Inputs",
        "Revenue Drivers",
        "Debt Config",
        "Debt Schedule",
        "Financial Statements",
        "Covenants",
        "Outputs",
        "Checks",
    ]
    missing = [name for name in required if name not in wb.sheetnames]
    if missing:
        raise SystemExit(f"Missing sheets: {missing}")

    formulas = 0
    inputs = 0
    validations = 0
    for ws in wb.worksheets:
        validations += len(ws.data_validations.dataValidation)
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    formulas += 1
                if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb == "00D9EAF7":
                    inputs += 1

    if formulas < 10000:
        raise SystemExit(f"Formula count too low: {formulas}")
    if validations < 10:
        raise SystemExit(f"Validation count too low: {validations}")
    if wb["Control Panel"]["C11"].value != 250000:
        raise SystemExit("Saved BP Builder opening cash was not written to Control Panel.")
    if wb["Revenue Drivers"]["B7"].value != "Smoke revenue stream":
        raise SystemExit("Saved BP Builder revenue stream was not written to Revenue Drivers.")
    if wb["Debt Config"]["H5"].value != 72:
        raise SystemExit("Saved BP Builder debt term was not written to Debt Config.")
    print(f"OK {path.name} sheets={len(wb.sheetnames)} formulas={formulas} input_cells={inputs} validations={validations}")


if __name__ == "__main__":
    main()
