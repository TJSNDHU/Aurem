"""
services/hot_lead_alerts.py — Founder alert when a hot lead is detected.

Shared between:
  - routers/website_builder_router.py  (prospect on sample page)
  - services/inbound_reply_handler.py  (positive email reply)

Fires WhatsApp (preserves the original website_builder behavior) AND
Telegram (iter 325d) so the founder gets the signal on whichever
channel they're watching. Best-effort: never raises.

Source channels are independent — WhatsApp failing does not block
Telegram and vice versa. Both attempts are logged for audit.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

HOT_LEAD_ADMIN_PHONE = os.environ.get("AUREM_HOT_LEAD_PHONE", "+16134000000")


async def fire_hot_lead_admin_alert(
    db,
    business_name: str,
    slug: Optional[str] = None,
    lead_id: Optional[str] = None,
    source: str = "sample_page",
    detail: Optional[str] = None,
) -> dict:
    """Fire the founder alert across WhatsApp + Telegram.

    Parameters
    ----------
    db
        Mongo handle (used for audit log; safe to pass None).
    business_name : str
        Human-readable name shown in the alert body.
    slug : Optional[str]
        Sample-site slug when the trigger is a live viewer. Used to
        build a clickable URL.
    lead_id : Optional[str]
        Campaign lead row id when the trigger is an email reply.
    source : str
        Where the alert came from — ``"sample_page"`` (default) or
        ``"email_reply"``. Used to choose the message template.
    detail : Optional[str]
        Optional one-liner appended verbatim — e.g. the reply preview
        or the engagement context. Truncated at 200 chars.

    Returns
    -------
    dict
        ``{"whatsapp": {...}, "telegram": {...}}`` with per-channel results.
    """
    public_base = os.environ.get("PUBLIC_APP_URL", "https://aurem.live").rstrip("/")

    if source == "email_reply":
        header = "🔥 *HOT LEAD — Email Reply*"
        action_line = (
            f"*{business_name}* just replied positive to outreach.\n\n"
            f"Open them in the CRM: {public_base}/admin/leads"
            + (f"?id={lead_id}" if lead_id else "")
        )
    else:
        header = "🔥 *HOT LEAD*"
        action_line = (
            f"*{business_name}* is on their sample page RIGHT NOW!\n\n"
            f"👉 {public_base}/sample/{slug or ''}"
        )
    msg = (
        f"{header}\n\n"
        f"{action_line}\n\n"
        + (f"_Context:_ {detail[:200]}\n\n" if detail else "")
        + "Campaign HQ, react in the next 30 sec.\n"
        + "_AUREM Intelligence_"
    )

    out = {"whatsapp": {"ok": False, "reason": "not_attempted"},
           "telegram": {"ok": False, "reason": "not_attempted"}}

    # ── WhatsApp via WHAPI ─────────────────────────────────────────
    phone = HOT_LEAD_ADMIN_PHONE.replace("+", "").replace("-", "").replace(" ", "")
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    whapi_url = os.environ.get("WHAPI_API_URL", "")
    if phone and whapi_token and whapi_url:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{whapi_url}/messages/text",
                    headers={"authorization": f"Bearer {whapi_token}",
                             "content-type": "application/json"},
                    json={"to": f"{phone}@s.whatsapp.net", "body": msg},
                )
            out["whatsapp"] = {"ok": r.status_code == 200,
                               "reason": f"http_{r.status_code}"}
        except Exception as e:
            out["whatsapp"] = {"ok": False, "reason": "error",
                               "detail": str(e)[:200]}
            logger.warning(f"[hot-lead-alert] WhatsApp error: {e}")
    else:
        out["whatsapp"] = {"ok": False, "reason": "whapi_not_configured"}

    # ── Telegram ────────────────────────────────────────────────────
    try:
        from services.telegram_bot_service import send_telegram_alert
        # Strip the WhatsApp-flavoured markdown bolds; Telegram sender
        # is plain-text by design (we learned this in autopilot_brief_notifier).
        plain = msg.replace("*", "").replace("_", "")
        out["telegram"] = await send_telegram_alert(
            message=plain,
            alert_type="hot_lead",
            # Per-lead dedup so repeat sample-page heartbeats don't double-fire,
            # but a new email reply on a different lead still pings.
            fingerprint=(lead_id or slug or business_name)[:120],
        )
    except Exception as e:
        out["telegram"] = {"ok": False, "reason": "import_error",
                           "detail": str(e)[:200]}
        logger.warning(f"[hot-lead-alert] Telegram error: {e}")

    # ── Audit log ───────────────────────────────────────────────────
    if db is not None:
        try:
            await db.hot_lead_alerts.insert_one({
                "business_name": business_name,
                "slug": slug,
                "lead_id": lead_id,
                "source": source,
                "whatsapp_ok": out["whatsapp"]["ok"],
                "telegram_ok": out["telegram"]["ok"],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.debug(f"[hot-lead-alert] audit log skipped: {e}")

    return out
