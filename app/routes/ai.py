from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.ai_service import claude_status, chat_with_claude, extract_financials_from_chat, generate_project_brief, generate_workspace_intelligence, stream_chat_with_claude
from app.services.bp_assumption_service import load_bp_assumptions, save_bp_assumptions
from app.services.chat_service import (
    DEFAULT_THREAD_ID,
    append_message,
    context_messages,
    last_user_message,
    list_threads,
    load_thread,
    update_message,
)
from app.services.financial_mapping_service import (
    load_normalized_financials,
    merge_ai_extraction_into_financials,
    normalize_project_financials,
    save_normalized_financials,
)
from app.services.project_service import get_project


router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)
    thread_id: str = DEFAULT_THREAD_ID


class EditMessageRequest(BaseModel):
    content: str
    thread_id: str = DEFAULT_THREAD_ID


@router.get("/status")
def ai_status():
    return claude_status()


@router.get("/projects/{project_id}/chat/thread")
def ai_chat_thread(project_id: str, thread_id: str = DEFAULT_THREAD_ID):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True, "project_id": project_id, "thread": load_thread(project_id, thread_id)}


@router.get("/projects/{project_id}/chat/threads")
def ai_chat_threads(project_id: str):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return list_threads(project_id)


@router.post("/projects/{project_id}/brief")
def ai_project_brief(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    financials = load_normalized_financials(project_id)
    return generate_project_brief(project, financials)


@router.get("/projects/{project_id}/intelligence")
def ai_project_intelligence(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    financials = load_normalized_financials(project_id)
    assumptions = load_bp_assumptions(project_id, project)
    return {
        "ok": True,
        "project_id": project_id,
        "intelligence": generate_workspace_intelligence(project, financials, assumptions),
    }


@router.post("/projects/{project_id}/extract-historicals")
def ai_extract_historicals(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    normalized = normalize_project_financials(project_id, use_ai=True)
    assumptions = _apply_extraction_to_bp_assumptions(
        project_id,
        project,
        _extraction_from_normalized(normalized),
        normalized,
        source="Claude extraction",
    )
    return {
        "ok": True,
        "project_id": project_id,
        "normalized": normalized,
        "extraction": normalized.get("extraction", {}),
        "assumptions": assumptions,
        "bridge": _bp_bridge_summary(assumptions, normalized),
    }


@router.get("/projects/{project_id}/financials")
def ai_project_financials(project_id: str):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return load_normalized_financials(project_id)


@router.post("/projects/{project_id}/chat")
def ai_chat(project_id: str, payload: ChatRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    financials = load_normalized_financials(project_id)
    append_message(project_id, "user", payload.message, payload.thread_id)
    history = context_messages(project_id, payload.thread_id)
    result = chat_with_claude(project, financials, payload.message, history)
    assistant = append_message(
        project_id,
        "assistant",
        result.get("reply", ""),
        payload.thread_id,
        source=result.get("source"),
        error=result.get("error"),
    )
    return {
        **result,
        "ok": True,
        "thread": load_thread(project_id, payload.thread_id),
        "message": assistant,
    }


@router.post("/projects/{project_id}/chat/stream")
def ai_chat_stream(project_id: str, payload: ChatRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    financials = load_normalized_financials(project_id)
    append_message(project_id, "user", payload.message, payload.thread_id)
    history = context_messages(project_id, payload.thread_id)

    def stream_reply():
        buffer = []
        for chunk in stream_chat_with_claude(project, financials, payload.message, history):
            buffer.append(chunk)
            yield chunk
        append_message(
            project_id,
            "assistant",
            "".join(buffer),
            payload.thread_id,
            source="claude_stream" if claude_status().get("configured") else "local_fallback_stream",
            error=None,
        )

    return StreamingResponse(stream_reply(), media_type="text/plain; charset=utf-8")


@router.post("/projects/{project_id}/chat/regenerate")
def ai_chat_regenerate(project_id: str, payload: ChatRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    last_message = last_user_message(project_id, payload.thread_id)
    if not last_message:
        raise HTTPException(status_code=422, detail="No user message to regenerate")
    financials = load_normalized_financials(project_id)
    history = context_messages(project_id, payload.thread_id)
    result = chat_with_claude(project, financials, last_message.get("content", ""), history)
    assistant = append_message(
        project_id,
        "assistant",
        result.get("reply", ""),
        payload.thread_id,
        source=result.get("source"),
        error=result.get("error"),
        regenerated=True,
    )
    return {"ok": True, **result, "message": assistant, "thread": load_thread(project_id, payload.thread_id)}


@router.put("/projects/{project_id}/chat/messages/{message_id}")
def ai_chat_edit_message(project_id: str, message_id: str, payload: EditMessageRequest):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        message = update_message(project_id, message_id, payload.content, payload.thread_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Message not found") from None
    return {"ok": True, "message": message, "thread": load_thread(project_id, payload.thread_id)}


@router.post("/projects/{project_id}/chat/apply")
def ai_chat_apply(project_id: str, payload: ChatRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    current = load_normalized_financials(project_id)
    if payload.message:
        append_message(project_id, "user", f"[Apply to BP] {payload.message}", payload.thread_id)
    history = context_messages(project_id, payload.thread_id)
    ai_result = extract_financials_from_chat(project, current, payload.message, history)
    merged = merge_ai_extraction_into_financials(current, ai_result)
    save_normalized_financials(project_id, merged)
    assumptions = _apply_extraction_to_bp_assumptions(
        project_id,
        project,
        ai_result.get("extraction") or _extraction_from_normalized(merged),
        merged,
        source="Claude chat",
    )
    return {
        "ok": True,
        "project_id": project_id,
        "source": ai_result.get("source"),
        "configured": ai_result.get("configured"),
        "extraction": merged.get("extraction", {}),
        "normalized": merged,
        "assumptions": assumptions,
        "bridge": _bp_bridge_summary(assumptions, merged),
        "thread": load_thread(project_id, payload.thread_id),
    }


@router.post("/projects/{project_id}/bp-sync")
def ai_sync_bp_from_current_financials(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    normalized = load_normalized_financials(project_id)
    assumptions = _apply_extraction_to_bp_assumptions(
        project_id,
        project,
        _extraction_from_normalized(normalized),
        normalized,
        source="Claude BP sync",
    )
    return {
        "ok": True,
        "project_id": project_id,
        "normalized": normalized,
        "assumptions": assumptions,
        "bridge": _bp_bridge_summary(assumptions, normalized),
    }


def _apply_extraction_to_bp_assumptions(
    project_id: str,
    project: dict,
    extraction: dict,
    normalized: dict | None = None,
    source: str = "Claude chat",
) -> dict:
    assumptions = load_bp_assumptions(project_id, project)
    historical_lines = []
    detail_lines = extraction.get("historical_detail", []) or (normalized or {}).get("historical_detail", []) or []
    for line in detail_lines:
        values = line.get("values") or {}
        periods = sorted(values)
        latest_period = periods[-1] if periods else None
        historical_lines.append(
            {
                "statement": line.get("statement") or "",
                "model_line": line.get("model_line") or line.get("category") or "",
                "detail_line": line.get("detail_line") or line.get("model_line") or "",
                "fy2022": _safe_number(values.get("FY2022")),
                "fy2023": _safe_number(values.get("FY2023")),
                "fy2024": _safe_number(values.get("FY2024")),
                "fy2025": _safe_number(values.get("FY2025")),
                "latest_actual": _safe_number(values.get(latest_period)) if latest_period else 0,
            }
        )
    if historical_lines:
        assumptions["historical_actuals"] = historical_lines[:180]

    bp_assumptions = extraction.get("bp_assumptions") or {}
    for key in ["revenue_streams", "cost_items", "debt_tranches"]:
        if bp_assumptions.get(key):
            assumptions[key] = bp_assumptions[key]

    derived = _derive_bp_assumptions_from_historicals(historical_lines)
    if derived.get("revenue_streams") and not bp_assumptions.get("revenue_streams"):
        assumptions["revenue_streams"] = derived["revenue_streams"]
    if derived.get("cost_items") and not bp_assumptions.get("cost_items"):
        assumptions["cost_items"] = derived["cost_items"]
    if derived.get("debt_tranches") and not bp_assumptions.get("debt_tranches"):
        assumptions["debt_tranches"] = derived["debt_tranches"]

    model = assumptions.setdefault("model", {})
    if derived.get("opening_cash") is not None:
        model["opening_cash"] = derived["opening_cash"]
    if derived.get("opening_debt") is not None:
        model["opening_debt"] = derived["opening_debt"]
    model["historical_source"] = source
    return save_bp_assumptions(project_id, assumptions)


def _extraction_from_normalized(normalized: dict | None) -> dict:
    normalized = normalized or {}
    return {
        "historical_detail": normalized.get("historical_detail", []),
        "bp_assumptions": normalized.get("bp_assumptions", {}),
    }


def _derive_bp_assumptions_from_historicals(lines: list[dict]) -> dict:
    revenue_streams = []
    cost_items = []
    debt_tranches = []
    opening_cash = None
    opening_debt = None

    for line in lines:
        model_line = str(line.get("model_line") or "").lower()
        detail_line = str(line.get("detail_line") or line.get("model_line") or "").strip()
        latest = _safe_number(line.get("latest_actual"))
        if not detail_line or latest == 0:
            continue

        latest = abs(latest)
        descriptor = f"{model_line} {detail_line}".lower()

        if opening_cash is None and _contains_any(descriptor, ["cash", "bank"]):
            opening_cash = latest

        if _contains_any(descriptor, ["debt", "loan", "borrow", "lease liab", "financial liability"]):
            opening_debt = max(opening_debt or 0, latest)
            if len(debt_tranches) < 12:
                debt_tranches.append(
                    {
                        "name": detail_line[:80],
                        "debt_type": _guess_debt_type(descriptor),
                        "borrower": "OpCo",
                        "start_date": "2026-01-31",
                        "opening_balance": latest,
                        "commitment": latest,
                        "term_months": 60,
                        "moratorium_months": 6,
                        "interest_cap_months": 0,
                        "margin": 0.045,
                        "base_rate": 0.035,
                        "amortization": "Linear",
                        "bullet_percent": 0.20,
                        "cash_sweep_percent": 0.25,
                        "interest_type": "Cash",
                        "cash_pay_frequency": "Monthly",
                        "cash_pay_percent": 1.0,
                        "pik": False,
                        "minimum_cash": 50000,
                    }
                )
            continue

        if _contains_any(descriptor, ["revenue", "sales", "turnover", "gross receipts"]):
            if len(revenue_streams) < 15:
                revenue_streams.append(
                    {
                        "name": detail_line[:80],
                        "type": _guess_revenue_type(descriptor),
                        "volume": 1,
                        "price": max(latest / 12, 1),
                        "volume_growth": 0.01,
                        "price_growth": 0.002,
                    }
                )
            continue

        if _contains_any(descriptor, ["cogs", "cost", "expense", "payroll", "salary", "rent", "marketing", "opex", "sga", "sg&a"]):
            if len(cost_items) < 35:
                cost_items.append(
                    {
                        "name": detail_line[:80],
                        "driver": "% Revenue" if _contains_any(descriptor, ["commission", "marketing", "freight"]) else "Fixed",
                        "monthly_fixed": latest / 12,
                        "percent_revenue": 0.0,
                        "cost_per_fte": 0.0,
                    }
                )

    return {
        "revenue_streams": revenue_streams,
        "cost_items": cost_items,
        "debt_tranches": debt_tranches,
        "opening_cash": opening_cash,
        "opening_debt": opening_debt,
    }


def _bp_bridge_summary(assumptions: dict, normalized: dict | None = None) -> dict:
    historicals = assumptions.get("historical_actuals") or []
    revenues = assumptions.get("revenue_streams") or []
    costs = assumptions.get("cost_items") or []
    debts = assumptions.get("debt_tranches") or []
    periods = (normalized or {}).get("periods") or []
    confidence = ((normalized or {}).get("extraction") or {}).get("confidence", "review")
    status = "Ready for BP generation" if historicals and revenues else "Needs review"
    return {
        "status": status,
        "confidence": confidence,
        "periods": periods,
        "historical_lines": len([line for line in historicals if line.get("detail_line")]),
        "revenue_streams": len([row for row in revenues if row.get("name")]),
        "cost_items": len([row for row in costs if row.get("name")]),
        "debt_tranches": len([row for row in debts if row.get("name")]),
    }


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _guess_revenue_type(text: str) -> str:
    if _contains_any(text, ["recurring", "subscription", "saas", "maintenance"]):
        return "Recurring"
    if _contains_any(text, ["service", "consulting", "fee"]):
        return "Service"
    if _contains_any(text, ["project", "contract"]):
        return "Project"
    return "Product"


def _guess_debt_type(text: str) -> str:
    if _contains_any(text, ["revolver", "rcf", "working capital"]):
        return "RCF"
    if _contains_any(text, ["bond", "note"]):
        return "Bond"
    if _contains_any(text, ["lease"]):
        return "Lease"
    return "Senior Term Loan"


def _safe_number(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if value in (None, ""):
        return 0.0
    text = str(value).strip().replace(",", "").replace(" ", "").replace("(", "-").replace(")", "")
    try:
        return float(text)
    except ValueError:
        return 0.0
