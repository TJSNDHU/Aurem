"""
AUREM Trial Win-back Sequence — Section 8
==========================================
Fires automatically when a 7-day trial expires without conversion to a
paid plan. 3-step nudge sequence over 8 days designed to convert
expired-trial users into paying subscribers.

Cadence (from trial_ends_at):
  Day 0 (immediate)  → "Trial just ended — preview link still live"
  Day 3              → "Founder discount: 25% off your first month"
  Day 8              → "Final notice — preview goes dark in 7 days"

Each step is idempotent (one shot per (email, step)). If the user starts
any paid subscription between steps, the remaining steps auto-cancel.

Persistence: `trial_winbacks` collection — one doc per email
  {
    email, tenant_bin,
    armed_at, ends_at,
    last_step: 0..3,
    last_step_at, completed: bool, cancelled: bool
  }

Public:
  arm_trial_winback(db, email, tenant_bin)  -> dict
  fire_due_steps(db)                        -> dict (advanced count)
  trial_winback_scheduler()                 -> never returns
"""
from __future__ import annotations

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ── tunables ─────────────────────────────────────────────────────────
STEP_OFFSETS_DAYS = [
    int(x) for x in os.environ.get(
        "TRIAL_WINBACK_OFFSETS", "0,3,8",
    ).split(",")
]
PUBLIC_BASE = os.environ.get(
    "AUREM_PUBLIC_URL", "https://aurem.live",
).rstrip("/")
FOUNDER_DISCOUNT_PCT = int(os.environ.get("TRIAL_WINBACK_DISCOUNT", "25"))


# ─── Step content ────────────────────────────────────────────────────

def _step_content(step: int, email: str, tenant_bin: str) -> Dict[str, str]:
    """Return subject/email-body/sms-body for a step."""
    upgrade_url = f"{PUBLIC_BASE}/billing?ref=winback&step={step}"
    if step == 1:
        return {
            "subject": "Your AUREM trial ended — your preview is still live",
            "html": (
                "<div style='font-family:Georgia,serif;max-width:520px'>"
                "<h2 style='color:#8a6d1c'>Your trial ended — but your site is still live</h2>"
                f"<p>Hey, your 7-day Power Trial wrapped up. Your auto-built site"
                f" + AI agents are paused for now, but your preview link is still"
                f" up if anyone clicks it.</p>"
                f"<p>If you'd like to keep things running, just pick a plan:</p>"
                f"<p><a href='{upgrade_url}' "
                f"style='background:#C9A227;color:#0A0A0A;padding:10px 20px;"
                f"text-decoration:none;border-radius:6px;font-weight:700'>"
                f"Continue with AUREM →</a></p>"
                f"<p style='color:#666;font-size:13px'>No pressure — reply if you "
                f"want a quick walkthrough first.</p></div>"
            ),
            "sms": (
                f"AUREM: your trial ended but your preview is still live. "
                f"Keep it running → {upgrade_url}"
            ),
        }
    if step == 2:
        return {
            "subject": f"{FOUNDER_DISCOUNT_PCT}% off — founder personal offer",
            "html": (
                "<div style='font-family:Georgia,serif;max-width:520px'>"
                f"<h2 style='color:#8a6d1c'>{FOUNDER_DISCOUNT_PCT}% off your first month</h2>"
                f"<p>Hey — TJ here, founder of AUREM.</p>"
                f"<p>I noticed you tried us out but didn't subscribe yet. "
                f"That's totally fine — but I'd hate for you to lose the "
                f"momentum. Here's a personal offer: "
                f"<strong>{FOUNDER_DISCOUNT_PCT}% off your first month</strong> "
                f"on any plan, this week only.</p>"
                f"<p><a href='{upgrade_url}&promo=founder{FOUNDER_DISCOUNT_PCT}' "
                f"style='background:#C9A227;color:#0A0A0A;padding:10px 20px;"
                f"text-decoration:none;border-radius:6px;font-weight:700'>"
                f"Claim {FOUNDER_DISCOUNT_PCT}% off →</a></p>"
                f"<p style='margin-top:22px'>— TJ, Founder · AUREM</p></div>"
            ),
            "sms": (
                f"TJ from AUREM — {FOUNDER_DISCOUNT_PCT}% off your first month, "
                f"this week only: {upgrade_url}&promo=founder{FOUNDER_DISCOUNT_PCT}"
            ),
        }
    # step 3 — final notice
    return {
        "subject": "Final notice — your AUREM preview goes dark in 7 days",
        "html": (
            "<div style='font-family:Georgia,serif;max-width:520px'>"
            "<h2 style='color:#8a6d1c'>Last call before we take your preview down</h2>"
            f"<p>This is the last note from us, promise. Your auto-built "
            f"preview site is still live, but we'll archive it in 7 days "
            f"if there's no activity.</p>"
            f"<p>If there was something we should have done differently, "
            f"reply to this email. I read every one personally.</p>"
            f"<p><a href='{upgrade_url}' "
            f"style='background:#0A0A0A;color:#C9A227;padding:10px 20px;"
            f"text-decoration:none;border-radius:6px;font-weight:700;"
            f"border:1px solid #C9A227'>Keep my preview live →</a></p>"
            f"<p style='margin-top:22px'>— TJ, Founder · AUREM</p></div>"
        ),
        "sms": (
            f"AUREM final notice: your preview goes dark in 7 days unless "
            f"you keep it live → {upgrade_url}"
        ),
    }


