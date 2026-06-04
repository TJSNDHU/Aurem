"""Recall skill — fetch relevant learnings from cto_learnings."""
from typing import Any

from .registry import skill


@skill(
    name="recall",
    description=(
        "Pull up recent CTO learnings related to a topic or tag. Use at "
        "the start of a session to load context before answering."
    ),
    requires_db=True,
)
async def recall(*, db, topic: str = "", tag: str = "",
                    limit: int = 10) -> dict[str, Any]:
    q: dict = {}
    if topic:
        q["topic"] = {"$regex": topic[:80], "$options": "i"}
    if tag:
        q["tags"] = tag
    items: list = []
    async for d in db.cto_learnings.find(q, {"_id": 0}) \
                                       .sort("created_at", -1).limit(limit):
        items.append(d)
    return {"query": {"topic": topic, "tag": tag},
             "count": len(items), "items": items}
