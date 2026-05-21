"""
Smoke test — runs before any deployment.
Verifies: imports, engine logic, Excel generation.
No external network calls. No pytest needed.
"""

import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def test(name: str, fn):
    try:
        fn()
        print(f"  ✓  {name}")
        return True
    except Exception as exc:
        print(f"  ✗  {name}")
        traceback.print_exc()
        return False


def main():
    results = []
    print("\n── MG Advisory Finance OS — Smoke Test ──\n")

    # ---- Config ----
    results.append(test("Config loads", lambda: __import__("app.config", fromlist=["APP_NAME"])))

    # ---- Engines ----
    def check_bp_engine():
        from app.engines.bp_engine import forecast_periods, build_revenue_forecast, apply_scenario, available_scenarios
        periods = forecast_periods("FY2024", years=3)
        assert periods == ["FY2025", "FY2026", "FY2027"], f"unexpected: {periods}"
        rev = build_revenue_forecast({"FY2024": 1_000_000}, {"FY2025": 0.10}, periods)
        assert rev["FY2025"] == 1_100_000
        scenarios = available_scenarios()
        assert "Base" in scenarios
        result = apply_scenario({"FY2025": 1_100_000}, 0.30, "Downside")
        assert result["scenario"] == "Downside"

    def check_qoe_engine():
        from app.engines.qoe_engine import normalize_ebitda, build_qoe_pack, score_revenue_quality
        result = normalize_ebitda(1_000_000, [
            {"category": "non_recurring_cost", "amount": 150_000, "period": "FY2024", "source": "p.12"},
            {"category": "non_recurring_income", "amount": 50_000, "period": "FY2024", "source": "p.8"},
        ])
        assert result["adjusted_ebitda"] == 1_100_000, f"got {result['adjusted_ebitda']}"
        assert len(result["adjustments_detail"]) == 2
        # Revenue quality
        inc = [{"name": "Revenue", "values": {"FY2023": 10_000_000, "FY2024": 11_000_000}}]
        rq = score_revenue_quality(inc, ["FY2023", "FY2024"])
        assert rq["quality_flag"] in ("strong", "acceptable", "caution")
        # Full pack
        project = {"company_name": "TestCo", "currency": "EUR"}
        financials = {
            "periods": ["FY2023", "FY2024"],
            "income_statement": [
                {"name": "Revenue", "values": {"FY2023": 10_000_000, "FY2024": 11_000_000}},
                {"name": "EBITDA", "values": {"FY2023": 2_000_000, "FY2024": 2_200_000}},
            ],
            "balance_sheet": [],
        }
        pack = build_qoe_pack(project, financials)
        assert "normalised_ebitda" in pack

    def check_restructuring_engine():
        from app.engines.restructuring_engine import (
            estimate_liquidity_runway,
            compute_debt_capacity,
            compute_liquidity_headroom,
            build_restructuring_paper,
            score_options,
        )
        assert estimate_liquidity_runway(600_000, 100_000) == 6.0
        assert estimate_liquidity_runway(600_000, 0) is None
        cap = compute_debt_capacity(2_000_000, existing_debt=5_000_000)
        assert "max_gross_debt" in cap
        headroom = compute_liquidity_headroom(1_000_000, 500_000, 100_000, 0, 200_000, 100_000)
        assert "net_headroom" in headroom
        options = score_options(liquidity_months=4, leverage_turns=6.5, creditor_support="mixed")
        assert len(options) > 0
        project = {"company_name": "TestCo", "currency": "EUR"}
        financials = {
            "periods": ["FY2024"],
            "income_statement": [{"name": "EBITDA", "values": {"FY2024": 2_000_000}}],
            "balance_sheet": [{"name": "Debt", "values": {"FY2024": 8_000_000}}],
        }
        paper = build_restructuring_paper(project, financials, opening_cash=500_000, monthly_burn=80_000)
        assert "options_ranked" in paper

    def check_debt_engine():
        from app.engines.debt_engine import debt_library_payload, DEBT_INSTRUMENT_LIBRARY
        assert len(DEBT_INSTRUMENT_LIBRARY) > 50
        payload = debt_library_payload()
        assert "library" in payload

    results.append(test("BP engine", check_bp_engine))
    results.append(test("QoE engine", check_qoe_engine))
    results.append(test("Restructuring engine", check_restructuring_engine))
    results.append(test("Debt engine", check_debt_engine))

    # ---- Services (no network) ----
    def check_project_service():
        from app.services.project_service import list_projects, project_dir
        assert isinstance(list_projects(), list)

    results.append(test("Project service", check_project_service))

    # ---- Excel builder ----
    def check_excel():
        import tempfile
        from pathlib import Path as P
        from app.builders.excel_builder import build_business_plan_workbook
        project = {
            "id": "smoketest001",
            "company_name": "SmokeTest Ltd",
            "project_type": "Investment case",
            "currency": "EUR",
            "fiscal_year_end": "December",
        }
        financials = {
            "periods": ["FY2023", "FY2024"],
            "income_statement": [
                {"name": "Revenue", "values": {"FY2023": 5_000_000, "FY2024": 5_500_000}},
                {"name": "EBITDA", "values": {"FY2023": 1_200_000, "FY2024": 1_400_000}},
            ],
            "balance_sheet": [
                {"name": "Cash", "values": {"FY2023": 300_000, "FY2024": 350_000}},
                {"name": "Debt", "values": {"FY2023": 3_500_000, "FY2024": 3_200_000}},
            ],
            "cash_flow": [],
            "source_files": ["smoke_test_input.csv"],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            out = P(tmpdir) / "smoke_bp.xlsx"
            build_business_plan_workbook(project, financials, out)
            assert out.exists() and out.stat().st_size > 10_000, "Excel file too small or missing"
            # Quick openpyxl sanity check
            from openpyxl import load_workbook
            wb = load_workbook(out, read_only=True)
            assert "Cover" in wb.sheetnames
            assert "Debt Config" in wb.sheetnames
            assert "Covenants" in wb.sheetnames
            print(f"     → {len(wb.sheetnames)} sheets generated, file size {out.stat().st_size:,} bytes")

    results.append(test("Excel BP workbook generation", check_excel))

    # ---- Summary ----
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n── {passed}/{total} tests passed ──\n")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
