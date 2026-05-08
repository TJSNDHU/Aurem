"""
AUREM Sentinel Client Router — Production Error Observability + AI Diagnose
═══════════════════════════════════════════════════════════════════════════════

Captures client-side errors (JS exceptions, failed API calls, chunk errors) from
the AUREM frontend, classifies them, auto-heals known patterns silently, and
surfaces a human-review AI repair queue to admins.

TRUST-BUT-VERIFY MODEL:
  • Tier 1 — Auto-heal KNOWN patterns (stale URL rewrite, token refresh) without AI
  • Tier 2 — AI Diagnose suggests a fix as a structured repair suggestion, stored
             in `db.repair_suggestions`. AI DOES NOT modify code or deploy.
  • Tier 3 — Admin reviews suggestion in dashboard and clicks Apply / Modify / Reject

Endpoints:
  Public ingest (rate-limited, session-keyed):
    POST /api/sentinel/client-error          — ingest one error event

  Admin (super_admin JWT):
    GET  /api/admin/sentinel/overview         — aggregate stats (last 1h/24h)
    GET  /api/admin/sentinel/errors           — paginated error feed with filters
    POST /api/admin/sentinel/analyze/{id}     — trigger Claude diagnosis for one error
    GET  /api/admin/sentinel/suggestions      — AI repair suggestions awaiting review
    POST /api/admin/sentinel/suggestions/{id}/review — approve/reject an AI suggestion

Collections:
  • db.client_errors         — raw captured errors
  • db.repair_suggestions    — Claude-produced structured repair diffs
"""
import os
import re
import json
import uuid
import hashlib
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import jwt
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Sentinel Client"])

_db = None


def set_db(database):
    global _db
    _db = database
    # iter 295 — production hardening: ensure indexes for hot count_documents queries
    try:
        import asyncio as _asyncio
        async def _ensure_indexes():
            try:
                await database.client_errors.create_index([("session_id", 1), ("ts", -1)], background=True)
                await database.client_errors.create_index([("ip_hash", 1), ("ts", -1)], background=True)
                await database.client_errors.create_index([("ts", -1)], background=True, expireAfterSeconds=60 * 60 * 24 * 14)
            except Exception as e:
                logging.getLogger(__name__).debug(f"[sentinel-client] index setup skipped: {e}")
        _asyncio.create_task(_ensure_indexes())
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════
# PII scrubbing — strip emails/phones/tokens from captured data before
# writing to Mongo or shipping to LLM.
# ═════════════════════════════════════════════════════════════════════
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_=-]{10,}\.[A-Za-z0-9_=-]{10,}\.[A-Za-z0-9_=-]{8,}")


