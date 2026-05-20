"""
Pixel Patches Router — Inbound live-patch engine for aurem-pixel.js
====================================================================
Endpoints (public — auth by api_key query param):
    GET  /api/pixel/patches?key=<api_key>   -- returns pending patches for this site
    POST /api/pixel/patches/report           -- receives application results from the pixel

Patch shape:
    { id, type: 'meta'|'jsonld'|'css'|'js'|'attr'|'html',
      selector?, html?, content?, css?, code?, attrs? }

Pulls from `pending_pixel_patches` collection (written by auto_fix_engine / ai_repair_router).
"""

import os
import logging
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pixel", tags=["Pixel Patches"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(503, "Database not available")
    return _db


async def _resolve_tenant_by_api_key(db, api_key: str) -> Optional[Dict[str, Any]]:
    """Look up api_keys by plaintext key OR SHA-256 hash. Returns owner info or None.
    Supports BOTH schemas: legacy plaintext (aurem_rr_*) and new hashed (rr_live_*)."""
    if not api_key:
        return None
    try:
        # Try plaintext first (AUREM-style legacy keys)
        plaintext = await db.api_keys.find_one(
            {"key": api_key, "is_active": True},
            {"_id": 0, "tenant_id": 1, "owner_email": 1, "business_name": 1, "business_id": 1, "permissions": 1, "created_at": 1, "last_used": 1},
        )
        if plaintext:
            await db.api_keys.update_one(
                {"key": api_key},
                {"$set": {"last_used": datetime.now(timezone.utc).isoformat()}, "$inc": {"hit_count": 1}},
            )
            return {
                "tenant_id": plaintext.get("tenant_id", ""),
                "email": (plaintext.get("owner_email") or "").lower(),
                "business_name": plaintext.get("business_name", ""),
                "key_format": "legacy_plaintext",
            }

        # Hashed lookup (new format)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        doc = await db.api_keys.find_one(
            {"$or": [{"key_hash": key_hash}, {"api_key_hash": key_hash}], "active": True},
            {"_id": 0, "tenant_id": 1, "email": 1, "client_name": 1},
        )
        if doc:
            await db.api_keys.update_one(
                {"$or": [{"key_hash": key_hash}, {"api_key_hash": key_hash}]},
                {"$set": {"last_used": datetime.now(timezone.utc).isoformat()}, "$inc": {"usage_count": 1}},
            )
            return {
                "tenant_id": doc.get("tenant_id", ""),
                "email": (doc.get("email") or "").lower(),
                "business_name": doc.get("client_name", ""),
                "key_format": "hashed",
            }
        return None
    except Exception as e:
        logger.warning(f"[PIXEL] API key lookup failed: {e}")
        return None


@router.get("/patches")
async def get_patches(key: str = Query(..., description="Customer API key")):
    """Return all pending patches for the given api_key's tenant."""
    db = _get_db()
    owner = await _resolve_tenant_by_api_key(db, key)
    if not owner:
        return {"patches": [], "error": "invalid_key"}

    tenant_id = owner.get("tenant_id") or owner.get("email", "")

    cursor = db.pending_pixel_patches.find(
        {
            "tenant_id": tenant_id,
            "status": {"$in": ["pending", "approved"]},
        },
        {"_id": 0, "id": 1, "type": 1, "selector": 1, "html": 1, "content": 1, "css": 1, "code": 1, "attrs": 1, "created_at": 1},
    ).sort("created_at", 1).limit(50)

    patches = [p async for p in cursor]
    return {"patches": patches, "count": len(patches), "tenant_id": tenant_id}


class PatchReport(BaseModel):
    api_key: Optional[str] = None
    key: Optional[str] = None  # alt field
    patch_id: str
    status: str = Field(..., description="applied | failed | rolled_back")
    error: Optional[str] = None
    url: Optional[str] = None
    session_id: Optional[str] = None


