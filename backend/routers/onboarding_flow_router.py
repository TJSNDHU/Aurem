"""
routers/onboarding_flow_router.py — iter D-32

POST-SIGNUP FLOW (Watchdog-approved, 2026-05-26):

  1. Customer signs up → lands on /my/projects/new (no GitHub/server/domain prompts).
  2. They describe what they want → AUREM CTO builds a project preview live at
     preview.aurem.live/<project_id>.
  3. Tokens deplete with each chat turn (cheap model = 1 tok, frontier = 5 tok).
  4. Social-share bonus = +2500 tokens (auto-scrape, admin manual fallback).
  5. At progress >= 0.80, frontend reveals the Go-Live checklist
     (GitHub → server → domain → BYOK).

Collections (new, prefixed `onboarding_`):
  - onboarding_projects        — project state + preview manifest + progress
  - onboarding_token_wallets   — per-user wallet + ledger
  - onboarding_share_claims    — pending/approved/rejected social shares

Public endpoints (no auth) used by the multi-tenant preview surface:
  GET /api/preview/projects/{project_id}/manifest
  GET /preview/{project_id}                 (rendered HTML, dev-only)

Customer endpoints (dev JWT):
  POST   /api/onboarding/projects                  — create project
  GET    /api/onboarding/projects                  — list mine
  GET    /api/onboarding/projects/{project_id}     — single project
  PATCH  /api/onboarding/projects/{project_id}     — update prompt/progress/manifest
  GET    /api/onboarding/wallet                    — balance + ledger
  POST   /api/onboarding/wallet/debit              — debit tokens for a chat turn
  POST   /api/onboarding/share/submit              — submit social-share URL
  GET    /api/onboarding/share/mine                — my share history

Admin endpoints (admin JWT):
  GET    /api/onboarding/admin/shares/pending      — manual review queue
  POST   /api/onboarding/admin/shares/{id}/decide  — approve / reject
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(db) -> None:
    global _db
    _db = db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _dev(authorization: Optional[str]) -> dict:
    from routers.developer_portal_router import _current_dev
    return await _current_dev(authorization)


# ──────────────────────────────────────────────────────────────────────
# Token wallet
# ──────────────────────────────────────────────────────────────────────

SIGNUP_GRANT_TOKENS = 1000
SHARE_BONUS_TOKENS = 2500
COST_CHEAP_MODEL = 1
COST_FRONTIER_MODEL = 5


async def _ensure_wallet(user_id: str) -> dict:
    """Get-or-create the user's wallet with the signup grant."""
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    row = await _db.onboarding_token_wallets.find_one(
        {"user_id": user_id}, {"_id": 0},
    )
    if row:
        return row
    wallet = {
        "user_id":    user_id,
        "balance":    SIGNUP_GRANT_TOKENS,
        "lifetime_earned": SIGNUP_GRANT_TOKENS,
        "lifetime_spent":  0,
        "ledger": [{
            "ts":     _now_iso(),
            "delta":  SIGNUP_GRANT_TOKENS,
            "kind":   "grant_signup",
            "note":   "Welcome — 1000 free tokens to get you started.",
        }],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await _db.onboarding_token_wallets.insert_one(dict(wallet))
    return wallet


@router.get("/api/onboarding/wallet")
async def get_wallet(authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    w = await _ensure_wallet(me["user_id"])
    return {
        "balance":         w.get("balance", 0),
        "lifetime_earned": w.get("lifetime_earned", 0),
        "lifetime_spent":  w.get("lifetime_spent", 0),
        "ledger":          (w.get("ledger") or [])[-50:],
        "cost_cheap":      COST_CHEAP_MODEL,
        "cost_frontier":   COST_FRONTIER_MODEL,
        "low_threshold":   100,
    }


class DebitBody(BaseModel):
    model_tier: str = Field("cheap", pattern="^(cheap|frontier)$")
    project_id: str = Field("", max_length=64)
    note:       str = Field("chat turn", max_length=200)


@router.post("/api/onboarding/wallet/debit")
async def debit_wallet(body: DebitBody,
                       authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    await _ensure_wallet(me["user_id"])
    cost = COST_FRONTIER_MODEL if body.model_tier == "frontier" else COST_CHEAP_MODEL
    # Atomic conditional decrement so two concurrent chat turns can't
    # both go through when balance was 1.
    res = await _db.onboarding_token_wallets.find_one_and_update(
        {"user_id": me["user_id"], "balance": {"$gte": cost}},
        {
            "$inc": {"balance": -cost, "lifetime_spent": cost},
            "$push": {"ledger": {
                "ts":         _now_iso(),
                "delta":      -cost,
                "kind":       f"debit_{body.model_tier}",
                "project_id": body.project_id or None,
                "note":       body.note[:200],
            }},
            "$set": {"updated_at": _now_iso()},
        },
        projection={"_id": 0, "balance": 1},
        return_document=True,  # returns updated doc
    )
    if res is None:
        # Read current balance to tell the caller exactly where they are.
        current = await _db.onboarding_token_wallets.find_one(
            {"user_id": me["user_id"]}, {"_id": 0, "balance": 1},
        )
        raise HTTPException(402, {
            "code": "insufficient_tokens",
            "balance": (current or {}).get("balance", 0),
            "cost":    cost,
        })
    return {"ok": True, "balance": res.get("balance", 0), "cost": cost}


# ──────────────────────────────────────────────────────────────────────
# Projects (multi-tenant preview surface)
# ──────────────────────────────────────────────────────────────────────

_PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)[:32] or "project"
    return slug


def _public_project_view(p: dict) -> dict:
    return {
        "project_id":   p.get("project_id"),
        "slug":         p.get("slug"),
        "name":         p.get("name"),
        "intent":       p.get("intent"),
        "progress":     float(p.get("progress", 0.0)),
        "phase":        p.get("phase", "drafting"),
        "preview_url":  p.get("preview_url"),
        "manifest":     p.get("manifest") or {},
        "go_live_ready": float(p.get("progress", 0.0)) >= 0.80,
        "created_at":   p.get("created_at"),
        "updated_at":   p.get("updated_at"),
    }


class ProjectCreateBody(BaseModel):
    name:   str = Field(..., min_length=2, max_length=80)
    intent: str = Field(..., min_length=5, max_length=2000)


@router.post("/api/onboarding/projects")
async def create_project(body: ProjectCreateBody,
                         authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    await _ensure_wallet(me["user_id"])

    base_slug = _slugify(body.name)
    project_id = f"{base_slug}-{secrets.token_urlsafe(4).lower().replace('_','').replace('-','')[:5]}"
    if not _PROJECT_ID_RE.match(project_id):
        project_id = f"prj-{uuid.uuid4().hex[:10]}"

    # iter D-32 — Watchdog rule: no GitHub/server/domain prompts upfront.
    # Project goes live as a free multi-tenant preview at
    # preview.aurem.live/<project_id>. Customer sees their build live.
    base_preview = "https://preview.aurem.live"
    preview_url = f"{base_preview}/{project_id}"

    doc = {
        "project_id": project_id,
        "user_id":    me["user_id"],
        "slug":       base_slug,
        "name":       body.name.strip(),
        "intent":     body.intent.strip(),
        "progress":   0.0,
        "phase":      "drafting",
        "preview_url": preview_url,
        "manifest": {
            # Default starter manifest — AUREM CTO updates this on each
            # build turn. Keys mirror the multi-tenant preview renderer.
            "title":       body.name.strip(),
            "tagline":     "",
            "sections":    [],
            "primary_cta": None,
            "theme":       {"accent": "#FF6B00", "bg": "#0B0B0E"},
        },
        "go_live": {
            "github":  {"done": False, "linked_at": None},
            "server":  {"done": False, "linked_at": None},
            "domain":  {"done": False, "linked_at": None},
            "byok":    {"done": False, "linked_at": None},
        },
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await _db.onboarding_projects.insert_one(dict(doc))
    return _public_project_view(doc)


@router.get("/api/onboarding/projects")
async def list_projects(authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        return {"projects": []}
    cur = _db.onboarding_projects.find(
        {"user_id": me["user_id"]}, {"_id": 0},
    ).sort("updated_at", -1).limit(50)
    rows = [_public_project_view(d) async for d in cur]
    return {"projects": rows}


@router.get("/api/onboarding/projects/{project_id}")
async def get_project(project_id: str,
                      authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    row = await _db.onboarding_projects.find_one(
        {"project_id": project_id, "user_id": me["user_id"]}, {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "project_not_found")
    return _public_project_view(row)


class ProjectUpdateBody(BaseModel):
    name:     Optional[str]   = Field(None, max_length=80)
    intent:   Optional[str]   = Field(None, max_length=2000)
    progress: Optional[float] = Field(None, ge=0.0, le=1.0)
    phase:    Optional[str]   = Field(None, max_length=40)
    manifest: Optional[dict]  = None


@router.patch("/api/onboarding/projects/{project_id}")
async def update_project(project_id: str,
                         body: ProjectUpdateBody,
                         authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    upd: dict[str, Any] = {"updated_at": _now_iso()}
    if body.name is not None:    upd["name"] = body.name.strip()
    if body.intent is not None:  upd["intent"] = body.intent.strip()
    if body.progress is not None: upd["progress"] = float(body.progress)
    if body.phase is not None:    upd["phase"] = body.phase[:40]
    if body.manifest is not None:
        # Drop _id/user_id if the caller smuggled them in.
        clean = {k: v for k, v in body.manifest.items()
                 if k not in ("_id", "user_id", "project_id")}
        upd["manifest"] = clean
    r = await _db.onboarding_projects.find_one_and_update(
        {"project_id": project_id, "user_id": me["user_id"]},
        {"$set": upd},
        projection={"_id": 0},
        return_document=True,
    )
    if not r:
        raise HTTPException(404, "project_not_found")
    return _public_project_view(r)


# ──────────────────────────────────────────────────────────────────────
# Public preview manifest (no auth) — what the preview surface renders
# ──────────────────────────────────────────────────────────────────────

@router.get("/api/preview/projects/{project_id}/manifest")
async def public_project_manifest(project_id: str) -> dict[str, Any]:
    """No auth. Anyone with the preview URL can fetch the manifest.
    No PII is exposed — only what the customer chose to show publicly."""
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    row = await _db.onboarding_projects.find_one(
        {"project_id": project_id},
        {"_id": 0, "user_id": 0, "go_live": 0},
    )
    if not row:
        raise HTTPException(404, "project_not_found")
    return _public_project_view(row)


# ──────────────────────────────────────────────────────────────────────
# Social-share verification (Watchdog answer: c = auto-scrape + manual fallback)
# ──────────────────────────────────────────────────────────────────────

class ShareSubmitBody(BaseModel):
    url:        str = Field(..., min_length=12, max_length=400)
    handle:     str = Field(..., min_length=1, max_length=80,
                            description="The social-network handle that posted it")
    platform:   str = Field("other", max_length=30)


REQUIRED_MENTIONS = ("aurem", "@aurem", "aurem.live")


async def _scrape_share(url: str) -> tuple[bool, str, str]:
    """Returns (looks_legit, reason, snippet). Best-effort GET + heuristic."""
    try:
        async with httpx.AsyncClient(timeout=8.0,
                                      headers={"User-Agent": "AUREM-ShareBot/1.0"},
                                      follow_redirects=True) as c:
            r = await c.get(url)
        body = (r.text or "").lower()
        for token in REQUIRED_MENTIONS:
            if token in body:
                snippet = body[max(0, body.find(token) - 80):body.find(token) + 120]
                return True, f"matched {token}", snippet[:300]
        return False, "no_aurem_mention_in_html", ""
    except Exception as e:
        return False, f"scrape_failed: {type(e).__name__}", ""


@router.post("/api/onboarding/share/submit")
async def submit_share(body: ShareSubmitBody,
                       authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "url_must_be_http")
    # No duplicates: same URL = same claim.
    dup = await _db.onboarding_share_claims.find_one(
        {"user_id": me["user_id"], "url": url}, {"_id": 0, "status": 1},
    )
    if dup:
        return {"status": dup.get("status"), "duplicate": True}

    looks_ok, reason, snippet = await _scrape_share(url)
    auto_ok = looks_ok and reason.startswith("matched")
    status = "approved" if auto_ok else "pending"

    claim_id = uuid.uuid4().hex[:16]
    await _db.onboarding_share_claims.insert_one({
        "claim_id":   claim_id,
        "user_id":    me["user_id"],
        "email":      me.get("email", ""),
        "platform":   body.platform[:30],
        "handle":     body.handle.strip(),
        "url":        url,
        "scrape_ok":  looks_ok,
        "scrape_reason": reason,
        "scrape_snippet": snippet,
        "status":     status,
        "submitted_at": _now_iso(),
        "decided_at": _now_iso() if auto_ok else None,
        "decided_by": "auto-scraper" if auto_ok else None,
        "tokens_awarded": SHARE_BONUS_TOKENS if auto_ok else 0,
    })

    if auto_ok:
        await _credit_share_bonus(me["user_id"], claim_id)

    return {"claim_id": claim_id, "status": status, "reason": reason}


async def _credit_share_bonus(user_id: str, claim_id: str) -> None:
    if _db is None:
        return
    await _ensure_wallet(user_id)
    await _db.onboarding_token_wallets.update_one(
        {"user_id": user_id},
        {
            "$inc": {"balance": SHARE_BONUS_TOKENS,
                     "lifetime_earned": SHARE_BONUS_TOKENS},
            "$push": {"ledger": {
                "ts":     _now_iso(),
                "delta":  SHARE_BONUS_TOKENS,
                "kind":   "grant_social_share",
                "claim_id": claim_id,
                "note":   "Social-share verified — +2500 tokens.",
            }},
            "$set": {"updated_at": _now_iso()},
        },
    )


@router.get("/api/onboarding/share/mine")
async def my_shares(authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        return {"shares": []}
    cur = _db.onboarding_share_claims.find(
        {"user_id": me["user_id"]}, {"_id": 0, "scrape_snippet": 0},
    ).sort("submitted_at", -1).limit(20)
    rows = [d async for d in cur]
    return {"shares": rows}


# ──────────────────────────────────────────────────────────────────────
# Admin queue
# ──────────────────────────────────────────────────────────────────────

async def _require_admin(authorization: Optional[str]) -> dict:
    """Re-uses the developer_portal admin-JWT bypass."""
    me = await _dev(authorization)
    if not (me.get("is_admin") or me.get("is_super_admin")
            or me.get("kind") == "admin_bootstrap"):
        # Fallback — verify the raw JWT explicitly.
        try:
            import jwt as _jwt
            from config import JWT_SECRET, JWT_ALGORITHM
            token = (authorization or "").split(" ", 1)[-1]
            payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if not (payload.get("is_admin") or payload.get("is_super_admin")):
                raise HTTPException(403, "admin_required")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(403, "admin_required")
    return me


@router.get("/api/onboarding/admin/shares/pending")
async def admin_pending_shares(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    if _db is None:
        return {"shares": []}
    cur = _db.onboarding_share_claims.find(
        {"status": "pending"}, {"_id": 0},
    ).sort("submitted_at", 1).limit(100)
    rows = [d async for d in cur]
    return {"shares": rows}


class AdminDecideBody(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    note:     str = Field("", max_length=400)


@router.post("/api/onboarding/admin/shares/{claim_id}/decide")
async def admin_decide_share(claim_id: str,
                              body: AdminDecideBody,
                              authorization: str = Header(None)) -> dict[str, Any]:
    me = await _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    claim = await _db.onboarding_share_claims.find_one(
        {"claim_id": claim_id}, {"_id": 0},
    )
    if not claim:
        raise HTTPException(404, "claim_not_found")
    if claim.get("status") != "pending":
        raise HTTPException(400, f"already_{claim.get('status')}")
    new_status = "approved" if body.decision == "approve" else "rejected"
    awarded = SHARE_BONUS_TOKENS if new_status == "approved" else 0
    await _db.onboarding_share_claims.update_one(
        {"claim_id": claim_id},
        {"$set": {
            "status":       new_status,
            "decided_at":   _now_iso(),
            "decided_by":   me.get("email") or me.get("user_id"),
            "admin_note":   body.note,
            "tokens_awarded": awarded,
        }},
    )
    if new_status == "approved":
        await _credit_share_bonus(claim["user_id"], claim_id)
    return {"ok": True, "status": new_status, "tokens_awarded": awarded}


# ──────────────────────────────────────────────────────────────────────
# Index bootstrap (run once at startup)
# ──────────────────────────────────────────────────────────────────────

async def ensure_indexes() -> None:
    if _db is None:
        return
    try:
        await asyncio.gather(
            _db.onboarding_projects.create_index("project_id", unique=True),
            _db.onboarding_projects.create_index("user_id"),
            _db.onboarding_token_wallets.create_index("user_id", unique=True),
            _db.onboarding_share_claims.create_index("claim_id", unique=True),
            _db.onboarding_share_claims.create_index([("status", 1), ("submitted_at", 1)]),
            _db.onboarding_share_claims.create_index([("user_id", 1), ("url", 1)], unique=True),
        )
        logger.info("[onboarding] indexes ensured")
    except Exception as e:
        logger.warning(f"[onboarding] index ensure failed: {e}")
