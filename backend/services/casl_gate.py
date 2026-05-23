"""
services/casl_gate.py — iter 327m

Canada's Anti-Spam Legislation (CASL) compliance gate.

ORA-CTO has TWO outreach surfaces:
  1. `pillars/sales/routes/auto_blast.py` (blast pipeline)
  2. `services/armed_outreach.py` + `services/aurem_outreach_templates.py`
     (agent-direct outreach)

The blast pipeline already filters against `db.do_not_contact` at lines
481 and 590 of auto_blast.py. The agent-direct path did NOT — that's
the gap the audit (2026-02-23) found. This module is the single
source of truth used by BOTH paths so the rule is enforced everywhere.

Public API
----------
    await is_blocked_by_casl(db, email=..., phone=...) -> dict
       Returns {"blocked": bool, "reason": str, "matched_field": "email"|"phone"|None}

    await suppress(db, email=None, phone=None, reason="...", source="...") -> dict
       Adds to db.do_not_contact (idempotent on email+phone key).

Behaviour
---------
- Email comparison is case-insensitive + whitespace-stripped.
- Phone comparison is digits-only.
- Empty / missing email AND phone → blocked=True (we don't ship to
  unknown recipients — that's spam).
- Any Mongo failure → blocked=True (fail-closed; safer than
  accidentally emailing an opted-out recipient because the gate
  glitched).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def _norm_email(e: Optional[str]) -> str:
    return (e or "").strip().lower()


def _norm_phone(p: Optional[str]) -> str:
    if not p:
        return ""
    return re.sub(r"\D", "", str(p))


async def is_blocked_by_casl(
    db,
    *,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> dict:
    """Return whether (email, phone) should be SUPPRESSED before send.

    Fail-closed: every error path returns blocked=True so we never
    accidentally email an opted-out recipient because of an outage."""
    ne, np_ = _norm_email(email), _norm_phone(phone)
    if not ne and not np_:
        return {"blocked": True, "reason": "no_identifier",
                 "matched_field": None}
    if db is None:
        logger.warning("[casl_gate] db handle missing — fail-closed")
        return {"blocked": True, "reason": "db_unavailable",
                 "matched_field": None}
    try:
        # Build $or only with non-empty fields so we don't match
        # everyone whose email == "".
        clauses = []
        if ne:
            clauses.append({"email": ne})
        if np_:
            clauses.append({"phone": np_})
        hit = await db.do_not_contact.find_one({"$or": clauses}, {"_id": 0})
        if hit:
            return {
                "blocked":        True,
                "reason":         "on_do_not_contact_list",
                "matched_field":  "email" if hit.get("email") == ne else "phone",
                "row":            {k: v for k, v in hit.items()
                                    if k in ("email", "phone", "added_at",
                                              "reason", "source")},
            }
        # Optional: check the user-level dnc flag too.
        if ne:
            user_dnc = await db.users.find_one(
                {"email": ne, "$or": [{"dnc": True},
                                        {"status": "opted_out"},
                                        {"status": "unsubscribed"}]},
                {"_id": 0, "email": 1, "dnc": 1, "status": 1},
            )
            if user_dnc:
                return {
                    "blocked":       True,
                    "reason":        "user_marked_dnc",
                    "matched_field": "email",
                }
        return {"blocked": False, "reason": "ok", "matched_field": None}
    except Exception as e:
        logger.warning(f"[casl_gate] lookup failed → fail-closed: {e}")
        return {"blocked": True, "reason": f"lookup_error_{type(e).__name__}",
                 "matched_field": None}


async def suppress(
    db,
    *,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    reason: str = "user_opt_out",
    source: str = "casl_gate",
) -> dict:
    """Idempotently add a recipient to db.do_not_contact."""
    if db is None:
        return {"ok": False, "error": "db_unavailable"}
    ne, np_ = _norm_email(email), _norm_phone(phone)
    if not ne and not np_:
        return {"ok": False, "error": "no_identifier"}
    from datetime import datetime, timezone
    doc = {
        "email":    ne or None,
        "phone":    np_ or None,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "reason":   reason[:200],
        "source":   source[:80],
    }
    try:
        # Composite key: whichever fields we have.
        filter_q = {k: v for k, v in {"email": ne or None,
                                        "phone": np_ or None}.items() if v}
        await db.do_not_contact.update_one(
            filter_q, {"$setOnInsert": doc}, upsert=True
        )
        return {"ok": True, "suppressed": doc}
    except Exception as e:
        logger.warning(f"[casl_gate] suppress failed: {e}")
        return {"ok": False, "error": str(e)[:160]}
