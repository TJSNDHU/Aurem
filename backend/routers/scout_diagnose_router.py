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
    # Accept singular `industry` (str) OR plural `industries` (list[str]).
    # Accept `count` OR `limit` as the per-industry cap.
    industry: Optional[str] = None
    industries: Optional[list] = None
    city: str = "Mississauga, ON"
    count: int = 20
    limit: Optional[int] = None  # alias for `count`
    background: Optional[bool] = None  # force async mode (auto-on if >=4 industries)


async def _run_osm_hunt_core(ind_list: list, city: str, per_industry_cap: int,
                              job_id: Optional[str] = None) -> Dict[str, Any]:
    """Shared core logic. Used by both sync and background paths."""
    from services.osm_scout import osm_leads

    overall_written = 0
    overall_skipped_dup = 0
    overall_skipped_no_contact = 0
    overall_raw = 0
    per_industry: list = []

    now = datetime.now(timezone.utc).isoformat()
    city_slug = city.split(",")[0].strip().lower().replace(" ", "-")

    import asyncio as _aio
    osm_tasks = [
        osm_leads(query=industry, location=city,
                  limit=per_industry_cap, radius_m=15000)
        for industry in ind_list
    ]
    osm_results = await _aio.gather(*osm_tasks, return_exceptions=True)

    for industry, res in zip(ind_list, osm_results):
        if isinstance(res, Exception):
            per_industry.append({"industry": industry, "ok": False,
                                  "error": f"{type(res).__name__}: {str(res)[:120]}",
                                  "written": 0})
            continue
        if not res.get("success"):
            per_industry.append({"industry": industry, "ok": False,
                                  "error": res.get("error", "osm_failed"),
                                  "written": 0})
            continue

        leads = res.get("leads", [])
        overall_raw += len(leads)
        written = 0
        skipped_no_contact = 0
        skipped_duplicate = 0

        for lead in leads:
            email = (lead.get("email") or "").strip()
            phone = (lead.get("phone") or "").strip()
            website = (lead.get("website") or "").strip()
            if not (email or phone or website):
                skipped_no_contact += 1
                continue

            existing = await _db.campaign_leads.find_one(
                {"business_name": lead["business_name"], "city": city},
                {"_id": 1},
            )
            if existing:
                skipped_duplicate += 1
                continue

            lead_id = f"osm-{city_slug}-{uuid.uuid4().hex[:10]}"
            doc = {
                "lead_id": lead_id,
                "business_name": lead["business_name"],
                "category":      industry,
                "city":          city,
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

            if website:
                try:
                    from services.apollo_enrichment import enrich_lead_with_apollo_diy
                    _aio.create_task(enrich_lead_with_apollo_diy(
                        _db, lead_id, website,
                    ))
                except Exception as _en:
                    logger.debug(f"[scout-diagnose] enrichment kickoff failed for {lead_id}: {_en}")

        overall_written += written
        overall_skipped_dup += skipped_duplicate
        overall_skipped_no_contact += skipped_no_contact
        per_industry.append({"industry": industry, "ok": True,
                              "raw_returned": len(leads), "written": written,
                              "skipped_duplicate": skipped_duplicate,
                              "skipped_no_contact": skipped_no_contact})
        logger.info(f"[scout-diagnose] OSM {industry!r}@{city!r}: written={written}")

    summary = {
        "success": True,
        "city": city,
        "industries_run": ind_list,
        "raw_returned_total": overall_raw,
        "leads_written_total": overall_written,
        "skipped_duplicate_total": overall_skipped_dup,
        "skipped_no_contact_total": overall_skipped_no_contact,
        "per_industry": per_industry,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist result if this is a background job so caller can poll.
    if job_id and _db is not None:
        await _db.scout_hunt_jobs.update_one(
            {"job_id": job_id},
            {"$set": {**summary, "status": "complete", "job_id": job_id}},
            upsert=True,
        )
    return summary


@router.post("/run-osm-hunt")
async def run_osm_hunt(body: OSMHuntBody = Body(...)):
    """
    Emergency hunt that uses ONLY OpenStreetMap Overpass (no API key).

    Modes:
    • Synchronous (default for ≤3 industries): waits, returns full result.
    • Background  (auto for ≥4 industries, or `background:true`): returns
      a `job_id` immediately. Poll `GET /api/admin/scout/hunt-job/{job_id}`
      for status + result. Avoids ingress 60s timeout when OSM mirrors lag.
    """
    if _db is None:
        raise HTTPException(503, "Database unavailable")

    # Normalize industry list.
    ind_list: list = []
    if body.industries and isinstance(body.industries, list):
        ind_list = [str(x).strip() for x in body.industries if str(x).strip()]
    if body.industry:
        ind_list.append(body.industry.strip())
    seen = set()
    ind_list = [x for x in ind_list if not (x in seen or seen.add(x))]
    if not ind_list:
        raise HTTPException(400, "Provide `industry` (str) or `industries` (list[str]).")

    per_industry_cap = int(body.limit or body.count or 20)

    # Decide sync vs background.
    use_background = body.background if body.background is not None else (len(ind_list) >= 4)

    if not use_background:
        return {
            **(await _run_osm_hunt_core(ind_list, body.city, per_industry_cap)),
            "mode": "sync",
            "enrichment": "Apollo DIY enrichment fired as background task per lead.",
            "next_step": "Visit /api/campaign/why-not-sending to verify funnel.",
        }

    # Background mode — return 202 with job_id; run in background task.
    import asyncio as _aio
    job_id = f"hunt-{uuid.uuid4().hex[:12]}"
    await _db.scout_hunt_jobs.insert_one({
        "job_id": job_id,
        "status": "running",
        "city": body.city,
        "industries": ind_list,
        "per_industry_cap": per_industry_cap,
        "started_at": datetime.now(timezone.utc).isoformat(),
    })
    _aio.create_task(_run_osm_hunt_core(ind_list, body.city, per_industry_cap, job_id=job_id))

    return {
        "success": True,
        "mode": "background",
        "job_id": job_id,
        "status": "running",
        "industries": ind_list,
        "city": body.city,
        "poll_url": f"/api/admin/scout/hunt-job/{job_id}",
        "eta_seconds": min(15 * len(ind_list), 120),
        "next_step": (
            f"GET /api/admin/scout/hunt-job/{job_id} every 10s until "
            f"status='complete'. Then /api/campaign/why-not-sending."
        ),
    }


@router.get("/hunt-job/{job_id}")
async def get_hunt_job(job_id: str):
    """Poll the status + result of a background OSM hunt job."""
    if _db is None:
        raise HTTPException(503, "Database unavailable")
    job = await _db.scout_hunt_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Job not found")
    return job


# ──────────────────────────────────────────────────────────────────────
# Replenish Cron — admin endpoints
# ──────────────────────────────────────────────────────────────────────
@router.get("/cron-status")
async def cron_status():
    """Return cron config + last 10 replenish runs + current queue depth."""
    if _db is None:
        raise HTTPException(503, "Database unavailable")

    from services import scout_replenish_cron as cron

    cities = cron._cities()
    industries = cron._industries()
    cursor = await cron._get_cursor()
    queue_depth = await cron._current_queue_depth()

    runs = []
    async for r in _db.scout_replenish_runs.find(
        {}, {"_id": 0, "summary": 0}
    ).sort("started_at", -1).limit(10):
        runs.append(r)

    return {
        "enabled": True,
        "config": {
            "interval_minutes": cron._interval_min(),
            "queue_target": cron._queue_target(),
            "per_run_cap": cron._per_run_cap(),
            "cities": cities,
            "industries": industries,
            "matrix_size": len(cities) * len(industries),
        },
        "queue_depth_now": queue_depth,
        "next_cell": {
            "city": cities[cursor["city_idx"] % len(cities)],
            "industry": industries[cursor["ind_idx"] % len(industries)],
        },
        "recent_runs": runs,
    }


@router.post("/cron-trigger")
async def cron_trigger(force: bool = True):
    """Manually fire one cron tick (bypasses queue-target check by default)."""
    from services.scout_replenish_cron import replenish_tick
    return await replenish_tick(force=force)
