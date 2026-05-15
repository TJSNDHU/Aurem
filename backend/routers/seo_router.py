"""
SEO / unlinked-mentions router — iter 282al-4.

Endpoints:
  POST  /api/seo/unlinked/scan           — trigger a fresh scan
  GET   /api/seo/unlinked/results        — latest grouped results
  POST  /api/seo/unlinked/outreach       — compose reclamation email
  PATCH /api/seo/unlinked/status         — update one mention's status
  GET   /api/seo/unlinked/stats          — summary counts
  GET   /api/seo/unlinked/health         — pillar chip
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from services.unlinked_mentions_service import (
    ALLOWED_STATUSES,
    COLLECTION_HIST,
    COLLECTION_MAIN,
    get_reclamation_status,
    scan_for_unlinked_mentions,
    send_reclamation_outreach,
    unlinked_mentions_health,
    update_mention_status,
)

router = APIRouter(tags=["seo"])


def _db():
    try:
        import server  # type: ignore
        return getattr(server, "db", None)
    except Exception:
        return None


# ── Request bodies ──────────────────────────────────────────────────
class _ScanBody(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=200)
    website_url:   str = Field(..., min_length=4, max_length=500)
    client_bin:    str | None = None
    lead_id:       str | None = None
    limit:         int = Field(20, ge=1, le=50)


class _OutreachBody(BaseModel):
    mention_id: str
    client_bin: str | None = None
    lead:       dict | None = None


class _StatusBody(BaseModel):
    mention_id: str
    status:     str
    notes:      str = ""


# ── Endpoints ───────────────────────────────────────────────────────
@router.post("/api/seo/unlinked/scan")
async def scan_endpoint(body: _ScanBody, request: Request):
    """Bug-fix #182 (R22): admin auth required. Burns Google/Tavily
    quota per call — unauthenticated callers could drain budget."""
    from utils.admin_guard import verify_admin
    verify_admin(request.headers.get("Authorization", ""))
    db = _db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    if not body.website_url.startswith(("http://", "https://")):
        raise HTTPException(400, "website_url must be absolute")
    result = await scan_for_unlinked_mentions(
        body.business_name, body.website_url, db, limit=body.limit,
    )
    # Stamp ownership on the upserted doc (best-effort)
    try:
        await db[COLLECTION_MAIN].update_one(
            {"business_name": body.business_name,
             "scan_date":     result.get("scan_date")},
            {"$set": {k: v for k, v in {
                "client_bin": body.client_bin,
                "lead_id":    body.lead_id,
            }.items() if v}},
        )
    except Exception:
        pass
    return result


@router.get("/api/seo/unlinked/results")
async def results_endpoint(client_bin: str | None = Query(default=None)):
    db = _db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    if not client_bin:
        # Admin / global view — last 20 scans
        cursor = db[COLLECTION_MAIN].find(
            {}, projection={"_id": 0},
        ).sort("ts", -1)
        return {"scans": await cursor.to_list(length=20)}
    grouped = await get_reclamation_status(db, client_bin)
    return {"client_bin": client_bin, "groups": grouped}


@router.post("/api/seo/unlinked/outreach")
async def outreach_endpoint(body: _OutreachBody, request: Request):
    """Bug-fix #182 (R22): admin auth required. Sends real outreach
    email via RESEND — unauthenticated abuse turns the platform into
    a spam engine impersonating AUREM's domain."""
    from utils.admin_guard import verify_admin
    verify_admin(request.headers.get("Authorization", ""))
    db = _db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    lead = body.lead or {}
    if body.client_bin and not lead:
        # Hydrate lead from business_profiles
        try:
            prof = await db.business_profiles.find_one(
                {"bin": body.client_bin},
                projection={"_id": 0, "business_name": 1, "website_url": 1,
                              "email": 1, "phone": 1, "industry": 1},
            ) or {}
            lead = {
                "business_name": prof.get("business_name"),
                "website":       prof.get("website_url"),
                "email":         prof.get("email"),
                "phone":         prof.get("phone"),
                "category":      prof.get("industry") or "local business",
            }
        except Exception:
            pass
    return await send_reclamation_outreach(db, body.mention_id, lead)


@router.patch("/api/seo/unlinked/status")
async def status_endpoint(body: _StatusBody):
    db = _db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    if body.status not in ALLOWED_STATUSES:
        raise HTTPException(400, f"status must be one of {list(ALLOWED_STATUSES)}")
    ok = await update_mention_status(db, body.mention_id, body.status,
                                       body.notes or "")
    return {"ok": ok}


@router.get("/api/seo/unlinked/stats")
async def stats_endpoint(client_bin: str | None = Query(default=None)):
    db = _db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    q = {"client_bin": client_bin} if client_bin else {}
    try:
        docs = await db[COLLECTION_MAIN].find(
            q, projection={"_id": 0, "mentions": 1, "total_unlinked": 1},
        ).to_list(length=500)
        total_scans = len(docs)
        total_unlinked = sum(d.get("total_unlinked", 0) for d in docs)
        sent_count = reclaimed_count = ignored_count = 0
        for d in docs:
            for m in (d.get("mentions") or []):
                st = m.get("status") or "pending"
                if st == "outreach_sent":
                    sent_count += 1
                elif st == "reclaimed":
                    reclaimed_count += 1
                elif st == "ignored":
                    ignored_count += 1
        # Monthly reclaimed from status history
        month_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        try:
            month_reclaimed = await db[COLLECTION_HIST].count_documents(
                {"status": "reclaimed", "ts": {"$gte": month_cutoff}},
            )
        except Exception:
            month_reclaimed = 0
        return {
            "total_scans":            total_scans,
            "total_unlinked":         total_unlinked,
            "outreach_sent":          sent_count,
            "reclaimed":              reclaimed_count,
            "ignored":                ignored_count,
            "this_month_reclaimed":   month_reclaimed,
        }
    except Exception as e:
        raise HTTPException(500, f"stats failed: {type(e).__name__}")


@router.get("/api/seo/unlinked/health")
async def health_endpoint():
    db = _db()
    return await unlinked_mentions_health(db)
