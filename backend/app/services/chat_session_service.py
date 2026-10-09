"""
Multi-session requirement chat: each session is its own draft SearchPlan +
chat history, so a recruiter can start a fresh conversation ("New Chat")
without losing an earlier one — same pattern as a typical chat app's session
list. Session state is held in this module's in-memory dict (mirroring the
other module-global state in api/search.py) and persisted via
state_persistence.py so a backend restart doesn't drop in-progress chats.

One-time migration: if a backend restarts after an upgrade and finds the
OLD single-draft shape (draft_plan/chat_history at the top level of the
state file, from before sessions existed) but no `sessions` key yet, that
single draft is wrapped into one session rather than silently discarded.
"""
import time
import uuid
from typing import Any, Dict, List, Optional

from app.services import state_persistence

_TITLE_MAX_LEN = 60


def _derive_title(chat_history: List[dict]) -> str:
    for msg in chat_history:
        if msg.get("role") == "user" and msg.get("content"):
            text = " ".join(msg["content"].split())  # collapse newlines/whitespace
            return text[:_TITLE_MAX_LEN] + ("..." if len(text) > _TITLE_MAX_LEN else "")
    return "New chat"


def _new_session_dict() -> Dict[str, Any]:
    now = time.time()
    return {
        "id": str(uuid.uuid4()),
        "title": "New chat",
        "draft_plan": None,
        "chat_history": [],
        "draft_timestamp": 0.0,
        "created_at": now,
        "updated_at": now,
        # active_in on the FIRST draft this session ever produced — the
        # baseline the recruiter started from, captured once and never
        # overwritten, so a later apply can be compared against it to detect
        # "ended up widening this" (see services/preference_service.py).
        "generated_active_in": None,
    }


class ChatSessionStore:
    def __init__(self):
        persisted = state_persistence.load_state()
        self.sessions: Dict[str, Dict[str, Any]] = persisted.get("sessions") or {}
        self.active_session_id: Optional[str] = persisted.get("active_session_id")

        # Migrate the pre-sessions single-draft shape, if present and we
        # haven't already got real sessions from a previous migration.
        legacy_draft = persisted.get("draft_plan")
        legacy_history = persisted.get("chat_history")
        if not self.sessions and (legacy_draft or legacy_history):
            session = _new_session_dict()
            session["draft_plan"] = legacy_draft
            session["chat_history"] = legacy_history or []
            session["draft_timestamp"] = persisted.get("draft_timestamp") or 0.0
            session["title"] = _derive_title(session["chat_history"])
            self.sessions[session["id"]] = session
            self.active_session_id = session["id"]

        if not self.sessions:
            session = _new_session_dict()
            self.sessions[session["id"]] = session
            self.active_session_id = session["id"]
        elif self.active_session_id not in self.sessions:
            # Stale pointer (e.g. active session got deleted in a way that
            # didn't update the pointer) — fall back to most recently updated.
            self.active_session_id = max(self.sessions.values(), key=lambda s: s["updated_at"])["id"]

    def _persist(self, persist_callback) -> None:
        persist_callback()

    def list_sessions(self) -> List[Dict[str, Any]]:
        return sorted(
            [
                {
                    "id": s["id"],
                    "title": s["title"],
                    "updated_at": s["updated_at"],
                    "message_count": len(s["chat_history"]),
                    "active": s["id"] == self.active_session_id,
                }
                for s in self.sessions.values()
            ],
            key=lambda s: s["updated_at"],
            reverse=True,
        )

    def get_active(self) -> Dict[str, Any]:
        return self.sessions[self.active_session_id]

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def create_session(self, persist_callback) -> Dict[str, Any]:
        session = _new_session_dict()
        self.sessions[session["id"]] = session
        self.active_session_id = session["id"]
        self._persist(persist_callback)
        return session

    def set_active(self, session_id: str, persist_callback) -> Optional[Dict[str, Any]]:
        if session_id not in self.sessions:
            return None
        self.active_session_id = session_id
        self._persist(persist_callback)
        return self.sessions[session_id]

    def update_session(
        self, session_id: str, draft_plan: Optional[dict], chat_history: list, persist_callback
    ) -> Dict[str, Any]:
        session = self.sessions[session_id]
        if session["draft_plan"] is None and draft_plan is not None:
            # First real draft this session has ever had — baseline for
            # preference-learning comparison (see preference_service.py).
            session["generated_active_in"] = draft_plan.get("active_in")
        if draft_plan is None:
            session["generated_active_in"] = None  # reset (clear chat) — next draft starts a fresh baseline
        session["draft_plan"] = draft_plan
        session["chat_history"] = chat_history
        session["draft_timestamp"] = time.time()
        session["updated_at"] = session["draft_timestamp"]
        session["title"] = _derive_title(chat_history)  # "New chat" again if history is now empty (reset case)
        self._persist(persist_callback)
        return session

    def delete_session(self, session_id: str, persist_callback) -> bool:
        if session_id not in self.sessions:
            return False
        del self.sessions[session_id]
        if not self.sessions:
            new_session = _new_session_dict()
            self.sessions[new_session["id"]] = new_session
            self.active_session_id = new_session["id"]
        elif self.active_session_id == session_id:
            self.active_session_id = max(self.sessions.values(), key=lambda s: s["updated_at"])["id"]
        self._persist(persist_callback)
        return True
