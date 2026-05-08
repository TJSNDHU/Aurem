"""
Public ORA Demo Chat (iter 281.7)
====================================
Lightweight, snappy demo chat for the public homepage at /. Uses a single
Claude Sonnet call with a tight system prompt — bypasses the heavy
ULTRAPLINIAN multi-model race + memory + NBA pipeline that the admin
`/api/ora/command` runs.

Target latency: ~1.5-3s (vs ~10s for the full pipeline).

NO auth. Rate limiting handled at middleware. Stateless — no session
memory, no language localizer (Claude follows whatever language it's
addressed in naturally).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public/ora", tags=["Public ORA Demo Chat"])

_db = None


def set_db(db):
    global _db
    _db = db


_DEMO_SYSTEM = (
    "You are ORA, the AI employee built into AUREM — Canada's first "
    "autonomous business intelligence platform. You are speaking with a "
    "small business owner who landed on the public homepage and is "
    "trying you out. Stay concise: 2-4 sentences max. Be warm, direct, "
    "no jargon. Mirror the user's language exactly (English/French/"
    "Hindi/Punjabi/etc.). If they ask about pricing: Starter $97 CAD, "
    "Growth $449 CAD, Enterprise $997 CAD — 14-day free trial, no card "
    "needed. If they describe a service business need (plumbing, "
    "cleaning, etc.), demo what you'd do for that business: answer "
    "calls, qualify leads, book appointments, follow up. End with a "
    "soft nudge to scan their website at /repair-quote when relevant. "
    "Never say 'I cannot' — always offer a path."
)


class DemoChatReq(BaseModel):
    text: str = Field(..., min_length=1, max_length=600)
    session_id: Optional[str] = None
    source: Optional[str] = None   # "dev" → route through ORA dev skills
    # iter 282al-14 — Optional client-side emotion (face-api.js). The
    # video stream NEVER leaves the browser; only the label is sent.
    emotion: Optional[str] = Field(default=None, max_length=20)
    emotion_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


# ── Emotion → tone-adjustment context (iter 282al-14) ───────────────
_EMOTION_TONE = {
    "happy":     "The user looks happy. Match their warmth — keep replies upbeat and concise.",
    "sad":       "The user looks down. Open with one short empathetic line, then help. Avoid hype.",
    "angry":     "The user looks frustrated. Acknowledge the friction in one sentence, then give a clear next step. No fluff.",
    "fearful":   "The user looks anxious. Reassure briefly (you're safe, no card needed), then answer plainly.",
    "disgusted": "The user looks put off. Skip the sales tone — give a direct, factual answer.",
    "surprised": "The user looks surprised. Confirm what they're seeing in one line, then guide.",
    "neutral":   "The user looks focused. Stay crisp and useful — no emotional padding.",
}


def _emotion_context(emo: Optional[str], conf: Optional[float]) -> str:
    if not emo:
        return ""
    label = (emo or "").strip().lower()
    line = _EMOTION_TONE.get(label)
    if not line:
        return ""
    pct = f"{int(round((conf or 0) * 100))}%" if conf else "—"
    return (
        "\n\nLIVE EMOTION SIGNAL (from user's webcam, processed in-browser, "
        f"never uploaded): {label} ({pct} confidence). {line}"
    )


# ── User context hydration (iter 282n / Fix 7) ──────────────────────
async def _resolve_user_context(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    """If Bearer token decodes, return logged-in user identity. Else None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token or _db is None:
        return None
    try:
        import jwt  # type: ignore
        secret = os.environ.get("JWT_SECRET", "")
        if not secret:
            return None
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        return None
    email = payload.get("email") or payload.get("sub")
    user_id = payload.get("user_id")
    role = payload.get("role")

    # Try by email (customer / platform_users), then user_id (admin / users)
    user = None
    if email:
        user = await _db.platform_users.find_one(
            {"email": email},
            {"_id": 0, "email": 1, "first_name": 1, "business_name": 1,
             "bin": 1, "plan_label": 1, "plan": 1, "role": 1},
        )
    if user:
        return {
            "name": user.get("first_name") or user.get("business_name") or (email or "").split("@")[0],
            "email": user.get("email"),
            "bin": user.get("bin"),
            "business_name": user.get("business_name"),
            "plan": user.get("plan_label") or user.get("plan") or "Free",
            "role": user.get("role") or role or "user",
            "is_admin": (user.get("role") in ("admin", "super_admin"))
                        or (role in ("admin", "super_admin")),
        }
    # Admin / customer fallback lookup in `users` collection.
    #
    # SECURITY (P0 fix): the `users` collection holds BOTH admins and
    # customers in production. The previous code blindly marked anyone
    # found here as `is_admin=True` with `bin="AURE-ADMIN"` and
    # `plan="Founder"` — that was a real privacy leak (customers saw
    # platform-wide lead counts in ORA chat). Now we read the actual
    # role + business_id off the doc.
    admin_q = {}
    if user_id:
        admin_q = {"$or": [{"user_id": user_id}, {"id": user_id}]}
    elif email:
        admin_q = {"email": email}
    if admin_q:
        u_doc = await _db.users.find_one(
            admin_q,
            {"_id": 0, "email": 1, "name": 1, "first_name": 1, "last_name": 1,
             "role": 1, "user_id": 1, "business_id": 1, "business_name": 1,
             "is_admin": 1, "is_super_admin": 1, "plan": 1, "plan_label": 1},
        )
        if u_doc:
            doc_role = u_doc.get("role") or role or "user"
            doc_is_admin = bool(
                u_doc.get("is_admin")
                or u_doc.get("is_super_admin")
                or doc_role in ("admin", "super_admin")
                or role in ("admin", "super_admin")
            )
            display_name = (
                u_doc.get("name")
                or u_doc.get("first_name")
                or (u_doc.get("email") or "").split("@")[0]
                or "User"
            )
            if doc_is_admin:
                return {
                    "name": display_name,
                    "email": u_doc.get("email") or email,
                    "bin": u_doc.get("business_id") or "AURE-ADMIN",
                    "business_name": u_doc.get("business_name") or "AUREM (Founder)",
                    "plan": u_doc.get("plan_label") or u_doc.get("plan") or "Founder",
                    "role": doc_role,
                    "is_admin": True,
                }
            # Customer found in `users` collection — return CUSTOMER context,
            # NOT admin context. is_admin must be False so live-data injection
            # scopes to THIS customer's BIN only.
            return {
                "name": display_name,
                "email": u_doc.get("email") or email,
                "bin": u_doc.get("business_id"),
                "business_name": u_doc.get("business_name") or "Your Business",
                "plan": u_doc.get("plan_label") or u_doc.get("plan") or "Trial",
                "role": doc_role,
                "is_admin": False,
            }
    return None


