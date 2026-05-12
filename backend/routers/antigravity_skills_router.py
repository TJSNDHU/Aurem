"""
Antigravity Skills Router — 1,453+ agentic SKILL.md playbooks from
sickn33/antigravity-awesome-skills, queryable from ORA + broadcastable
to all 28 internal agents.

Endpoints (under /api/admin/antigravity-skills):
  GET  /library/meta             Last sync summary
  GET  /library                  Search/list (filters: q, category, risk)
  GET  /library/categories       Distinct categories with counts
  GET  /library/{skill_id}       Full SKILL.md body
  POST /sync                     Re-clone repo & upsert (idempotent)
  POST /broadcast                Push selected skill IDs to all 28 agents
  GET  /broadcast/active         What is currently broadcast
  POST /broadcast/clear          Stop the active broadcast

Agent integration helper:
  `services.agent_skill_broadcast.get_active_broadcast(db)` returns the
  active broadcast doc; agents append `system_addendum` to their system
  prompt so they instantly learn the broadcast skills.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/admin/antigravity-skills",
    tags=["antigravity-skills"],
)

_db = None


def set_db(database):
    global _db
    _db = database


async def _require_admin():
    if _db is None:
        raise HTTPException(503, "DB not initialised")
    return True


class BroadcastRequest(BaseModel):
    skill_ids: list[str] = Field(..., min_length=1, max_length=50)
    note: str = ""
    target_agents: list[str] = Field(default_factory=list)  # empty = all


@router.get("/library/meta")
async def library_meta(_=Depends(_require_admin)):
    meta = await _db.ora_skills_meta.find_one({"_id": "latest"}, {"_id": 0})
    total = await _db.ora_skills_library.count_documents({})
    return {"meta": meta or {}, "total_in_db": total}


@router.get("/library")
async def library_list(
    q: Optional[str] = Query(None, max_length=200),
    category: Optional[str] = None,
    risk: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    _=Depends(_require_admin),
):
    qry: dict = {}
    if category:
        qry["category"] = category
    if risk:
        qry["risk"] = risk
    if q:
        qry["$text"] = {"$search": q}
    projection = {
        "_id": 0, "id": 1, "name": 1, "description": 1,
        "category": 1, "risk": 1, "source": 1, "date_added": 1,
    }
    cur = _db.ora_skills_library.find(qry, projection).skip(skip).limit(limit)
    items = await cur.to_list(length=limit)
    total = await _db.ora_skills_library.count_documents(qry)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/library/categories")
async def library_categories(_=Depends(_require_admin)):
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    cur = _db.ora_skills_library.aggregate(pipeline)
    docs = await cur.to_list(length=500)
    return {"categories": [{"category": d["_id"], "count": d["count"]} for d in docs]}


@router.get("/library/{skill_id}")
async def library_get(skill_id: str, _=Depends(_require_admin)):
    doc = await _db.ora_skills_library.find_one({"id": skill_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Skill '{skill_id}' not found")
    return doc


@router.post("/sync")
async def library_sync(_=Depends(_require_admin)):
    """Re-clone repo & upsert. Runs in a thread so the git clone doesn't
    block the event loop."""
    import asyncio
    from scripts.ingest_antigravity_skills import ingest
    try:
        # ingest is already async and uses motor under the hood; the only
        # sync hop is the git clone which subprocess shells out. Run the
        # whole thing in a thread to be safe.
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: asyncio.run(ingest()))
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {e}")
    return {"ok": True, "result": result}


@router.post("/broadcast")
async def broadcast_skills(req: BroadcastRequest, _=Depends(_require_admin)):
    """Make selected skills active for all agents.

    Writes to `ora_skills_broadcast` collection (singleton doc
    `_id="active"`). Agents fetch this on every turn and merge the
    `system_addendum` into their system prompt for live learning.
    """
    docs = await _db.ora_skills_library.find(
        {"id": {"$in": req.skill_ids}},
        {"_id": 0, "id": 1, "name": 1, "description": 1, "category": 1, "body": 1},
    ).to_list(length=len(req.skill_ids))

    found_ids = {d["id"] for d in docs}
    missing = [sid for sid in req.skill_ids if sid not in found_ids]
    if missing:
        raise HTTPException(404, f"Unknown skills: {missing}")

    bits: list[str] = []
    for d in docs:
        head = (d.get("body") or "")[:600].strip()
        bits.append(
            f"### SKILL: {d['name']} ({d['category']})\n"
            f"{d.get('description', '')}\n"
            f"{head}"
        )
    addendum = "\n\n".join(bits)

    now = datetime.now(timezone.utc).isoformat()
    broadcast_doc = {
        "skill_ids": list(found_ids),
        "system_addendum": addendum,
        "note": req.note,
        "target_agents": req.target_agents or "ALL",
        "broadcast_at": now,
        "skill_count": len(found_ids),
    }
    await _db.ora_skills_broadcast.update_one(
        {"_id": "active"},
        {"$set": broadcast_doc},
        upsert=True,
    )
    await _db.ora_skills_broadcast_history.insert_one(
        {**broadcast_doc, "_id": f"bcast_{now}"}
    )
    try:
        from services.agent_skill_broadcast import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    # Mirror to Memoir — Git-versioned single source of truth for the
    # 28 agents that read via services.agent_skill_broadcast.
    try:
        from services import memoir_service as _M
        if _M.available():
            _M.skill_broadcast_set(addendum, list(found_ids))
    except Exception:
        pass
    return {
        "ok": True,
        "broadcast_at": now,
        "skill_count": len(found_ids),
        "skill_ids": list(found_ids),
        "addendum_chars": len(addendum),
        "target_agents": broadcast_doc["target_agents"],
    }


@router.get("/broadcast/active")
async def broadcast_active(_=Depends(_require_admin)):
    doc = await _db.ora_skills_broadcast.find_one({"_id": "active"}, {"_id": 0})
    return doc or {"active": False}


@router.post("/broadcast/clear")
async def broadcast_clear(_=Depends(_require_admin)):
    res = await _db.ora_skills_broadcast.delete_one({"_id": "active"})
    try:
        from services.agent_skill_broadcast import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    return {"cleared": res.deleted_count > 0}
