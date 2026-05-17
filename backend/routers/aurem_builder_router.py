"""
AUREM Builder Router — Iteration 211
====================================
Admin-only HTTP surface for the internal builder.

Endpoints
---------
  POST /api/admin/builder/build            — queue a build. Returns {build_id, status:"queued"}
  GET  /api/admin/builder/status/{id}      — poll a running/finished build
  GET  /api/admin/builder/stats            — dashboard stats (total/success/cost/last)
  GET  /api/admin/builder/recent           — recent build rows (?limit=20)

The actual LLM call + file write happens in a FastAPI BackgroundTask so the
client connection never blocks longer than the ingress' 60 s timeout.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import jwt
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/builder", tags=["AUREM Builder"])

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

_db = None


def set_db(db):
    global _db
    _db = db


async def _require_admin(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = payload.get("role", "")
    if role in ("admin", "super_admin") or payload.get("is_admin") or payload.get("is_super_admin"):
        return payload
    raise HTTPException(403, "Admin only")


class BuildRequest(BaseModel):
    description: str = Field(..., min_length=8, max_length=4000)
    model: str | None = None
    sync: bool = False  # sync=True runs inline (blocks up to ~55 s); default False → background
    # iter 281.3 — Phase 2.5 preview: route a build to repair-mode for
    # existing client sites instead of full greenfield "build" mode.
    mode: str = Field("build", pattern="^(build|repair)$")
    repair_report_id: str | None = None  # required when mode='repair'
    target_url: str | None = None  # convenience for repair flow


async def _run_build_and_log(build_id: str, description: str, admin: str, model: str):
    """Background task — persist outcome to build_log under the same build_id."""
    from services import aurem_builder, evolver_client
    try:
        result = await aurem_builder.build_feature(
            _db, description=description, admin=admin, model=model, build_id=build_id,
        )
        # Evolver hook — best-effort, no raise.
        try:
            if result.get("status") == "failed":
                await evolver_client.analyze_failure(
                    _db,
                    build_id=build_id,
                    description=description,
                    files=result.get("files", []),
                    error=result.get("error") or "",
                )
        except Exception as e:
            logger.warning(f"[builder] evolver hook failed: {e}")
    except Exception as e:
        logger.exception("[builder] background run crashed")
        # Mark the pending row as failed so polling sees the error.
        if _db is not None:
            await _db.build_log.update_one(
                {"build_id": build_id},
                {"$set": {"status": "failed", "error": str(e),
                          "finished_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )


@router.post("/build")
async def build(req: BuildRequest, request: Request, background_tasks: BackgroundTasks):
    """Queue a build (async by default) or run inline with sync=true."""
    admin_payload = await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "DB not available")
    from services import aurem_builder

    admin_email = admin_payload.get("email") or admin_payload.get("sub") or "admin"
    model = req.model or aurem_builder.DEFAULT_MODEL

    # iter 281.3 — Phase 2.5: repair mode short-circuits to the website-
    # repair pipeline. The actual fix is queued through that flow, but
    # we still log it under build_log so admins see one unified history.
    if req.mode == "repair":
        if not (req.repair_report_id or req.target_url):
            raise HTTPException(400, "mode='repair' requires repair_report_id or target_url")
        repair_doc = None
        if req.repair_report_id:
            repair_doc = await _db.website_repair_reports.find_one(
                {"report_id": req.repair_report_id}
            )
            if not repair_doc:
                raise HTTPException(404, f"repair report {req.repair_report_id} not found")
        repair_id = aurem_builder.new_build_id()
        now = datetime.now(timezone.utc).isoformat()
        await _db.build_log.insert_one({
            "build_id": repair_id,
            "mode": "repair",
            "description": req.description,
            "repair_report_id": req.repair_report_id,
            "target_url": req.target_url or (repair_doc or {}).get("url"),
            "model": model,
            "admin": admin_email,
            "status": "queued",
            "started_at": now,
            "files": [],
            "notes": [
                "Phase 2.5 repair mode — handled by website_repair_router; "
                "no greenfield build pipeline runs here.",
            ],
            "test_command": None,
            "error": None,
        })
        return {
            "build_id": repair_id,
            "mode": "repair",
            "status": "queued",
            "started_at": now,
            "next_step": (
                f"Open /admin/website-repair to send the offer or create a "
                f"Stripe invoice for report_id {req.repair_report_id}"
            ),
        }

    if req.sync:
        # Inline — caller will see the full result but risks 502 at ingress after 60 s.
        try:
            return await aurem_builder.build_feature(
                _db, description=req.description, admin=admin_email, model=model,
            )
        except Exception as e:
            logger.exception("[builder/build sync] crashed")
            raise HTTPException(500, f"Builder crashed: {e}")

    # Async — insert a "queued" row immediately, schedule background task.
    build_id = aurem_builder.new_build_id()
    now = datetime.now(timezone.utc).isoformat()
    await _db.build_log.insert_one({
        "build_id": build_id,
        "description": req.description,
        "model": model,
        "admin": admin_email,
        "status": "queued",
        "started_at": now,
        "files": [],
        "notes": [],
        "test_command": None,
        "error": None,
    })
    background_tasks.add_task(_run_build_and_log, build_id, req.description, admin_email, model)
    return {"build_id": build_id, "status": "queued", "started_at": now}


@router.get("/status/{build_id}")
async def status(build_id: str, request: Request):
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "DB not available")
    doc = await _db.build_log.find_one({"build_id": build_id}, projection={"_id": 0})
    if not doc:
        raise HTTPException(404, "build_id not found")
    return doc


@router.get("/stats")
async def stats(request: Request):
    await _require_admin(request)
    from services import aurem_builder
    return await aurem_builder.get_stats(_db)


@router.get("/recent")
async def recent(request: Request, limit: int = 20):
    await _require_admin(request)
    from services import aurem_builder
    return {"items": await aurem_builder.list_recent(_db, limit=min(max(1, limit), 100))}
