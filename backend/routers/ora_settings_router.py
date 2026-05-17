"""
ORA Settings Router — iter 322es
=================================
Read/write the founder's ORA CTO platform settings. All settings live
in a single Mongo doc `platform_settings/_id=ora_cto` so the frontend
can show a "Save All" flow.

Endpoints (/api/admin/ora-settings):
  GET   /                       full settings doc (with safe defaults)
  PUT   /                       upsert the whole doc
  PATCH /{section}              partial update of one section
  POST  /github-test            test the saved GitHub PAT
  POST  /export-audit-csv       export ora_tool_invocations as CSV blob

Sections:
  github         { pat, repo, branch_protection, default_branch }
  permissions    { tools_enabled: {<name>: bool}, shell_whitelist: [str] }
  council        { peer_roles: [str], hard_gate: bool, vote_threshold: int }
  notifications  { whatsapp_critical: bool, email_digest_time: "HH:MM",
                    digest_email: str }
  audit          { retention_days: int }

Auth: JWT bearer.
"""
from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/ora-settings", tags=["ora-settings"])

_SECTION_DEFAULTS = {
    "github": {
        "pat":                "",
        "repo":               "",
        "default_branch":     "main",
        "branch_protection":  True,
    },
    "permissions": {
        "tools_enabled":  {},   # filled at runtime from TOOL_REGISTRY
        "shell_whitelist": [],  # extra commands the founder allows beyond _SHELL_WHITELIST
    },
    "council": {
        "peer_roles":     ["security", "backend", "qa", "devops"],
        "hard_gate":      True,
        "vote_threshold": 1,    # # of dissenters required to BLOCK an edit
    },
    "notifications": {
        "whatsapp_critical":  True,
        "email_digest_time":  "06:00",
        "digest_email":       "",
    },
    "audit": {
        "retention_days": 90,
    },
}


def _verify_token(authorization: Optional[str] = None) -> str:
    if not authorization:
        raise HTTPException(401, "Authorization required")
    import jwt
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Authorization required")
    try:
        secret = os.environ.get("JWT_SECRET") or ""
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("email") or payload.get("user_id") or payload.get("sub") or "unknown"
    except Exception:
        raise HTTPException(401, "Invalid token")


def _get_db():
    from server import db
    if db is None:
        raise HTTPException(500, "Database not initialized")
    return db


async def _read_settings(db):
    doc = await db.platform_settings.find_one({"_id": "ora_cto"}) or {}
    # Merge defaults so missing keys appear with safe values
    out = {}
    for section, defaults in _SECTION_DEFAULTS.items():
        cur = doc.get(section) or {}
        if section == "permissions":
            from services.ora_tools import TOOL_REGISTRY
            tools_enabled = dict(cur.get("tools_enabled") or {})
            for name in TOOL_REGISTRY.keys():
                tools_enabled.setdefault(name, True)
            cur["tools_enabled"] = tools_enabled
            cur.setdefault("shell_whitelist", defaults["shell_whitelist"])
        merged = {**defaults, **cur}
        # Mask PAT so it never leaves the server in full
        if section == "github" and merged.get("pat"):
            pat = merged["pat"]
            merged["pat_masked"] = f"{pat[:6]}…{pat[-4:]}" if len(pat) > 12 else "[set]"
            merged.pop("pat", None)
        out[section] = merged
    out["_updated_at"] = doc.get("_updated_at")
    out["_updated_by"] = doc.get("_updated_by")
    return out


# ── Read ──────────────────────────────────────────────────────────────

@router.get("/")
async def get_all(authorization: Optional[str] = Header(None)):
    _verify_token(authorization)
    db = _get_db()
    return {"ok": True, "settings": await _read_settings(db)}


# ── Write ─────────────────────────────────────────────────────────────

class SectionPatch(BaseModel):
    data: dict


@router.put("/")
async def put_all(payload: dict, authorization: Optional[str] = Header(None)):
    """Upsert the entire settings doc. Validates against known
    sections — unknown keys are ignored."""
    actor = _verify_token(authorization)
    db = _get_db()
    settings = payload.get("settings") if isinstance(payload, dict) else None
    if not isinstance(settings, dict):
        raise HTTPException(400, "payload must be {settings: {...}}")
    update_doc: dict = {}
    for section, data in settings.items():
        if section in _SECTION_DEFAULTS and isinstance(data, dict):
            update_doc[section] = data
    if not update_doc:
        raise HTTPException(400, "no recognised sections in payload")
    update_doc["_updated_at"] = datetime.now(timezone.utc).isoformat()
    update_doc["_updated_by"] = actor
    await db.platform_settings.update_one(
        {"_id": "ora_cto"}, {"$set": update_doc}, upsert=True,
    )
    return {"ok": True, "settings": await _read_settings(db)}


@router.patch("/{section}")
async def patch_section(
    section: str,
    patch: SectionPatch,
    authorization: Optional[str] = Header(None),
):
    actor = _verify_token(authorization)
    if section not in _SECTION_DEFAULTS:
        raise HTTPException(404, f"unknown section: {section}")
    db = _get_db()
    update = {
        section:         {**(_SECTION_DEFAULTS[section]), **patch.data},
        "_updated_at":   datetime.now(timezone.utc).isoformat(),
        "_updated_by":   actor,
    }
    await db.platform_settings.update_one(
        {"_id": "ora_cto"}, {"$set": update}, upsert=True,
    )
    return {"ok": True, "section": section,
             "settings": await _read_settings(db)}


# ── GitHub PAT test ───────────────────────────────────────────────────

@router.post("/github-test")
async def github_test(authorization: Optional[str] = Header(None)):
    """Hit https://api.github.com/user with the saved PAT to verify it
    still works."""
    _verify_token(authorization)
    db = _get_db()
    doc = await db.platform_settings.find_one({"_id": "ora_cto"}) or {}
    pat = (doc.get("github") or {}).get("pat") or ""
    if not pat:
        raise HTTPException(400, "no GitHub PAT saved")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {pat}",
                          "Accept": "application/vnd.github+json"},
            )
        if r.status_code == 200:
            j = r.json()
            return {"ok": True, "login": j.get("login"),
                    "scopes": r.headers.get("x-oauth-scopes")}
        return {"ok": False, "status": r.status_code,
                "error": r.text[:240]}
    except Exception as e:
        raise HTTPException(500, f"github test failed: {type(e).__name__}: {e}")


# ── Audit export ──────────────────────────────────────────────────────

@router.post("/export-audit-csv")
async def export_audit_csv(
    limit: int = 5000,
    authorization: Optional[str] = Header(None),
):
    _verify_token(authorization)
    db = _get_db()
    rows = await db.ora_tool_invocations.find(
        {}, {"_id": 0}
    ).sort("ts", -1).limit(max(1, min(limit, 50_000))).to_list(length=limit)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ts", "tool", "actor", "ok", "elapsed_ms", "error", "args_json"])
    import json as _json
    for r in rows:
        writer.writerow([
            r.get("ts"), r.get("tool"), r.get("actor"),
            r.get("ok"), r.get("elapsed_ms"),
            (r.get("error") or "")[:300],
            _json.dumps(r.get("args"), default=str)[:500],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ora-audit.csv"},
    )


@router.get("/_/health")
async def health():
    db = _get_db()
    return {
        "ok": True, "scope": "ora_settings",
        "has_settings_doc": (await db.platform_settings.find_one({"_id":"ora_cto"})) is not None,
    }
