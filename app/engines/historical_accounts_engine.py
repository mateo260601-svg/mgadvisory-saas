from collections import defaultdict
from datetime import date, datetime
from typing import Any


LINE_ALIASES = {
    "revenue": ["revenue", "sales", "turnover", "chiffre"],
    "cogs": ["cogs", "cost of sales", "costs of goods", "direct costs"],
    "opex": ["opex", "operating expenses", "sg&a", "admin"],
    "ebitda": ["ebitda"],
    "cash": ["cash", "bank"],
    "receivables": ["receivable", "debtors", "ar"],
    "inventory": ["inventory", "stock"],
    "payables": ["payable", "creditors", "ap"],
    "debt": ["debt", "loan", "borrowings"],
}


def build_basic_historical_pack(rows: list[dict], source_files: list[str]) -> dict:
    periods = _detect_periods(rows)
    if not periods:
        periods = []

    values = defaultdict(lambda: defaultdict(float))
    for row in rows:
        label = _row_label(row)
        canonical = _canonical_line(label)
        if not canonical:
            continue
        for period in periods:
            value = _coerce_number(row.get(period))
            values[canonical][period] += value

    return {
        "periods": periods,
        "income_statement": [
            _line("Revenue", values["revenue"], periods),
            _line("COGS", values["cogs"], periods),
            _line("Opex", values["opex"], periods),
            _line("EBITDA", values["ebitda"], periods),
        ],
        "balance_sheet": [
            _line("Cash", values["cash"], periods),
            _line("Receivables", values["receivables"], periods),
            _line("Inventory", values["inventory"], periods),
            _line("Payables", values["payables"], periods),
            _line("Debt", values["debt"], periods),
        ],
        "cash_flow": [],
        "source_files": source_files,
    }


def _detect_periods(rows: list[dict]) -> list[str]:
    candidates = []
    for row in rows:
        for key in row.keys():
            period = _period_label(key)
            if period:
                candidates.append(period)
    return sorted(set(candidates))[-8:]


def _row_label(row: dict) -> str:
    for key in ["Line Item", "Account", "Description", "Name", "Metric", "line_item", "account"]:
        if key in row and row[key]:
            return str(row[key])
    for value in row.values():
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _canonical_line(label: str) -> str | None:
    lower = label.lower()
    for canonical, aliases in LINE_ALIASES.items():
        if any(alias in lower for alias in aliases):
            return canonical
    return None


def _coerce_number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace(" ", "").replace("(", "-").replace(")", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _line(name: str, values: dict, periods: list[str]) -> dict:
    if any(values.get(period) for period in periods):
        return {"name": name, "values": {period: values.get(period, 0.0) for period in periods}}
    return {"name": name, "values": {period: 0.0 for period in periods}}


def _period_label(value: Any) -> str | None:
    if isinstance(value, (date, datetime)):
        return f"FY{value.year}"
    text = str(value or "").strip()
    if not text:
        return None
    upper = text.upper().replace(" ", "")
    if upper.startswith("FY") and any(char.isdigit() for char in upper):
        digits = "".join(char for char in upper if char.isdigit())
        if len(digits) == 2:
            return f"FY20{digits}"
        if len(digits) >= 4:
            return f"FY{digits[:4]}"
    if text.isdigit() and len(text) == 4 and 1990 <= int(text) <= 2100:
        return f"FY{text}"
    for token in ["2021", "2022", "2023", "2024", "2025", "2026", "2027", "2028", "2029", "2030"]:
        if token in text:
            return f"FY{token}"
    return None
