"""
Scout Diagnose Router
=====================
Live health-check for every lead-source backend Aurem can use to hunt
businesses. Surfaces the EXACT reason a hunt is starving:
  • Google Places — quota suspended / billing disabled / key revoked
  • Yelp Fusion   — 401 (revoked key)
  • OSM Overpass  — community-API reachable / blocked
  • Tavily        — fallback (disabled by default)

Endpoints (all admin-gated by JWT in production):
    GET  /api/admin/scout/diagnose
        Returns { google_places, yelp, osm, tavily, summary }
        Each backend probed with a real (tiny) live call.

    POST /api/admin/scout/run-osm-hunt
        Body: { industry: str, city: str, count: int=20 }
        Emergency hunt that bypasses Google/Yelp and writes leads into
        `campaign_leads` so the auto-blast engine can resume sends while
        the user fixes Google/Yelp billing.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/scout", tags=["Admin · Scout Diagnose"])

_db = None


def set_db(db):
    global _db
    _db = db


# ──────────────────────────────────────────────────────────────────────
# Individual probes
# ──────────────────────────────────────────────────────────────────────
async def _probe_google_places() -> Dict[str, Any]:
    key = (
        os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
        or os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip()
    )
    if not key:
        return {"backend": "google_places", "ok": False, "status": "no_key",
                "detail": "GOOGLE_PLACES_API_KEY not set in env"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": key,
                    "X-Goog-FieldMask": "places.displayName",
                },
                json={"textQuery": "coffee in Toronto", "pageSize": 1},
            )
        if r.status_code == 200:
            count = len((r.json() or {}).get("places", []))
            return {"backend": "google_places", "ok": True, "status": "200",
                    "detail": f"Live probe returned {count} place(s)"}
        # Surface the actual Google error code so the user knows what to fix.
        body = r.text[:300]
        reason = "unknown"
        if "SUSPENDED" in body or "suspended" in body:
            reason = "key_suspended"
        elif "REQUEST_DENIED" in body or "API key not valid" in body:
            reason = "key_invalid"
        elif "OVER_QUERY_LIMIT" in body or "RESOURCE_EXHAUSTED" in body:
            reason = "quota_exhausted"
        elif "BILLING_DISABLED" in body or "billing" in body.lower():
            reason = "billing_disabled"
        return {
            "backend": "google_places", "ok": False,
            "status": f"http_{r.status_code}", "reason": reason,
            "detail": body,
            "fix": (
                "Open https://console.cloud.google.com/billing — verify the "
                "project tied to this key has an active billing account "
                "AND that the Places API (New) is enabled. If the key was "
                "SUSPENDED, you'll need to create a fresh key under "
                "APIs & Services → Credentials and update "
                "GOOGLE_PLACES_API_KEY in /app/backend/.env."
            ),
        }
    except Exception as e:
        return {"backend": "google_places", "ok": False,
                "status": "exception", "detail": str(e)[:200]}


async def _probe_yelp() -> Dict[str, Any]:
    key = os.environ.get("YELP_API_KEY", "").strip()
    if not key:
        return {"backend": "yelp", "ok": False, "status": "no_key",
                "detail": "YELP_API_KEY not set in env"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://api.yelp.com/v3/businesses/search",
                headers={"Authorization": f"Bearer {key}"},
                params={"location": "Toronto, ON", "term": "coffee", "limit": 1},
            )
        if r.status_code == 200:
            count = len((r.json() or {}).get("businesses", []))
            return {"backend": "yelp", "ok": True, "status": "200",
                    "detail": f"Live probe returned {count} business(es)"}
        reason = "unknown"
        if r.status_code == 401:
            reason = "key_invalid_or_revoked"
        elif r.status_code == 429:
            reason = "rate_limited"
        return {
            "backend": "yelp", "ok": False,
            "status": f"http_{r.status_code}", "reason": reason,
            "detail": r.text[:300],
            "fix": (
                "Open https://www.yelp.com/developers/v3/manage_app — if the "
                "app shows Active, regenerate the API key and update "
                "YELP_API_KEY in /app/backend/.env. If the app is gone, "
                "create a new Fusion app (free, 5000 calls/day)."
            ),
        }
    except Exception as e:
        return {"backend": "yelp", "ok": False,
                "status": "exception", "detail": str(e)[:200]}


async def _probe_osm() -> Dict[str, Any]:
    # Minimal valid Overpass QL — pull 1 cafe near downtown Toronto.
    q = ('[out:json][timeout:10];'
         '(node["amenity"="cafe"](around:1000,43.6532,-79.3832););'
         'out tags 1;')
    try:
        async with httpx.AsyncClient(timeout=15,
                                     headers={"User-Agent":
                                              "AUREM-AutomationPlatform/diagnose"}) as c:
            r = await c.post(
                "https://overpass-api.de/api/interpreter",
                content=f"data={q}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if r.status_code == 200:
            count = len((r.json() or {}).get("elements", []))
            return {"backend": "osm_overpass", "ok": True, "status": "200",
                    "detail": f"Live probe returned {count} element(s)"}
        return {"backend": "osm_overpass", "ok": False,
                "status": f"http_{r.status_code}",
                "detail": r.text[:200]}
    except Exception as e:
        return {"backend": "osm_overpass", "ok": False,
                "status": "exception", "detail": str(e)[:200]}


async def _probe_tavily() -> Dict[str, Any]:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    enabled = os.environ.get("HUNT_ENABLE_WEB_FALLBACK", "0").strip() in ("1", "true", "yes")
    if not key:
        return {"backend": "tavily", "ok": False, "status": "no_key",
                "detail": "TAVILY_API_KEY not set"}
    return {
        "backend": "tavily", "ok": bool(key), "status": "key_present",
        "fallback_enabled": enabled,
        "detail": (
            "Tavily is the LAST-RESORT fallback. Off by default because "
            "it returns HTML page titles, not real businesses. Set "
            "HUNT_ENABLE_WEB_FALLBACK=1 only if all 3 primary scouts die."
        ),
    }


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────
@router.get("/diagnose")
async def diagnose():
    """Live health-check every lead-source backend in one call."""
    gp = await _probe_google_places()
    yelp = await _probe_yelp()
    osm = await _probe_osm()
    tav = await _probe_tavily()
    healthy = [p for p in (gp, yelp, osm) if p.get("ok")]
    can_hunt = bool(healthy)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "can_hunt": can_hunt,
            "healthy_backends": [p["backend"] for p in healthy],
            "dead_backends":   [p["backend"] for p in (gp, yelp, osm) if not p.get("ok")],
            "recommended_action": (
                "All primary scouts healthy — hunt should produce real leads."
                if can_hunt and len(healthy) >= 2 else
                "At least one primary scout (OSM) healthy — hunts will work but "
                "limited to industries with OSM tag mappings. Fix Google "
                "Places + Yelp keys for full coverage."
                if can_hunt else
                "ALL primary scouts dead. Fix at least Google Places OR Yelp "
                "key (see `fix` field of each probe). OSM is free + needs "
                "no key — investigate network/firewall if it's also failing."
            ),
        },
        "probes": {
            "google_places": gp,
            "yelp":          yelp,
            "osm_overpass":  osm,
            "tavily":        tav,
        },
    }


class OSMHuntBody(BaseModel):
    industry: str
    city: str = "Mississauga, ON"
    count: int = 20


@router.post("/run-osm-hunt")
async def run_osm_hunt(body: OSMHuntBody = Body(...)):
    """
    Emergency hunt that uses ONLY OpenStreetMap Overpass (no API key required).
    Writes results straight into `campaign_leads` collection with status='queued'
    so the auto-blast engine picks them up on the next cycle.

    Use this when Google Places / Yelp are dead and you need leads RIGHT NOW.
    """
    if _db is None:
        raise HTTPException(503, "Database unavailable")

    from services.osm_scout import osm_leads

    res = await osm_leads(
        query=body.industry,
        location=body.city,
        limit=int(body.count),
        radius_m=15000,
    )

    if not res.get("success"):
        return {
            "success": False,
            "error": res.get("error", "osm_failed"),
            "industry": body.industry,
            "city": body.city,
            "leads_written": 0,
        }

    leads = res.get("leads", [])
    written = 0
    skipped_no_contact = 0
    skipped_duplicate = 0

    now = datetime.now(timezone.utc).isoformat()
    city_slug = body.city.split(",")[0].strip().lower().replace(" ", "-")

    for lead in leads:
        # Aurem outreach needs at least phone OR email OR website.
        email = (lead.get("email") or "").strip()
        phone = (lead.get("phone") or "").strip()
        website = (lead.get("website") or "").strip()
        if not (email or phone or website):
            skipped_no_contact += 1
            continue

        # Dedupe by business_name + city.
        existing = await _db.campaign_leads.find_one(
            {"business_name": lead["business_name"], "city": body.city},
            {"_id": 1},
        )
        if existing:
            skipped_duplicate += 1
            continue

        lead_id = f"osm-{city_slug}-{uuid.uuid4().hex[:10]}"
        doc = {
            "lead_id": lead_id,
            "business_name": lead["business_name"],
            "category":      body.industry,
            "city":          body.city,
            "phone":         phone,
            "email":         email,
            "website_url":   website,
            "website":       website,
            "address":       lead.get("address") or "",
            "rating":        lead.get("rating"),
            "review_count":  lead.get("review_count") or 0,
            "source":        "osm_overpass_admin_hunt",
            "status":        "queued",
            "noise_flag":    False,
            "created_at":    now,
            "ingested_via":  "admin_run_osm_hunt",
        }
        await _db.campaign_leads.insert_one(doc)
        written += 1

    logger.info(
        f"[scout-diagnose] OSM hunt complete: industry={body.industry!r} "
        f"city={body.city!r} written={written} duplicate={skipped_duplicate} "
        f"no_contact={skipped_no_contact}"
    )

    return {
        "success": True,
        "industry": body.industry,
        "city": body.city,
        "raw_returned": len(leads),
        "leads_written": written,
        "skipped_duplicate": skipped_duplicate,
        "skipped_no_contact": skipped_no_contact,
        "next_step": (
            "auto_blast_engine will pick these up on next cycle. Visit "
            "/api/campaign/auto-blast/diagnose-blocker to verify the "
            "eligibility funnel sees them."
        ) if written else "Try a different industry — see osm_scout.INDUSTRY_TO_OSM_TAGS.",
    }
