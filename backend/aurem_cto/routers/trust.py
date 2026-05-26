"""
aurem_cto.routers.trust — Gap 3 (iter D-33)

Surfaces existing DB data only. Zero new collections except
`aurem_cto_public_gallery` for opt-in showcase.

Routes (all mounted under /aurem-cto/trust/* and /aurem-cto/gallery/*):
  GET  /aurem-cto/trust/deploy-count   (public — total successful deploys)
  GET  /aurem-cto/trust/uptime         (public — last-24h uptime %)
  GET  /aurem-cto/gallery              (public — opted-in projects)
  POST /aurem-cto/gallery/opt-in       (auth  — flip project into gallery)
  POST /aurem-cto/gallery/opt-out      (auth  — remove from gallery)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..services.auth import current_dev
from ..services.db import require_db

router = APIRouter(tags=["AUREM CTO Trust"])


# ─── Deploy count ────────────────────────────────────────────────────
@router.get("/trust/deploy-count")
async def deploy_count() -> dict[str, Any]:
    """Aggregates across every deploy-history collection in the DB."""
    db = require_db()
    # Use the collections we discovered in the D-33 DB scan.
    targets = [
        ("developer_deploy_runs",   {"status": "ok"}),
        ("github_deployments",      {"status": {"$in": ["success", "ok"]}}),
        ("deploy_events",           {"status": {"$in": ["success", "ok"]}}),
        ("push_deployments",        {"status": {"$in": ["success", "ok"]}}),
        ("deployment_log",          {"status": {"$in": ["success", "ok"]}}),
    ]
    total = 0
    by_source: dict[str, int] = {}
    for coll, q in targets:
        try:
            n = await db[coll].count_documents(q)
        except Exception:
            n = 0
        by_source[coll] = n
        total += n
    return {"total_successful_deploys": total, "by_source": by_source}


# ─── Uptime badge ────────────────────────────────────────────────────
@router.get("/trust/uptime")
async def uptime() -> dict[str, Any]:
    """Returns the rolling 24h uptime % from external_uptime_pings."""
    db = require_db()
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    coll = db.external_uptime_pings
    try:
        total = await coll.count_documents({"ts": {"$gte": since}})
        ok    = await coll.count_documents(
            {"ts": {"$gte": since}, "status": {"$in": ["up", "ok", 200]}})
    except Exception:
        total = ok = 0
    pct = round((ok / total * 100), 2) if total else None
    return {
        "window_hours":   24,
        "total_pings":    total,
        "successful":     ok,
        "uptime_percent": pct,
        "status":         "green" if (pct or 0) >= 99
                          else "yellow" if (pct or 0) >= 95
                          else "red" if pct is not None else "unknown",
    }


# ─── Public gallery ──────────────────────────────────────────────────
@router.get("/gallery")
async def gallery() -> dict[str, Any]:
    db = require_db()
    cur = db.aurem_cto_public_gallery.find(
        {"opted_in": True},
        {"_id": 0},
    ).sort("opted_in_at", -1).limit(60)
    rows = [d async for d in cur]
    # Hydrate from onboarding_projects so the gallery shows up-to-date
    # name/tagline/progress without duplicating data.
    if rows:
        ids = [r["project_id"] for r in rows]
        proj_cur = db.onboarding_projects.find(
            {"project_id": {"$in": ids}},
            {"_id": 0, "project_id": 1, "name": 1, "progress": 1,
             "phase": 1, "manifest": 1, "preview_url": 1},
        )
        proj_map = {p["project_id"]: p async for p in proj_cur}
        for r in rows:
            p = proj_map.get(r["project_id"]) or {}
            r["name"]        = p.get("name")
            r["tagline"]     = (p.get("manifest") or {}).get("tagline")
            r["progress"]    = p.get("progress")
            r["phase"]       = p.get("phase")
            r["preview_url"] = p.get("preview_url")
    return {"projects": rows}


class GalleryToggleBody(BaseModel):
    project_id: str = Field(..., min_length=3, max_length=60)


@router.post("/gallery/opt-in")
async def gallery_opt_in(body: GalleryToggleBody,
                          authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    proj = await db.onboarding_projects.find_one(
        {"project_id": body.project_id, "user_id": me["user_id"]},
        {"_id": 0},
    )
    if not proj:
        raise HTTPException(404, "project_not_found")
    await db.aurem_cto_public_gallery.update_one(
        {"project_id": body.project_id},
        {"$set": {
            "project_id":  body.project_id,
            "user_id":     me["user_id"],
            "opted_in":    True,
            "opted_in_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "opted_in": True}


@router.post("/gallery/opt-out")
async def gallery_opt_out(body: GalleryToggleBody,
                           authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    await db.aurem_cto_public_gallery.update_one(
        {"project_id": body.project_id, "user_id": me["user_id"]},
        {"$set": {"opted_in": False,
                   "opted_out_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "opted_in": False}