def _personalised_system(user: Optional[Dict[str, Any]]) -> str:
    if not user:
        return _DEMO_SYSTEM
    bin_ = user.get("bin") or "(not set)"
    trial_str = ""
    try:
        if user.get("trial_ends_at"):
            from datetime import datetime as _dt, timezone as _tz
            end = _dt.fromisoformat(str(user["trial_ends_at"]).replace("Z", "+00:00"))
            days = max(0, int((end - _dt.now(_tz.utc)).total_seconds() // 86400))
            trial_str = f"\n  Trial days left: {days}"
    except Exception:
        pass
    return _DEMO_SYSTEM + (
        f"\n\nLOGGED-IN USER CONTEXT (use this to answer who/BIN/admin/lead questions):\n"
        f"  Name: {user.get('name')}\n"
        f"  Business: {user.get('business_name') or '—'}\n"
        f"  BIN: {bin_}\n"
        f"  Plan: {user.get('plan')}\n"
        f"  Email: {user.get('email')}\n"
        f"  Role: {user.get('role')}\n"
        f"  Admin: {'Yes — full admin access' if user.get('is_admin') else 'No'}"
        f"{trial_str}\n"
        f"\nWhen the user asks about leads, revenue, or signups: if they are admin, "
        f"answer with platform-wide totals from the daily verification log; if they "
        f"are a customer, answer ONLY with their own BIN's data (their reviews, "
        f"their site, their subscription). Never quote platform totals to a customer."
    )


async def _live_business_context(user: Optional[Dict[str, Any]]) -> str:
    """Pull a snapshot of real DB metrics for the logged-in user and return
    it as a system-prompt block. Without this block, ORA fabricates demo
    answers like 'I don't have access to your data yet'.

    Admin → platform-wide totals. Customer → only their BIN's data.
    Best-effort: any DB error returns "" (LLM falls back to generic answer).
    """
    if not user or _db is None:
        return ""
    try:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        since_24h = now - timedelta(days=1)
        is_admin = bool(user.get("is_admin"))
        bid = user.get("bin")

        # ── Admin: platform-wide totals ─────────────────────────
        if is_admin:
            (leads_total, leads_24h, customers, msgs_unanswered,
             invoices_outstanding, invoices_at_risk) = await asyncio.gather(
                _db.leads.count_documents({}),
                _db.leads.count_documents(
                    {"created_at": {"$gte": since_24h.isoformat()}}
                ),
                _db.platform_users.count_documents(
                    {"business_id": {"$exists": True}}
                ),
                _db.aurem_messages.count_documents({"status": "unanswered"}),
                _db.aurem_invoices.count_documents({"status": "outstanding"}),
                _db.aurem_invoices.count_documents({"status": "at_risk"}),
                return_exceptions=True,
            )
            health = await _db.customer_health_summary.find_one(
                {"_id": "latest"}, {"_id": 0, "counts": 1}
            )
            counts = (health or {}).get("counts", {}) or {}

            def _safe(v):
                return v if isinstance(v, int) else 0

            return (
                "\n\nLIVE BUSINESS DATA (authoritative — use these numbers, "
                "do not invent):\n"
                f"  Leads total: {_safe(leads_total)} ({_safe(leads_24h)} added in last 24h)\n"
                f"  Active customers (with BIN): {_safe(customers)}\n"
                f"  Customer health: {counts.get('healthy',0)} healthy, "
                f"{counts.get('degraded',0)} degraded, "
                f"{counts.get('critical',0)} critical\n"
                f"  Unanswered messages: {_safe(msgs_unanswered)}\n"
                f"  Outstanding invoices: {_safe(invoices_outstanding)}\n"
                f"  At-risk invoices: {_safe(invoices_at_risk)}\n"
            )

        # ── Customer: only their BIN's data ─────────────────────
        if not bid:
            return ""
        (my_leads, my_invoices, my_health) = await asyncio.gather(
            _db.leads.count_documents({"business_id": bid}),
            _db.aurem_invoices.count_documents(
                {"business_id": bid, "status": "outstanding"}
            ),
            _db.customer_health_log.find_one(
                {"business_id": bid}, {"_id": 0, "status": 1, "failed": 1}
            ),
            return_exceptions=True,
        )

        def _safe(v):
            return v if isinstance(v, int) else 0

        h_status = "unknown"
        if isinstance(my_health, dict):
            h_status = my_health.get("status") or "unknown"
        return (
            "\n\nLIVE BUSINESS DATA for this customer (authoritative):\n"
            f"  My leads: {_safe(my_leads)}\n"
            f"  My outstanding invoices: {_safe(my_invoices)}\n"
            f"  My account health: {h_status}\n"
        )
    except Exception as e:
        logger.debug(f"[public-ora-demo] live context fetch failed: {e}")
        return ""


@router.get("/health")
async def health():
    return {"ok": True}


@router.post("/chat")
async def public_demo_chat(
    req: DemoChatReq,
    authorization: Optional[str] = Header(None),
):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Empty message")

    # ─── FAST-PATH SHORT-CIRCUIT (P0 fix — date hallucination + latency) ──
    # Trivial deterministic queries (today's date, time, leads count,
    # customer health) bypass the LLM entirely — answer from wall-clock /
    # live DB in <50 ms. Authoritative; cannot hallucinate.
    try:
        from services.ora_fast_cache import try_short_circuit
        _fast = await try_short_circuit(text)
        if _fast is not None:
            return {
                "ok":            True,
                "reply":         _fast,
                "authenticated": False,
                "llm_source":    "ora_fast_cache",
            }
    except Exception as _fce:
        logger.debug(f"[public-ora-demo] fast-cache skipped: {_fce}")

    # iter 282al-2 — /ora-dev mode. When `source="dev"` or the message
    # starts with "/dev ", route through ORA's dev skill pipeline with
    # AUREM codebase context injected.
    _is_dev = (
        (req.source or "").lower() == "dev"
        or text.lstrip().lower().startswith("/dev ")
    )
    if _is_dev:
        try:
            from services.skill_router import (
                detect_dev_intent, execute_skill, DEV_SKILLS,
            )
            _msg = text.lstrip()
            if _msg.lower().startswith("/dev "):
                _msg = _msg[5:].lstrip()
            _skill = detect_dev_intent(_msg) or "dev_senior-fullstack"
            if _skill not in DEV_SKILLS:
                _skill = "dev_senior-fullstack"
            _reply = await execute_skill(_skill, _msg, None, {})
            return {
                "ok":            True,
                "reply":         _reply,
                "authenticated": False,
                "llm_source":    "dev_mode",
                "skill":         _skill,
            }
        except Exception as e:
            logger.warning(f"[public-ora-demo] dev mode failed: {e}")
            # Fall through to regular LLM chat on failure.

    user = await _resolve_user_context(authorization)
    sys_prompt = _personalised_system(user)
    # ── LIVE DB CONTEXT INJECTION (P0 fix — was hallucinating "I don't
    # have access to your data yet" because the LLM had no real numbers).
    # Now every authenticated request gets a snapshot of leads / customers /
    # invoices / health right in the system prompt. Best-effort; "" on err.
    sys_prompt = sys_prompt + await _live_business_context(user)
    # iter 282al-14 — Append emotion-aware tone hint when supplied
    sys_prompt = sys_prompt + _emotion_context(req.emotion, req.emotion_confidence)
    # ── REAL-TIME DATE (P0 fix — was hallucinating "January 22, 2025") ──
    # Prepend authoritative date block so Claude can never drift to
    # training cutoff. Single source of truth: services.ora_date_helper.
    try:
        from services.ora_date_helper import prepend_date
        sys_prompt = prepend_date(sys_prompt)
    except Exception:
        pass
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=req.session_id or f"demo_{uuid.uuid4()}",
            system_message=sys_prompt,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        out = (await chat.send_message(UserMessage(text=text))).strip()
        if not out:
            out = "I'm here — tell me what your business does and I'll show you what I can do."
        return {"ok": True, "reply": out, "authenticated": bool(user)}
    except Exception as e:
        logger.warning(f"[public-ora-demo] LLM call failed: {e}")
        # Graceful canned reply — keeps the homepage demo from looking dead.
        # When user is authenticated, answer identity questions deterministically.
        t = text.lower()
        if user and any(k in t for k in ("my bin", "what bin", "is admin", "am i admin", "who am i")):
            admin_status = "full admin access" if user.get("is_admin") else f"on the {user.get('plan')} plan"
            return {"ok": True, "reply": (
                f"You're {user.get('name')} ({user.get('business_name') or 'AUREM customer'}). "
                f"Your BIN is {user.get('bin') or 'not set'}. You have {admin_status}."
            ), "authenticated": True}
        return {
            "ok": False,
            "reply": (
                "I'm warming up — try again in a few seconds. "
                "Meanwhile, scan your website free at /repair-quote — "
                "it takes 60 seconds and shows you exactly what's costing you leads."
            ),
            "authenticated": bool(user),
        }
