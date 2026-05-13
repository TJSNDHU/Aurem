"""
Public ORA Demo Chat (iter 281.7 · 322bn)
=========================================
Lightweight, snappy demo chat for the public homepage at /. Uses a single
Claude Sonnet call with a tight system prompt — bypasses the heavy
ULTRAPLINIAN multi-model race + memory + NBA pipeline that the admin
`/api/ora/command` runs.

Target latency: ~1.5-3s (vs ~10s for the full pipeline).

iter 322bn — Founder Priority Override:
  BUG 1 (hallucination) — see services/ora_fast_cache._ans_bin_lookup. ANY
    BIN code in the message hits MongoDB directly with no LLM inference.
  BUG 2 (context loss) — last 10 messages per session_id stored in
    db.ora_sessions and replayed on every turn.
  BUG 3 (warmup error) — Claude failure now silently falls back to Groq
    instead of showing "I'm warming up". Zero user-facing warmup message.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
    # iter 322bp — raised 600 → 8000 so pasted content (snippets, errors,
    # JSON, emails) doesn't get silently rejected with 422 = empty body =
    # frontend one-liner fallback. 8000 covers ~1500 words / 2-page paste.
    text: str = Field(..., min_length=1, max_length=8000)
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

    # iter 322bq — FOUNDER SAVE / HARD-SAVE PROTOCOL.
    # When the caller is authenticated, replace the public-demo prompt with
    # an authenticated-mode prompt. ORA must NEVER ask "what kind of
    # business do you run" — that information is already in DB. ORA must
    # OBEY Founder Save commands without re-asking for confirmation.
    name = user.get("name") or "the founder"
    biz = user.get("business_name") or "their business"
    plan = user.get("plan") or "Trial"
    role_str = "AUREM Founder/Admin" if user.get("is_admin") else "AUREM customer"
    admin_block = ""
    if user.get("is_admin"):
        admin_block = (
            "\n\nFOUNDER-SAVE / HARD-SAVE PROTOCOL (this user is an AUREM Founder):\n"
            "  • When the founder issues a command, OBEY it. Do NOT ask for "
            "    re-confirmation. Do NOT re-explain the consequences.\n"
            "  • You have full read access to db.users, db.platform_users, "
            "    db.campaign_leads, db.invoices, db.customer_health_log, "
            "    db.aurem_pixel, db.repair_log, db.truth_ledger.\n"
            "  • For ANY question about a specific BIN, look it up directly "
            "    (the fast-cache short-circuit handles this). Never guess.\n"
            "  • You can execute admin actions: enable pixel, run scan, "
            "    pause/resume agent, push deploy. Reply with a concise "
            "    confirmation of what you did and the affected rows count.\n"
            "  • Treat 'Founder Save', 'Founder Override', 'Hard Save' as "
            "    equivalent: bypass the Council approval queue and ship.\n"
        )
    return (
        f"You are ORA, the autonomous orchestration brain of AUREM.\n"
        f"You are speaking with **{name}** from **{biz}** "
        f"(BIN: {bin_}, role: {role_str}, plan: {plan}).{trial_str}\n\n"
        f"RULES — NEVER VIOLATE:\n"
        f"  1. NEVER ask 'what kind of business do you run' or 'tell me about "
        f"     your business' — you already know. The user is {name} at {biz}.\n"
        f"  2. NEVER ask for their BIN — it is {bin_}.\n"
        f"  3. NEVER greet them like a stranger. They are already a customer "
        f"     (or the founder) — get straight to the answer.\n"
        f"  4. When they ask about leads, revenue, scans, or repairs: pull "
        f"     from the data block injected below. Never make up numbers.\n"
        f"  5. Keep replies tight: 2-4 sentences for routine questions, "
        f"     longer only when they ask for analysis or a plan.\n"
        f"  6. Speak Hinglish if they speak Hinglish. English if English. "
        f"     Mirror their tone — formal vs casual.\n"
        f"  7. Pasted content (errors, JSON, emails, snippets) — READ IT. "
        f"     Reference specific lines/values. Never reply 'tell me what "
        f"     you want' to a paste.\n"
        f"{admin_block}"
    )


# ── iter 322bn — Conversation memory (BUG 2 fix) ──────────────────
# Last 10 (user, assistant) turns persisted in db.ora_sessions per
# session_id + BIN. Loaded on every new message → ORA never asks "who are
# you" if the user told it 3 turns ago.

async def _load_history(session_id: str, bin_: Optional[str], limit: int = 10) -> List[Dict[str, str]]:
    if _db is None or not session_id:
        return []
    try:
        key = f"{session_id}:{(bin_ or 'anon').upper()}"
        doc = await _db.ora_sessions.find_one(
            {"key": key}, {"_id": 0, "turns": 1},
        )
        if not doc:
            return []
        return (doc.get("turns") or [])[-limit:]
    except Exception as e:
        logger.debug(f"[public-ora-demo] history load failed: {e}")
        return []


async def _save_turn(session_id: str, bin_: Optional[str], user_text: str, ora_text: str) -> None:
    if _db is None or not session_id or not user_text or not ora_text:
        return
    try:
        key = f"{session_id}:{(bin_ or 'anon').upper()}"
        now = datetime.now(timezone.utc).isoformat()
        await _db.ora_sessions.update_one(
            {"key": key},
            {
                "$set": {"key": key, "session_id": session_id, "bin": bin_ or None, "updated_at": now},
                "$setOnInsert": {"created_at": now},
                "$push": {
                    "turns": {
                        "$each": [
                            {"role": "user", "text": user_text[:1200], "ts": now},
                            {"role": "assistant", "text": ora_text[:1800], "ts": now},
                        ],
                        # Keep only the last 20 entries (10 turns ≈ user+assistant pairs)
                        "$slice": -20,
                    }
                },
            },
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[public-ora-demo] history save failed: {e}")


def _history_block(turns: List[Dict[str, str]]) -> str:
    if not turns:
        return ""
    lines = ["\n\nPREVIOUS CONVERSATION (use this — do NOT ask the user to repeat themselves):"]
    for t in turns:
        role = (t.get("role") or "").upper()
        text = (t.get("text") or "").strip()[:400]
        if text:
            lines.append(f"  {role}: {text}")
    return "\n".join(lines)


# ── iter 322br — Persistent Groq HTTP client (pre-warm) ────────────
# A single AsyncClient kept open for the process lifetime so TCP+TLS
# handshake (80-120ms) happens once at boot, not on every request.
# Idle pings keep the keep-alive socket warm.

_GROQ_CLIENT: Optional[Any] = None


def _get_groq_client():
    global _GROQ_CLIENT
    if _GROQ_CLIENT is None:
        import httpx
        _GROQ_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=4.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10,
                                keepalive_expiry=120.0),
            # http2 needs the 'h2' wheel; HTTP/1.1 keep-alive is plenty for our QPS
            headers={
                "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY','')}",
                "Content-Type":  "application/json",
                "User-Agent":    "AUREM-ORA/322br",
            },
        )
    return _GROQ_CLIENT


async def prewarm_groq():
    """Touch Groq once at startup so the first user request is hot."""
    if not os.environ.get("GROQ_API_KEY", "").strip():
        return
    try:
        c = _get_groq_client()
        await c.get("https://api.groq.com/openai/v1/models", timeout=5.0)
        logger.info("[public-ora-demo] Groq pre-warmed ✓")
    except Exception as e:
        logger.debug(f"[public-ora-demo] Groq pre-warm skipped: {e}")


# ── iter 322br — RAM cache with TTL (no Redis, multi-pod safe) ─────
# Per-process LRU-ish dict. TTL'd entries; Mongo remains source-of-truth.
# Pod restart → rebuilt lazily. Pod 1 vs Pod 2 may briefly disagree for
# up to TTL_S seconds — acceptable for hot-path settings.

_RAM_CACHE: Dict[str, Dict[str, Any]] = {}
_RAM_CACHE_TTL_S = float(os.environ.get("ORA_RAM_CACHE_TTL", "30"))


async def cache_get_or_fetch(key: str, fetch_coro_fn) -> Any:
    """Read RAM cache; on miss/stale, await `fetch_coro_fn()` once and store."""
    import time as _t
    now = _t.time()
    hit = _RAM_CACHE.get(key)
    if hit and (now - hit["t"]) < _RAM_CACHE_TTL_S:
        return hit["v"]
    val = await fetch_coro_fn()
    _RAM_CACHE[key] = {"v": val, "t": now}
    # Bound the cache size (LRU-ish: drop oldest 25% when >1000)
    if len(_RAM_CACHE) > 1000:
        oldest = sorted(_RAM_CACHE.items(), key=lambda kv: kv[1]["t"])[:250]
        for k, _ in oldest:
            _RAM_CACHE.pop(k, None)
    return val


# iter 322br — Groq with persistent client + temp 0.3 (was 0.4)
async def _groq_fallback(messages: List[Dict[str, str]]) -> Optional[str]:
    """Try Groq with the chat messages. Returns reply text or None."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        client = _get_groq_client()
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                "messages": messages,
                "temperature": float(os.environ.get("ORA_GROQ_TEMP", "0.3")),
                "max_tokens": 700,
            },
        )
        if resp.status_code != 200:
            logger.debug(f"[public-ora-demo] groq {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        out = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        return out or None
    except Exception as e:
        logger.debug(f"[public-ora-demo] groq error: {e}")
        return None


# iter 322br — Streaming Groq generator (SSE)
async def _groq_stream(messages: List[Dict[str, str]]):
    """Yield text tokens as Groq generates them. Each yield is a partial
    string suitable for SSE 'data:' lines. Yields '' at end to signal done."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return
    try:
        import json as _json
        client = _get_groq_client()
        async with client.stream(
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                "messages": messages,
                "temperature": float(os.environ.get("ORA_GROQ_TEMP", "0.3")),
                "max_tokens": 700,
                "stream": True,
            },
            timeout=20.0,
        ) as resp:
            if resp.status_code != 200:
                logger.debug(f"[public-ora-demo] groq stream {resp.status_code}")
                return
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = _json.loads(payload)
                    delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                    token = delta.get("content") or ""
                    if token:
                        yield token
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"[public-ora-demo] groq stream error: {e}")


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


# iter 322br — Streaming SSE chat. Tokens stream from Groq → frontend as
# they're generated. TTFB ~80ms instead of waiting for full reply.
@router.post("/chat/stream")
async def public_demo_chat_stream(
    req: DemoChatReq,
    authorization: Optional[str] = Header(None),
):
    """SSE chat — yields 'data: <token>\\n\\n' frames as Groq generates.
    Final frame: 'event: done\\ndata: {json metadata}\\n\\n'."""
    from fastapi.responses import StreamingResponse
    import time as _time
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "Empty message")

    user = await _resolve_user_context(authorization)

    # Same fast-cache path as non-stream — instant deterministic answers
    try:
        from services.ora_fast_cache import try_short_circuit
        fast = await try_short_circuit(text, user=user)
        if fast is not None:
            async def _fast_gen():
                # emit the whole answer in 4-char chunks so frontend still
                # feels typing animation
                for i in range(0, len(fast), 6):
                    yield f"data: {json_dumps(fast[i:i+6])}\n\n"
                    await asyncio.sleep(0.012)
                yield f"event: done\ndata: {json_dumps({'src': 'ora_fast_cache'})}\n\n"
            return StreamingResponse(_fast_gen(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache, no-transform",
                                              "X-Accel-Buffering": "no"})
    except Exception as _e:
        logger.debug(f"[stream] fast-cache skipped: {_e}")

    sys_prompt = _personalised_system(user) + await _live_business_context(user) + _emotion_context(req.emotion, req.emotion_confidence)
    try:
        from services.ora_date_helper import prepend_date
        sys_prompt = prepend_date(sys_prompt)
    except Exception:
        pass
    # Live skill broadcast — admin can push Antigravity skills to every agent
    # via /api/admin/antigravity-skills/broadcast. ORA picks them up here.
    try:
        from services.agent_skill_broadcast import get_addendum
        _ad = await get_addendum(_db, agent_name="ORA")
        if _ad:
            sys_prompt += _ad
    except Exception:
        pass
    sid = req.session_id or f"demo_{uuid.uuid4()}"
    bin_for_session = (user or {}).get("bin")
    history = await _load_history(sid, bin_for_session, limit=10)
    sys_prompt += _history_block(history)

    messages = [{"role": "system", "content": sys_prompt}]
    for t in history[-6:]:
        messages.append({
            "role": "user" if t.get("role") == "user" else "assistant",
            "content": t.get("text", ""),
        })
    messages.append({"role": "user", "content": text})

    async def _gen():
        t0 = _time.monotonic()
        collected: List[str] = []
        try:
            async for token in _groq_stream(messages):
                collected.append(token)
                yield f"data: {json_dumps(token)}\n\n"
        except Exception as e:
            logger.warning(f"[stream] error: {e}")

        full = "".join(collected).strip()
        if not full:
            # Fallback to non-stream (Claude path) if Groq failed mid-stream
            full = await _groq_fallback(messages) or ""
            if full:
                # send remaining as one chunk
                yield f"data: {json_dumps(full)}\n\n"
        if not full:
            full = "One sec — connection blinked. Try once more."
            yield f"data: {json_dumps(full)}\n\n"

        # Persist + metrics (non-blocking)
        asyncio.create_task(_save_turn(sid, bin_for_session, text, full))
        # Memoir mirror — Git-versioned turn history (audit trail FREE).
        try:
            from services import memoir_service as _M
            if _M.available():
                _M.ora_remember_turn(sid, "user", text)
                _M.ora_remember_turn(sid, "assistant", full)
        except Exception:
            pass
        total_ms = int((_time.monotonic() - t0) * 1000)
        try:
            if _db is not None:
                asyncio.create_task(_db.ora_chat_metrics.insert_one({
                    "session_id": sid, "bin": bin_for_session,
                    "authenticated": bool(user), "llm_source": "groq_stream",
                    "total_ms": total_ms, "claude_ms": 0, "groq_ms": total_ms,
                    "reply_len": len(full), "history_size": len(history),
                    "ts": datetime.now(timezone.utc),
                }))
        except Exception:
            pass

        yield f"event: done\ndata: {json_dumps({'src': 'groq_stream', 'lat_ms': total_ms, 'session_id': sid})}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform",
                                      "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


def json_dumps(o):
    import json as _j
    return _j.dumps(o, ensure_ascii=False)


# iter 322bo — Latency & speed dashboard for ORA chat.
@router.get("/metrics/summary")
async def metrics_summary(window_min: int = 60):
    """Return aggregated ORA chat performance over the last `window_min`
    minutes: p50/p95/p99 latency, requests/min, fallback rates, source mix.
    """
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    from datetime import timedelta as _td
    since = datetime.now(timezone.utc) - _td(minutes=max(1, int(window_min)))
    cursor = _db.ora_chat_metrics.find(
        {"ts": {"$gte": since}},
        {"_id": 0, "total_ms": 1, "claude_ms": 1, "groq_ms": 1,
         "llm_source": 1, "authenticated": 1, "ts": 1, "reply_len": 1},
    ).sort("ts", -1).limit(2000)
    rows = await cursor.to_list(length=2000)

    def _pct(values, p):
        if not values:
            return 0
        vs = sorted(values)
        k = max(0, min(len(vs) - 1, int(round((p / 100.0) * (len(vs) - 1)))))
        return vs[k]

    by_source: Dict[str, List[int]] = {}
    for r in rows:
        by_source.setdefault(r.get("llm_source") or "unknown", []).append(int(r.get("total_ms") or 0))

    total_latencies = [int(r.get("total_ms") or 0) for r in rows]
    claude_lat = [int(r.get("claude_ms") or 0) for r in rows if r.get("claude_ms")]
    groq_lat = [int(r.get("groq_ms") or 0) for r in rows if r.get("groq_ms")]

    return {
        "window_min": window_min,
        "total_requests": len(rows),
        "rps_avg": round(len(rows) / max(1, window_min * 60), 3),
        "latency_ms": {
            "p50": _pct(total_latencies, 50),
            "p95": _pct(total_latencies, 95),
            "p99": _pct(total_latencies, 99),
            "avg": int(sum(total_latencies) / len(total_latencies)) if total_latencies else 0,
            "max": max(total_latencies) if total_latencies else 0,
        },
        "claude": {
            "calls": len(claude_lat),
            "p50": _pct(claude_lat, 50),
            "p95": _pct(claude_lat, 95),
            "avg": int(sum(claude_lat) / len(claude_lat)) if claude_lat else 0,
        },
        "groq": {
            "calls": len(groq_lat),
            "p50": _pct(groq_lat, 50),
            "p95": _pct(groq_lat, 95),
            "avg": int(sum(groq_lat) / len(groq_lat)) if groq_lat else 0,
        },
        "by_source": {
            k: {
                "calls": len(v),
                "share_pct": round((len(v) / len(rows)) * 100, 1) if rows else 0,
                "avg_ms": int(sum(v) / len(v)) if v else 0,
            } for k, v in by_source.items()
        },
        "claude_timeout_threshold_ms": int(float(os.environ.get("ORA_CLAUDE_TIMEOUT_S", "6.0")) * 1000),
        "groq_configured": bool(os.environ.get("GROQ_API_KEY", "").strip()),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


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
    # iter 322bq — also handles founder pixel-state ground-truth.
    _ora_user = await _resolve_user_context(authorization)
    try:
        from services.ora_fast_cache import try_short_circuit
        _fast = await try_short_circuit(text, user=_ora_user)
        if _fast is not None:
            return {
                "ok":            True,
                "reply":         _fast,
                "authenticated": bool(_ora_user),
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

    user = _ora_user  # iter 322bq — reuse resolution from fast-cache step
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

    # iter 322bn — BUG 2: load last 10 turns from db.ora_sessions so ORA
    # remembers what the user said earlier in the conversation.
    sid = req.session_id or f"demo_{uuid.uuid4()}"
    bin_for_session = (user or {}).get("bin")
    history = await _load_history(sid, bin_for_session, limit=10)
    sys_prompt = sys_prompt + _history_block(history)

    # iter 322bo — Speed-first routing. Groq is 5-10x faster than Claude
    # (~500-1000ms vs 4-8s). Use it as PRIMARY for chat. Fall back to
    # Claude only if Groq is unreachable. Set ORA_PROVIDER_ORDER=claude,groq
    # in env to flip the priority if needed.
    import time as _time
    t_started = _time.monotonic()
    out: Optional[str] = None
    llm_source = "groq"
    claude_ms = 0
    groq_ms = 0

    order = (os.environ.get("ORA_PROVIDER_ORDER", "claude,groq")
             .lower().replace(" ", "").split(","))

    async def _try_claude() -> Optional[str]:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
                session_id=sid,
                system_message=sys_prompt,
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            return (await chat.send_message(UserMessage(text=text))).strip() or None
        except Exception as e:
            logger.warning(f"[public-ora-demo] Claude failed: {type(e).__name__}")
            return None

    async def _try_groq() -> Optional[str]:
        groq_messages = [{"role": "system", "content": sys_prompt}]
        for t in history[-6:]:
            groq_messages.append({
                "role": "user" if t.get("role") == "user" else "assistant",
                "content": t.get("text", ""),
            })
        groq_messages.append({"role": "user", "content": text})
        return await _groq_fallback(groq_messages)

    # iter 322fe — Auto tool-calling for authenticated founder/admin chats.
    # Public visitors stay on the plain LLM path (token cost guard). When
    # the user is authenticated (admin or paying customer), ORA gets the
    # 11 read-only tools (view_file, grep, curl_internal, db_count, git_log,
    # health_check, lint_python, shell_exec, view_dir, db_distinct, and the
    # all-important claim_build_done anti-hallucination receipt).
    _tool_audit: List[Dict[str, Any]] = []

    async def _try_groq_with_tools() -> Optional[str]:
        try:
            from services.ora_chat_tools import groq_chat_with_tools
        except Exception as _ie:
            logger.debug(f"[public-ora-demo] ora_chat_tools import failed: {_ie}")
            return None
        # Augment system prompt with the tool-use directive ONCE here so
        # we don't bloat the default prompt for unauthenticated visitors.
        sys_for_tools = sys_prompt + (
            "\n\nTOOL-USE DIRECTIVE (iter 322fe): You have these REAL tools "
            "available — view_file, view_dir, grep_codebase, curl_internal, "
            "db_count, db_distinct, git_log, health_check, lint_python, "
            "shell_exec, claim_build_done. Use them whenever you need to "
            "VERIFY a claim before answering. NEVER fabricate file paths, "
            "ls/stat output, curl responses, byte counts, or timestamps — "
            "call the appropriate tool and quote the real result. Before "
            "any 'I built X / shipped Y / X is now active' message, call "
            "claim_build_done with the actual files and endpoints first. "
            "If its verdict is FABRICATED_CLAIM_DETECTED, admit plainly "
            "that the build is not done — do not invent."
        )
        tools_messages = [{"role": "system", "content": sys_for_tools}]
        for t in history[-6:]:
            tools_messages.append({
                "role": "user" if t.get("role") == "user" else "assistant",
                "content": t.get("text", ""),
            })
        tools_messages.append({"role": "user", "content": text})
        try:
            client = _get_groq_client()
            reply, audit = await groq_chat_with_tools(
                tools_messages,
                client=client,
                max_iters=5,
                actor=f"ora-chat:{sid}",
            )
            _tool_audit.extend(audit)
            return reply
        except Exception as e:
            logger.warning(f"[public-ora-demo] groq with-tools failed: {type(e).__name__}: {e}")
            return None

    # iter 322fe — Authenticated users → tools-enabled Groq path first.
    # If with-tools fails (rate limit, network), we fall back to plain Claude
    # (different provider, different quota) so ORA stays online when Groq
    # daily TPD hits 100k. Only if BOTH fail do we surface an honest message.
    auto_tools_on = bool(user)
    auto_tools_failed = False
    if auto_tools_on:
        _g0 = _time.monotonic()
        out = await _try_groq_with_tools()
        groq_ms = int((_time.monotonic() - _g0) * 1000)
        if out:
            llm_source = "groq-tools"
        else:
            auto_tools_failed = True
            logger.warning(
                f"[public-ora-demo] auto-tools path failed for user sid={sid} "
                f"— trying Claude fallback (iter 322fh)"
            )

    # iter 322fh — when auto-tools fails OR user is anon, try Claude/Groq
    # in normal text mode. Claude has a different daily quota and an
    # entirely separate key path via Emergent universal LLM key, so it
    # rescues us when Groq hits its rate limit.
    if not out:
        for provider in order:
            if provider == "groq":
                _g0 = _time.monotonic()
                out = await _try_groq()
                groq_ms = max(groq_ms, int((_time.monotonic() - _g0) * 1000))
                if out:
                    llm_source = "groq"
                    break
            elif provider == "claude":
                _c0 = _time.monotonic()
                out = await _try_claude()
                claude_ms = int((_time.monotonic() - _c0) * 1000)
                if out:
                    llm_source = "claude" + ("-fallback" if auto_tools_failed else "")
                    break

    # Both providers dead → honest non-LLM reply (anti-hallucination).
    if not out and auto_tools_failed:
        out = (
            "Bhai, dono LLM providers abhi quiet hain (Groq rate-limit + "
            "Claude bhi reach nahi ho raha). 10-15 min me retry kar — "
            "ya CTO Mode tab me ja ke tool manually run kar le."
        )
        llm_source = "all-providers-down-honest-fallback"

    # If both providers are unreachable AND we know the user, give a
    # deterministic identity reply (zero LLM, zero hallucination).
    if not out and user:
        t_lower = text.lower()
        if any(k in t_lower for k in ("my bin", "what bin", "is admin", "am i admin", "who am i")):
            admin_status = "full admin access" if user.get("is_admin") else f"on the {user.get('plan')} plan"
            out = (
                f"You're {user.get('name')} ({user.get('business_name') or 'AUREM customer'}). "
                f"Your BIN is {user.get('bin') or 'not set'}. You have {admin_status}."
            )
            llm_source = "deterministic"

    # Last-resort reply — no warmup language. Always offers a path.
    if not out:
        out = (
            "I'm here. Tell me what your business does and I'll show you "
            "what I can do — or scan your website free at /repair-quote "
            "for a 60-second teardown."
        )
        llm_source = "fallback_template"

    # Persist this turn for future context (BUG 2 fix)
    await _save_turn(sid, bin_for_session, text, out)

    # iter 322bo — write per-request latency metrics for the ops dashboard
    total_ms = int((_time.monotonic() - t_started) * 1000)
    try:
        if _db is not None:
            await _db.ora_chat_metrics.insert_one({
                "session_id": sid,
                "bin": bin_for_session,
                "authenticated": bool(user),
                "llm_source": llm_source,
                "total_ms": total_ms,
                "claude_ms": claude_ms,
                "groq_ms": groq_ms,
                "reply_len": len(out),
                "history_size": len(history),
                "ts": datetime.now(timezone.utc),
            })
    except Exception as _me:
        logger.debug(f"[public-ora-demo] metrics write failed: {_me}")

    return {
        "ok": True,
        "reply": out,
        "authenticated": bool(user),
        "llm_source": llm_source,
        "session_id": sid,
        "latency_ms": total_ms,
        # iter 322fe — surface auto tool-call receipts so the founder can
        # see which real tools ORA invoked while composing this reply.
        "auto_tools_on": auto_tools_on,
        "tool_calls":   _tool_audit,
    }
