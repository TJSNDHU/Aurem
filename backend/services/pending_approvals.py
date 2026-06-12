"""
services/pending_approvals.py — thin write-helper for the
`db.pending_approvals` collection (the same one `ai_repair_router`
uses for SEO/GEO/Accessibility fix proposals).

Iter 325f Phase 1.3 — introduced so Shannon Security, ORA CTO repair
proposals, and any other future "founder-approved fix" producer can
share one consistent schema instead of inlining ad-hoc inserts
in twenty different routers.

Schema (collection: `pending_approvals`):
    approval_id   : str    (uuid4[:12])
    type          : str    (e.g. 'security_fix', 'code_error', 'crash',
                            'endpoint_failure', 'seo', 'geo', 'a11y')
    severity      : str    (low | medium | high | critical)
    title         : str    (one-line founder-facing summary)
    detail        : str    (fix suggestion / proposed diff / etc.)
    source        : str    (which scanner created this — 'shannon',
                            'ora_cto', etc.)
    fingerprint   : str    (dedup key — same fingerprint within 24h is
                            de-duplicated)
    status        : str    ('pending_approval' | 'approved' | 'rejected'
                            | 'auto_applied' | 'cancelled')
    tier          : int    (1 = auto-apply after cancel window,
                            2 = requires founder Telegram approval)
    auto_execute_at : Optional[str]  (ISO ts when a tier-1 will fire)
    metadata      : dict   (free-form scan context)
    created_at    : str    (ISO ts)
    created_by    : str    (subsystem name)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# 5-minute cancel window for tier-1 auto-fixes (per founder spec).
TIER1_CANCEL_WINDOW_S = 5 * 60
DEDUP_WINDOW_H = 24


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def create_pending_approval(
    *,
    type: str,
    title: str,
    detail: str = "",
    severity: str = "medium",
    source: str = "unknown",
    fingerprint: Optional[str] = None,
    tier: int = 2,
    metadata: Optional[Dict[str, Any]] = None,
    db=None,
) -> Dict[str, Any]:
    """Create (or dedupe) a pending approval row.

    Returns the row dict (without `_id`). On dedup, returns the existing
    row with ``"deduped": True``.
    """
    db = db or _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    fp = fingerprint or f"{type}:{title[:80]}"
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=DEDUP_WINDOW_H)).isoformat()

    # Dedup window — same fingerprint within 24h reuses the row.
    existing = await db.pending_approvals.find_one(
        {"fingerprint": fp, "business_id": FOUNDER_BIN,
         "status": {"$in": ["pending_approval", "approved", "auto_applied"]},
         "created_at": {"$gte": cutoff}},
        {"_id": 0},
    )
    if existing:
        try:
            await db.pending_approvals.update_one(
                {"approval_id": existing["approval_id"],
                 "business_id": FOUNDER_BIN},
                {"$inc": {"occurrences": 1}, "$set": {"last_seen": now.isoformat()}},
            )
        except Exception as e:
            logger.debug(f"[pending_approvals] dedup increment failed: {e}")
        return {**existing, "deduped": True}

    approval_id = str(uuid.uuid4())[:12]
    row = {
        "approval_id": approval_id,
        "type": type,
        "severity": severity,
        "title": title[:200],
        "detail": detail[:4000],
        "source": source,
        "fingerprint": fp,
        "status": "pending_approval",
        "tier": int(tier) if tier in (1, 2) else 2,
        "metadata": metadata or {},
        "occurrences": 1,
        "created_at": now.isoformat(),
        "last_seen": now.isoformat(),
        "created_by": source,
    }
    if row["tier"] == 1:
        row["auto_execute_at"] = (
            now + timedelta(seconds=TIER1_CANCEL_WINDOW_S)
        ).isoformat()

    row["business_id"] = FOUNDER_BIN
    await db.pending_approvals.insert_one(row)
    return {k: v for k, v in row.items() if k != "_id"}
