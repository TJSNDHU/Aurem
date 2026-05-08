"""
Founders Console — chat-driven control plane (iter 296)
=======================================================
TJ types instructions → ORA Brain interprets → routes through Council →
emits A2A tasks → logs outcomes via ORA Learning.

POST /api/admin/console/message
  body: {message, session_id?}
  → {reply, decision_id, action_kind?, task_ids?, requires_approval?}

GET /api/admin/console/history?session_id=
GET /api/admin/console/sessions
POST /api/admin/console/approve/{decision_id}
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Query, UploadFile, File, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/console", tags=["Founders Console"])


def _verify_admin(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Admin authentication required")
    import jwt
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            os.environ.get("JWT_SECRET", ""),
            algorithms=["HS256"],
        )
        if payload.get("is_admin") or payload.get("role") == "admin" or payload.get("email"):
            return payload
        raise HTTPException(403, "Admin only")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")


_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is None:
        try:
            import server
            _db = getattr(server, "db", None)
        except Exception:
            pass
    return _db


# ─── Intent classifier (heuristic + LLM fallback) ──────────────────────────
# Order matters — first match wins. Report/info_query checked before blast
# so "how many sends today?" doesn't fire an outreach_blast.
KEYWORDS = [
    ("report",          ["report", "summary", "metrics", "stats", "how many",
                         "what is", "what's", "show me", "tell me"]),
    ("pause_outreach",  ["pause outreach", "stop outreach", "halt outreach",
                         "kill outreach", "pause blast", "stop blast"]),
    ("resume_outreach", ["resume outreach", "restart outreach", "resume blast",
                         "start blast"]),
    ("domain_purchase", ["buy domain", "register domain", "purchase domain"]),
    ("site_deploy",     ["deploy site", "build site", "launch site",
                         "publish site", "ship site"]),
    ("site_scan",       ["scan site", "audit site", "run scan", "run audit"]),
    ("stripe_charge",   ["charge customer", "create invoice", "stripe charge"]),
    ("scout_run",       ["scout", "find leads", "enrich leads", "enrich batch"]),
    ("outreach_blast",  ["send blast", "send outreach", "blast leads",
                         "send to leads", "follow up", "follow-up",
                         "trigger blast", "run blast"]),
]


def _classify(message: str) -> str:
    m = message.lower()
    for kind, words in KEYWORDS:
        if any(w in m for w in words):
            return kind
    return "info_query"


async def _ora_brain_reply(
    message: str,
    intent: str,
    council_decision: Dict[str, Any],
    history_context: str = "",
) -> str:
    """Generate the chat reply via Emergent LLM Key. Falls back to template."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if api_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
            try:
                from services.ora_date_helper import get_authoritative_date_block
                _date_hdr = get_authoritative_date_block()
            except Exception:
                _date_hdr = ""
            chat = LlmChat(
                api_key=api_key, session_id=f"console-{uuid.uuid4().hex[:8]}",
                system_message=(
                    _date_hdr +
                    "\nYou are ORA Brain — TJ Sandhu's executive assistant for AUREM. "
                    "Be concise, direct, actionable. Hinglish optional. Show numbers. No fluff. "
                    "Respond in 3 sentences max unless TJ asks for detail. "
                    "If a council decision is provided, mention the verdict and reasoning briefly. "
                    "If <<SUMMARY>> + <<RECENT>> context is present, use it for continuity."
                ),
            ).with_model("anthropic", "claude-sonnet-4.5").with_max_tokens(400)
            ctx_parts = []
            if history_context:
                ctx_parts.append(history_context)
            ctx_parts.append(
                f"User said: {message}\n"
                f"Intent: {intent}\n"
                f"Council verdict: {council_decision.get('decision')} "
                f"(conf={council_decision.get('avg_confidence')})\n"
                f"Reason: {council_decision.get('reason','')[:160]}"
            )
            ctx = "\n\n".join(ctx_parts)
            import asyncio as _a
            r = await _a.wait_for(chat.send_message(UserMessage(text=ctx)), timeout=10.0)
            return (r or "").strip() or _fallback_reply(intent, council_decision)
        except Exception as e:
            logger.debug(f"[console] LLM reply failed: {e}")
    return _fallback_reply(intent, council_decision)