@router.post("/patches/report")
async def report_patch_result(body: PatchReport):
    """Log the outcome of a patch application. Used for canary rollout decisions."""
    db = _get_db()
    api_key = body.api_key or body.key or ""
    owner = await _resolve_tenant_by_api_key(db, api_key) or {}
    tenant_id = owner.get("tenant_id") or owner.get("email", "")

    doc = {
        "tenant_id": tenant_id,
        "patch_id": body.patch_id,
        "status": body.status,
        "error": body.error,
        "url": body.url,
        "session_id": body.session_id,
        "reported_at": datetime.now(timezone.utc).isoformat(),
        "ttl_at": datetime.now(timezone.utc),  # Iter 206: enable 30-day TTL
    }
    await db.patch_reports.insert_one(doc)

    # If patch applied successfully, mark the pending patch as deployed
    if body.status == "applied":
        await db.pending_pixel_patches.update_one(
            {"id": body.patch_id, "tenant_id": tenant_id},
            {"$set": {"status": "deployed", "deployed_at": datetime.now(timezone.utc).isoformat()}},
        )
    elif body.status in ("failed", "rolled_back"):
        await db.pending_pixel_patches.update_one(
            {"id": body.patch_id, "tenant_id": tenant_id},
            {"$inc": {"failure_count": 1}, "$set": {"last_error": body.error or "unknown", "last_failed_at": datetime.now(timezone.utc).isoformat()}},
        )
        # Auto-disable after 3 failures
        p = await db.pending_pixel_patches.find_one({"id": body.patch_id, "tenant_id": tenant_id}, {"_id": 0, "failure_count": 1})
        if p and p.get("failure_count", 0) >= 3:
            await db.pending_pixel_patches.update_one(
                {"id": body.patch_id, "tenant_id": tenant_id},
                {"$set": {"status": "disabled"}},
            )

    return {"success": True}


@router.get("/health")
async def health():
    return {"status": "ok", "service": "pixel-patches"}


# ═══════════════════════════════════════════════════════════════
# PIXEL STATUS — admin + customer can check install health
# ═══════════════════════════════════════════════════════════════

@router.get("/status")
async def pixel_status_by_key(key: str = Query(..., description="API key")):
    """Public endpoint — returns installation status for a given API key.
    Meant for customer portal + admin to show 'Pixel active / not installed'.
    """
    db = _get_db()
    owner = await _resolve_tenant_by_api_key(db, key)
    if not owner:
        return {"connected": False, "reason": "invalid_or_inactive_key"}

    tenant_id = owner.get("tenant_id", "")

    # Fetch key doc for last_used + counters (legacy + hashed both supported)
    key_doc = await db.api_keys.find_one(
        {"$or": [{"key": key}, {"key_hash": hashlib.sha256(key.encode()).hexdigest()},
                 {"api_key_hash": hashlib.sha256(key.encode()).hexdigest()}]},
        {"_id": 0, "last_used": 1, "hit_count": 1, "usage_count": 1, "created_at": 1, "key": 1, "key_preview": 1},
    ) or {}

    last_used = key_doc.get("last_used")
    total_hits = int(key_doc.get("hit_count") or key_doc.get("usage_count") or 0)

    # Count recent patch reports + events in last 24h
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    events_24h = await db.patch_reports.count_documents({"tenant_id": tenant_id, "reported_at": {"$gte": cutoff}})

    connected = bool(last_used) or total_hits > 0 or events_24h > 0

    return {
        "connected": connected,
        "tenant_id": tenant_id,
        "business_name": owner.get("business_name", ""),
        "email": owner.get("email", ""),
        "last_ping": last_used,
        "total_hits": total_hits,
        "events_24h": events_24h,
        "created_at": key_doc.get("created_at"),
        "key_preview": key_doc.get("key_preview") or (key[:14] + "..." + key[-4:] if len(key) > 20 else key),
        "format": owner.get("key_format", "unknown"),
    }


# ═══════════════════════════════════════════════════════════════
# LIGHTWEIGHT EVENT INGESTION — capture page_view, engagement, scroll, etc.
# (Pixel posts to this endpoint too; previously nothing was receiving events.)
# ═══════════════════════════════════════════════════════════════

class PixelEvent(BaseModel):
    api_key: Optional[str] = None
    key: Optional[str] = None
    event: str
    url: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@router.get("/events")
