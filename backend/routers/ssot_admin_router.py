"""
SSOT Admin — read/edit AUREM_CONFIG with full audit trail.

Edits are stored in `ssot_overrides` MongoDB collection (not Python source).
public_config() merges overrides on read, so changes apply instantly with no
backend restart required.

Endpoints:
  GET    /api/admin/ssot/config       — full editable config (admin)
  PUT    /api/admin/ssot/update       — patch a field (logged)
  GET    /api/admin/ssot/log          — recent change history
  POST   /api/admin/ssot/reset        — clear all overrides
  GET    /api/admin/ssot/morning-brief — ORA digest for last 7d
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from aurem_ssot.aurem_config import AUREM_CONFIG, public_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/ssot", tags=["SSOT Admin"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is None:
        try:
            import server
            _db = getattr(server, "db", None)
        except Exception:
            pass
    return _db


def _verify_admin(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Admin authentication required")
    import jwt
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
            algorithms=["HS256"],
        )
        if payload.get("is_admin") or payload.get("is_super_admin") or payload.get("role") in ("admin", "super_admin"):
            return payload
        # Bug-fix #84 — was previously `or payload.get("email")` which made
        # every authenticated user effectively admin (every JWT has email).
        # Now check the admin whitelist explicitly.
        from utils.admin_guard import is_admin_email
        if is_admin_email(payload.get("email")):
            payload["is_admin"] = True
            return payload
        raise HTTPException(403, "Admin only")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")


# ─── Override merge helpers ─────────────────────────────────────────────────

EDITABLE_PATHS = {
    "pricing.starter.price_cad":      {"type": "int",    "label": "Starter price (CAD)"},
    "pricing.starter.price_display":  {"type": "string", "label": "Starter display"},
    "pricing.growth.price_cad":       {"type": "int",    "label": "Growth price (CAD)"},
    "pricing.growth.price_display":   {"type": "string", "label": "Growth display"},
    "pricing.enterprise.price_cad":   {"type": "int",    "label": "Enterprise price (CAD)"},
    "pricing.enterprise.price_display":{"type": "string","label": "Enterprise display"},
    "trial.days":                     {"type": "int",    "label": "Trial days"},
    "trial.reminder_day":             {"type": "int",    "label": "Reminder day"},
    "company.tagline":                {"type": "string", "label": "Hero tagline"},
    "company.email_support":          {"type": "string", "label": "Support email"},
    "company.email_sales":            {"type": "string", "label": "Sales email"},
    "company.phone":                  {"type": "string", "label": "Phone"},
    "company.address":                {"type": "string", "label": "Address"},
    "company.name":                   {"type": "string", "label": "Company name"},
}


def _get_path(d: dict, path: str):
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _set_path(d: dict, path: str, value: Any):
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


async def _load_overrides(db) -> dict:
    """Return path→value of all active overrides."""
    if db is None:
        return {}
    out = {}
    async for doc in db.ssot_overrides.find({"active": True}, {"_id": 0, "path": 1, "value": 1}):
        out[doc["path"]] = doc["value"]
    return out


async def _merged_config(db) -> dict:
    """Deep-copy AUREM_CONFIG and apply overrides — fresh per call."""
    import copy
    cfg = copy.deepcopy(AUREM_CONFIG)
    overrides = await _load_overrides(db)
    for path, value in overrides.items():
        _set_path(cfg, path, value)
    return cfg


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/config")
async def get_editable_config(authorization: Optional[str] = Header(None)):
    """Return full editable config + which fields are overridden."""
    _verify_admin(authorization)
    db = _get_db()
    overrides = await _load_overrides(db) if db is not None else {}
    cfg = await _merged_config(db) if db is not None else AUREM_CONFIG
    return {
        "config": cfg,
        "overrides": overrides,
        "editable_paths": EDITABLE_PATHS,
    }


class UpdatePayload(BaseModel):
    path: str
    value: Any
    reason: Optional[str] = None


@router.put("/update")
async def update_field(body: UpdatePayload, authorization: Optional[str] = Header(None)):
    user = _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not available")

    if body.path not in EDITABLE_PATHS:
        raise HTTPException(400, f"Field not editable: {body.path}")

    spec = EDITABLE_PATHS[body.path]
    val = body.value
    # Type coercion
    if spec["type"] == "int":
        try:
            val = int(val)
        except (TypeError, ValueError):
            raise HTTPException(400, f"{body.path} must be int")

    # Read previous merged value (override or default)
    cur = await _merged_config(db)
    old = _get_path(cur, body.path)

    if old == val:
        return {"ok": True, "noop": True, "value": val}

    now = datetime.now(timezone.utc).isoformat()
    # Upsert override
    await db.ssot_overrides.update_one(
        {"path": body.path, "active": True},
        {"$set": {"path": body.path, "value": val, "active": True, "updated_at": now}},
        upsert=True,
    )

    # Auto-sync display if numeric price changed
    if body.path.endswith(".price_cad"):
        display_path = body.path.replace(".price_cad", ".price_display")
        await db.ssot_overrides.update_one(
            {"path": display_path, "active": True},
            {"$set": {"path": display_path, "value": f"${val}", "active": True, "updated_at": now}},
            upsert=True,
        )

    await db.ssot_change_log.insert_one({
        "field": body.path,
        "old_value": old,
        "new_value": val,
        "changed_by": user.get("email", "unknown"),
        "reason": body.reason or "",
        "timestamp": now,
    })
    return {"ok": True, "field": body.path, "old": old, "new": val}


@router.get("/log")
async def get_change_log(limit: int = 50, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        return {"changes": []}
    docs = await db.ssot_change_log.find({}, {"_id": 0}).sort("timestamp", -1).limit(int(limit)).to_list(limit)
    return {"changes": docs}


@router.post("/reset")
async def reset_overrides(authorization: Optional[str] = Header(None)):
    user = _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not available")
    res = await db.ssot_overrides.update_many({"active": True}, {"$set": {"active": False}})
    await db.ssot_change_log.insert_one({
        "field": "_reset",
        "old_value": f"{res.modified_count} overrides",
        "new_value": "all_cleared",
        "changed_by": user.get("email", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "cleared": int(res.modified_count)}


@router.get("/morning-brief")
async def morning_brief_digest(days: int = 7, authorization: Optional[str] = Header(None)):
    """ORA Brain digest: SSOT changes in last N days for Morning Brief."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        return {"summary": "", "changes": []}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
    changes = await db.ssot_change_log.find(
        {"timestamp": {"$gte": cutoff}, "field": {"$ne": "_reset"}},
        {"_id": 0},
    ).sort("timestamp", -1).to_list(50)

    if not changes:
        return {"summary": "", "changes": []}

    lines = []
    for c in changes[:5]:
        f = c.get("field", "")
        old = c.get("old_value", "?")
        new = c.get("new_value", "?")
        ts = c.get("timestamp", "")
        try:
            day = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%a %b %-d")
        except Exception:
            day = ts[:10]
        lines.append(f"{f}: {old} → {new} on {day}")

    summary = (
        f"SSOT changes in last {days} days ({len(changes)} total):\n  - "
        + "\n  - ".join(lines)
    )
    return {"summary": summary, "changes": changes, "count": len(changes)}
