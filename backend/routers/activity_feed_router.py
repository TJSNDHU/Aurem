"""
Activity Feed Router — Iteration 213
====================================
Unified "live activity" stream for the System Overview marquee.

GET /api/admin/activity-feed?limit=20

Fuses recent items from:
  • build_log           → 🔨 Builder runs
  • evolver_events      → 🧬 Evolver reviews / hooks
  • evolver_genes       → 🧪 Gene proposals + status flips
  • ora_command_log     → 🎛 ORA Command Center intents
  • system_auto_repairs → 🔁 Website auto-repair scans

Response:
  { items: [{kind, icon, title, detail, ts, tone}, ...], count }
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import jwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Activity Feed"])

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


def _ts(doc: Dict[str, Any], *fields: str) -> str:
    for f in fields:
        v = doc.get(f)
        if v:
            if isinstance(v, datetime):
                return v.astimezone(timezone.utc).isoformat()
            return str(v)
    return datetime.now(timezone.utc).isoformat()


async def _fetch_builds(db, per: int) -> List[Dict[str, Any]]:
    if db is None:
        return []
    out: List[Dict[str, Any]] = []
    docs = await db.build_log.find({}, projection={"_id": 0}).sort("started_at", -1).limit(per).to_list(length=per)
    for d in docs:
        status = d.get("status", "unknown")
        tone = {"success": "good", "failed": "bad", "queued": "gold", "running": "gold"}.get(status, "neutral")
        files = len(d.get("files") or [])
        desc = (d.get("description") or "").strip()
        build_id = d.get("build_id", "")
        out.append({
            "kind": "build",
            "icon": "🔨",
            "title": f"Build {build_id[:8]} — {status}",
            "detail": f"{desc[:110]}{'…' if len(desc) > 110 else ''} · {files} file(s) · {d.get('admin','')}",
            "ts": _ts(d, "started_at"),
            "tone": tone,
            "href": f"/admin/builder/{build_id}" if build_id else None,
        })
    return out


async def _fetch_gene_events(db, per: int) -> List[Dict[str, Any]]:
    if db is None:
        return []
    out: List[Dict[str, Any]] = []
    docs = await db.evolver_events.find({}, projection={"_id": 0}).sort("ts", -1).limit(per).to_list(length=per)
    tone_for = {
        "review_run_success": "good", "review_run_offline": "warn",
        "analyze_failure_success": "good", "analyze_failure_offline": "warn",
        "gene_status_changed": "gold",
    }
    for d in docs:
        kind = d.get("kind", "evolver")
        p = d.get("payload") or {}
        gene_id = p.get("gene_id") or ""
        build_id = p.get("build_id") or ""
        if kind == "gene_status_changed":
            title = f"Gene {p.get('new_status','?').upper()}"
            detail = f"{gene_id or '?'} by {p.get('admin','?')}"
            href = f"/admin/evolver?highlight={gene_id}" if gene_id else "/admin/evolver"
        elif kind == "review_run_success":
            title = "Evolver nightly review"
            detail = f"{p.get('genes_saved',0)} gene(s) saved · {p.get('patterns_learned',0)} pattern(s)"
            href = "/admin/evolver"
        elif kind == "review_run_offline":
            title = "Evolver review — offline"
            detail = str(p.get("reason", "unreachable"))[:120]
            href = "/admin/evolver"
        elif kind.startswith("analyze_failure"):
            title = "Evolver analyzed build fail"
            detail = f"build {build_id[:8] if build_id else '?'} · {p.get('error','')[:80]}"
            href = f"/admin/builder/{build_id}" if build_id else "/admin/evolver"
        else:
            title = kind
            detail = str(p)[:140]
            href = "/admin/evolver"
        out.append({
            "kind": "evolver",
            "icon": "🧬",
            "title": title,
            "detail": detail,
            "ts": _ts(d, "ts"),
            "tone": tone_for.get(kind, "neutral"),
            "href": href,
        })
    return out


async def _fetch_ora(db, per: int) -> List[Dict[str, Any]]:
    if db is None:
        return []
    out: List[Dict[str, Any]] = []
    docs = await db.ora_command_log.find({}, projection={"_id": 0}).sort("timestamp", -1).limit(per).to_list(length=per)
    for d in docs:
        intent = d.get("intent", "UNKNOWN")
        href = None
        if intent == "BUILD":
            href = "/admin/control-center"
        elif intent in ("TEST_ENDPOINT",):
            href = "/admin/control-center"
        elif intent == "IMPERSONATE":
            href = "/admin/impersonation-log"
        out.append({
            "kind": "ora",
            "icon": "🎛",
            "title": f"ORA · {intent}",
            "detail": f"{(d.get('raw') or '')[:120]} → {(d.get('reply_preview') or '')[:60]}",
            "ts": _ts(d, "timestamp"),
            "tone": "good" if d.get("ok") else "warn",
            "href": href,
        })
    return out


async def _fetch_repairs(db, per: int) -> List[Dict[str, Any]]:
    if db is None:
        return []
    out: List[Dict[str, Any]] = []
    docs = await db.system_auto_repairs.find({}, projection={"_id": 0, "repairs": 0})\
        .sort("completed_at", -1).limit(per).to_list(length=per)
    for d in docs:
        score = d.get("overall_score")
        repairs = d.get("issues_total", 0)
        tenant = d.get("tenant_id") or d.get("label") or ""
        out.append({
            "kind": "repair",
            "icon": "🔁",
            "title": f"Auto-repair scan · {d.get('label') or d.get('site_url','')[:40]}",
            "detail": f"score {score}/100 · {repairs} issue(s) · {d.get('critical_count',0)} critical",
            "ts": _ts(d, "completed_at", "scanned_at"),
            "tone": "good" if (score or 0) >= 85 else "warn" if (score or 0) >= 60 else "bad",
            "href": f"/admin/customer/{tenant}" if tenant else None,
        })
    return out


@router.get("/activity-feed")
async def activity_feed(request: Request, limit: int = 20):
    await _require_admin(request)
    if _db is None:
        return {"items": [], "count": 0}
    per = max(3, min(10, (limit // 3) or 5))
    import asyncio as _asyncio
    builds, gene_events, ora, repairs = await _asyncio.gather(
        _fetch_builds(_db, per),
        _fetch_gene_events(_db, per),
        _fetch_ora(_db, per),
        _fetch_repairs(_db, per),
    )
    fused: List[Dict[str, Any]] = builds + gene_events + ora + repairs
    fused.sort(key=lambda x: x.get("ts", ""), reverse=True)
    capped = fused[: min(max(1, limit), 60)]
    return {"items": capped, "count": len(capped)}
