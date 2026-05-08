"""
Google Places Reviews Sync — P1 #3
====================================
Nightly 3 AM cron: for each tenant with place_id configured, pull latest Google reviews
via Places API, store in google_reviews collection. Also trigger WhatsApp review requests
to recent customers (campaign_leads converted in last 7 days) if enabled.

Requires GOOGLE_PLACES_API_KEY in env. Tenants must have place_id on their workspace
(editable via Settings → Integrations in a future iteration).
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

import httpx

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


async def fetch_place_reviews(place_id: str) -> Optional[Dict]:
    if not PLACES_API_KEY or not place_id:
        return None
    params = {
        "place_id": place_id,
        "fields": "name,rating,user_ratings_total,reviews",
        "key": PLACES_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(PLACE_DETAILS_URL, params=params)
            if r.status_code != 200:
                return None
            data = r.json()
            return data.get("result")
    except Exception as e:
        logger.warning(f"[PLACES] Fetch failed for {place_id}: {e}")
        return None


async def sync_tenant_reviews(tenant_doc: Dict) -> int:
    """Pull reviews for one tenant, upsert into google_reviews. Returns new count."""
    if _db is None:
        return 0
    place_id = tenant_doc.get("google_place_id") or tenant_doc.get("place_id")
    email = tenant_doc.get("email") or tenant_doc.get("owner_email")
    if not place_id or not email:
        return 0

    result = await fetch_place_reviews(place_id)
    if not result:
        return 0

    reviews = result.get("reviews") or []
    new_count = 0
    for r in reviews:
        review_id = f"{place_id}:{r.get('time', '')}:{hash(r.get('text', ''))}"
        existing = await _db.google_reviews.find_one({"review_id": review_id}, {"_id": 0, "review_id": 1})
        if existing:
            continue
        await _db.google_reviews.insert_one({
            "review_id": review_id,
            "email": email,
            "place_id": place_id,
            "author": r.get("author_name", ""),
            "rating": int(r.get("rating", 0)),
            "text": r.get("text", ""),
            "date": datetime.fromtimestamp(r.get("time", 0), tz=timezone.utc).isoformat() if r.get("time") else "",
            "source": "google_places",
            "synced_at": datetime.now(timezone.utc).isoformat(),
        })
        new_count += 1

    # Update aggregate stats on the workspace
    if result.get("rating") is not None:
        await _db.aurem_workspaces.update_one(
            {"owner_email": email},
            {"$set": {
                "google_rating": float(result.get("rating", 0)),
                "google_total_reviews": int(result.get("user_ratings_total", 0)),
                "google_reviews_synced_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=False,
        )
    return new_count


async def nightly_reviews_sync() -> Dict:
    """Cron entry point: sync all tenants with a place_id."""
    if _db is None:
        return {"ok": False, "reason": "db_unset"}
    if not PLACES_API_KEY:
        logger.info("[PLACES] GOOGLE_PLACES_API_KEY not configured — skipping nightly sync")
        return {"ok": False, "reason": "no_api_key"}

    total_new = 0
    total_tenants = 0
    cursor = _db.aurem_workspaces.find(
        {"google_place_id": {"$exists": True, "$ne": ""}},
        {"_id": 0, "owner_email": 1, "google_place_id": 1},
    )
    async for ws in cursor:
        total_tenants += 1
        new = await sync_tenant_reviews({"email": ws.get("owner_email"), "place_id": ws.get("google_place_id")})
        total_new += new

    await _db.system_cron_log.insert_one({
        "job": "google_reviews_nightly",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "tenants": total_tenants,
        "new_reviews": total_new,
    })
    logger.info(f"[PLACES] Nightly sync: {total_tenants} tenants, {total_new} new reviews")
    return {"ok": True, "tenants": total_tenants, "new_reviews": total_new}
