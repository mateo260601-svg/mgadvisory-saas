import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.services.project_service import project_dir


DEFAULT_THREAD_ID = "main"
MAX_STORED_MESSAGES = 120
MAX_CONTEXT_MESSAGES = 24


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def chat_store_path(project_id: str) -> Path:
    folder = project_dir(project_id) / "chat"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "conversations.json"


def load_thread(project_id: str, thread_id: str = DEFAULT_THREAD_ID) -> dict:
    store = _load_store(project_id)
    thread = _ensure_thread(store, thread_id)
    _save_store(project_id, store)
    return thread


def list_threads(project_id: str) -> dict:
    store = _load_store(project_id)
    if not store.get("threads"):
        _ensure_thread(store, DEFAULT_THREAD_ID)
        _save_store(project_id, store)
    return {
        "project_id": project_id,
        "threads": [
            {
                "id": thread["id"],
                "title": thread.get("title", "Claude workspace"),
                "created_at": thread.get("created_at"),
                "updated_at": thread.get("updated_at"),
                "message_count": len(thread.get("messages", [])),
            }
            for thread in store.get("threads", [])
        ],
    }


def append_message(project_id: str, role: str, content: str, thread_id: str = DEFAULT_THREAD_ID, **metadata) -> dict:
    store = _load_store(project_id)
    thread = _ensure_thread(store, thread_id)
    message = {
        "id": uuid.uuid4().hex,
        "role": role,
        "content": content or "",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": metadata.pop("status", "complete"),
        "source": metadata.pop("source", None),
        "error": metadata.pop("error", None),
        "metadata": metadata,
    }
    thread.setdefault("messages", []).append(message)
    thread["messages"] = thread["messages"][-MAX_STORED_MESSAGES:]
    thread["updated_at"] = utc_now()
    if role == "user" and (not thread.get("title") or thread.get("title") == "Claude workspace"):
        thread["title"] = _title_from_message(content)
    _save_store(project_id, store)
    return message


def update_message(project_id: str, message_id: str, content: str, thread_id: str = DEFAULT_THREAD_ID) -> dict:
    store = _load_store(project_id)
    thread = _ensure_thread(store, thread_id)
    for message in thread.get("messages", []):
        if message.get("id") == message_id:
            message["content"] = content
            message["updated_at"] = utc_now()
            thread["updated_at"] = utc_now()
            _save_store(project_id, store)
            return message
    raise KeyError("Message not found")


def context_messages(project_id: str, thread_id: str = DEFAULT_THREAD_ID) -> list[dict]:
    thread = load_thread(project_id, thread_id)
    return [
        {"role": item.get("role"), "content": item.get("content", "")}
        for item in thread.get("messages", [])[-MAX_CONTEXT_MESSAGES:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]


def last_user_message(project_id: str, thread_id: str = DEFAULT_THREAD_ID) -> dict | None:
    thread = load_thread(project_id, thread_id)
    for message in reversed(thread.get("messages", [])):
        if message.get("role") == "user":
            return message
    return None


def _load_store(project_id: str) -> dict:
    path = chat_store_path(project_id)
    if not path.exists():
        return {"version": 1, "threads": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "threads": []}


def _save_store(project_id: str, store: dict) -> None:
    path = chat_store_path(project_id)
    path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def _ensure_thread(store: dict, thread_id: str) -> dict:
    for thread in store.setdefault("threads", []):
        if thread.get("id") == thread_id:
            return thread
    thread = {
        "id": thread_id,
        "title": "Claude workspace",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "messages": [
            {
                "id": uuid.uuid4().hex,
                "role": "assistant",
                "content": "I am ready to help analyse uploads, map historicals, build BP assumptions and prepare Excel/PPT outputs for this project.",
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "status": "complete",
                "source": "system",
                "error": None,
                "metadata": {},
            }
        ],
    }
    store["threads"].append(thread)
    return thread


def _title_from_message(content: str) -> str:
    text = " ".join(str(content or "").split())
    if not text:
        return "Claude workspace"
    return text[:54] + ("..." if len(text) > 54 else "")