# ─── State machine ───────────────────────────────────────────────────

async def arm_trial_winback(
    db, email: str, tenant_bin: str = "",
) -> Dict[str, Any]:
    """Idempotent: create a winback row for this email if none exists."""
    if db is None or not email:
        return {"ok": False, "error": "db_or_email_missing"}
    email = email.lower().strip()
    existing = await db.trial_winbacks.find_one({"email": email}, {"_id": 0})
    if existing and not existing.get("cancelled"):
        return {"ok": True, "already_armed": True, "winback": existing}

    now = datetime.now(timezone.utc)
    doc = {
        "email": email,
        "tenant_bin": tenant_bin or "",
        "armed_at": now.isoformat(),
        "last_step": 0,
        "last_step_at": None,
        "completed": False,
        "cancelled": False,
    }
    await db.trial_winbacks.update_one(
        {"email": email}, {"$set": doc}, upsert=True,
    )
    logger.info(f"[trial-winback] armed for {email}")
    return {"ok": True, "armed": True, "winback": doc}


async def cancel_trial_winback(db, email: str, reason: str = "subscribed") -> None:
    if db is None or not email:
        return
    await db.trial_winbacks.update_one(
        {"email": email.lower().strip()},
        {"$set": {"cancelled": True, "cancelled_reason": reason,
                  "cancelled_at": datetime.now(timezone.utc).isoformat()}},
    )


async def _send_step(db, wb: Dict[str, Any], step: int) -> Dict[str, Any]:
    """Send one step (email + SMS where possible). Reuses platform_users
    row to find phone/name."""
    email = wb.get("email", "")
    user = await db.platform_users.find_one(
        {"email": email}, {"_id": 0, "phone": 1, "business_name": 1, "name": 1},
    ) or {}
    content = _step_content(step, email, wb.get("tenant_bin", ""))

    sent = {"email": False, "sms": False}
    # Email via Resend
    try:
        from services.resend_email import send_email
        await send_email(
            to=email, subject=content["subject"], html=content["html"],
        )
        sent["email"] = True
    except Exception as e:
        logger.warning(f"[trial-winback] email step {step} failed for {email}: {e}")

    # SMS via Twilio (best effort)
    phone = (user.get("phone") or "").strip()
    if phone:
        try:
            from services.twilio_sms import send_sms
            await send_sms(to=phone, body=content["sms"])
            sent["sms"] = True
        except Exception as e:
            logger.debug(f"[trial-winback] sms step {step} failed for {email}: {e}")

    return sent


async def fire_due_steps(db) -> Dict[str, Any]:
    """Advance every armed winback whose next step is due."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}
    now = datetime.now(timezone.utc)
    advanced = 0
    skipped = 0

    cur = db.trial_winbacks.find(
        {"completed": False, "cancelled": False},
        {"_id": 0},
    ).limit(500)
    rows: List[Dict[str, Any]] = await cur.to_list(500)
    for wb in rows:
        # Auto-cancel if the user is now subscribed
        try:
            sub = await db.customer_subscriptions.count_documents(
                {"email": wb.get("email"), "status": "active"},
            )
            if sub:
                await cancel_trial_winback(db, wb["email"], "subscribed")
                continue
        except Exception:
            pass

        last = int(wb.get("last_step") or 0)
        if last >= len(STEP_OFFSETS_DAYS):
            await db.trial_winbacks.update_one(
                {"email": wb["email"]}, {"$set": {"completed": True}},
            )
            continue

        next_step = last + 1
        offset = STEP_OFFSETS_DAYS[next_step - 1]
        try:
            armed_at = datetime.fromisoformat(
                wb.get("armed_at", "").replace("Z", "+00:00"),
            )
        except Exception:
            armed_at = now
        due_at = armed_at + timedelta(days=offset)
        if due_at > now:
            skipped += 1
            continue

        sent = await _send_step(db, wb, next_step)
        await db.trial_winbacks.update_one(
            {"email": wb["email"]},
            {"$set": {
                "last_step": next_step,
                "last_step_at": now.isoformat(),
                f"step_{next_step}_sent": sent,
                "completed": next_step >= len(STEP_OFFSETS_DAYS),
            }},
        )
        advanced += 1

    return {"ok": True, "advanced": advanced, "scanned": len(rows),
            "skipped_not_due": skipped}


async def trial_winback_scheduler():
    """Forever loop — every 30 min, fire any due winback steps."""
    print("[trial-winback] scheduler alive — 60s grace before first cycle",
          flush=True)
    await asyncio.sleep(60)
    while True:
        try:
            from services.auto_blast_engine import _get_db
            db = _get_db()
            if db is None:
                await asyncio.sleep(60)
                continue
            res = await fire_due_steps(db)
            if (res.get("advanced") or 0) > 0:
                print(f"[trial-winback] cycle: {res}", flush=True)
            await asyncio.sleep(1800)  # 30 min
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[trial-winback] scheduler error: {e}",
                         exc_info=True)
            await asyncio.sleep(300)
