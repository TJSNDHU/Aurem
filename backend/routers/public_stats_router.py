"""
Public AUREM Stats — homepage ticker + stats bar.
No auth. Cached/lightweight. Conservative DB reads.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["Public Stats"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not url:
            return None
        _db = AsyncIOMotorClient(url)[os.environ.get("DB_NAME", "aurem_db")]
    except Exception:
        return None
    return _db


@router.get("/aurem-stats")
async def aurem_stats():
    """Homepage stats — fast, public, sane defaults if DB hiccups."""
    db = _get_db()
    out = {
        "active_workspaces": 0,
        "total_patches_applied": 0,
        "reroots_applied": 0,
        "uptime_pct": 99,
    }
    if db is None:
        return out

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        active = await db.pixel_verification_log.distinct("url", {"detected": True, "verified_at": {"$gte": cutoff}})
        out["active_workspaces"] = len(active) or await db.workspaces.count_documents({}) or 0
    except Exception as e:
        logger.debug(f"[public-stats] active_workspaces calc fail: {e}")

    try:
        out["total_patches_applied"] = await db.patch_reports.count_documents({"status": "applied"})
    except Exception as e:
        logger.debug(f"[public-stats] applied calc fail: {e}")

    try:
        out["reroots_applied"] = await db.patch_reports.count_documents({
            "status": "applied",
            "url": {"$regex": "reroots", "$options": "i"},
        }) or await db.auto_fix_patches.count_documents({
            "site_url": {"$regex": "reroots", "$options": "i"},
            "status": "auto_patched",
        })
    except Exception as e:
        logger.debug(f"[public-stats] reroots calc fail: {e}")

    return out


@router.get("/pixel-stats")
async def pixel_stats(domain: str = Query(..., description="Domain to query")):
    """Per-domain pixel stats for homepage strip."""
    db = _get_db()
    if db is None:
        return {"domain": domain, "applied": 0, "pending": 0}
    try:
        applied = await db.patch_reports.count_documents({
            "status": "applied",
            "url": {"$regex": domain.replace(".", r"\."), "$options": "i"},
        }) or await db.auto_fix_patches.count_documents({
            "site_url": {"$regex": domain.replace(".", r"\."), "$options": "i"},
            "status": "auto_patched",
        })
        pending = await db.auto_fix_patches.count_documents({
            "site_url": {"$regex": domain.replace(".", r"\."), "$options": "i"},
            "status": {"$in": ["pending", "queued", "generated"]},
        })
        return {"domain": domain, "applied": applied, "pending": pending}
    except Exception:
        return {"domain": domain, "applied": 0, "pending": 0}


@router.get("/config")
async def get_public_config():
    """
    iter 293 — SSOT: serve canonical AUREM config to clients.
    iter 294 — Merges live overrides from ssot_overrides collection.
    """
    try:
        from aurem_ssot.aurem_config import public_config, AUREM_CONFIG
        import copy
        cfg_full = copy.deepcopy(AUREM_CONFIG)
        # Apply overrides
        db = _get_db()
        if db is not None:
            try:
                async for ov in db.ssot_overrides.find({"active": True}, {"_id": 0, "path": 1, "value": 1}):
                    parts = ov["path"].split(".")
                    cur = cfg_full
                    for p in parts[:-1]:
                        cur = cur.setdefault(p, {}) if isinstance(cur, dict) else cur
                    if isinstance(cur, dict):
                        cur[parts[-1]] = ov["value"]
            except Exception as e:
                logger.debug(f"[public-config] override merge skip: {e}")
        # Build the same public slice but from merged dict
        return {
            "company": cfg_full["company"],
            "trial": cfg_full["trial"],
            "pricing": cfg_full["pricing"],
            "plan_features": cfg_full["plan_features"],
            "scan_widget": cfg_full["scan_widget"],
            "copy": {
                "hero_headline": cfg_full["company"]["tagline"],
                "trial_cta": f"Start Free {cfg_full['trial']['days']}-Day Trial",
                "trial_days": cfg_full["trial"]["days"],
                "trial_note": "No credit card required",
                "cancel_note": "Cancel anytime in one click",
            },
        }
    except Exception as e:
        logger.error(f"[public-config] error: {e}")
        return {"error": "config unavailable"}
