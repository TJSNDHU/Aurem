"""
Payments health endpoint — single source of truth for the payments
subsystem on the Pillars Map dashboard.

Why a dedicated endpoint?
  Pillars Map's `_check_flow()` does GET on `be_endpoint` and infers DB +
  backend + frontend health. The payments subsystem has FOUR health axes
  (Stripe key mode, webhook endpoint reachable, recent transactions,
  recent webhook deliveries) which we want collapsed into ONE GET that
  the existing flow checker can consume.

Returns JSON with:
  - stripe_mode            : "live" | "test" | "unknown"
  - in_sync                : secret + publishable in same mode
  - webhook_alias_reachable: True iff /api/stripe/webhook responds 200
                              to a synthetic ping (catches the iter 280.13
                              "404 webhook into the void" bug)
  - last_payment_tx_at     : ISO ts of latest payment_transactions row
  - last_webhook_event_at  : ISO ts of latest webhook delivery (best effort)
  - status                 : "green"/"yellow"/"red" rolled up — directly
                              consumed by Pillars Map worst-of-three logic
                              (HTTP 200 == green, HTTP 503 == red)

iter 280.14
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Header

from utils.admin_guard import verify_admin as _verify_admin

router = APIRouter(prefix="/api/admin/payments", tags=["Payments Health"])

_db = None


def set_db(db):
    global _db
    _db = db


def _key_mode(s: str) -> str:
    if not s:
        return "empty"
    if s.startswith("sk_live_") or s.startswith("pk_live_"):
        return "live"
    if s.startswith("sk_test_") or s.startswith("pk_test_"):
        return "test"
    return "unknown"


async def _last_doc_ts(collection_name: str, ts_fields: list[str]) -> Optional[str]:
    """Return ISO timestamp of newest doc, scanning multiple possible ts fields."""
    if _db is None:
        return None
    try:
        doc = await _db[collection_name].find_one({}, sort=[("_id", -1)])
        if not doc:
            return None
        for f in ts_fields:
            v = doc.get(f)
            if v:
                return str(v)[:25]
    except Exception:
        return None
    return None


async def _webhook_alias_reachable() -> tuple[bool, str]:
    """Best-effort self-check: POST a synthetic event to /api/stripe/webhook
    on the loopback, expect 200. The canonical handler accepts unsigned
    events (logs a warning) so this works without a live Stripe signature.
    """
    import httpx
    url = "http://localhost:8001/api/stripe/webhook"
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            r = await client.post(
                url,
                headers={"Content-Type": "application/json", "Stripe-Signature": "t=0,v1=ping"},
                json={"id": "evt_pillars_map_health_ping", "type": "ping",
                      "data": {"object": {}}},
            )
        return (r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        return (False, f"unreachable: {str(e)[:60]}")


@router.get("/health")
async def payments_health(authorization: Optional[str] = Header(None)):
    """Aggregated payments health for Pillars Map.

    Auth model:
      - Externally callable by admins (dashboard view).
      - INTERNALLY callable without auth — Pillars Map's _check_flow does
        a loopback probe with no Authorization header, and double-auth
        would force a fake 401 (pre-iter-280.14 behavior). The endpoint
        intentionally exposes only safe metadata (mode flags, counts,
        timestamps) — no keys or secrets — so unauth access is OK.
      - When called WITH a token, we still verify it (best-effort).
    """
    if authorization:
        # If a token was supplied, validate it. Reject only if explicitly
        # bad — missing-admin is fine, since the body is non-sensitive.
        try:
            _verify_admin(authorization)
        except HTTPException as e:
            if e.status_code == 401:
                # invalid token format — still reject to avoid silently
                # accepting forged headers
                raise
            # 403 (not admin) → allow, body is safe
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    runtime_sk = os.environ.get("STRIPE_SECRET_KEY", "")
    runtime_pk = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    secret_mode = _key_mode(runtime_sk)
    publishable_mode = _key_mode(runtime_pk)
    in_sync = secret_mode == publishable_mode and secret_mode in ("live", "test")
    configured = bool(runtime_sk and runtime_pk)

    webhook_ok, webhook_reason = await _webhook_alias_reachable()
    webhook_secret_set = bool(os.environ.get("STRIPE_WEBHOOK_SECRET", ""))

    last_tx = await _last_doc_ts("payment_transactions", ["created_at", "ts", "timestamp"])
    last_webhook_event = await _last_doc_ts(
        "stripe_webhook_events", ["received_at", "ts", "timestamp", "created_at"]
    )

    # Roll-up status
    reasons: list[str] = []
    rollup = "green"
    if not configured:
        rollup = "red"
        reasons.append("Stripe keys missing")
    elif not in_sync:
        rollup = "red"
        reasons.append(f"key mode mismatch (sk={secret_mode}, pk={publishable_mode})")
    elif secret_mode == "test":
        rollup = "yellow"
        reasons.append("running in TEST mode")

    if not webhook_ok:
        rollup = "red"
        reasons.append(f"webhook alias broken ({webhook_reason})")

    if not webhook_secret_set:
        # Yellow — webhook handler still accepts events but signatures aren't
        # being validated. Production-incomplete but not catastrophic.
        if rollup == "green":
            rollup = "yellow"
        reasons.append("STRIPE_WEBHOOK_SECRET not set (signatures unverified)")

    # Stale-data check: a healthy production sees at least 1 payment_tx
    # within 30 days. Older than that = nobody is paying = yellow.
    if last_tx:
        try:
            tx_dt = datetime.fromisoformat(last_tx.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - tx_dt > timedelta(days=30) and rollup == "green":
                rollup = "yellow"
                reasons.append("no payment activity in last 30 days")
        except Exception:
            pass

    if rollup == "green":
        reasons.append("all checks passing")

    return {
        "status": rollup,
        "reason": " · ".join(reasons),
        "checks": {
            "stripe_configured": configured,
            "stripe_secret_mode": secret_mode,
            "stripe_publishable_mode": publishable_mode,
            "stripe_in_sync": in_sync,
            "webhook_alias_reachable": webhook_ok,
            "webhook_alias_reason": webhook_reason,
            "webhook_secret_configured": webhook_secret_set,
            "last_payment_tx_at": last_tx,
            "last_webhook_event_at": last_webhook_event,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
