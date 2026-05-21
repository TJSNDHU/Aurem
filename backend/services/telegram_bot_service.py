"""
services/telegram_bot_service.py — Outbound Telegram alerts.

Single canonical sender for *every* "founder alert" channel:
  - campaign_zero       → ora_campaign_watchdog trips on zero_sent_streak
  - new_signup          → platform_auth_router register success
  - server_down         → any health-check failure (future)
  - hot_lead            → inbound_reply_handler positive intent
  - server.misc         → ad-hoc plumbing alerts

Env vars (already populated in this pod):
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID

Design notes
------------
- Best-effort: never raises. Returns a dict the caller can ignore.
- Sends plain text (no parse_mode) — Markdown/MarkdownV2 breaks on
  underscores in IDs, URLs, etc. We learned this in autopilot_brief_notifier.
- Throttles duplicate alerts per (alert_type, fingerprint) for 5 minutes
  so a watchdog tripping every cycle doesn't spam the founder.
- Records every send to `db.telegram_alert_log` for auditability.

Public surface
--------------
- ``send_telegram_alert(message, alert_type="generic", fingerprint=None)``
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# In-memory dedup window. Process-local; that's fine because the
# watchdog/inbound handler are single-instance background workers.
_DEDUP_TTL_SEC = 300  # 5 minutes
_dedup: Dict[str, float] = {}


def _db():
    """Lazy import — service may be called before server.db is set."""
    try:
        import server  # type: ignore
        if hasattr(server, "db") and server.db is not None:
            return server.db
    except Exception:
        pass
    return None


def _deduped(key: str) -> bool:
    now = time.time()
    # Sweep expired
    expired = [k for k, t in _dedup.items() if now - t > _DEDUP_TTL_SEC]
    for k in expired:
        _dedup.pop(k, None)
    if key in _dedup:
        return True
    _dedup[key] = now
    return False


async def send_telegram_alert(
    message: str,
    alert_type: str = "generic",
    fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """Send an alert to the founder Telegram chat.

    Parameters
    ----------
    message : str
        Plain-text body. Newlines OK. Telegram caps at 4096 chars; we
        truncate at 3900 to leave headroom for the alert-type prefix.
    alert_type : str
        Tag used for both dedup and the log row. Example: ``"campaign_zero"``,
        ``"new_signup"``, ``"hot_lead"``, ``"server_down"``.
    fingerprint : Optional[str]
        Extra dedup key beyond alert_type. For example, the new-signup
        path passes the email so the same person can't double-fire on a
        retry; the watchdog passes the streak count so each escalation
        is its own ping.

    Returns
    -------
    dict
        ``{"ok": bool, "reason": str, ...}``. Never raises.
    """
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        return {"ok": False, "reason": "creds_missing",
                "missing": [k for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
                            if not os.environ.get(k)]}

    dedup_key = f"{alert_type}::{fingerprint or ''}"
    if fingerprint and _deduped(dedup_key):
        return {"ok": False, "reason": "deduped", "key": dedup_key}

    # Prefix the alert_type so a founder skimming the chat can triage at
    # a glance even when the message body is generic.
    prefix = {
        "campaign_zero": "📉 CAMPAIGN ZERO",
        "new_signup":    "🆕 NEW SIGNUP",
        "server_down":   "🚨 SERVER DOWN",
        "hot_lead":      "🔥 HOT LEAD",
    }.get(alert_type, f"[{alert_type}]")
    body = f"{prefix}\n\n{message}"
    if len(body) > 3900:
        body = body[:3900] + "\n…(truncated)"

    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": body,
                      "disable_web_page_preview": True},
            )
        ok = r.status_code == 200
        result = {"ok": ok, "reason": "sent" if ok else f"http_{r.status_code}",
                  "alert_type": alert_type}
        if not ok:
            result["detail"] = r.text[:200]
    except Exception as e:
        result = {"ok": False, "reason": "error",
                  "detail": str(e)[:200], "alert_type": alert_type}

    # Audit log — best-effort, never blocks the send result.
    db = _db()
    if db is not None:
        try:
            from datetime import datetime, timezone
            await db.telegram_alert_log.insert_one({
                "alert_type": alert_type,
                "fingerprint": fingerprint,
                "ok": result["ok"],
                "reason": result["reason"],
                "preview": body[:200],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.debug(f"[telegram_bot_service] audit log skipped: {e}")

    return result
