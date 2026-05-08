"""
Admin Financials Router — Iteration 203
========================================
Apple Pay / Stripe checkout sessions + Canadian HST/GST financial records.

GET /api/admin/financials/transactions     — Stripe payment_transactions (paginated)
GET /api/admin/financials/hst-summary      — HST/GST breakdown by quarter
GET /api/admin/financials/health
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/financials", tags=["Admin Financials"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

# Canadian HST / GST rates by province (2026)
CA_TAX_RATES = {
    "ON": 0.13, "NB": 0.15, "NS": 0.15, "NL": 0.15, "PE": 0.15,
    "QC": 0.14975, "BC": 0.12, "AB": 0.05, "SK": 0.11, "MB": 0.12,
    "YT": 0.05, "NT": 0.05, "NU": 0.05,
}

_db = None


def set_db(db):
    global _db
    _db = db


async def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    if payload.get("role") != "admin" and not payload.get("is_admin") and not payload.get("is_super_admin"):
        raise HTTPException(403, "Admin only")
    return payload


def _get_db():
    if _db is None:
        raise HTTPException(503, "DB not available")
    return _db


@router.get("/health")
async def health():
    return {"status": "ok", "service": "admin-financials"}


@router.get("/transactions")
async def transactions(request: Request, limit: int = 50):
    """Recent Apple Pay / embedded Stripe transactions."""
    await _require_admin(request)
    db = _get_db()
    limit = max(1, min(limit, 200))
    try:
        cursor = db.payment_transactions.find(
            {},
            {"_id": 0, "session_id": 1, "email": 1, "plan": 1, "amount": 1,
             "currency": 1, "status": 1, "payment_status": 1, "mode": 1, "created_at": 1},
        ).sort("created_at", -1).limit(limit)
        rows = await cursor.to_list(limit)
    except Exception as e:
        logger.warning(f"[Financials] tx load failed: {e}")
        rows = []

    total_paid = sum(float(r.get("amount") or 0) for r in rows if r.get("payment_status") == "paid")
    return {
        "count": len(rows),
        "total_paid_usd": round(total_paid, 2),
        "transactions": rows,
    }


@router.get("/hst-summary")
async def hst_summary(request: Request, months: int = 3):
    """Quarterly HST/GST summary — sums paid transactions and computes tax collected."""
    await _require_admin(request)
    db = _get_db()
    months = max(1, min(months, 24))

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30 * months)).isoformat()
    try:
        cursor = db.payment_transactions.find(
            {"payment_status": "paid", "created_at": {"$gte": cutoff}},
            {"_id": 0},
        )
        paid = await cursor.to_list(5000)
    except Exception:
        paid = []

    # Group by month
    buckets: Dict[str, Dict[str, Any]] = {}
    for t in paid:
        month = (t.get("created_at") or "")[:7] or "unknown"
        amt = float(t.get("amount") or 0)
        province = (t.get("province") or "ON").upper()
        rate = CA_TAX_RATES.get(province, 0.13)
        tax = round(amt * rate / (1 + rate), 2)  # back-out tax from tax-inclusive
        b = buckets.setdefault(month, {"revenue": 0.0, "tax_collected": 0.0, "count": 0})
        b["revenue"] += amt
        b["tax_collected"] += tax
        b["count"] += 1

    rows = [{"month": m, **v} for m, v in sorted(buckets.items(), reverse=True)]
    total_revenue = round(sum(r["revenue"] for r in rows), 2)
    total_tax = round(sum(r["tax_collected"] for r in rows), 2)

    return {
        "months_window": months,
        "total_revenue": total_revenue,
        "total_tax_collected": total_tax,
        "by_month": rows,
        "note": "Tax computed using Canadian HST/GST rates. Stripe automatic_tax handles real tax at checkout time.",
    }
