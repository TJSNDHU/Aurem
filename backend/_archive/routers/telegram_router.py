"""
Telegram Router
===============
Operational visibility layer for the Telegram integration.

The webhook + parser already live in `routers.ora_command_router`
(POST /api/ora/telegram/webhook). This router exposes one additional
admin-facing endpoint:

  GET  /api/telegram/status   — Is Telegram wired? Bot info, webhook info,
                                 secret/whitelist enforcement status.

Kept deliberately thin so there's a single source of truth for message
parsing + replies inside services.ora_command_center.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Telegram"])

_db = None


def set_db(db):
    global _db
    _db = db


# ─────────────────────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────────────────────
@router.get("/api/telegram/status")
async def telegram_status() -> Dict[str, Any]:
    """
    Report Telegram integration health for the Admin Control Center.

    Checks:
      • TELEGRAM_BOT_TOKEN present
      • getMe         — bot identity + username
      • getWebhookInfo — current webhook URL + last error
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return {
            "ok": False,
            "configured": False,
            "reason": "TELEGRAM_BOT_TOKEN not set",
            "bot": None,
            "webhook": None,
        }

    base = f"https://api.telegram.org/bot{token}"
    bot_info: Dict[str, Any] = {}
    webhook_info: Dict[str, Any] = {}
    reachable = False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            me = await client.get(f"{base}/getMe")
            if me.status_code == 200:
                data = me.json()
                if data.get("ok"):
                    reachable = True
                    r = data.get("result", {}) or {}
                    bot_info = {
                        "id": r.get("id"),
                        "username": r.get("username"),
                        "first_name": r.get("first_name"),
                        "can_join_groups": r.get("can_join_groups"),
                    }
            wh = await client.get(f"{base}/getWebhookInfo")
            if wh.status_code == 200:
                data = wh.json()
                if data.get("ok"):
                    r = data.get("result", {}) or {}
                    webhook_info = {
                        "url": r.get("url"),
                        "has_custom_certificate": r.get("has_custom_certificate"),
                        "pending_update_count": r.get("pending_update_count"),
                        "last_error_date": r.get("last_error_date"),
                        "last_error_message": r.get("last_error_message"),
                    }
    except Exception as e:
        logger.warning(f"[Telegram] status check failed: {e}")
        return {
            "ok": False,
            "configured": True,
            "reachable": False,
            "error": str(e),
            "bot": None,
            "webhook": None,
        }

    return {
        "ok": reachable,
        "configured": True,
        "reachable": reachable,
        "bot": bot_info,
        "webhook": webhook_info,
        "admin_phones_whitelisted": bool(
            os.environ.get("AUREM_ADMIN_PHONES", "").strip()
        ),
        "webhook_secret_enforced": bool(
            os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
        ),
    }

