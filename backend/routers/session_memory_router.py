"""
Session Memory Router — append development session entries to /app/docs/session_memory.md

Bug-fix 146 (Round 17): every endpoint here writes / reads files on the
production filesystem. Was completely unauthenticated; an attacker could
inject arbitrary Markdown (or links) into the dev session log and read all
past dev notes via /latest. Now admin-gated via shared require_admin helper.
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from utils.require_auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/session-memory",
    tags=["Session Memory"],
    dependencies=[Depends(require_admin)],
)

MEMORY_FILE = "/app/docs/session_memory.md"


def _sanitize(s: str) -> str:
    """Strip control chars and cap length. Was: raw string concat into Markdown."""
    if not isinstance(s, str):
        return ""
    out = "".join(ch for ch in s if ch == "\n" or ch == "\t" or 0x20 <= ord(ch) < 0x7F or ord(ch) > 0x9F)
    return out[:2000]


class SessionEntry(BaseModel):
    built: str
    changed: str
    tested: str
    pending: str
    issues: Optional[str] = "None"


@router.post("/append")
async def append_session(entry: SessionEntry):
    """Append a sanitised session entry. Admin-only."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")

    block = (
        f"\n## Session {date_str}\n"
        f"- Built: {_sanitize(entry.built)}\n"
        f"- Changed: {_sanitize(entry.changed)}\n"
        f"- Tested: {_sanitize(entry.tested)}\n"
        f"- Pending: {_sanitize(entry.pending)}\n"
        f"- Known issues: {_sanitize(entry.issues or 'None')}\n"
    )

    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, "a") as f:
            f.write(block)
        return {"status": "ok", "date": date_str}
    except Exception as e:
        logger.error(f"[Session Memory] Append failed: {e}")
        return {"status": "error", "detail": str(e)}


@router.get("/latest")
async def get_latest_sessions():
    """Read the session memory file. Admin-only."""
    try:
        if not os.path.exists(MEMORY_FILE):
            return {"sessions": [], "note": "No session memory file yet"}
        with open(MEMORY_FILE, "r") as f:
            content = f.read()
        return {"content": content, "file": MEMORY_FILE}
    except Exception as e:
        return {"error": str(e)}
