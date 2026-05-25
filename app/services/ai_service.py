import json
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import ANTHROPIC_MODEL


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = ANTHROPIC_MODEL


def claude_status() -> dict:
    return {
        "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "model": DEFAULT_MODEL,
        "provider": "Anthropic Claude",
    }


def generate_project_brief(project: dict, financials: dict) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {
            "configured": False,
            "brief": _fallback_brief(project, financials),
            "source": "local_fallback",
        }

    prompt = _project_prompt(project, financials)
    try:
        text = _call_claude(prompt)
        return {"configured": True, "brief": text, "source": "claude"}
    except Exception as exc:
        return {
            "configured": True,
            "brief": _fallback_brief(project, financials),
            "source": "local_fallback_after_error",
            "error": str(exc),
        }


def chat_with_claude(project: dict, financials: dict, message: str, history: list[dict] | None = None) -> dict:
    history = history or []
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {
            "configured": False,
            "source": "local_fallback",
            "reply": _fallback_chat_reply(project, message),
        }
    prompt = _chat_prompt(project, financials, message, history)
    try:
        reply = _call_claude(prompt, max_tokens=2200)
        if not reply.strip():
            raise RuntimeError("Claude API returned an empty answer")
        return {"configured": True, "source": "claude", "reply": reply}
    except Exception as exc:
        return {
            "configured": True,
            "source": "local_fallback_after_error",
            "error": str(exc),
            "reply": _fallback_chat_reply(project, message),
        }


def stream_chat_with_claude(project: dict, financials: dict, message: str, history: list[dict] | None = None):
    history = history or []
    if not os.getenv("ANTHROPIC_API_KEY"):
        yield from _chunk_text(_fallback_chat_reply(project, message))
        return
    prompt = _chat_prompt(project, financials, message, history)
    try:
        yielded = False
        for chunk in _stream_claude(prompt, max_tokens=2200):
            yielded = True
            yield chunk
        if not yielded:
            yield from _chunk_text(_fallback_chat_reply(project, message))
    except Exception as exc:
        yield from _chunk_text(f"{_fallback_chat_reply(project, message)}\n\nTechnical note: {exc}")


def extract_financials_from_chat(project: dict, financials: dict, message: str, history: list[dict] | None = None) -> dict:
    history = history or []
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {
            "configured": False,
            "source": "local_fallback",
            "extraction": _fallback_chat_extraction(message),
        }
    prompt = _chat_extraction_prompt(project, financials, message, history)
    try:
        text = _call_claude(prompt, max_tokens=4200)
        extraction = _parse_json_object(text)
        return {"configured": True, "source": "claude_chat", "extraction": extraction}
    except Exception as exc:
        return {
            "configured": True,
            "source": "local_fallback_after_error",
            "error": str(exc),
            "extraction": _fallback_chat_extraction(message),
        }


def extract_financial_historicals(project: dict, document_context: dict) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {
            "configured": False,
            "source": "local_fallback",
            "extraction": _fallback_extraction(document_context),
        }

    prompt = _historical_extraction_prompt(project, document_context)
    try:
        text = _call_claude(prompt, max_tokens=3200)
        extraction = _parse_json_object(text)
        return {"configured": True, "source": "claude", "extraction": extraction}
    except Exception as exc:
        return {
            "configured": True,
            "source": "local_fallback_after_error",
            "error": str(exc),
            "extraction": _fallback_extraction(document_context),
        }


def plan_deck_from_templates(project: dict, financials: dict, pattern_library: dict, deck_type: str = "lender") -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {
            "configured": False,
            "source": "local_fallback",
            "blueprint": _fallback_deck_blueprint(project, deck_type),
        }

    prompt = _deck_planning_prompt(project, financials, pattern_library, deck_type)
    try:
        text = _call_claude(prompt, max_tokens=4200)
        blueprint = _parse_json_object(text)
        return {"configured": True, "source": "claude", "blueprint": blueprint}
    except Exception as exc:
        return {
            "configured": True,
            "source": "local_fallback_after_error",
            "error": str(exc),
            "blueprint": _fallback_deck_blueprint(project, deck_type),
        }


