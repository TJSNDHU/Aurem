"""
Inbound email webhook router — iter 282al-9.

  POST /api/email/inbound       — Resend Inbound / generic webhook receiver
  GET  /api/email/inbound/health
  GET  /api/email/inbound/recent — admin (last 50 inbound replies + intent)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from services.inbound_reply_handler import handle_inbound_reply

logger = logging.getLogger(__name__)
router = APIRouter()

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server  # noqa: WPS433
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


# ─────────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────────
@router.get("/api/email/inbound/health")
async def inbound_health() -> dict:
    db = _get_db()
    return {"ok": True, "service": "inbound_reply_handler",
            "db_attached": db is not None,
            "ts": datetime.now(timezone.utc).isoformat()}


# ─────────────────────────────────────────────────────────────────────
# /inbound — main webhook
# ─────────────────────────────────────────────────────────────────────
class InboundEmail(BaseModel):
    from_: str | None = None
    sender: str | None = None  # alias when "from" is reserved
    to: str | list | None = None
    subject: str | None = None
    text: str | None = None
    html: str | None = None
    in_reply_to: str | None = None
    references: str | None = None

    class Config:
        # Allow client to send "from" (Python keyword) via alias
        populate_by_name = True
        extra = "allow"


@router.post("/api/email/inbound")
async def inbound_webhook(request: Request) -> dict:
    """Accept inbound email from any provider. Normalises a handful of
    common payload shapes (Resend Inbound, SendGrid, custom IMAP feeder)."""
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")

    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="payload must be object")

    # Normalise from-address — try common shapes.
    from_addr = (
        raw.get("from") or raw.get("sender")
        or (raw.get("envelope") or {}).get("from")
        or ""
    )
    if isinstance(from_addr, dict):
        from_addr = from_addr.get("email") or from_addr.get("address") or ""
    if isinstance(from_addr, list) and from_addr:
        from_addr = from_addr[0]
    from_addr = str(from_addr or "").strip()
    # Strip "Name <email@x>" → "email@x"
    import re as _re
    m = _re.search(r"<([^>]+)>", from_addr)
    if m:
        from_addr = m.group(1)

    to_addr = raw.get("to") or raw.get("recipient") or ""
    if isinstance(to_addr, list) and to_addr:
        to_addr = to_addr[0]

    payload = {
        "from": from_addr.lower(),
        "to": to_addr,
        "subject": raw.get("subject") or "",
        "text": raw.get("text") or raw.get("body_plain") or raw.get("body-plain") or "",
        "html": raw.get("html") or raw.get("body_html") or "",
        "in_reply_to": raw.get("in_reply_to") or raw.get("In-Reply-To")
                        or (raw.get("headers") or {}).get("In-Reply-To") or "",
        "references": raw.get("references") or "",
    }
    if not payload["from"]:
        raise HTTPException(status_code=400, detail="from address required")

    db = _get_db()
    result = await handle_inbound_reply(db, payload)

    # iter 322aj — Belt-and-suspenders: even if handle_inbound_reply skips
    # the unified_inbox write (DB connection lost mid-call, etc.), guarantee
    # at least one row lands so the customer-facing OmnichannelHub never
    # misses an inbound email.
    if db is not None and not result.get("inbox_mirrored"):
        try:
            from services.inbox_writer import write_inbox
            await write_inbox(
                db,
                channel="email",
                direction="inbound",
                sender=payload.get("from") or "",
                message=payload.get("text") or payload.get("subject") or "",
                thread_id=result.get("lead_id") or "",
                business_id=result.get("business_id"),
            )
        except Exception:
            pass

    return result


# ─────────────────────────────────────────────────────────────────────
# /inbound/recent — admin glance
# ─────────────────────────────────────────────────────────────────────
def _verify_admin(authorization: Optional[str]) -> None:
    """Light auth — same shape as other admin endpoints. Reuses JWT."""
    if not authorization:
        raise HTTPException(status_code=401, detail="missing token")
    try:
        import os
        import jwt
        token = authorization.replace("Bearer ", "").strip()
        secret = os.environ.get("JWT_SECRET", "")
        if not secret:
            raise HTTPException(status_code=500, detail="JWT_SECRET unset")
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        if not decoded.get("is_admin"):
            raise HTTPException(status_code=403, detail="admin only")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")


@router.get("/api/email/inbound/recent")
async def inbound_recent(authorization: Optional[str] = Header(None)) -> dict:
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        return {"items": [], "total": 0}
    try:
        cur = db.inbound_replies.find(
            {}, projection={"_id": 0, "text": 0, "html": 0},
        ).sort("received_at", -1).limit(50)
        items = [d async for d in cur]
        # Cast datetimes for JSON
        for it in items:
            if isinstance(it.get("received_at"), datetime):
                it["received_at"] = it["received_at"].isoformat()
        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.warning(f"[inbound] recent fetch failed: {e}")
        return {"items": [], "total": 0, "error": str(e)[:200]}
