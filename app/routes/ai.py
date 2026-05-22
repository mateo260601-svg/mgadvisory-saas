from fastapi import APIRouter, HTTPException

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.ai_service import claude_status, chat_with_claude, extract_financials_from_chat, generate_project_brief, stream_chat_with_claude
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


@router.post("/projects/{project_id}/extract-historicals")
def ai_extract_historicals(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    normalized = normalize_project_financials(project_id, use_ai=True)
    return {
        "ok": True,
        "project_id": project_id,
        "normalized": normalized,
        "extraction": normalized.get("extraction", {}),
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
    assumptions = _apply_extraction_to_bp_assumptions(project_id, project, ai_result.get("extraction") or {})
    return {
        "ok": True,
        "project_id": project_id,
        "source": ai_result.get("source"),
        "configured": ai_result.get("configured"),
        "extraction": merged.get("extraction", {}),
        "normalized": merged,
        "assumptions": assumptions,
        "thread": load_thread(project_id, payload.thread_id),
    }


def _apply_extraction_to_bp_assumptions(project_id: str, project: dict, extraction: dict) -> dict:
    assumptions = load_bp_assumptions(project_id, project)
    historical_lines = []
    for line in extraction.get("historical_detail", []) or []:
        values = line.get("values") or {}
        periods = sorted(values)
        latest_period = periods[-1] if periods else None
        historical_lines.append(
            {
                "model_line": line.get("model_line") or line.get("category") or "",
                "detail_line": line.get("detail_line") or line.get("model_line") or "",
                "fy2022": values.get("FY2022", 0) or 0,
                "fy2023": values.get("FY2023", 0) or 0,
                "fy2024": values.get("FY2024", 0) or 0,
                "fy2025": values.get("FY2025", 0) or 0,
                "latest_actual": values.get(latest_period, 0) if latest_period else 0,
            }
        )
    if historical_lines:
        assumptions["historical_actuals"] = historical_lines[:24]

    bp_assumptions = extraction.get("bp_assumptions") or {}
    for key in ["revenue_streams", "cost_items", "debt_tranches"]:
        if bp_assumptions.get(key):
            assumptions[key] = bp_assumptions[key]
    assumptions.setdefault("model", {})["historical_source"] = "Claude chat"
    return save_bp_assumptions(project_id, assumptions)