def _call_claude(prompt: str, max_tokens: int = 1400) -> str:
    payload = {
        "model": DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        ANTHROPIC_API_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": os.getenv("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Claude API HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Claude API network error: {exc.reason}") from exc

    content = data.get("content", [])
    text_parts = [part.get("text", "") for part in content if part.get("type") == "text"]
    return "\n".join(part for part in text_parts if part).strip()


def _stream_claude(prompt: str, max_tokens: int = 1400):
    payload = {
        "model": DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }
    request = Request(
        ANTHROPIC_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": os.getenv("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urlopen(request, timeout=35) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    yield delta["text"]


def _chunk_text(text: str, size: int = 22):
    for idx in range(0, len(text), size):
        yield text[idx : idx + size]


def _project_prompt(project: dict, financials: dict) -> str:
    return (
        "You are an institutional finance advisor. Produce a concise Alvarez & Marsal / FTI style "
        "investment and restructuring briefing. Use professional finance language. Include: "
        "1) business snapshot, 2) historical financial observations, 3) debt/covenant considerations, "
        "4) key diligence questions, 5) recommended next analyses. Do not invent facts beyond the data.\n\n"
        f"Project:\n{json.dumps(project, indent=2)}\n\n"
        f"Normalized financials:\n{json.dumps(financials, indent=2)}"
    )


def _chat_prompt(project: dict, financials: dict, message: str, history: list[dict]) -> str:
    return (
        "You are Claude inside MG Advisory Finance OS, acting as a senior investment banking / restructuring "
        "financial modeller. Help the user convert uploaded documents, notes and questions into a rigorous BP model. "
        "Be concise, technical and action-oriented. If the user asks for extraction, explain what you can map into "
        "P&L, balance sheet, cash flow, debt and BP assumptions. Do not invent numbers.\n\n"
        "BP engine context:\n"
        "- the target output is a Project Bolt-style institutional workbook with Control Panel, Historical Detail Input, "
        "Historical Bridge, Revenue Drivers, Product Build, Headcount, Opex, Working Capital, Capex D&A, Debt Config, "
        "Debt Schedule, Financial Statements, Covenants, Sensitivities, Outputs, Checks and manual placeholder rows;\n"
        "- formulas should be driven by assumptions, not hardcoded values;\n"
        "- historical actuals should bridge into forecast drivers, debt opening balances, opening cash, working capital and checks;\n"
        "- when documents are incomplete, create a precise missing-data request instead of guessing.\n\n"
        "Conversation style requirements:\n"
        "- behave like an embedded finance copilot, not a generic chatbot;\n"
        "- structure answers as: Diagnosis, BP mapping, Next action when relevant;\n"
        "- explicitly say when the user should click Apply to BP to push extracted data into assumptions;\n"
        "- flag missing data needed for a Project Bolt / investment banking quality BP;\n"
        "- keep replies compact, premium and operational.\n\n"
        f"Project:\n{json.dumps(project, indent=2)}\n\n"
        f"Current normalized financials:\n{json.dumps(financials, indent=2)[:22000]}\n\n"
        f"Recent chat history:\n{json.dumps(history[-10:], indent=2)[:12000]}\n\n"
        f"User message:\n{message}"
    )


def _chat_extraction_prompt(project: dict, financials: dict, message: str, history: list[dict]) -> str:
    return (
        "You are an institutional financial modelling extraction engine. Convert the chat conversation into "
        "normalized financial data that can feed an Excel BP. Return ONLY valid JSON, no markdown. "
        "Extract only values explicitly provided or strongly evidenced in the conversation/current financials. "
        "Do not invent missing values; use null or omit unknown lines.\n\n"
        "Target workbook standard: Project Bolt / investment banking BP. Extract enough granularity to populate "
        "Historical Detail Input and then drive Revenue Drivers, Product Build, Headcount, Opex, Working Capital, "
        "Capex D&A, Debt Config, Debt Schedule and Financial Statements. Prefer detailed line items over summary-only "
        "mapping when the source supports it.\n\n"
        "Required JSON schema:\n"
        "{\n"
        '  "periods": ["FY2023", "FY2024", "FY2025"],\n'
        '  "currency": "EUR",\n'
        '  "unit": "actual|thousands|millions|unknown",\n'
        '  "income_statement": [{"name": "Revenue", "values": {"FY2025": 0}}],\n'
        '  "balance_sheet": [{"name": "Cash", "values": {"FY2025": 0}}],\n'
        '  "cash_flow": [{"name": "Free Cash Flow", "values": {"FY2025": 0}}],\n'
        '  "historical_detail": [\n'
        '    {"statement": "Income Statement", "category": "Revenue", "subcategory": "Revenue streams", "model_line": "Revenue", "detail_line": "Product revenue", "values": {"FY2025": 0}, "source_file": "Claude chat", "confidence": "medium"}\n'
        "  ],\n"
        '  "debt": [{"lender": null, "facility": null, "amount": null, "maturity": null, "margin": null}],\n'
        '  "working_capital": [{"name": "Receivables", "values": {"FY2025": 0}}],\n'
        '  "bp_assumptions": {"revenue_streams": [], "cost_items": [], "debt_tranches": []},\n'
        '  "confidence": "high|medium|low",\n'
        '  "issues": ["short issue list"],\n'
        '  "source_files": ["Claude chat"]\n'
        "}\n\n"
        "Map lines to one of these BP model_line values where possible: Revenue, COGS, Payroll, Opex, EBITDA, D&A, "
        "Cash Interest, Tax, Cash, Receivables, Inventory, Payables, Closing Debt, Capex, Change in NWC, Free Cash Flow, Equity.\n\n"
        "For bp_assumptions, build usable objects when source evidence allows it: revenue_streams with name/type/start_volume/"
        "start_price/monthly growth; cost_items with name/driver/fixed/% revenue/cost per FTE; debt_tranches with name, type, "
        "opening balance, commitment, maturity/term, amortization, cash vs PIK interest and payment frequency.\n\n"
        f"Project:\n{json.dumps(project, indent=2)}\n\n"
        f"Current normalized financials:\n{json.dumps(financials, indent=2)[:20000]}\n\n"
        f"Recent chat history:\n{json.dumps(history[-12:], indent=2)[:16000]}\n\n"
        f"Latest user instruction:\n{message}"
    )


def _historical_extraction_prompt(project: dict, document_context: dict) -> str:
    return (
        "You are an institutional financial due diligence analyst extracting historical financials "
        "from uploaded source documents for a business plan model. Return ONLY valid JSON, with no "
        "markdown and no commentary. Do not invent values. If a value is not available, use null. "
        "Use positive numbers for revenue/assets and negative numbers for costs/liabilities only when "
        "the source clearly presents them as negative. Standardize line names.\n\n"
        "Target output standard: Project Bolt / investment banking BP. The extraction must be useful for a formula-driven "
        "model, not just a summary. Prioritize a detailed historical_detail mapping that can populate 150+ lines across "
        "income statement, balance sheet, cash flow, working capital, capex and debt when the uploaded files contain that "
        "granularity. Preserve source line names in detail_line so reviewers can trace the mapping.\n\n"
        "Required JSON schema:\n"
        "{\n"
        '  "periods": ["FY2023", "FY2024"],\n'
        '  "currency": "EUR",\n'
        '  "unit": "actual|thousands|millions|unknown",\n'
        '  "income_statement": [{"name": "Revenue", "values": {"FY2023": 0}}],\n'
        '  "balance_sheet": [{"name": "Cash", "values": {"FY2023": 0}}],\n'
        '  "cash_flow": [{"name": "Operating Cash Flow", "values": {"FY2023": 0}}],\n'
        '  "historical_detail": [\n'
        '    {"statement": "Income Statement", "category": "Revenue", "subcategory": "Revenue streams", "model_line": "Revenue", "detail_line": "Product revenue", "values": {"FY2023": 0}, "source_file": "file.xlsx", "confidence": "medium"}\n'
        "  ],\n"
        '  "debt": [{"lender": null, "facility": null, "amount": null, "maturity": null, "margin": null}],\n'
        '  "working_capital": [{"name": "Receivables", "values": {"FY2023": 0}}],\n'
        '  "confidence": "high|medium|low",\n'
        '  "issues": ["short issue list"],\n'
        '  "source_files": ["file.xlsx"]\n'
        "}\n\n"
        "Project:\n"
        f"{json.dumps(project, indent=2)}\n\n"
        "Also extract the maximum useful granularity for a business plan model: revenue by product/service/geography/customer if available, "
        "cost lines, payroll, opex, assets, liabilities, working capital, debt layers and cash-flow movements. "
        "The historical_detail array should map each source line to one of the model_line values used by the BP: Revenue, COGS, Payroll, Opex, EBITDA, D&A, Cash Interest, Tax, Cash, Receivables, Inventory, Payables, Closing Debt, Capex, Change in NWC, Free Cash Flow, Equity.\n\n"
        "If the source includes trial balance or management accounts tabs, preserve as many rows as possible and classify each row. "
        "If a row cannot be mapped confidently, still include it with confidence='low' and a clear category rather than dropping it.\n\n"
        "Document context:\n"
        f"{json.dumps(document_context, indent=2)[:65000]}"
    )


def _deck_planning_prompt(project: dict, financials: dict, pattern_library: dict, deck_type: str) -> str:
    return (
        "You are a senior investment banking / restructuring presentation director. "
        "Your job is to design a client-ready PowerPoint deck plan by choosing the best slide pattern "
        "from the available reference template library for each slide. Return ONLY valid JSON. "
        "Do not copy confidential wording from the reference decks. Use the references only for layout pattern, "
        "slide rhythm, proof-object style and analytical density.\n\n"
        "Required JSON schema:\n"
        "{\n"
        '  "deck_type": "lender|im|restructuring|qoe",\n'
        '  "narrative_thesis": "one sentence",\n'
        '  "slides": [\n'
        "    {\n"
        '      "slide_number": 1,\n'
        '      "slide_title": "claim-led title",\n'
        '      "slide_objective": "why this slide exists",\n'
        '      "recommended_template_file": "book_schemas_janvier_2023_reference.pptx",\n'
        '      "recommended_template_slide": 29,\n'
        '      "pattern_type": "chart_or_financial_analysis",\n'
        '      "proof_object": "chart|table|bridge|timeline|matrix|process|text",\n'
        '      "content_requirements": ["specific things to show"],\n'
        '      "data_needed": ["financial lines / documents needed"],\n'
        '      "speaker_takeaway": "what the banker should say"\n'
        "    }\n"
        "  ],\n"
        '  "quality_gates": ["no invented data", "source linked"]\n'
        "}\n\n"
        f"Deck type: {deck_type}\n\n"
        f"Project:\n{json.dumps(project, indent=2)}\n\n"
        f"Financials:\n{json.dumps(financials, indent=2)[:18000]}\n\n"
        f"Available pattern library:\n{json.dumps(pattern_library, indent=2)[:45000]}"
    )


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("JSON\n", "", 1)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Claude response did not contain a JSON object")
    return json.loads(cleaned[start : end + 1])


def _fallback_deck_blueprint(project: dict, deck_type: str) -> dict:
    company = project.get("company_name", "Target Company")
    slides = [
        ("Cover", "title_or_cover", "Introduce the company and deck purpose", "book_schemas_janvier_2023_reference.pptx", 1, "text"),
        ("Executive snapshot", "investment_highlights", "Frame the investment / credit thesis", "jbf_ge_im_draft_reference.pptx", 5, "matrix"),
        ("Historical financials", "chart_or_financial_analysis", "Show extracted P&L and balance sheet history", "book_schemas_janvier_2023_reference.pptx", 29, "table"),
        ("Business plan bridge", "timeline_or_process", "Explain how historicals become forecast outputs", "book_schemas_janvier_2023_reference.pptx", 23, "process"),
        ("Debt and covenants", "chart_or_financial_analysis", "Analyse serviceability and headroom", "book_schemas_janvier_2023_reference.pptx", 32, "table"),
        ("Restructuring options", "timeline_or_process", "Sequence options by liquidity relief and execution risk", "book_schemas_janvier_2023_reference.pptx", 21, "matrix"),
        ("Diligence priorities", "general_content", "Convert model output into next diligence actions", "jbf_ge_im_draft_reference.pptx", 30, "process"),
    ]
    return {
        "deck_type": deck_type,
        "narrative_thesis": f"{company} requires a source-linked institutional pack connecting historicals, forecast, debt capacity and restructuring options.",
        "slides": [
            {
                "slide_number": idx,
                "slide_title": title,
                "slide_objective": objective,
                "recommended_template_file": template,
                "recommended_template_slide": template_slide,
                "pattern_type": pattern,
                "proof_object": proof_object,
                "content_requirements": ["Use uploaded financials", "Keep calculations source-linked", "Avoid unsupported claims"],
                "data_needed": ["historical financials", "BP outputs", "debt schedule"],
                "speaker_takeaway": objective,
            }
            for idx, (title, pattern, objective, template, template_slide, proof_object) in enumerate(slides, start=1)
        ],
        "quality_gates": ["No invented metrics", "Reference data sources", "One proof object per slide", "Claim-led titles"],
    }


def _fallback_extraction(document_context: dict) -> dict:
    rows = document_context.get("structured_rows", [])
    periods = []
    for row in rows:
        for key in row.keys():
            text = str(key).strip()
            if text.upper().startswith("FY") or text.isdigit():
                periods.append(text if text.upper().startswith("FY") else f"FY{text}")
    periods = sorted(set(periods))[-5:] or ["FY2023", "FY2024", "FY2025"]
    return {
        "periods": periods,
        "currency": "unknown",
        "unit": "unknown",
        "income_statement": [],
        "balance_sheet": [],
        "cash_flow": [],
        "debt": [],
        "working_capital": [],
        "confidence": "low",
        "issues": [
            "Claude is not configured or failed; no AI extraction was performed.",
            "No synthetic financial values were inserted. Configure ANTHROPIC_API_KEY for real AI extraction.",
        ],
        "source_files": document_context.get("source_files", []),
    }


def _fallback_chat_reply(project: dict, message: str) -> str:
    company = project.get("company_name", "the active project")
    return (
        f"I can help structure this for {company}. The live Anthropic connection is not active on this deployment yet, "
        "so I am using a local finance fallback instead of a real Claude response.\n\n"
        "To make this fully conversational with Claude, add `ANTHROPIC_API_KEY` in Railway variables. "
        "For automatic BP population in fallback mode, write explicit lines with periods, for example:\n"
        "- Revenue FY2025 1200000\n"
        "- EBITDA FY2025 180000\n"
        "- Cash FY2025 90000\n"
        "- Debt FY2025 500000"
    )


def _fallback_chat_extraction(message: str) -> dict:
    periods = sorted(set(re.findall(r"FY20\d{2}|20\d{2}", message, flags=re.IGNORECASE)))
    periods = [period.upper() if period.upper().startswith("FY") else f"FY{period}" for period in periods] or ["FY2025"]
    lines = []
    aliases = {
        "revenue": "Revenue",
        "sales": "Revenue",
        "turnover": "Revenue",
        "ebitda": "EBITDA",
        "cash": "Cash",
        "debt": "Closing Debt",
        "cogs": "COGS",
        "opex": "Opex",
        "capex": "Capex",
    }
    for raw_line in message.splitlines():
        lower = raw_line.lower()
        model_line = next((target for key, target in aliases.items() if key in lower), None)
        if not model_line:
            continue
        values = {}
        for period in periods:
            year = period.replace("FY", "")
            match = re.search(rf"(?:FY)?{year}[^0-9\-()]*([-()]?[0-9][0-9,.\s]*\)?)", raw_line, flags=re.IGNORECASE)
            if match:
                number = _coerce_chat_number(match.group(1))
                if number is not None:
                    values[period] = number
        if values:
            lines.append({
                "statement": "Income Statement" if model_line in ["Revenue", "EBITDA", "COGS", "Opex"] else "Balance Sheet",
                "category": model_line,
                "subcategory": "Claude chat fallback",
                "model_line": model_line,
                "detail_line": model_line,
                "values": values,
                "source_file": "Claude chat",
                "confidence": "low",
            })
    return {
        "periods": periods,
        "currency": "unknown",
        "unit": "unknown",
        "income_statement": [
            {"name": item["model_line"], "values": item["values"]}
            for item in lines
            if item["statement"] == "Income Statement"
        ],
        "balance_sheet": [
            {"name": item["model_line"], "values": item["values"]}
            for item in lines
            if item["statement"] == "Balance Sheet"
        ],
        "cash_flow": [],
        "historical_detail": lines,
        "debt": [],
        "working_capital": [],
        "confidence": "low",
        "issues": ["Local fallback parsed only explicit line-level values from the chat. Configure Claude for institutional extraction."],
        "source_files": ["Claude chat"],
    }


def _coerce_chat_number(value: str) -> float | None:
    text = value.strip().replace(",", "").replace(" ", "").replace("(", "-").replace(")", "")
    try:
        return float(text)
    except ValueError:
        return None


def _fallback_brief(project: dict, financials: dict) -> str:
    company = project.get("company_name", "Target Company")
    periods = ", ".join(financials.get("periods", [])) or "no historical periods loaded"
    sources = ", ".join(financials.get("source_files", [])) or "no source files"
    return (
        f"{company} preliminary finance brief.\n\n"
        f"Historical periods available: {periods}.\n"
        f"Source files: {sources}.\n\n"
        "Claude is not configured, so this is a local fallback. Recommended next steps: upload audited "
        "accounts, management accounts, trial balance, debt schedule and budget; validate mapping; then "
        "generate the BP model and covenant pack."
    )
