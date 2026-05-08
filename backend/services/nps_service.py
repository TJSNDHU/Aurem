"""
NPS Service (iter 315c)
=======================
2-tap NPS captured right after a customer saves their edit-portal site
or completes the BUILD verdict.

Public:
  await submit_nps(db, *, token, score, source) -> dict
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DETRACTOR_THRESHOLD = 3
ALERT_PHONE = os.environ.get("FOUNDER_PHONE", "+16134000000")


async def _alert_founder(score: int, site: Dict[str, Any]) -> bool:
    """Fire WhatsApp alert to TJ for any detractor score (≤ 3)."""
    biz = site.get("business_name") or "unknown"
    slug = site.get("slug") or site.get("site_id") or "?"
    body = (
        f"🚨 NPS detractor — {biz}\n"
        f"score: {score}/5  ·  site: {slug}\n"
        f"site_id: {site.get('site_id')}\n"
        f"check edit portal logs immediately."
    )
    try:
        from routers.whatsapp_alerts import send_whatsapp
        out = await send_whatsapp(ALERT_PHONE, body)
        return bool(out and out.get("ok"))
    except Exception as e:
        logger.warning(f"[nps] founder alert failed: {e}")
        return False


async def submit_nps(db, *, token: str, score: int,
                       source: str = "edit_portal") -> Dict[str, Any]:
    """Validate session token → record NPS → alert TJ on detractor."""
    if not isinstance(score, int) or not (1 <= score <= 5):
        return {"ok": False, "error": "score must be 1..5"}
    from services.customer_edit import _resolve_session, _find_site, _hash
    sess = await _resolve_session(db, token)
    site_id: Optional[str] = sess.get("site_id") if sess else None
    # Fallback: token might still be the request token (pre-session click)
    if not site_id:
        rec = await db.edit_sessions.find_one(
            {"token_hash": _hash(token)}, {"_id": 0, "site_id": 1},
        )
        site_id = rec.get("site_id") if rec else None
    if not site_id:
        return {"ok": False, "error": "invalid session"}

    site = await _find_site(db, site_id) or {}
    lead_id = site.get("lead_id")

    # Idempotent within 1 min for the same site_id (stops double-tap dupes)
    now = datetime.now(timezone.utc)
    recent = await db.nps_responses.find_one(
        {"site_id": site_id},
        sort=[("created_at", -1)], projection={"_id": 0, "created_at": 1, "score": 1},
    )
    duplicate = False
    if recent and recent.get("created_at"):
        try:
            prev = datetime.fromisoformat(recent["created_at"])
            if (now - prev).total_seconds() < 60:
                duplicate = True
        except Exception:
            pass

    rec_doc = {
        "nps_id": __import__("uuid").uuid4().hex[:12],
        "site_id": site_id,
        "lead_id": lead_id,
        "score": int(score),
        "source": source,
        "created_at": now.isoformat(),
    }
    if not duplicate:
        await db.nps_responses.insert_one(dict(rec_doc))

    alerted = False
    armed_winback = None
    if score <= DETRACTOR_THRESHOLD and not duplicate:
        alerted = await _alert_founder(score, site)
        try:
            from services.winback_sequence import arm_winback_sequence
            wb = await arm_winback_sequence(
                db, site_id=site_id, lead_id=lead_id, score=int(score))
            armed_winback = wb.get("winback_id") if wb.get("ok") else None
        except Exception as e:
            logger.warning(f"[nps] winback arm failed: {e}")
    return {"ok": True, "nps_id": rec_doc["nps_id"], "score": score,
            "detractor": score <= DETRACTOR_THRESHOLD, "alerted": alerted,
            "winback_armed": armed_winback, "duplicate": duplicate}
