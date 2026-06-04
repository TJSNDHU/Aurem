"""Remember skill — persist a learning into cto_learnings."""
from datetime import datetime, timezone
from typing import Any

from .registry import skill


@skill(
    name="remember",
    description=(
        "Save a one-line learning, gotcha, or decision to the CTO's "
        "long-term memory. Re-loaded on every chat session for context."
    ),
    requires_db=True,
)
async def remember(*, db, topic: str, lesson: str,
                      tags: list[str] | None = None) -> dict[str, Any]:
    doc = {
        "topic":      topic[:80],
        "lesson":     lesson[:600],
        "tags":       (tags or [])[:10],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source":     "cto_skill",
    }
    await db.cto_learnings.insert_one(doc)
    return {"topic": topic, "stored": True,
             "snippet": lesson[:120]}
