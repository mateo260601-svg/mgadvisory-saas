import csv
import json
from pathlib import Path

from app.engines.historical_accounts_engine import build_basic_historical_pack
from app.services.ai_service import extract_financial_historicals
from app.services.extraction_service import list_project_documents
from app.services.project_service import get_project, project_dir


def normalize_project_financials(project_id: str, use_ai: bool = True) -> dict:
    documents = list_project_documents(project_id)
    extracted_rows = []
    document_summaries = []

    for document in documents:
        if document.suffix.lower() == ".csv":
            rows = _read_csv_rows(document)
            extracted_rows.extend(rows)
            document_summaries.append(_document_summary(document, rows))
        elif document.suffix.lower() in {".xlsx", ".xlsm"}:
            rows = _read_xlsx_rows(document)
            extracted_rows.extend(rows)
            document_summaries.append(_document_summary(document, rows))
        elif document.suffix.lower() == ".pdf":
            text = _read_pdf_text(document)
            document_summaries.append(_document_summary(document, [], text=text))

    normalized = build_basic_historical_pack(extracted_rows, [path.name for path in documents])
    normalized["extraction"] = {
        "mode": "local",
        "confidence": "low" if not extracted_rows else "medium",
        "documents": document_summaries,
    }

    if use_ai:
        ai_result = _run_ai_historical_extraction(project_id, documents, extracted_rows, document_summaries)
        if ai_result:
            normalized = _merge_ai_extraction(normalized, ai_result)

    output_path = project_dir(project_id) / "normalized" / "financials.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return normalized


def load_normalized_financials(project_id: str) -> dict:
    output_path = project_dir(project_id) / "normalized" / "financials.json"
    if not output_path.exists():
        return normalize_project_financials(project_id)
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return normalize_project_financials(project_id)


def _read_csv_rows(path: Path) -> list[dict]:
    rows = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append({str(key or "").strip(): value for key, value in row.items()})
    except Exception:
        return []
    return rows


def _read_xlsx_rows(path: Path) -> list[dict]:
    try:
        from openpyxl import load_workbook
    except Exception:
        return []

    rows = []
    try:
        workbook = load_workbook(path, data_only=True, read_only=True)
        sheet = workbook.worksheets[0]
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            return []
        headers = [str(cell or "").strip() for cell in values[0]]
        for values_row in values[1:]:
            row = {}
            for index, header in enumerate(headers):
                if header:
                    row[header] = values_row[index] if index < len(values_row) else None
            rows.append(row)
    except Exception:
        return []
    return rows


def _read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""

    try:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages[:25]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)[:45000]
    except Exception:
        return ""


def _document_summary(path: Path, rows: list[dict], text: str = "") -> dict:
    preview_rows = rows[:80]
    return {
        "filename": path.name,
        "extension": path.suffix.lower(),
        "row_count": len(rows),
        "columns": list(preview_rows[0].keys())[:40] if preview_rows else [],
        "preview_rows": preview_rows[:25],
        "text_preview": text[:12000],
    }


def _run_ai_historical_extraction(
    project_id: str,
    documents: list[Path],
    rows: list[dict],
    document_summaries: list[dict],
) -> dict | None:
    context = {
        "source_files": [path.name for path in documents],
        "structured_rows": rows[:250],
        "documents": document_summaries,
    }
    project = get_project(project_id) or {"id": project_id}
    result = extract_financial_historicals(project, context)

    trace_path = project_dir(project_id) / "normalized" / "claude_extraction.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _merge_ai_extraction(normalized: dict, ai_result: dict) -> dict:
    extraction = ai_result.get("extraction") or {}
    merged = dict(normalized)

    for key in ["periods", "income_statement", "balance_sheet", "cash_flow", "source_files"]:
        value = extraction.get(key)
        if value:
            merged[key] = value

    if extraction.get("working_capital"):
        merged["working_capital"] = extraction["working_capital"]
    if extraction.get("debt"):
        merged["debt"] = extraction["debt"]

    merged["currency"] = extraction.get("currency") or merged.get("currency", "unknown")
    merged["unit"] = extraction.get("unit") or merged.get("unit", "unknown")
    merged["extraction"] = {
        "mode": ai_result.get("source", "unknown"),
        "claude_configured": ai_result.get("configured", False),
        "confidence": extraction.get("confidence", "low"),
        "issues": extraction.get("issues", []),
        "error": ai_result.get("error"),
        "documents": normalized.get("extraction", {}).get("documents", []),
    }
    return merged
