"""
Session Memory Router — append development session entries to /app/docs/session_memory.md
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session-memory", tags=["Session Memory"])

MEMORY_FILE = "/app/docs/session_memory.md"


class SessionEntry(BaseModel):
    built: str
    changed: str
    tested: str
    pending: str
    issues: Optional[str] = "None"


@router.post("/append")
async def append_session(entry: SessionEntry):
    """Append a session entry to the memory file."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")

    block = f"""
## Session {date_str}
- Built: {entry.built}
- Changed: {entry.changed}
- Tested: {entry.tested}
- Pending: {entry.pending}
- Known issues: {entry.issues}
"""

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
    """Read the session memory file."""
    try:
        if not os.path.exists(MEMORY_FILE):
            return {"sessions": [], "note": "No session memory file yet"}
        with open(MEMORY_FILE, "r") as f:
            content = f.read()
        return {"content": content, "file": MEMORY_FILE}
    except Exception as e:
        return {"error": str(e)}
