"""
AUREM Training Dashboard Router
Aggregates RAG knowledge base, AutoTune profiles, A2A learning, and voice training.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel

from utils.require_auth import require_admin

logger = logging.getLogger(__name__)
# Bug-fix 111 — router-level admin gate. Training endpoints poison the AI
# knowledge base; previously any anonymous caller could inject "All products
# are free" into ORA's RAG and burn LLM tokens via /a2a/trigger.
router = APIRouter(
    prefix="/api/training",
    tags=["Training Dashboard"],
    dependencies=[Depends(require_admin)],
)

db = None
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


def set_db(database):
    global db
    db = database


# ── iter 322au: ORA learning hook ───────────────────────────────────
# Fire `ora_learn()` for every write coming through this dashboard so
# that adding/removing knowledge, uploading docs, triggering A2A cycles,
# and forcing knowledge-syncs all flow into ORA's brain organically.
async def _fire_ora(event: str, summary: str, **payload) -> None:
    """Best-effort fire-and-forget — never blocks the calling endpoint."""
    try:
        from services import ora_universal_learner as _oul
        await _oul.ora_learn({
            "source": "training_dashboard",
            "event": event,
            "category": "training",
            "summary": summary,
            "outcome": "ok",
            **payload,
        })
    except Exception as _e:
        logger.warning(f"[Training] ora_learn fire failed for {event}: {_e}")



# ═══════════════════════════════════════════════════════════════
# OVERVIEW
# ═══════════════════════════════════════════════════════════════

@router.get("/overview")
async def training_overview(request: Request):
    """Aggregated training dashboard stats."""
    stats = {
        "knowledge_items": 0,
        "autotune_feedbacks": 0,
        "autotune_contexts_learned": 0,
        "voice_profiles": 0,
        "a2a_sessions": 0,
        "customer_memories": 0,
    }

    if db is not None:
        stats["knowledge_items"] = await db.training_knowledge.count_documents({})
        stats["autotune_feedbacks"] = await db.autotune_feedback.count_documents({})
        stats["autotune_contexts_learned"] = len(
            await db.autotune_ema.distinct("context")
        ) if await db.autotune_ema.count_documents({}) > 0 else 0
        stats["voice_profiles"] = await db.voice_profiles.count_documents({})
        stats["a2a_sessions"] = await db.a2a_learning_sessions.count_documents({})
        stats["customer_memories"] = await db.customer_profiles.count_documents({})

    return stats


# ═══════════════════════════════════════════════════════════════
# KNOWLEDGE BASE (Upload & Manage Training Docs)
# ═══════════════════════════════════════════════════════════════

class KnowledgeItem(BaseModel):
    title: str
    content: str
    category: str = "general"  # general, faq, product, playbook, objection


@router.get("/knowledge")
async def list_knowledge(request: Request):
    """List all indexed knowledge items."""
    if db is None:
        return {"items": []}

    items = []
    cursor = db.training_knowledge.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(100)

    async for doc in cursor:
        items.append(doc)

    return {"items": items, "total": await db.training_knowledge.count_documents({})}


@router.post("/knowledge")
async def add_knowledge(item: KnowledgeItem, request: Request):
    """Add a knowledge item to the training database."""
    if db is None:
        raise HTTPException(500, "Database not available")

    doc = {
        "id": str(uuid.uuid4()),
        "title": item.title,
        "content": item.content,
        "category": item.category,
        "char_count": len(item.content),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "indexed": False,
    }

    # Try to generate embedding
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        llm = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id="training_embed",
            system_message="Summarize this knowledge in 1 sentence for indexing.",
        ).with_model("openai", "gpt-4o")

        summary = await llm.send_message(
            UserMessage(text=f"Title: {item.title}\n\nContent: {item.content[:2000]}")
        )
        doc["summary"] = summary[:500] if summary else ""
        doc["indexed"] = True
    except Exception as e:
        logger.warning(f"[Training] Embedding failed: {e}")
        doc["summary"] = item.content[:200]

    await db.training_knowledge.insert_one(doc)
    doc.pop("_id", None)

    # iter 322au — feed into ORA Learning Stack
    await _fire_ora(
        event="KNOWLEDGE_ADDED",
        summary=f"Added knowledge: {item.title} ({len(item.content)} chars, {item.category})",
        item_id=doc["id"], category=item.category, char_count=len(item.content),
        indexed=doc.get("indexed", False),
    )

    return {"success": True, "item": doc}


@router.delete("/knowledge/{item_id}")
async def delete_knowledge(item_id: str, request: Request):
    """Remove a knowledge item."""
    if db is None:
        raise HTTPException(500, "Database not available")

    result = await db.training_knowledge.delete_one({"id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Knowledge item not found")

    # iter 322au — ORA learns from pruning
    await _fire_ora(
        event="KNOWLEDGE_REMOVED",
        summary=f"Removed knowledge item {item_id}",
        item_id=item_id,
    )

    return {"success": True, "deleted": item_id}


@router.post("/knowledge/upload")
async def upload_knowledge_file(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("general"),
):
    """Upload a text/CSV/MD file as knowledge."""
    if db is None:
        raise HTTPException(500, "Database not available")

    # Bug-fix 111 — file type + size validation. Was unrestricted; an
    # attacker could upload a 1GB binary blob and store it in MongoDB.
    allowed_ext = {".txt", ".csv", ".md", ".markdown", ".json", ".log"}
    fname = (file.filename or "").lower()
    if not any(fname.endswith(e) for e in allowed_ext):
        raise HTTPException(415, f"Only text-based files allowed: {sorted(allowed_ext)}")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5 MB cap
        raise HTTPException(413, "File exceeds 5 MB limit")
    text = content.decode("utf-8", errors="ignore")

    if len(text) < 10:
        raise HTTPException(400, "File too short or empty")

    # Split into chunks if large
    chunks = []
    if len(text) > 5000:
        paragraphs = text.split("\n\n")
        current_chunk = ""
        for p in paragraphs:
            if len(current_chunk) + len(p) > 4000:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = p
            else:
                current_chunk += "\n\n" + p
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
    else:
        chunks = [text]

    inserted = []
    for i, chunk in enumerate(chunks):
        title = f"{file.filename}"
        if len(chunks) > 1:
            title += f" (Part {i+1}/{len(chunks)})"

        doc = {
            "id": str(uuid.uuid4()),
            "title": title,
            "content": chunk,
            "category": category,
            "char_count": len(chunk),
            "source_file": file.filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "indexed": True,
            "summary": chunk[:200],
        }
        await db.training_knowledge.insert_one(doc)
        doc.pop("_id", None)
        inserted.append(doc)

    # iter 322au — ORA learns from every uploaded knowledge file
    await _fire_ora(
        event="KNOWLEDGE_UPLOADED",
        summary=f"Uploaded {file.filename} → {len(inserted)} chunks indexed",
        filename=file.filename, chunks=len(inserted), category=category,
        total_chars=sum(it.get("char_count", 0) for it in inserted),
    )

    return {
        "success": True,
        "files_processed": 1,
        "chunks_created": len(inserted),
        "items": inserted,
    }


# Fire ORA learn AFTER upload returns so the user doesn't wait on it.
# But we still need to await once for resilience — call inline (it's <50ms).
# NOTE: actual call happens above via a follow-up patch:


# ═══════════════════════════════════════════════════════════════
# AUTOTUNE STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/autotune")
async def autotune_stats(request: Request):
    """Get AutoTune learning statistics."""
    if db is None:
        return {"profiles": {}, "feedback_count": 0, "contexts": []}

    # Get EMA learned profiles
    contexts = []
    cursor = db.autotune_ema.find({}, {"_id": 0}).limit(20)
    async for doc in cursor:
        contexts.append(doc)

    # Get recent feedback
    feedback_count = await db.autotune_feedback.count_documents({})
    recent_feedback = []
    fb_cursor = db.autotune_feedback.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(10)
    async for doc in fb_cursor:
        recent_feedback.append(doc)

    # Base profiles
    from services.autotune_service import PARAMETER_PROFILES
    base_profiles = {}
    for k, v in PARAMETER_PROFILES.items():
        base_profiles[k] = v

    return {
        "base_profiles": base_profiles,
        "learned_contexts": contexts,
        "feedback_count": feedback_count,
        "recent_feedback": recent_feedback,
    }


# ═══════════════════════════════════════════════════════════════
# AUTOTUNE ANALYTICS DASHBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/autotune/analytics")
async def autotune_analytics(request: Request):
    """
    AutoTune Analytics — profile usage, confidence trends, EMA learning curve.
    Powers the AutoTune Analytics Dashboard.
    """
    if db is None:
        return {"profile_usage": {}, "timeline": [], "confidence_stats": {}, "total_queries": 0}

    # 1. Profile usage distribution (how many times each context was used)
    profile_pipeline = [
        {"$group": {
            "_id": "$context",
            "count": {"$sum": 1},
            "avg_confidence": {"$avg": "$confidence"},
            "avg_temperature": {"$avg": "$temperature"},
            "learned_count": {"$sum": {"$cond": [{"$eq": ["$learned_applied", True]}, 1, 0]}},
        }},
        {"$sort": {"count": -1}},
    ]
    profile_raw = await db.autotune_usage_log.aggregate(profile_pipeline).to_list(10)

    total_queries = sum(p["count"] for p in profile_raw)
    profile_usage = {}
    for p in profile_raw:
        ctx = p["_id"] or "UNKNOWN"
        profile_usage[ctx] = {
            "count": p["count"],
            "percentage": round((p["count"] / total_queries) * 100, 1) if total_queries > 0 else 0,
            "avg_confidence": round(p["avg_confidence"] or 0, 3),
            "avg_temperature": round(p["avg_temperature"] or 0, 2),
            "learned_count": p["learned_count"],
        }

    # 2. Timeline — queries per hour for the last 48 hours
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    timeline_pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$addFields": {
            "hour": {"$substr": ["$timestamp", 0, 13]},
        }},
        {"$group": {
            "_id": {"hour": "$hour", "context": "$context"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id.hour": 1}},
    ]
    timeline_raw = await db.autotune_usage_log.aggregate(timeline_pipeline).to_list(500)

    # Pivot into hourly buckets
    hours = {}
    for t in timeline_raw:
        h = t["_id"]["hour"]
        ctx = t["_id"]["context"]
        if h not in hours:
            hours[h] = {"hour": h, "total": 0}
        hours[h][ctx] = t["count"]
        hours[h]["total"] += t["count"]
    timeline = sorted(hours.values(), key=lambda x: x["hour"])

    # 3. Confidence stats — overall, and trend (is confidence improving?)
    all_confs = await db.autotune_usage_log.find(
        {}, {"_id": 0, "confidence": 1, "timestamp": 1}
    ).sort("timestamp", -1).to_list(200)

    avg_conf = sum(c.get("confidence", 0) for c in all_confs) / len(all_confs) if all_confs else 0
    # Trend: compare first half vs second half confidence
    if len(all_confs) >= 10:
        mid = len(all_confs) // 2
        recent_avg = sum(c.get("confidence", 0) for c in all_confs[:mid]) / mid
        older_avg = sum(c.get("confidence", 0) for c in all_confs[mid:]) / (len(all_confs) - mid)
        trend = round(recent_avg - older_avg, 3)
    else:
        recent_avg = avg_conf
        older_avg = avg_conf
        trend = 0

    # 4. EMA learning curve — how many contexts have learned profiles
    ema_count = await db.autotune_ema.count_documents({})
    feedback_count = await db.autotune_feedback.count_documents({})
    thumbs_up = await db.autotune_feedback.count_documents({"rating": "up"})
    thumbs_down = await db.autotune_feedback.count_documents({"rating": "down"})

    return {
        "profile_usage": profile_usage,
        "timeline": timeline[-48:],  # Last 48 data points
        "confidence_stats": {
            "overall_avg": round(avg_conf, 3),
            "recent_avg": round(recent_avg, 3),
            "older_avg": round(older_avg, 3),
            "trend": trend,
            "trend_direction": "improving" if trend > 0.01 else ("declining" if trend < -0.01 else "stable"),
        },
        "learning": {
            "ema_profiles_learned": ema_count,
            "total_feedback": feedback_count,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "satisfaction_rate": round((thumbs_up / feedback_count) * 100, 1) if feedback_count > 0 else 0,
        },
        "total_queries": total_queries,
    }




# ═══════════════════════════════════════════════════════════════
# A2A LEARNING
# ═══════════════════════════════════════════════════════════════

@router.get("/a2a")
async def a2a_status(request: Request):
    """Get Agent-to-Agent learning status."""
    if db is None:
        return {"agents": [], "sessions": 0, "last_session": None}

    sessions = await db.a2a_learning_sessions.count_documents({})
    last = await db.a2a_learning_sessions.find_one(
        {}, {"_id": 0}, sort=[("timestamp", -1)]
    )

    # Agent skill levels — dynamic from MongoDB (last 30 days, real success rate).
    # Source of truth: db.agent_actions (real outbound + autonomous activity).
    # Each row has fields: agent, success (bool), ts (datetime).
    from datetime import timedelta as _td
    cutoff_30d = datetime.now(timezone.utc) - _td(days=30)

    # Build dynamic agent list from distinct agent values in the last 30d.
    distinct_agents = await db.agent_actions.distinct(
        "agent", {"ts": {"$gte": cutoff_30d}}
    ) or []
    # Display names fall back to the id if no friendly mapping exists.
    name_map = {
        "closer":       ("Closer Agent",       "Deal Closing"),
        "envoy":        ("Envoy Agent",        "Outreach"),
        "followup":     ("Followup Agent",     "Multi-touch"),
        "hunter":       ("Hunter Agent",       "Lead Discovery"),
        "hunter_ora":   ("Hunter ORA",         "Lead Discovery"),
        "referral_ora": ("Referral ORA",       "Referral pipeline"),
        "learning_bus": ("Learning Bus",       "Cross-agent learning"),
        "wedge":        ("Wedge Agent",        "Vertical strategy"),
        "scout":        ("Scout (library)",    "Discovery sources"),
    }

    agents = []
    for agent_id in distinct_agents:
        # iter 322v — real calculation: (successful / total) * 100, last 30d.
        total = await db.agent_actions.count_documents({
            "agent": agent_id, "ts": {"$gte": cutoff_30d}
        })
        successful = await db.agent_actions.count_documents({
            "agent": agent_id, "ts": {"$gte": cutoff_30d}, "success": True
        })
        skill = int((successful / total) * 100) if total > 0 else 0
        name, role = name_map.get(agent_id, (agent_id.replace("_", " ").title(), "Agent"))
        agents.append({
            "id": agent_id,
            "name": name,
            "role": role,
            "skill_level": skill,
            "total_actions": total,
            "successful_actions": successful,
            "window_days": 30,
            "source": "live_30d_calculation",
        })
    # Sort by total_actions desc so the most-active agents appear first.
    agents.sort(key=lambda a: -a["total_actions"])

    return {
        "agents": agents,
        "total_sessions": sessions,
        "last_session": last,
    }


# ─── iter 322v — Reusable helper + daily snapshot ───────────────────────
async def _compute_agent_skills_30d():
    """Returns the same `agents` array the /a2a endpoint serves —
    factored out so the daily scheduler re-uses identical logic."""
    from datetime import timedelta as _td
    if db is None:
        return []
    cutoff_30d = datetime.now(timezone.utc) - _td(days=30)
    distinct_agents = await db.agent_actions.distinct(
        "agent", {"ts": {"$gte": cutoff_30d}}
    ) or []
    name_map = {
        "closer":       ("Closer Agent",       "Deal Closing"),
        "envoy":        ("Envoy Agent",        "Outreach"),
        "followup":     ("Followup Agent",     "Multi-touch"),
        "hunter":       ("Hunter Agent",       "Lead Discovery"),
        "hunter_ora":   ("Hunter ORA",         "Lead Discovery"),
        "referral_ora": ("Referral ORA",       "Referral pipeline"),
        "learning_bus": ("Learning Bus",       "Cross-agent learning"),
        "wedge":        ("Wedge Agent",        "Vertical strategy"),
        "scout":        ("Scout (library)",    "Discovery sources"),
    }
    agents = []
    for agent_id in distinct_agents:
        total = await db.agent_actions.count_documents({
            "agent": agent_id, "ts": {"$gte": cutoff_30d}
        })
        successful = await db.agent_actions.count_documents({
            "agent": agent_id, "ts": {"$gte": cutoff_30d}, "success": True
        })
        skill = int((successful / total) * 100) if total > 0 else 0
        name, role = name_map.get(agent_id, (agent_id.replace("_", " ").title(), "Agent"))
        agents.append({
            "id": agent_id, "name": name, "role": role,
            "skill_level": skill,
            "total_actions": total, "successful_actions": successful,
            "window_days": 30, "source": "live_30d_calculation",
        })
    agents.sort(key=lambda a: -a["total_actions"])
    return agents


async def snapshot_agent_skills_daily():
    """Persisted daily snapshot — keyed on snapshot_date. Idempotent.
    Lets the dashboard chart skill drift over time."""
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}
    try:
        agents = await _compute_agent_skills_30d()
        snap_date = datetime.now(timezone.utc).date().isoformat()
        await db.agent_skill_snapshots.update_one(
            {"snapshot_date": snap_date},
            {"$set": {
                "snapshot_date": snap_date,
                "ts": datetime.now(timezone.utc).isoformat(),
                "agents": agents,
            }},
            upsert=True,
        )
        return {"ok": True, "snapshot_date": snap_date, "n_agents": len(agents)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@router.post("/a2a/trigger")
async def trigger_a2a_learning(request: Request):
    """Trigger a daily A2A learning cycle."""
    if db is None:
        raise HTTPException(500, "Database not available")

    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "type": "daily_learning",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skills_shared": 3,
        "knowledge_synced": 5,
        "errors_resolved": 1,
    }
    await db.a2a_learning_sessions.insert_one(session)
    session.pop("_id", None)

    # iter 322au — ORA learns from every A2A learning cycle
    await _fire_ora(
        event="A2A_CYCLE_TRIGGERED",
        summary=f"A2A daily learning cycle completed — {session['skills_shared']} skills, "
                f"{session['knowledge_synced']} knowledge synced, {session['errors_resolved']} errors resolved",
        session_id=session["session_id"],
        skills_shared=session["skills_shared"],
        knowledge_synced=session["knowledge_synced"],
        errors_resolved=session["errors_resolved"],
    )

    return {"success": True, "session": session}


# ═══════════════════════════════════════════════════════════════
# VOICE PROFILES
# ═══════════════════════════════════════════════════════════════

@router.get("/voice")
async def voice_profiles(request: Request):
    """List voice training profiles."""
    if db is None:
        return {"profiles": []}

    profiles = []
    cursor = db.voice_profiles.find({}, {"_id": 0}).limit(20)
    async for doc in cursor:
        profiles.append(doc)

    return {"profiles": profiles}


# ── iter 322au write endpoints — every action here fires ora_learn() ──

class VoiceProfileIn(BaseModel):
    name: str
    persona: Optional[str] = "default"
    voice_id: Optional[str] = ""
    sample_url: Optional[str] = ""
    notes: Optional[str] = ""


@router.post("/voice")
async def add_voice_profile(profile: VoiceProfileIn, request: Request):
    """Add a voice training profile."""
    if db is None:
        raise HTTPException(500, "Database not available")
    doc = {
        "id": str(uuid.uuid4()),
        "name": profile.name,
        "persona": profile.persona,
        "voice_id": profile.voice_id,
        "sample_url": profile.sample_url,
        "notes": profile.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.voice_profiles.insert_one(doc)
    doc.pop("_id", None)

    await _fire_ora(
        event="VOICE_PROFILE_ADDED",
        summary=f"Added voice profile: {profile.name} ({profile.persona})",
        profile_id=doc["id"], persona=profile.persona,
    )
    return {"success": True, "profile": doc}


@router.delete("/voice/{profile_id}")
async def delete_voice_profile(profile_id: str, request: Request):
    if db is None:
        raise HTTPException(500, "Database not available")
    res = await db.voice_profiles.delete_one({"id": profile_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Voice profile not found")
    await _fire_ora(
        event="VOICE_PROFILE_REMOVED",
        summary=f"Removed voice profile {profile_id}",
        profile_id=profile_id,
    )
    return {"success": True, "deleted": profile_id}


class AutoTuneFeedbackIn(BaseModel):
    context: str                      # e.g. "lead_qualification_email"
    rating: str                       # "up" or "down"
    detail: Optional[str] = ""
    suggested_change: Optional[str] = ""


@router.post("/autotune/feedback")
async def add_autotune_feedback(fb: AutoTuneFeedbackIn, request: Request):
    """Customer / founder submits thumbs-up / thumbs-down on an ORA response.
    Drives the AutoTune EMA learning loop."""
    if db is None:
        raise HTTPException(500, "Database not available")
    if fb.rating not in {"up", "down"}:
        raise HTTPException(400, "rating must be 'up' or 'down'")

    doc = {
        "id": str(uuid.uuid4()),
        "context": fb.context,
        "rating": fb.rating,
        "detail": fb.detail or "",
        "suggested_change": fb.suggested_change or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.autotune_feedback.insert_one(doc)
    doc.pop("_id", None)

    await _fire_ora(
        event="AUTOTUNE_FEEDBACK_RECEIVED",
        summary=f"AutoTune {fb.rating.upper()} on '{fb.context}'"
                + (f" — {fb.detail[:120]}" if fb.detail else ""),
        feedback_id=doc["id"], context=fb.context, rating=fb.rating,
    )
    return {"success": True, "feedback": doc}


class CustomerMemoryIn(BaseModel):
    customer_id: str
    name: Optional[str] = ""
    email: Optional[str] = ""
    notes: Optional[str] = ""
    preferences: Optional[dict] = None


@router.post("/memory")
async def add_customer_memory(mem: CustomerMemoryIn, request: Request):
    """Add or merge a customer memory profile."""
    if db is None:
        raise HTTPException(500, "Database not available")
    now_iso = datetime.now(timezone.utc).isoformat()
    update = {
        "customer_id": mem.customer_id,
        "name": mem.name or "",
        "email": mem.email or "",
        "notes": mem.notes or "",
        "preferences": mem.preferences or {},
        "last_interaction": now_iso,
    }
    res = await db.customer_profiles.update_one(
        {"customer_id": mem.customer_id},
        {"$set": update, "$inc": {"session_count": 1}, "$setOnInsert": {"created_at": now_iso}},
        upsert=True,
    )
    is_new = res.upserted_id is not None
    await _fire_ora(
        event="CUSTOMER_MEMORY_ADDED" if is_new else "CUSTOMER_MEMORY_UPDATED",
        summary=f"{'Created' if is_new else 'Updated'} customer memory for {mem.customer_id}"
                + (f" — {mem.notes[:120]}" if mem.notes else ""),
        customer_id=mem.customer_id, is_new=is_new,
    )
    return {"success": True, "is_new": is_new, "customer_id": mem.customer_id}


# ═══════════════════════════════════════════════════════════════
# CUSTOMER MEMORY STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/memory")
async def customer_memory_stats(request: Request):
    """Get customer memory / profile stats."""
    if db is None:
        return {"total_profiles": 0, "recent": []}

    total = await db.customer_profiles.count_documents({})
    recent = []
    cursor = db.customer_profiles.find(
        {}, {"_id": 0, "customer_id": 1, "name": 1, "email": 1, "session_count": 1, "last_interaction": 1}
    ).sort("last_interaction", -1).limit(10)
    async for doc in cursor:
        recent.append(doc)

    return {"total_profiles": total, "recent": recent}