async def list_pixel_events(
    key: str = Query(..., description="Customer API key"),
    limit: int = Query(50, ge=1, le=500),
    since_hours: int = Query(24, ge=1, le=720),
):
    """List recent pixel events for a given API key's tenant."""
    db = _get_db()
    owner = await _resolve_tenant_by_api_key(db, key)
    if not owner:
        return {"events": [], "count": 0, "error": "invalid_or_inactive_key"}

    tenant_id = owner.get("tenant_id") or ""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()

    cursor = db.pixel_events.find(
        {"tenant_id": tenant_id, "received_at": {"$gte": cutoff}},
        {"_id": 0, "event": 1, "url": 1, "session_id": 1, "data": 1, "received_at": 1, "client_timestamp": 1},
    ).sort("received_at", -1).limit(limit)
    events = [e async for e in cursor]

    # Aggregate
    total_24h = await db.pixel_events.count_documents({"tenant_id": tenant_id, "received_at": {"$gte": cutoff}})
    total_all = await db.pixel_events.count_documents({"tenant_id": tenant_id})

    # Top pages
    pipeline = [
        {"$match": {"tenant_id": tenant_id, "received_at": {"$gte": cutoff}, "event": "page_view"}},
        {"$group": {"_id": "$url", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    top_pages = []
    async for p in db.pixel_events.aggregate(pipeline):
        top_pages.append({"url": p["_id"], "views": p["count"]})

    # Unique sessions
    sessions_24h = await db.pixel_events.distinct("session_id", {"tenant_id": tenant_id, "received_at": {"$gte": cutoff}})
    unique_sessions = len([s for s in sessions_24h if s])

    return {
        "events": events,
        "count": len(events),
        "stats": {
            "total_events_24h": total_24h,
            "total_events_all_time": total_all,
            "unique_sessions_24h": unique_sessions,
            "top_pages": top_pages,
        },
        "tenant_id": tenant_id,
        "business_name": owner.get("business_name", ""),
    }


@router.post("/events")
async def ingest_pixel_event(body: PixelEvent):
    db = _get_db()
    api_key = body.api_key or body.key or ""
    owner = await _resolve_tenant_by_api_key(db, api_key) or {}
    tenant_id = owner.get("tenant_id") or ""

    doc = {
        "tenant_id": tenant_id,
        "email": owner.get("email", ""),
        "event": body.event,
        "url": body.url or "",
        "session_id": body.session_id or "",
        "data": body.data or {},
        "received_at": datetime.now(timezone.utc).isoformat(),
        "client_timestamp": body.timestamp,
        # Iteration 206 — BSON Date for real TTL auto-expiry (90 days on pixel_events)
        "ttl_at": datetime.now(timezone.utc),
    }
    # Batch-first with automatic fallback to direct insert.
    # Safe-mode: if batching fails for any reason, the service falls back
    # to insert_one() — so behaviour is identical to pre-optimization.
    try:
        from services.pixel_event_buffer import enqueue_event, set_db as set_pb_db
        set_pb_db(db)
        await enqueue_event(doc)
    except Exception as e:
        logger.warning(f"[PixelIngest] buffer path failed: {e} — using direct insert fallback")
        await db.pixel_events.insert_one(doc)
    # iter 322 — pixel agent fan-out (visitor_intel, form_capture, error_healer)
    try:
        # Set business_id on the event so agent collections stay BIN-scoped.
        # tenant_id and business_id are aliases at this layer; pixel ingest
        # historically uses tenant_id, but downstream BIN-scoped tables key
        # off business_id.
        agent_doc = dict(doc)
        if owner.get("business_id"):
            agent_doc["business_id"] = owner["business_id"]
        elif tenant_id:
            agent_doc["business_id"] = tenant_id
        from services.pixel_agents import fan_out as _pixel_fan_out
        await _pixel_fan_out(db, agent_doc)
    except Exception as _agent_err:
        logger.debug(f"[PixelIngest] agent fan-out skipped: {_agent_err}")
    # Update last seen on the workspace
    if tenant_id:
        await db.aurem_workspaces.update_one(
            {"owner_id": tenant_id},
            {"$set": {"pixel_last_seen": doc["received_at"]}, "$inc": {"pixel_event_count": 1}},
        )
    return {"ok": True}


@router.get("/admin/customer-status")
async def admin_customer_pixel_status(email: str = Query(..., description="Customer email"), key: Optional[str] = None):
    """Admin utility: given a customer email, show their pixel install status + recent events.
    Note: not JWT-guarded because pixel_patches_router intentionally has no auth layer
    (served from a public path). In production, sit this behind an admin gate via ingress.
    """
    db = _get_db()
    # Find their active API key
    key_doc = None
    async for k in db.api_keys.find({"$or": [{"email": email}, {"owner_email": email}], "$and": [{"$or": [{"active": True}, {"is_active": True}]}]}, {"_id": 0}):
        key_doc = k
        break
    if not key_doc:
        return {"found": False, "message": "No active API key for this customer"}

    tenant_id = key_doc.get("tenant_id", "")
    plain = key_doc.get("key", "")
    total_events = await db.pixel_events.count_documents({"tenant_id": tenant_id}) if tenant_id else 0

    recent = []
    if tenant_id:
        cursor = db.pixel_events.find({"tenant_id": tenant_id}, {"_id": 0}).sort("received_at", -1).limit(20)
        recent = [e async for e in cursor]

    from datetime import timedelta
    d24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    events_24h = await db.pixel_events.count_documents({"tenant_id": tenant_id, "received_at": {"$gte": d24}}) if tenant_id else 0

    return {
        "found": True,
        "email": email,
        "tenant_id": tenant_id,
        "business_name": key_doc.get("business_name") or key_doc.get("client_name", ""),
        "key_preview": key_doc.get("key_preview") or (plain[:14] + "..." + plain[-4:] if plain else ""),
        "api_key": plain or "(hashed — not retrievable)",
        "last_used": key_doc.get("last_used"),
        "created_at": key_doc.get("created_at"),
        "total_events": total_events,
        "events_24h": events_24h,
        "recent_events": recent,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# F — WordPress plugin: downloadable .zip + auto-register
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/register")
async def pixel_register(payload: Dict[str, Any]):
    """
    Called by WP plugin / Shopify app on activation.
    Body: { "wid": <tenant_id>, "domain": "https://customer.com" }
    Marks aurem_onboarding.pixel_installed=true and triggers post-verify kickoff.
    """
    db = _get_db()
    tenant_id = (payload.get("wid") or payload.get("tenant_id") or "").strip()
    domain = (payload.get("domain") or "").strip()
    if not tenant_id or not domain:
        raise HTTPException(400, "wid and domain required")
    if not domain.startswith("http"):
        domain = "https://" + domain

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.pixel_verification_log.insert_one({
        "url": domain, "tenant_id": tenant_id, "verified_at": now_iso,
        "detected": True, "matched_signatures": ["wp-plugin-self-register"],
        "fetched": True, "source": "wp_plugin_register",
    })
    await db.aurem_onboarding.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "pixel_installed": True, "pixel_installed_at": now_iso, "domain": domain,
            "install_method": "wp_plugin",
        }},
    )
    # Fire-and-forget activation kickoff (mirrors onboarding verify path)
    try:
        import asyncio
        from routers.aurem_onboarding_router import _post_verify_kickoff  # type: ignore
        asyncio.create_task(_post_verify_kickoff(db, tenant_id, domain))
    except Exception as e:
        logger.warning(f"[pixel/register] kickoff failed: {e}")

    return {"ok": True, "tenant_id": tenant_id, "domain": domain}


@router.get("/wp-plugin/{tenant_id}.zip")
async def wp_plugin_zip(tenant_id: str):
    """Generate a per-tenant WordPress plugin .zip on the fly."""
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    origin = os.environ.get("PUBLIC_API_ORIGIN", "https://aurem.live").rstrip("/")
    plugin_php = f"""<?php
/**
 * Plugin Name: AUREM Auto-Repair Pixel
 * Description: Installs the AUREM pixel and auto-registers this site for automatic SEO/speed/security fixes.
 * Version: 1.0.0
 * Author: AUREM
 * License: GPL-2.0+
 */
if (!defined('ABSPATH')) exit;

define('AUREM_TENANT_ID', '{tenant_id}');
define('AUREM_ORIGIN', '{origin}');

add_action('wp_head', function () {{
    $key = esc_attr(AUREM_TENANT_ID);
    $origin = esc_url(AUREM_ORIGIN);
    echo '<script src="' . $origin . '/api/pixel/aurem-pixel.js" data-aurem-key="' . $key . '" async></script>' . "\\n";
}}, 1);

register_activation_hook(__FILE__, function () {{
    $domain = home_url('/');
    wp_remote_post(AUREM_ORIGIN . '/api/pixel/register', array(
        'headers' => array('Content-Type' => 'application/json'),
        'timeout' => 10,
        'body'    => wp_json_encode(array('wid' => AUREM_TENANT_ID, 'domain' => $domain)),
    ));
}});

add_action('admin_notices', function () {{
    echo '<div class="notice notice-success"><p><strong>AUREM</strong> pixel active. SEO + speed fixes are running automatically.</p></div>';
}});
"""
    readme = f"""=== AUREM Auto-Repair Pixel ===
Tenant: {tenant_id}
Install: Upload via WP Admin → Plugins → Add New → Upload Plugin → Activate.
On activation the pixel is injected and your site is auto-registered with AUREM.
"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"aurem-pixel-{tenant_id}/aurem-pixel.php", plugin_php)
        zf.writestr(f"aurem-pixel-{tenant_id}/readme.txt", readme)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="aurem-pixel-{tenant_id}.zip"',
            "Cache-Control": "no-store",
        },
    )