def _fallback_reply(intent: str, decision: Dict[str, Any]) -> str:
    verdict = decision.get("decision", "approve")
    if verdict == "approve":
        return f"Done. Council approved — confidence {decision.get('avg_confidence', 0):.0%}. A2A task queued."
    if verdict == "veto":
        return f"Council vetoed — {decision.get('reason','')[:160]}"
    return f"Needs your approval — {decision.get('reason','')[:160]}. Tap approve to proceed."


# ─── Models ─────────────────────────────────────────────────────────────────
class MessagePayload(BaseModel):
    message: str
    session_id: Optional[str] = None


# ─── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/message")
async def send_message(body: MessagePayload, authorization: Optional[str] = Header(None)):
    user = _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB unavailable")

    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(400, "message required")

    session_id = body.session_id or f"sess-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    intent = _classify(msg)

    # Persist user turn
    await db.console_messages.insert_one({
        "session_id": session_id, "role": "user",
        "user_email": user.get("email"),
        "message": msg, "intent": intent, "ts": now,
    })

    # Council deliberation
    from services.council import council
    decision = await council.deliberate(
        action_kind=intent,
        payload={"message": msg[:400], "user": user.get("email")},
        cost_usd=0.005,
    )

    # If approved + intent maps to a real action, emit A2A task chain
    task_ids: List[str] = []
    if decision["decision"] == "approve":
        from services.a2a_task_queue import tq
        if intent == "outreach_blast":
            t = await tq.submit("ora_brain", "envoy", "trigger_blast",
                                {"source": "founders_console", "message": msg[:200]},
                                council_decision_id=decision["decision_id"])
            task_ids.append(t)
        elif intent == "site_deploy":
            t = await tq.submit("ora_brain", "architect", "build_site",
                                {"source": "founders_console", "instruction": msg[:400]},
                                council_decision_id=decision["decision_id"])
            task_ids.append(t)
        elif intent == "scout_run":
            t = await tq.submit("ora_brain", "scout", "enrich_batch",
                                {"source": "founders_console", "instruction": msg[:400]},
                                council_decision_id=decision["decision_id"])
            task_ids.append(t)
        elif intent in ("pause_outreach", "resume_outreach"):
            try:
                await db.auto_blast_config.update_one(
                    {"tenant_id": "global"},
                    {"$set": {"enabled": intent == "resume_outreach",
                              "updated_at": now, "updated_by": "founders_console"}},
                    upsert=True,
                )
            except Exception:
                pass

    # Log to ORA Learning
    from services.ora_learning import ora
    aid = await ora.log_action(
        agent="ora_brain", action=f"console_{intent}",
        input_data={"message": msg[:200], "session_id": session_id},
        output_data={"decision": decision["decision"], "task_ids": task_ids},
    )
    await ora.update_outcome(aid, "success" if decision["decision"] != "veto" else "failed")

    # Build context: pull recent history + auto-compress if too long
    raw_history = await db.console_messages.find(
        {"session_id": session_id}, {"_id": 0},
    ).sort("ts", 1).to_list(200)
    from services.token_compression import build_context
    history_context = await build_context(
        db, session_id, raw_history, scope="founders_console", keep_last=8,
    )

    # Generate reply
    reply = await _ora_brain_reply(msg, intent, decision, history_context=history_context)

    # Persist assistant turn
    await db.console_messages.insert_one({
        "session_id": session_id, "role": "assistant",
        "message": reply,
        "intent": intent,
        "decision_id": decision["decision_id"],
        "decision": decision["decision"],
        "confidence": decision.get("avg_confidence"),
        "task_ids": task_ids,
        "requires_approval": decision["decision"] == "escalate",
        "ts": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "session_id": session_id,
        "reply": reply,
        "intent": intent,
        "decision_id": decision["decision_id"],
        "decision": decision["decision"],
        "confidence": decision.get("avg_confidence"),
        "task_ids": task_ids,
        "requires_approval": decision["decision"] == "escalate",
    }


@router.get("/history")
async def history(session_id: str = Query(...),
                  authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        return {"messages": []}
    msgs = await db.console_messages.find(
        {"session_id": session_id}, {"_id": 0},
    ).sort("ts", 1).limit(200).to_list(200)
    return {"messages": msgs, "session_id": session_id}


@router.get("/sessions")
async def sessions(authorization: Optional[str] = Header(None)):
    user = _verify_admin(authorization)
    db = _get_db()
    if db is None:
        return {"sessions": []}
    pipe = [
        {"$match": {"user_email": user.get("email")}},
        {"$group": {"_id": "$session_id",
                    "last_ts": {"$max": "$ts"},
                    "first_msg": {"$first": "$message"},
                    "n": {"$sum": 1}}},
        {"$sort": {"last_ts": -1}},
        {"$limit": 30},
    ]
    out = []
    async for r in db.console_messages.aggregate(pipe):
        out.append({
            "session_id": r["_id"], "last_ts": r["last_ts"],
            "preview": (r.get("first_msg") or "")[:80], "n": r["n"],
        })
    return {"sessions": out}



# ─── Voice input (Whisper STT) ──────────────────────────────────────────────
@router.post("/voice")
async def voice_transcribe(
    audio: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
):
    """Browser MediaRecorder → Whisper STT. Returns {transcript}."""
    _verify_admin(authorization)
    if audio is None:
        raise HTTPException(400, "audio file required")
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise HTTPException(503, "Whisper unavailable: EMERGENT_LLM_KEY missing")
    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText  # type: ignore
    except Exception as e:
        raise HTTPException(503, f"emergentintegrations not available: {e}")

    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "empty audio")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "audio > 25 MB limit")

    # Whisper expects a file-like object with a name attribute
    import io
    fname = audio.filename or "voice.webm"
    if "." not in fname:
        fname += ".webm"
    bio = io.BytesIO(raw)
    bio.name = fname

    try:
        stt = OpenAISpeechToText(api_key=api_key)
        resp = await stt.transcribe(file=bio, model="whisper-1", response_format="json")
        text = (getattr(resp, "text", "") or "").strip()
        return {"transcript": text, "bytes": len(raw)}
    except Exception as e:
        logger.warning(f"[console.voice] whisper failed: {e}")
        raise HTTPException(502, f"transcription failed: {str(e)[:160]}")



