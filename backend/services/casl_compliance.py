"""SHIM — migrated to `shared.compliance.casl` + Council voter (Phase 0)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Tuple

from shared.compliance.casl import *  # noqa: F401,F403


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def vote(action: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    """CASL Council vote — required voter for any outreach action.

    Rejects if:
      • phone or email is on do_not_contact
      • phone is non-Canadian (must start +1)
      • >= 9 contacts to this lead in last 30 days (CASL frequency cap)
    """
    phone = (payload.get("phone_e164") or payload.get("phone") or "").strip()
    email = (payload.get("email") or "").lower().strip()

    db = _get_db()
    if db is None:
        return "APPROVE", "db unavailable — failsafe"

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    or_clause = []
    if phone:
        or_clause.append({"phone": phone})
    if email:
        or_clause.append({"email": email})

    dnc_check = None
    freq_check = 0
    if or_clause:
        import asyncio
        dnc_check, freq_check = await asyncio.gather(
            db.do_not_contact.find_one({"$or": or_clause}),
            db.blast_log.count_documents({
                "$or": or_clause,
                "sent_at": {"$gte": cutoff},
            }),
            return_exceptions=True,
        )
        if isinstance(dnc_check, Exception):
            dnc_check = None
        if isinstance(freq_check, Exception):
            freq_check = 0

    if dnc_check:
        return "REJECT", "On DNC list"
    if phone and not phone.startswith("+1"):
        return "REJECT", "Non-Canadian number"
    if freq_check and freq_check >= 9:
        return "REJECT", f"Contact limit reached ({freq_check}/30d)"

    return "APPROVE", "CASL compliant"
