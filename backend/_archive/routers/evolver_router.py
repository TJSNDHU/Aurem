"""
AUREM Evolver Router — Iteration 212
====================================
Admin-only HTTP surface for the EvoMap Evolver integration.

  GET  /api/admin/evolver/status                — configured? reachable? gene counts
  GET  /api/admin/evolver/genes                 — list genes (?status=pending_review|approved|rejected)
  POST /api/admin/evolver/genes/{id}/approve    — admin flips gene to "approved"
  POST /api/admin/evolver/genes/{id}/reject     — admin flips gene to "rejected"
  POST /api/admin/evolver/run-review            — fire a nightly review on-demand

Every gene the Evolver emits is stored as status="pending_review" unless
EVOLVER_ALLOW_SELF_MODIFY=true. AUREM never auto-applies without admin sign-off.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/evolver", tags=["AUREM Evolver"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
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


@router.get("/status")
async def status(request: Request):
    await _require_admin(request)
    from services import evolver_client
    return await evolver_client.get_status(_db)


@router.get("/genes")
async def genes(request: Request, status: Optional[str] = None, limit: int = 50):
    await _require_admin(request)
    from services import evolver_client
    items = await evolver_client.list_genes(_db, status=status, limit=min(max(1, limit), 200))
    return {"items": items, "count": len(items)}


@router.post("/genes/{gene_id}/approve")
async def approve(gene_id: str, request: Request):
    admin = await _require_admin(request)
    from services import evolver_client
    ok = await evolver_client.set_gene_status(
        _db, gene_id, "approved", admin.get("email") or admin.get("sub") or "admin",
    )
    if not ok:
        raise HTTPException(404, "Gene not found")
    return {"ok": True, "gene_id": gene_id, "status": "approved"}


@router.post("/genes/{gene_id}/reject")
async def reject(gene_id: str, request: Request):
    admin = await _require_admin(request)
    from services import evolver_client
    ok = await evolver_client.set_gene_status(
        _db, gene_id, "rejected", admin.get("email") or admin.get("sub") or "admin",
    )
    if not ok:
        raise HTTPException(404, "Gene not found")
    return {"ok": True, "gene_id": gene_id, "status": "rejected"}


@router.post("/run-review")
async def run_review(request: Request):
    """Fire a nightly-style review on-demand. Best-effort — no-op if Evolver offline."""
    await _require_admin(request)
    from services import evolver_client
    return await evolver_client.run_review(_db)
