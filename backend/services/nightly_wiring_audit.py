"""
Nightly Wiring Audit — Iteration 204
=====================================
Runs the feature wiring audit every night at 03:15 AM.
If coverage falls below threshold (default 95%), sends a WhatsApp alert
to the admin with the list of missing/error features.

Registered in nightly_cycle.register_nightly_jobs().
Persists history in `aurem_wiring_audits` collection (TTL-trimmed to 30 days).
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

COVERAGE_THRESHOLD = float(os.environ.get("WIRING_AUDIT_THRESHOLD", "95.0"))

_db = None


def set_db(db):
    global _db
    _db = db


async def _probe(client: httpx.AsyncClient, base: str, path: str) -> Dict[str, Any]:
    try:
        r = await client.get(f"{base}{path}", timeout=8.0)
        code = r.status_code
        status = "ok" if code < 400 else "wired" if code in (401, 403, 422) else "missing" if code == 404 else "error"
        return {"http": code, "status": status}
    except Exception as e:
        return {"http": 0, "status": "error", "error": str(e)[:120]}


async def _admin_phone() -> Optional[str]:
    ph = (os.environ.get("ADMIN_ALERT_PHONE") or "").strip()
    if ph:
        return ph
    if _db is None:
        return None
    try:
        u = await _db.platform_users.find_one(
            {"role": "admin", "phone": {"$exists": True, "$ne": ""}},
            {"_id": 0, "phone": 1},
        )
        if u and u.get("phone"):
            return u["phone"]
    except Exception:
        pass
    return None


async def nightly_wiring_audit() -> Dict[str, Any]:
    """Top-level scheduler entry. Runs probes + WA alert on coverage drop."""
    from routers.wiring_audit_router import ADMIN_CHECKLIST, CUSTOMER_CHECKLIST

    if _db is None:
        logger.warning("[WiringAudit] db not set — skipping")
        return {"skipped": True}

    base = "http://localhost:8001"
    async with httpx.AsyncClient(follow_redirects=True) as client:
        admin_rows: List[Dict[str, Any]] = []
        for feature, panel, probe, comp in ADMIN_CHECKLIST:
            p = await _probe(client, base, probe)
            admin_rows.append({"feature": feature, "panel": panel, "probe": probe, **p})

        customer_rows: List[Dict[str, Any]] = []
        for feature, panel, probe, comp in CUSTOMER_CHECKLIST:
            p = await _probe(client, base, probe)
            customer_rows.append({"feature": feature, "panel": panel, "probe": probe, **p})

    all_rows = admin_rows + customer_rows
    ok = sum(1 for r in all_rows if r["status"] in ("ok", "wired"))
    missing = [r["feature"] for r in all_rows if r["status"] == "missing"]
    errors  = [r["feature"] for r in all_rows if r["status"] == "error"]
    total = len(all_rows)
    pct = round(ok / max(total, 1) * 100, 1)
    now = datetime.now(timezone.utc).isoformat()

    summary = {
        "ran_at": now,
        "coverage_pct": pct,
        "ok_or_wired": ok,
        "total": total,
        "missing": missing,
        "errors": errors,
        "threshold": COVERAGE_THRESHOLD,
    }

    # Persist (trim older than 30 days)
    try:
        await _db.aurem_wiring_audits.insert_one({**summary, "admin": admin_rows, "customer": customer_rows})
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        await _db.aurem_wiring_audits.delete_many({"ran_at": {"$lt": cutoff}})
    except Exception as e:
        logger.debug(f"[WiringAudit] persist failed: {e}")

    # Alert if below threshold
    if pct < COVERAGE_THRESHOLD:
        phone = await _admin_phone()
        if phone:
            try:
                from routers.whatsapp_alerts import send_whatsapp
                broken = missing + errors
                preview = ", ".join(broken[:4]) + (f" +{len(broken)-4} more" if len(broken) > 4 else "")
                await send_whatsapp(
                    phone,
                    "🚨 AUREM Wiring Audit — coverage dropped\n\n"
                    f"Coverage: {pct}% (threshold {COVERAGE_THRESHOLD}%)\n"
                    f"Broken: {preview}\n\n"
                    f"Dashboard: https://aurem.live/admin/wiring-audit\n"
                    f"Ran at: {now[:19]}Z",
                )
                summary["alerted"] = phone
            except Exception as e:
                logger.warning(f"[WiringAudit] alert failed: {e}")

    logger.info(f"[WiringAudit] coverage={pct}% missing={len(missing)} errors={len(errors)} alerted={summary.get('alerted', False)}")
    return summary