def _scrub(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    t = str(text)[:4000]
    t = _JWT_RE.sub("[JWT_REDACTED]", t)
    t = _EMAIL_RE.sub("[EMAIL]", t)
    t = _PHONE_RE.sub("[PHONE]", t)
    return t


# ═════════════════════════════════════════════════════════════════════
# Classifier — Tier 1 auto-heal + Tier 2 AI-eligible
# ═════════════════════════════════════════════════════════════════════
AUTO_HEAL_PATTERNS = {
    "stale_preview_pod":    "Frontend hit a dead preview pod URL — fetch healer rewrites to same-origin.",
    "chunk_load_error":     "Webpack chunk 404 — service worker cache nuke + hard reload.",
    "auth_token_expired":   "JWT expired (401) — redirect to login with return URL.",
    "rate_limited_429":     "Backend rate limit — client-side exponential backoff.",
}


def _classify(err: Dict[str, Any]) -> Dict[str, Any]:
    """Return {type, auto_heal_key or None, ai_eligible}."""
    etype = (err.get("type") or "").lower()
    msg = (err.get("message") or "").lower()
    url = (err.get("url") or "").lower()
    status = err.get("status_code")

    # Known auto-heal patterns
    if "preview.emergentagent.com" in url or "emergent.host" in url:
        return {"type": "stale_preview_pod", "auto_heal_key": "stale_preview_pod", "ai_eligible": False}
    if "chunkloaderror" in msg or "loading chunk" in msg or "unexpected token '<'" in msg:
        return {"type": "chunk_load_error", "auto_heal_key": "chunk_load_error", "ai_eligible": False}
    if status == 401:
        return {"type": "auth_token_expired", "auto_heal_key": "auth_token_expired", "ai_eligible": False}
    if status == 429:
        return {"type": "rate_limited_429", "auto_heal_key": "rate_limited_429", "ai_eligible": False}

    # AI-eligible buckets
    if etype == "network_failure":
        return {"type": "network_failure", "auto_heal_key": None, "ai_eligible": True}
    if etype == "api_error" and status and status >= 500:
        return {"type": "backend_5xx", "auto_heal_key": None, "ai_eligible": True}
    if etype == "api_error" and status and 400 <= status < 500:
        return {"type": "client_4xx", "auto_heal_key": None, "ai_eligible": True}
    if etype == "js_exception":
        return {"type": "js_exception", "auto_heal_key": None, "ai_eligible": True}
    if etype == "unhandled_rejection":
        return {"type": "unhandled_rejection", "auto_heal_key": None, "ai_eligible": True}
    if etype == "console_error":
        return {"type": "console_error", "auto_heal_key": None, "ai_eligible": False}

    return {"type": "unknown", "auto_heal_key": None, "ai_eligible": False}


def _hash_signature(err: Dict[str, Any]) -> str:
    """Dedup key: same error type + message-head + file should hash the same."""
    parts = [
        (err.get("type") or "")[:40],
        (err.get("message") or "")[:120],
        (err.get("stack") or "")[:200],
        str(err.get("status_code") or ""),
        (err.get("url") or "").split("?")[0][:120],
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8", errors="ignore")).hexdigest()[:16]


# ═════════════════════════════════════════════════════════════════════
# Auth helper
# ═════════════════════════════════════════════════════════════════════
def _decode_jwt(request: Request) -> dict:
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        return jwt.decode(token, os.environ.get("JWT_SECRET", ""), algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


async def _require_admin(request: Request) -> dict:
    payload = _decode_jwt(request)
    role = (payload.get("role") or "").lower()
    if role not in ("admin", "super_admin") and not (payload.get("is_admin") or payload.get("is_super_admin")):
        raise HTTPException(403, "Admin role required")
    return payload


# ═════════════════════════════════════════════════════════════════════
# Public — Ingest (rate-limited)
# ═════════════════════════════════════════════════════════════════════
class ClientErrorBody(BaseModel):
    type: str = Field(..., max_length=50)
    message: Optional[str] = Field(None, max_length=2000)
    stack: Optional[str] = Field(None, max_length=4000)
    url: Optional[str] = Field(None, max_length=500)
    method: Optional[str] = Field(None, max_length=10)
    status_code: Optional[int] = None
    user_agent: Optional[str] = Field(None, max_length=400)
    session_id: Optional[str] = Field(None, max_length=80)
    release_hash: Optional[str] = Field(None, max_length=40)
    hostname: Optional[str] = Field(None, max_length=120)
    page_url: Optional[str] = Field(None, max_length=500)
    user_email: Optional[str] = Field(None, max_length=200)
    tenant_bin: Optional[str] = Field(None, max_length=60)
    extra: Optional[Dict[str, Any]] = None


# URLs we never persist — client OR server side blocklist, duplicate of the
# frontend list in lib/sentinel.js so stale cached clients can't flood.
_IGNORED_URL_FRAGMENTS = (
    "/api/sentinel/client-error",
    "/api/sentinel/heartbeat",
    "/api/voice-agent/health",
    "/api/ora/health",
    "/api/leads/health",
    "/api/system/overview/public",
    "/api/service-catalog",
    "/api/services/catalog",
    "/robots.txt",
    "/sitemap.xml",
    "/llms.txt",
    "/llms-full.txt",
    "/favicon.ico",
    "chrome-extension://",
    "moz-extension://",
    "googleads",
    "doubleclick",
    "google-analytics",
    # Stale preview-pod hosts — retired frontends keep firing into dead URLs.
    # Drop them BEFORE any Mongo hit so they can't starve the K8s probe loop.
    "preview.emergentagent.com",
    "emergent.host",
    "emergent.sh",
    ".preview.",
)


@router.post("/api/sentinel/client-error")
async def ingest_client_error(body: ClientErrorBody, request: Request):
    """Public ingest — rate-limited by IP + session + signature. Scrubs PII."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    # Drop known-ignored URLs immediately (no DB hit).
    url_lower = (body.url or "").lower()
    if url_lower and any(frag in url_lower for frag in _IGNORED_URL_FRAGMENTS):
        return {"ok": False, "dropped": "ignored_url"}

    # Also drop when the originating PAGE / hostname is a stale preview pod —
    # retired frontend tabs keep firing their cached backend URL at our prod
    # instance and each one costs 3× count_documents on Atlas. Starves the
    # event loop → K8s health probe timeout → pod restart loop.
    page_lower = (body.page_url or "").lower() + " " + (body.hostname or "").lower()
    for frag in ("preview.emergentagent.com", "emergent.host", "emergent.sh", ".preview."):
        if frag in page_lower:
            return {"ok": False, "dropped": "stale_preview_pod"}

    # Drop 404s — always expected on optional endpoints, never signal.
    if body.status_code == 404:
        return {"ok": False, "dropped": "http_404_ignored"}

    # iter 295 — production hardening: drop trivial / empty errors before any DB hit
    msg = (body.message or "").strip()
    if not msg or len(msg) < 8:
        return {"ok": False, "dropped": "empty_or_trivial"}

    ip = request.client.host if request.client else "0.0.0.0"
    ip_hash = hashlib.sha1(ip.encode("utf-8")).hexdigest()[:12]
    session_id = body.session_id or "anon"

    try:
        # iter 295 — hard 1.5s cap per DB read to prevent event-loop stalls under Atlas latency
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        cutoff_10s = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        cooldown_hit = await asyncio.wait_for(
            _db.client_errors.count_documents({
                "session_id": session_id, "ts": {"$gte": cutoff_10s}
            }), timeout=1.5,
        )
        if cooldown_hit >= 1:
            return {"ok": False, "throttled": "cooldown_10s"}
        recent_session = await asyncio.wait_for(
            _db.client_errors.count_documents({
                "session_id": session_id, "ts": {"$gte": cutoff}
            }), timeout=1.5,
        )
        if recent_session >= 10:
            return {"ok": False, "throttled": "session"}
        recent_ip = await asyncio.wait_for(
            _db.client_errors.count_documents({
                "ip_hash": ip_hash, "ts": {"$gte": cutoff}
            }), timeout=1.5,
        )
        if recent_ip >= 30:
            return {"ok": False, "throttled": "ip"}
    except asyncio.TimeoutError:
        # Atlas slow — fail open silently rather than blocking the event loop
        return {"ok": False, "throttled": "atlas_slow"}
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    raw = body.model_dump()
    # Scrub PII
    raw["message"] = _scrub(raw.get("message"))
    raw["stack"] = _scrub(raw.get("stack"))
    raw["url"] = _scrub(raw.get("url"))
    raw["page_url"] = _scrub(raw.get("page_url"))
    if raw.get("user_email"):
        raw["user_email"] = (raw["user_email"] or "").lower()[:200]
    if raw.get("extra"):
        try:
            raw["extra"] = json.loads(_scrub(json.dumps(raw["extra"])))
        except Exception:
            raw["extra"] = None

    signature = _hash_signature(raw)
    classification = _classify(raw)

    # Per-signature global cap — once 25 of the same signature exist in the
    # last 5 min, sample 1-in-10 going forward. Keeps storm events visible
    # without letting a single flood fill the DB.
    try:
        cutoff_sig = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        sig_count = await _db.client_errors.count_documents({
            "signature": signature, "ts": {"$gte": cutoff_sig}
        })
        if sig_count >= 25 and (sig_count % 10) != 0:
            return {"ok": False, "throttled": "signature", "signature": signature}
    except Exception:
        pass

    doc = {
        "error_id": f"ce_{uuid.uuid4().hex[:12]}",
        "ts": now.isoformat(),
        "signature": signature,
        "classification": classification["type"],
        "auto_heal_key": classification["auto_heal_key"],
        "ai_eligible": classification["ai_eligible"],
        "ip_hash": ip_hash,
        "status": "new",  # new | analyzed | reviewed
        **raw,
    }
    try:
        await _db.client_errors.insert_one(dict(doc))
    except Exception as e:
        logger.warning(f"[sentinel] insert failed: {e}")
        raise HTTPException(500, "insert failed")

    return {
        "ok": True,
        "error_id": doc["error_id"],
        "classification": classification["type"],
        "auto_heal_suggestion": AUTO_HEAL_PATTERNS.get(classification["auto_heal_key"] or ""),
        "ai_eligible": classification["ai_eligible"],
    }


# ═════════════════════════════════════════════════════════════════════
# Public — Sidebar Heartbeat
# Lightweight health dots for the platform dashboard. Polled every 60s
# by every open tab so it MUST stay fast (<100ms) and resilient.
# Returns: {status: {item_id: "healthy"|"degraded"|"error"}}
# ═════════════════════════════════════════════════════════════════════
@router.get("/api/sentinel/heartbeat")
async def sentinel_heartbeat(request: Request):
    """Aggregate per-item health for the dashboard sidebar pulse dots."""
    status_map: Dict[str, str] = {"overall": "healthy"}
    if _db is None:
        return {"status": status_map}
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        recent = await _db.client_errors.count_documents({"ts": {"$gte": cutoff}})
        if recent > 50:
            status_map["overall"] = "error"
        elif recent > 10:
            status_map["overall"] = "degraded"
    except Exception:
        # Never let heartbeat fail — fallback to healthy
        pass
    return {"status": status_map}


# ═════════════════════════════════════════════════════════════════════
# Admin — Overview + Feed
# ═════════════════════════════════════════════════════════════════════
@router.get("/api/admin/sentinel/overview")
async def admin_overview(request: Request):
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")

    now = datetime.now(timezone.utc)
    cut_1h = (now - timedelta(hours=1)).isoformat()
    cut_24h = (now - timedelta(hours=24)).isoformat()

    total_1h = await _db.client_errors.count_documents({"ts": {"$gte": cut_1h}})
    total_24h = await _db.client_errors.count_documents({"ts": {"$gte": cut_24h}})

    # Top error types (last 24h)
    pipeline = [
        {"$match": {"ts": {"$gte": cut_24h}}},
        {"$group": {
            "_id": "$classification",
            "count": {"$sum": 1},
            "users": {"$addToSet": "$user_email"},
            "last_ts": {"$max": "$ts"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    top_types = []
    async for d in _db.client_errors.aggregate(pipeline):
        users = [u for u in (d.get("users") or []) if u]
        top_types.append({
            "type": d["_id"],
            "count": d["count"],
            "unique_users": len(users),
            "last_ts": d.get("last_ts"),
        })

    # Spike detector (same signature affecting > 10 users in 5 min)
    cut_5m = (now - timedelta(minutes=5)).isoformat()
    spike_pipeline = [
        {"$match": {"ts": {"$gte": cut_5m}}},
        {"$group": {
            "_id": "$signature",
            "count": {"$sum": 1},
            "users": {"$addToSet": "$user_email"},
            "sample": {"$first": "$message"},
            "classification": {"$first": "$classification"},
        }},
        {"$match": {"count": {"$gte": 5}}},
        {"$sort": {"count": -1}},
    ]
    spikes = []
    async for d in _db.client_errors.aggregate(spike_pipeline):
        users = [u for u in (d.get("users") or []) if u]
        if len(users) >= 3:
            spikes.append({
                "signature": d["_id"],
                "count": d["count"],
                "unique_users": len(users),
                "sample": d.get("sample"),
                "classification": d.get("classification"),
            })

    pending_suggestions = await _db.repair_suggestions.count_documents({"status": "pending"})

    return {
        "ok": True,
        "errors_1h": total_1h,
        "errors_24h": total_24h,
        "top_types": top_types,
        "active_spikes": spikes,
        "pending_ai_suggestions": pending_suggestions,
    }


@router.get("/api/admin/sentinel/errors")
async def admin_list_errors(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    classification: Optional[str] = None,
    hours: int = Query(24, ge=1, le=720),
):
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q: Dict[str, Any] = {"ts": {"$gte": cutoff}}
    if classification:
        q["classification"] = classification
    docs = []
    async for d in _db.client_errors.find(q, {"_id": 0}).sort("ts", -1).limit(limit):
        docs.append(d)
    return {"ok": True, "count": len(docs), "errors": docs}


# ═════════════════════════════════════════════════════════════════════
# Admin — AI Diagnose (stores suggestion, does NOT apply)
# ═════════════════════════════════════════════════════════════════════
@router.post("/api/admin/sentinel/analyze/{error_id}")
async def admin_analyze_error(error_id: str, request: Request):
    """Trigger Claude to produce a structured repair suggestion for one error.
    Stores the suggestion in db.repair_suggestions with status='pending'.
    AI NEVER modifies code or deploys."""
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")

    err = await _db.client_errors.find_one({"error_id": error_id}, {"_id": 0})
    if not err:
        raise HTTPException(404, "error not found")

    if not err.get("ai_eligible"):
        raise HTTPException(400, f"error classification '{err.get('classification')}' is not AI-eligible (has auto-heal or not analyzable)")

    # Check if a pending suggestion already exists for this signature
    existing = await _db.repair_suggestions.find_one({
        "source_signature": err.get("signature"),
        "status": "pending",
    }, {"_id": 0})
    if existing:
        return {"ok": True, "suggestion_id": existing["suggestion_id"], "reused": True, "suggestion": existing}

    # Call Claude via Emergent LLM key
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

        chat = LlmChat(
            api_key=key,
            session_id=f"sentinel-{uuid.uuid4().hex[:8]}",
            system_message=(
                "You are AUREM's senior SRE. Given a captured client-side error, "
                "produce a STRICT JSON repair suggestion for human review. "
                "Never modify code — only suggest. Keep confidence honest.\n\n"
                "Output JSON schema (no other text, no markdown fences):\n"
                '{\n'
                '  "severity": "P0"|"P1"|"P2"|"P3",\n'
                '  "root_cause": "1-2 sentence diagnosis",\n'
                '  "suggested_fix": "natural-language description of the fix",\n'
                '  "code_hint": "optional pseudo-diff or file path to inspect",\n'
                '  "affected_files": ["path/to/file1", ...],\n'
                '  "test_hint": "how to verify the fix works",\n'
                '  "confidence": 0.0-1.0,\n'
                '  "requires_deploy": true|false,\n'
                '  "safe_auto_apply": false\n'
                "}\n"
                'Rule: set "safe_auto_apply" to true ONLY for mechanical single-line fixes. '
                'For anything structural, set to false.'
            ),
        ).with_model("anthropic", "claude-sonnet-4-5")

        compact = {
            "type": err.get("type"),
            "classification": err.get("classification"),
            "message": err.get("message"),
            "status_code": err.get("status_code"),
            "url": err.get("url"),
            "method": err.get("method"),
            "stack_head": (err.get("stack") or "")[:1200],
            "page_url": err.get("page_url"),
            "hostname": err.get("hostname"),
        }
        reply = await chat.send_message(UserMessage(text=f"Error:\n{json.dumps(compact, indent=2)}"))
        raw = str(reply).strip()

        # Extract JSON (handle any wrapping)
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"LLM did not return JSON: {raw[:200]}")
        parsed = json.loads(raw[start:end + 1])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[sentinel] AI analyze failed: {e}")
        raise HTTPException(500, f"AI diagnosis failed: {e}")

    now = datetime.now(timezone.utc)
    suggestion = {
        "suggestion_id": f"rs_{uuid.uuid4().hex[:12]}",
        "error_id": error_id,
        "source_signature": err.get("signature"),
        "created_at": now.isoformat(),
        "status": "pending",  # pending | applied | rejected | modified
        "severity": parsed.get("severity") or "P2",
        "root_cause": (parsed.get("root_cause") or "")[:500],
        "suggested_fix": (parsed.get("suggested_fix") or "")[:1500],
        "code_hint": (parsed.get("code_hint") or "")[:2000],
        "affected_files": (parsed.get("affected_files") or [])[:10],
        "test_hint": (parsed.get("test_hint") or "")[:400],
        "confidence": float(parsed.get("confidence") or 0),
        "requires_deploy": bool(parsed.get("requires_deploy")),
        "safe_auto_apply": bool(parsed.get("safe_auto_apply")),  # informational only — NOT acted on
        "error_snapshot": {
            "classification": err.get("classification"),
            "message": err.get("message"),
            "url": err.get("url"),
            "status_code": err.get("status_code"),
        },
    }
    await _db.repair_suggestions.insert_one(dict(suggestion))
    await _db.client_errors.update_one(
        {"error_id": error_id},
        {"$set": {"status": "analyzed", "suggestion_id": suggestion["suggestion_id"]}},
    )

    suggestion.pop("_id", None)
    return {"ok": True, "suggestion_id": suggestion["suggestion_id"], "reused": False, "suggestion": suggestion}


# ═════════════════════════════════════════════════════════════════════
# Admin — Repair Suggestions queue (list + review)
# ═════════════════════════════════════════════════════════════════════
@router.get("/api/admin/sentinel/suggestions")
async def admin_list_suggestions(
    request: Request,
    status: Optional[str] = Query("pending"),
    limit: int = Query(50, ge=1, le=500),
):
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    out = []
    async for d in _db.repair_suggestions.find(q, {"_id": 0}).sort("created_at", -1).limit(limit):
        out.append(d)
    return {"ok": True, "count": len(out), "suggestions": out}


class ReviewBody(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|modify)$")
    note: Optional[str] = Field(None, max_length=2000)
    modified_fix: Optional[str] = Field(None, max_length=4000)


@router.post("/api/admin/sentinel/suggestions/{suggestion_id}/review")
async def admin_review_suggestion(suggestion_id: str, body: ReviewBody, request: Request):
    """Admin reviews AI suggestion. NOTE: this endpoint never auto-applies code
    or triggers deploys — it ONLY records the admin's decision. Actual code
    changes remain a human action via git/IDE."""
    payload = await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    s = await _db.repair_suggestions.find_one({"suggestion_id": suggestion_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "suggestion not found")
    if s.get("status") != "pending":
        raise HTTPException(409, f"suggestion already {s.get('status')}")

    now_iso = datetime.now(timezone.utc).isoformat()
    new_status = {"approve": "approved", "reject": "rejected", "modify": "modified"}[body.action]
    upd: Dict[str, Any] = {
        "status": new_status,
        "reviewed_at": now_iso,
        "reviewed_by": payload.get("email") or payload.get("user_id") or "admin",
        "review_note": (body.note or "")[:2000],
    }
    if body.modified_fix:
        upd["modified_fix"] = body.modified_fix[:4000]
    await _db.repair_suggestions.update_one(
        {"suggestion_id": suggestion_id}, {"$set": upd}
    )
    return {"ok": True, "status": new_status}
