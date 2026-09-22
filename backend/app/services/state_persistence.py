"""
Tiny file-based persistence for the process-global search state (active
SearchPlan + extracted candidates) in backend/app/api/search.py.

That state used to live purely in memory, so a backend restart (or, on a
host that recycles idle workers, an unexpected one) silently dropped every
candidate the recruiter had collected. This writes a snapshot to disk after
every mutation and reloads it at import time, so state survives a restart.
It is deliberately NOT a database: single JSON file, single-tenant, same
scope as the in-memory globals it backs — just durable across restarts.
"""
import json
import logging
import os
import tempfile
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".data")
_STATE_FILE = os.path.join(_STATE_DIR, "search_state.json")


def load_state() -> Dict[str, Any]:
    """Best-effort load; any problem (missing file, corrupt JSON) yields empty state
    rather than crashing app startup."""
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("Could not load persisted search state (%s) — starting empty.", exc)
    return {}


def save_state(
    search_plan: Optional[dict],
    plan_timestamp: float,
    candidates: list,
    candidates_timestamp: float,
    search_id: Optional[str],
) -> None:
    """Best-effort save; a write failure (e.g. read-only filesystem on some hosts)
    must never break the request that triggered it — log and move on."""
    try:
        os.makedirs(_STATE_DIR, exist_ok=True)
        payload = {
            "search_plan": search_plan,
            "plan_timestamp": plan_timestamp,
            "candidates": candidates,
            "candidates_timestamp": candidates_timestamp,
            "search_id": search_id,
        }
        # Write to a temp file then rename, so a crash mid-write never leaves
        # a truncated/corrupt state file behind.
        fd, tmp_path = tempfile.mkstemp(dir=_STATE_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp_path, _STATE_FILE)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    except Exception as exc:
        logger.warning("Could not persist search state (%s) — continuing with in-memory only.", exc)
