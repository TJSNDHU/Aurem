"""
Design Extract Admin Router — iter 322ep
=========================================
Exposes the existing `services.design_extractor.extract_design()` (DTCG +
shadcn variable extraction via `npx designlang`) as a first-class admin API
so the founder can pull competitor brand tokens from the UI.

Endpoints (under /api/admin/design-extract):
  POST  /run        body: {url}             → live extraction (≤60s)
  GET   /history?limit=20                   → recent extracts from logs
  GET   /summary                            → counts + success rate (admin tile)
  GET   /export/{format}?url=...            → tailwind.config.js | variables.css | tokens.json
  POST  /compare    body: {url_a,url_b}     → side-by-side colors/fonts diff

Auth: JWT in `Authorization: Bearer <token>` header. Re-uses
`_verify_token()` pattern from admin_cache_router.

Wired from the `design_extract_logs` collection (already populated with
413 historical extracts at the time of writing).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/design-extract", tags=["design-extract"])


def _verify_token(authorization: Optional[str] = None) -> str:
    """JWT auth — matches admin_cache_router pattern."""
    if not authorization:
        raise HTTPException(401, "Authorization required")
    import jwt
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Authorization required")
    try:
        secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("user_id", payload.get("id", payload.get("sub", "unknown")))
    except Exception:
        raise HTTPException(401, "Invalid token")


class ExtractRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=400)


class CompareRequest(BaseModel):
    url_a: str = Field(..., min_length=4, max_length=400)
    url_b: str = Field(..., min_length=4, max_length=400)


def _get_db():
    from server import db
    if db is None:
        raise HTTPException(500, "Database not initialized")
    return db


@router.post("/run")
async def run_extract(req: ExtractRequest, authorization: Optional[str] = Header(None)):
    """Extract DTCG design tokens for the given URL via `npx designlang`.

    Returns flat `{colors, fonts, spacing, shadows, components, score, raw_files}`.
    Logs the run to `design_extract_logs` so it appears in /history.
    """
    user_id = _verify_token(authorization)
    db = _get_db()

    from services.design_extractor import extract_design
    started = datetime.now(timezone.utc)
    result = await extract_design(req.url, timeout=60, db=db)
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error", "extract_failed"),
            "url": req.url,
            "took_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        }
    # Persist the FULL extraction so the founder can re-open it later
    try:
        save_doc = {
            "url": result["source_url"],
            "ok": True,
            "colors": result.get("colors"),
            "fonts": result.get("fonts"),
            "spacing": result.get("spacing"),
            "shadows": result.get("shadows"),
            "components": result.get("components"),
            "score": result.get("score"),
            "raw_files": result.get("raw_files"),
            "duration_s": result.get("duration_s"),
            "ts": started.isoformat(),
            "extracted_by": user_id,
        }
        ins = await db.design_extracts.insert_one(save_doc)
        save_doc["id"] = str(ins.inserted_id)
        save_doc.pop("_id", None)
    except Exception as e:
        logger.warning(f"[design-extract] save failed: {e}")
        save_doc = {**result, "id": None, "extracted_by": user_id}

    return {"ok": True, "extract": save_doc}


@router.get("/history")
async def history(
    limit: int = Query(20, ge=1, le=100),
    authorization: Optional[str] = Header(None),
):
    """Recent extracts. Newest first."""
    _verify_token(authorization)
    db = _get_db()
    cursor = (
        db.design_extracts.find(
            {"ok": True},
            {"_id": 0, "raw_files": 0},
        )
        .sort("ts", -1)
        .limit(limit)
    )
    rows = await cursor.to_list(length=limit)
    # Fallback: if `design_extracts` is empty, surface the existing
    # `design_extract_logs` (lighter format).
    if not rows:
        cursor2 = (
            db.design_extract_logs.find(
                {"ok": True},
                {"_id": 0},
            )
            .sort("ts", -1)
            .limit(limit)
        )
        rows = await cursor2.to_list(length=limit)
    return {"ok": True, "rows": rows, "count": len(rows)}


@router.get("/summary")
async def summary(authorization: Optional[str] = Header(None)):
    """Tile-style stats for the admin dashboard."""
    _verify_token(authorization)
    db = _get_db()
    total = await db.design_extract_logs.count_documents({})
    ok = await db.design_extract_logs.count_documents({"ok": True})
    fails = total - ok
    last_7d = await db.design_extract_logs.count_documents({
        "ts": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}
    })
    explicit = await db.design_extracts.count_documents({})
    last = await db.design_extracts.find_one({}, {"_id": 0, "raw_files": 0}, sort=[("ts", -1)])
    return {
        "ok": True,
        "total_logs": total,
        "success": ok,
        "failed": fails,
        "success_rate": round(ok / total * 100, 1) if total else None,
        "last_7d": last_7d,
        "saved_extracts": explicit,
        "last_extract": last,
    }


@router.get("/export/{fmt}")
async def export_tokens(
    fmt: str,
    url: str = Query(..., min_length=4, max_length=400),
    authorization: Optional[str] = Header(None),
):
    """Download tailwind.config.js | variables.css | tokens.json | shadcn.css for the latest extract of `url`.

    Returns file-typed payload. Caller chooses Content-Type from the
    `format` parameter — useful for one-click export from the admin UI.
    """
    _verify_token(authorization)
    db = _get_db()
    fmt = fmt.lower().strip()
    valid = {
        "tailwind": "tailwind_js",
        "css": "variables_css",
        "shadcn": "shadcn_css",
        "tokens": "tokens_json",
        "theme": "theme_js",
        "voice": "voice_json",
        "visual": "visual_dna",
    }
    if fmt not in valid:
        raise HTTPException(400, f"Unknown format. Try: {list(valid.keys())}")

    norm = url.strip().rstrip("/")
    doc = await db.design_extracts.find_one(
        {"url": {"$regex": norm.replace(".", r"\.")}},
        {"_id": 0, "raw_files": 1, "url": 1, "ts": 1},
        sort=[("ts", -1)],
    )
    if not doc:
        raise HTTPException(404, f"No extract found for {url}. Run extraction first.")

    raw = (doc.get("raw_files") or {}).get(valid[fmt])
    if not raw:
        raise HTTPException(404, f"{fmt} not present in this extract (npx designlang may have skipped it).")
    return {
        "ok": True,
        "url": doc["url"],
        "format": fmt,
        "content": raw,
        "ts": doc.get("ts"),
        "size_bytes": len(raw),
    }


@router.post("/compare")
async def compare(req: CompareRequest, authorization: Optional[str] = Header(None)):
    """Run two extracts in parallel and return side-by-side comparison."""
    _verify_token(authorization)
    db = _get_db()
    from services.design_extractor import extract_design
    import asyncio

    a_task = extract_design(req.url_a, timeout=60, db=db)
    b_task = extract_design(req.url_b, timeout=60, db=db)
    a, b = await asyncio.gather(a_task, b_task, return_exceptions=True)

    def _safe(x):
        if isinstance(x, Exception):
            return {"ok": False, "error": str(x)[:240]}
        return x

    return {"ok": True, "a": _safe(a), "b": _safe(b)}


@router.get("/_/health")
async def design_health():
    """Pillars-Map probe — surface availability."""
    db = _get_db()
    total = await db.design_extract_logs.count_documents({})
    return {"ok": True, "scope": "design_extract", "logs": total}