# ═══ Iter 305 — 6-Stage Founders Build Pipeline ═══════════════════════════
class ProposeRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@router.post("/propose")
async def propose(body: ProposeRequest, authorization: Optional[str] = Header(None)):
    """Stages 1-3-4: pre-process → race → council → enriched approval card."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    started = datetime.now(timezone.utc)

    from services.founders_pipeline import (
        preprocess_input, multi_model_race, enhance_council,
    )
    from services.council import council

    task = await preprocess_input(body.message)
    race = await multi_model_race(task, db)

    council_decision = await council.deliberate(
        action_kind=f"founders_console:{task['intent'].lower()}",
        payload={
            "title": task["title"],
            "description": task["description"][:300],
            "scope": task["scope"], "priority": task["priority"],
            "files_planned": (race.get("gemini_plan") or {}).get("files") or [],
        },
        cost_usd=0.05, llm_voters=False,    # we already raced 3 models above
    )
    enriched = enhance_council(council_decision, task, race)

    proposal_id = uuid.uuid4().hex[:14]
    session_id = body.session_id or uuid.uuid4().hex[:10]
    proposal_doc = {
        "proposal_id": proposal_id, "session_id": session_id,
        "task": task, "race": race, "council": enriched,
        "status": "pending_approval",
        "created_at": started.isoformat(),
        "elapsed_s": round((datetime.now(timezone.utc) - started).total_seconds(), 2),
    }
    try:
        await db.console_proposals.insert_one(dict(proposal_doc))
        proposal_doc.pop("_id", None)
    except Exception as e:
        logger.warning(f"[fc-propose] persist failed: {e}")

    return {"ok": True, **proposal_doc}


class ApproveRequest(BaseModel):
    proposal_id: str
    confirm: bool = True


@router.post("/approve")
async def approve(body: ApproveRequest, authorization: Optional[str] = Header(None)):
    """Stage 5: hybrid auto-build (Self-Edit if eligible, else Stub).
    Stage 6: record_learning."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    started = datetime.now(timezone.utc)

    proposal = await db.console_proposals.find_one(
        {"proposal_id": body.proposal_id}, {"_id": 0},
    )
    if not proposal:
        raise HTTPException(404, "proposal not found")
    if proposal.get("status") != "pending_approval":
        raise HTTPException(409, f"proposal already {proposal.get('status')}")

    enriched = proposal["council"]
    task = proposal["task"]
    if not body.confirm:
        await db.console_proposals.update_one(
            {"proposal_id": body.proposal_id},
            {"$set": {"status": "rejected",
                      "rejected_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"ok": True, "status": "rejected"}

    if enriched.get("verdict") != "APPROVED":
        raise HTTPException(409, f"council verdict={enriched.get('verdict')}")

    # ── Stage 5: hybrid path ──
    from services.founders_pipeline import record_learning

    if enriched.get("auto_build_eligible"):
        from services.self_edit_engine import self_edit_apply
        files = (proposal["race"].get("gemini_plan") or {}).get("files") or []
        out = await self_edit_apply(
            prompt=enriched["optimized_prompt"],
            expected_files=files, db=db, dry_run=False,
        )
        build_path = "self_edit"
        outcome = "success" if out.get("ok") else "rolled_back"
        files_changed = out.get("files_changed") or []
    else:
        out = {
            "ok": True, "stage": "stub",
            "instructions": (
                "Paste the optimized prompt into Emergent → "
                "press 'Save to Github' → Deploy."
            ),
            "optimized_prompt": enriched["optimized_prompt"],
            "auto_build_blockers": enriched.get("auto_build_blockers") or [],
        }
        build_path = "stub"
        outcome = "stubbed"
        files_changed = []

    duration_s = round((datetime.now(timezone.utc) - started).total_seconds(), 2)
    learning_id = await record_learning(db, {
        "task_title": task["title"], "raw_input": task["raw_input"],
        "optimized_prompt": enriched["optimized_prompt"],
        "council_verdict": enriched["verdict"], "risk_score": enriched["risk_score"],
        "outcome": outcome, "files_changed": files_changed,
        "duration_seconds": duration_s, "build_path": build_path,
        "build_summary": {"ok": out.get("ok"), "stage": out.get("stage")},
    })

    await db.console_proposals.update_one(
        {"proposal_id": body.proposal_id},
        {"$set": {
            "status": outcome, "approved_at": started.isoformat(),
            "build_path": build_path, "build_result": out,
            "learning_id": learning_id, "duration_s": duration_s,
        }},
    )
    return {
        "ok": out.get("ok") is True, "status": outcome,
        "build_path": build_path, "result": out,
        "learning_id": learning_id, "duration_s": duration_s,
    }


# ═══ Iter 309 — Content Strategy Quick Chips ═══════════════════════════════
@router.get("/chips")
async def list_chips(authorization: Optional[str] = Header(None)):
    """Return chip catalog (id, label, icon, form spec). UI uses this to
    render the chip row + per-chip form."""
    _verify_admin(authorization)
    from services.console_chips import CHIP_TEMPLATES
    return {"chips": [
        {"chip_id": cid, "label": s["label"], "icon": s.get("icon"),
         "category": s.get("category", "content"),
         "needs_form": bool(s.get("needs_form")),
         "form_fields": s.get("form_fields") or []}
        for cid, s in CHIP_TEMPLATES.items()
    ]}


class ChipFireRequest(BaseModel):
    chip_id: str
    inputs: Optional[Dict[str, Any]] = None


@router.post("/chip/fire")
async def fire_chip_endpoint(body: ChipFireRequest,
                              authorization: Optional[str] = Header(None)):
    """Bypass Council — direct ORA call with chip's pre-built prompt."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.console_chips import fire_chip
    return await fire_chip(body.chip_id, body.inputs, db)


# ═══ Iter 310 — MEGA Console / Full Intelligence Scan ═════════════════════
class IntelligenceRequest(BaseModel):
    topic: str
    business_context: Optional[str] = "AUREM"
    goal: Optional[str] = "Revenue"
    urgency: Optional[str] = "This month"


@router.post("/intelligence")
async def intelligence_scan(body: IntelligenceRequest,
                              background_tasks: BackgroundTasks,
                              authorization: Optional[str] = Header(None)):
    """Kick off async 6-lens scan + council. Returns scan_id immediately;
    poll GET /intelligence/{scan_id} for status."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    if not (body.topic or "").strip():
        raise HTTPException(400, "topic required")

    from services.intelligence_scan import (
        prepare_intelligence_stub, run_intelligence_scan_into,
    )
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    stub = await prepare_intelligence_stub(payload, db)
    background_tasks.add_task(run_intelligence_scan_into,
                               stub["scan_id"], payload, db)
    return stub


@router.get("/intelligence/{scan_id}")
async def intelligence_detail(scan_id: str,
                                authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    doc = await db.intelligence_scans.find_one({"scan_id": scan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "not found")
    return doc


@router.post("/monday-brief/send-now")
async def monday_brief_now(count: int = Query(5, ge=1, le=10),
                             authorization: Optional[str] = Header(None)):
    """Force-send the Monday brief to founder. Admin trigger / manual test."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.monday_brief import send_monday_brief_now
    return await send_monday_brief_now(db, count=count)


@router.post("/forecast/send-now")
async def sunday_forecast_now(authorization: Optional[str] = Header(None)):
    """Force-send the Sunday founder forecast. Admin trigger / manual test."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.sunday_forecast import send_forecast_now
    return await send_forecast_now(db)


@router.get("/forecast/campaigns")
async def list_forecast_campaigns(authorization: Optional[str] = Header(None),
                                     limit: int = Query(20, ge=1, le=100)):
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.forecast_campaigns import list_forecast_campaigns as _list
    rows = await _list(db, limit=limit)
    return {"ok": True, "campaigns": rows, "count": len(rows)}


@router.post("/forecast/cancel-campaign")
async def cancel_forecast_campaign(
    body: Dict[str, str],
    authorization: Optional[str] = Header(None),
):
    """Body: {campaign_id}. Cancels an armed campaign before Monday fire."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    cid = (body or {}).get("campaign_id", "").strip()
    if not cid:
        raise HTTPException(400, "campaign_id required")
    from services.forecast_campaigns import cancel_forecast_campaign as _cancel
    out = await _cancel(db, cid)
    if not out.get("ok"):
        raise HTTPException(404, out.get("error", "not_found"))
    return out


@router.post("/forecast/dispatch-now")
async def dispatch_forecast_campaigns(
    authorization: Optional[str] = Header(None),
):
    """Force-fire any armed campaigns whose scheduled time has passed.
    Admin trigger / manual test."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.forecast_campaigns import dispatch_due_forecast_campaigns
    return await dispatch_due_forecast_campaigns(db)


# ─── Iter 315 — Outcome attribution + ORA learning bias ───────────────
@router.get("/forecast/proven-bets")
async def forecast_proven_bets(days: int = Query(30, ge=1, le=180),
                                  limit: int = Query(5, ge=1, le=20),
                                  authorization: Optional[str] = Header(None)):
    """Top-performing bets by revenue per 100 leads (rolling window)."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.attribution import top_performing_bets
    bets = await top_performing_bets(db, days=days, limit=limit)
    return {"ok": True, "days": days, "count": len(bets), "bets": bets}


class AttributeBody(BaseModel):
    lead_id: str
    outcome_type: str  # responded | booked | paid
    revenue_cad: Optional[float] = 0.0
    source_hint: Optional[str] = "manual"


@router.post("/forecast/attribute")
async def attribute_outcome(body: AttributeBody,
                              authorization: Optional[str] = Header(None)):
    """Manual outcome attribution for the founder (e.g. recording a
    booking from Calendly or a phone-call 'paid' that didn't go through
    Stripe webhook). Admin only."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.attribution import attribute_lead_outcome
    out = await attribute_lead_outcome(
        db, body.lead_id, body.outcome_type,
        revenue_cad=body.revenue_cad or 0.0,
        source_hint=body.source_hint or "manual",
    )
    if not out.get("ok"):
        raise HTTPException(400, out.get("error", "attribute failed"))
    return out


# ─── Iter 315b — Post-publish trigger admin endpoints ─────────────────
@router.post("/publish/welcome/{site_id}")
async def trigger_welcome(site_id: str,
                            authorization: Optional[str] = Header(None)):
    """Admin trigger: send the edit-portal welcome email + WhatsApp."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.post_publish_triggers import fire_onboarding_welcome
    return await fire_onboarding_welcome(db, site_id)


@router.post("/publish/upsell/{site_id}")
async def trigger_upsell(site_id: str,
                            authorization: Optional[str] = Header(None)):
    """Admin trigger: send the $29/yr domain upsell email + WhatsApp."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.post_publish_triggers import fire_domain_upsell
    return await fire_domain_upsell(db, site_id)


@router.post("/payment-audit/run")
async def trigger_payment_audit(authorization: Optional[str] = Header(None)):
    """Admin: run the payment funnel audit on-demand.
    Reconciles pending Stripe checkouts, recovers silent payments, flags
    48h+ abandoned orders. Persists to db.payment_audits."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.payment_funnel_audit import run_payment_audit
    return await run_payment_audit(db)


@router.get("/payment-audit/recent")
async def recent_payment_audits(limit: int = Query(10, ge=1, le=50),
                                  authorization: Optional[str] = Header(None)):
    """Admin: last N payment-audit runs."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    cur = db.payment_audits.find(
        {}, {"_id": 0}
    ).sort("started_at", -1).limit(limit)
    rows = await cur.to_list(limit)
    return {"ok": True, "count": len(rows), "audits": rows}


@router.post("/publish/edit-followup/{request_id}")
async def trigger_edit_followup(request_id: str,
                                  authorization: Optional[str] = Header(None)):
    """Admin trigger: fire the 24h edit-link follow-up nudge for a single
    edit_sessions request_id (manual override / tests)."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.post_publish_triggers import fire_edit_followup
    return await fire_edit_followup(db, request_id)


@router.get("/nps/summary")
async def nps_summary(days: int = Query(7, ge=1, le=90),
                        authorization: Optional[str] = Header(None)):
    """Admin: NPS rolling summary (responses, avg score, detractor list)."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cur = db.nps_responses.find(
        {"created_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("created_at", -1).limit(500)
    rows = await cur.to_list(500)
    total = len(rows)
    avg = (sum(r.get("score", 0) for r in rows) / total) if total else 0.0
    detractors = [r for r in rows if r.get("score", 0) <= 3]
    promoters = [r for r in rows if r.get("score", 0) >= 5]
    return {
        "ok": True, "window_days": days,
        "total": total, "avg_score": round(avg, 2),
        "detractor_count": len(detractors),
        "promoter_count": len(promoters),
        "detractors": detractors[:20],
        "recent": rows[:20],
    }


@router.get("/proposal/{proposal_id}")
async def proposal_detail(proposal_id: str,
                           authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    p = await db.console_proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "not found")
    return p


@router.get("/learnings")
async def learnings(limit: int = Query(20, ge=1, le=100),
                     authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        return {"learnings": []}
    from services.founders_pipeline import recent_learnings
    docs = await recent_learnings(db, limit)
    return {"learnings": docs, "count": len(docs)}
