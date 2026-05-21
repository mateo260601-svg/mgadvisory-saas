import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")


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
        with urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Claude API HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Claude API network error: {exc.reason}") from exc

    content = data.get("content", [])
    text_parts = [part.get("text", "") for part in content if part.get("type") == "text"]
    return "\n".join(part for part in text_parts if part).strip()


def _project_prompt(project: dict, financials: dict) -> str:
    return (
        "You are an institutional finance advisor. Produce a concise Alvarez & Marsal / FTI style "
        "investment and restructuring briefing. Use professional finance language. Include: "
        "1) business snapshot, 2) historical financial observations, 3) debt/covenant considerations, "
        "4) key diligence questions, 5) recommended next analyses. Do not invent facts beyond the data.\n\n"
        f"Project:\n{json.dumps(project, indent=2)}\n\n"
        f"Normalized financials:\n{json.dumps(financials, indent=2)}"
    )


def _historical_extraction_prompt(project: dict, document_context: dict) -> str:
    return (
        "You are an institutional financial due diligence analyst extracting historical financials "
        "from uploaded source documents for a business plan model. Return ONLY valid JSON, with no "
        "markdown and no commentary. Do not invent values. If a value is not available, use null. "
        "Use positive numbers for revenue/assets and negative numbers for costs/liabilities only when "
        "the source clearly presents them as negative. Standardize line names.\n\n"
        "Required JSON schema:\n"
        "{\n"
        '  "periods": ["FY2023", "FY2024"],\n'
        '  "currency": "EUR",\n'
        '  "unit": "actual|thousands|millions|unknown",\n'
        '  "income_statement": [{"name": "Revenue", "values": {"FY2023": 0}}],\n'
        '  "balance_sheet": [{"name": "Cash", "values": {"FY2023": 0}}],\n'
        '  "cash_flow": [{"name": "Operating Cash Flow", "values": {"FY2023": 0}}],\n'
        '  "debt": [{"lender": null, "facility": null, "amount": null, "maturity": null, "margin": null}],\n'
        '  "working_capital": [{"name": "Receivables", "values": {"FY2023": 0}}],\n'
        '  "confidence": "high|medium|low",\n'
        '  "issues": ["short issue list"],\n'
        '  "source_files": ["file.xlsx"]\n'
        "}\n\n"
        "Project:\n"
        f"{json.dumps(project, indent=2)}\n\n"
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
        "issues": ["Claude is not configured; local extraction only was used."],
        "source_files": document_context.get("source_files", []),
    }


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
