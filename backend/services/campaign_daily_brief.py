"""
Campaign Daily Brief — 9 PM EDT (iter 282x)
============================================

Sends founder a concise email summary of the day's campaign activity:

  ✅ 77 new leads · 📤 23 outreach sent · 📧 19 email opens
  💬 2 replies · 💰 $0 revenue · 🏗️ 3 sites built

Metrics pulled live from:
  - campaign_leads (scrape count)
  - auto_blast_config (processed/sent counters across all tenants)
  - sent_emails (Resend logs)
  - sms_logs (Twilio A2P)
  - outreach_history (4-channel dispatch)
  - auto_built_sites (Architect output)
  - stripe_charges / subscription_status (revenue — best-effort via Stripe API)

Schedule: daily 21:00 America/Toronto (9 PM EDT)
Recipient: `FOUNDER_EMAIL` env, fallback `teji.ss1986@gmail.com`
Delivery: Resend via `RESEND_API_KEY` (already configured)

Idempotency: inserts a row in `campaign_brief_log` keyed by date (YYYY-MM-DD).
A second fire the same day is a no-op.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger("campaign-daily-brief")

_TZ = ZoneInfo("America/Toronto")


def _founder_email() -> str:
    return (os.environ.get("FOUNDER_EMAIL") or "teji.ss1986@gmail.com").strip()


def _from_email() -> str:
    # Falls back to the canonical ORA address already in prod.
    return os.environ.get("RESEND_FROM_EMAIL") or "AUREM Campaign <ora@aurem.live>"


async def _count(db, collection: str, since_iso: str, until_iso: str, date_field: str = "created_at") -> int:
    try:
        return await db[collection].count_documents({
            date_field: {"$gte": since_iso, "$lt": until_iso},
        })
    except Exception:
        return 0


async def _sum_auto_blast(db) -> tuple[int, int]:
    """Returns (processed_today, sent_today) summed across all tenant configs.
    auto_blast_config tracks cumulative last_run_processed/sent per cycle; we
    snapshot the cycle-log today if available, else fall back to the single
    last_run counters on the global config."""
    try:
        # Preferred: explicit cycle log
        cnt = await db.auto_blast_cycles.count_documents({}) if "auto_blast_cycles" in await db.list_collection_names() else 0
        if cnt:
            today_start = datetime.now(_TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
            tomorrow_start = (datetime.now(_TZ).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).astimezone(timezone.utc).isoformat()
            processed = 0
            sent = 0
            cur = db.auto_blast_cycles.find(
                {"ran_at": {"$gte": today_start, "$lt": tomorrow_start}},
                {"_id": 0, "processed": 1, "sent": 1},
            )
            async for c in cur:
                processed += int(c.get("processed", 0))
                sent += int(c.get("sent", 0))
            return processed, sent
    except Exception:
        pass

    # Fallback: single-cycle snapshot from config
    try:
        cfg = await db.auto_blast_config.find_one({"tenant_id": "global"}, {"_id": 0}) or {}
        return int(cfg.get("last_run_processed", 0)), int(cfg.get("last_run_sent", 0))
    except Exception:
        return 0, 0


async def _revenue_today_usd(db) -> float:
    """Best-effort: read any `stripe_charges` docs from today (if the app logs them).
    Returns 0.0 if no collection or no rows — never raises."""
    try:
        today_start = datetime.now(_TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
        cols = await db.list_collection_names()
        total = 0.0
        for col in ("stripe_charges", "charges", "payments"):
            if col not in cols:
                continue
            cur = db[col].find(
                {"created_at": {"$gte": today_start}, "status": {"$in": ["succeeded", "paid", "completed"]}},
                {"_id": 0, "amount": 1, "amount_total": 1},
            )
            async for c in cur:
                amt = c.get("amount") or c.get("amount_total") or 0
                # Stripe stores in cents
                if amt > 1000:
                    total += float(amt) / 100.0
                else:
                    total += float(amt)
        return round(total, 2)
    except Exception:
        return 0.0


async def collect_brief_metrics(db) -> Dict[str, Any]:
    """Snapshot of today's KPIs. Public so /api/admin/campaign-brief/preview can reuse."""
    now_et = datetime.now(_TZ)
    today_start_utc = now_et.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
    tomorrow_start_utc = (now_et.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).astimezone(timezone.utc).isoformat()

    leads_scraped = await _count(db, "campaign_leads", today_start_utc, tomorrow_start_utc, date_field="created_at")
    leads_real = await db.campaign_leads.count_documents({
        "business_id": FOUNDER_BIN,
        "created_at": {"$gte": today_start_utc, "$lt": tomorrow_start_utc},
        "status": {"$nin": ["not_interested", "unsubscribed"]},
    }) if leads_scraped else 0

    processed, sent = await _sum_auto_blast(db)

    emails_sent = await db.sent_emails.count_documents({
        "sent_at": {"$gte": today_start_utc, "$lt": tomorrow_start_utc},
        "status": {"$in": ["sent", "delivered"]},
    })
    email_opens = 0
    email_replies = 0
    try:
        email_opens = await db.sent_emails.count_documents({
            "sent_at": {"$gte": today_start_utc, "$lt": tomorrow_start_utc},
            "opened": True,
        })
        email_replies = await db.sent_emails.count_documents({
            "sent_at": {"$gte": today_start_utc, "$lt": tomorrow_start_utc},
            "replied": True,
        })
    except Exception:
        pass

    sms_sent = await db.sms_logs.count_documents({
        "sent_at": {"$gte": today_start_utc, "$lt": tomorrow_start_utc},
        "status": {"$in": ["sent", "delivered", "queued"]},
    })

    replies_today = await db.campaign_leads.count_documents({
        "business_id": FOUNDER_BIN,
        "replied_at": {"$gte": today_start_utc, "$lt": tomorrow_start_utc},
    }) if await db.campaign_leads.count_documents(
        {"replied_at": {"$exists": True}, "business_id": FOUNDER_BIN}) else email_replies

    sites_built = await db.auto_built_sites.count_documents({
        "created_at": {"$gte": today_start_utc, "$lt": tomorrow_start_utc},
    })

    revenue_usd = await _revenue_today_usd(db)

    return {
        "date": now_et.strftime("%A, %B %d, %Y"),
        "date_iso": now_et.date().isoformat(),
        "leads_scraped": leads_scraped,
        "leads_real": leads_real,
        "outreach_processed": processed,
        "outreach_sent": sent,
        "emails_sent": emails_sent,
        "email_opens": email_opens,
        "sms_sent": sms_sent,
        "replies": replies_today,
        "sites_built": sites_built,
        "revenue_usd": revenue_usd,
    }


def _render_email_html(m: Dict[str, Any]) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#050510;font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:#F2EDE4">
  <div style="max-width:560px;margin:0 auto;padding:32px 24px">
    <div style="letter-spacing:4px;font-size:11px;color:#F97316;font-weight:700;margin-bottom:6px">AUREM · CAMPAIGN BRIEF</div>
    <h1 style="margin:0 0 6px;font-size:22px;color:#D4AF37;font-weight:600">Daily snapshot</h1>
    <div style="font-size:13px;color:#8A8279;margin-bottom:28px">{m['date']} · 9:00 PM EDT</div>

    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
      <tr>
        <td style="padding:14px 16px;background:rgba(249,115,22,0.08);border:1px solid rgba(249,115,22,0.25);border-radius:8px">
          <div style="font-size:10px;letter-spacing:2px;color:#F97316;margin-bottom:4px">🎯 SCOUT</div>
          <div style="font-size:26px;color:#F2EDE4;font-weight:600">{m['leads_scraped']}</div>
          <div style="font-size:11px;color:#8A8279">new leads · {m['leads_real']} qualified</div>
        </td>
      </tr>
      <tr><td style="height:10px"></td></tr>
      <tr>
        <td style="padding:14px 16px;background:rgba(212,175,55,0.06);border:1px solid rgba(212,175,55,0.2);border-radius:8px">
          <div style="font-size:10px;letter-spacing:2px;color:#D4AF37;margin-bottom:4px">📤 OUTREACH</div>
          <div style="font-size:26px;color:#F2EDE4;font-weight:600">{m['outreach_sent']}</div>
          <div style="font-size:11px;color:#8A8279">sent of {m['outreach_processed']} processed</div>
        </td>
      </tr>
      <tr><td style="height:10px"></td></tr>
      <tr>
        <td>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;border-spacing:0 6px">
            <tr>
              <td width="33%" style="padding:10px;background:rgba(255,255,255,0.04);border-radius:6px;text-align:center">
                <div style="font-size:9px;letter-spacing:1.5px;color:#8A8279">📧 EMAILS</div>
                <div style="font-size:18px;color:#F2EDE4;font-weight:600">{m['emails_sent']}</div>
                <div style="font-size:10px;color:#8A8279">{m['email_opens']} opens</div>
              </td>
              <td width="6"></td>
              <td width="33%" style="padding:10px;background:rgba(255,255,255,0.04);border-radius:6px;text-align:center">
                <div style="font-size:9px;letter-spacing:1.5px;color:#8A8279">📱 SMS</div>
                <div style="font-size:18px;color:#F2EDE4;font-weight:600">{m['sms_sent']}</div>
                <div style="font-size:10px;color:#8A8279">A2P queued</div>
              </td>
              <td width="6"></td>
              <td width="33%" style="padding:10px;background:rgba(255,255,255,0.04);border-radius:6px;text-align:center">
                <div style="font-size:9px;letter-spacing:1.5px;color:#8A8279">💬 REPLIES</div>
                <div style="font-size:18px;color:#F2EDE4;font-weight:600">{m['replies']}</div>
                <div style="font-size:10px;color:#8A8279">warm leads</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr><td style="height:10px"></td></tr>
      <tr>
        <td>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;border-spacing:0 6px">
            <tr>
              <td width="50%" style="padding:10px;background:rgba(255,255,255,0.04);border-radius:6px;text-align:center">
                <div style="font-size:9px;letter-spacing:1.5px;color:#8A8279">🏗️ SITES BUILT</div>
                <div style="font-size:18px;color:#F2EDE4;font-weight:600">{m['sites_built']}</div>
              </td>
              <td width="6"></td>
              <td width="50%" style="padding:10px;background:rgba(34,197,94,0.06);border-radius:6px;text-align:center;border:1px solid rgba(34,197,94,0.2)">
                <div style="font-size:9px;letter-spacing:1.5px;color:#22C55E">💰 REVENUE</div>
                <div style="font-size:18px;color:#22C55E;font-weight:600">${m['revenue_usd']:.2f}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>

    <div style="margin-top:32px;padding-top:20px;border-top:1px solid rgba(255,255,255,0.08);font-size:11px;color:#5A5449;text-align:center">
      AUREM · Autonomous Revenue Engine · <a href="https://aurem.live/admin" style="color:#F97316;text-decoration:none">Admin console</a>
    </div>
  </div>
</body></html>"""


def _render_text(m: Dict[str, Any]) -> str:
    return (
        f"AUREM · Daily Campaign Brief · {m['date']}\n\n"
        f"🎯 SCOUT        {m['leads_scraped']} new leads ({m['leads_real']} qualified)\n"
        f"📤 OUTREACH     {m['outreach_sent']} sent / {m['outreach_processed']} processed\n"
        f"📧 EMAILS       {m['emails_sent']} sent, {m['email_opens']} opens\n"
        f"📱 SMS          {m['sms_sent']} queued (Twilio A2P)\n"
        f"💬 REPLIES      {m['replies']}\n"
        f"🏗️ SITES BUILT  {m['sites_built']}\n"
        f"💰 REVENUE      ${m['revenue_usd']:.2f}\n\n"
        f"Admin: https://aurem.live/admin\n"
    )


async def send_campaign_daily_brief(db, force: bool = False) -> Dict[str, Any]:
    """Collect metrics, send Resend email, log to campaign_brief_log.
    force=True bypasses idempotency (used by /admin/campaign-brief/run-now).
    """
    if db is None:
        return {"ok": False, "error": "no_db"}

    metrics = await collect_brief_metrics(db)
    date_key = metrics["date_iso"]

    if not force:
        existing = await db.campaign_brief_log.find_one({"date": date_key}, {"_id": 0, "status": 1})
        if existing and existing.get("status") == "sent":
            return {"ok": True, "skipped": True, "reason": "already_sent_today", "metrics": metrics}

    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not api_key:
        await db.campaign_brief_log.insert_one({
            "date": date_key, "status": "skipped_no_key",
            "metrics": metrics, "ts": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": False, "error": "RESEND_API_KEY not set", "metrics": metrics}

    to_email = _founder_email()
    subject = (
        f"AUREM Brief · {metrics['leads_scraped']} leads · "
        f"{metrics['outreach_sent']} sent · "
        f"${metrics['revenue_usd']:.2f} · {metrics['date']}"
    )

    sent_ok = False
    send_id: Optional[str] = None
    error: Optional[str] = None
    try:
        from services.email_engine import resend  # iter 326x defensive
        resend.api_key = api_key
        res = resend.Emails.send({
            "from": _from_email(),
            "to": [to_email],
            "subject": subject,
            "html": _render_email_html(metrics),
            "text": _render_text(metrics),
            "headers": {"X-Entity-Ref-ID": f"aurem-campaign-brief-{date_key}"},
        })
        send_id = (res or {}).get("id")
        sent_ok = bool(send_id)
    except Exception as e:
        error = str(e)[:300]
        logger.warning(f"[campaign-brief] send failed: {e}")

    await db.campaign_brief_log.insert_one({
        "date": date_key,
        "status": "sent" if sent_ok else "failed",
        "resend_id": send_id,
        "to": to_email,
        "metrics": metrics,
        "error": error,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    logger.info(f"[campaign-brief] {date_key} → {'SENT ' + (send_id or '') if sent_ok else 'FAILED ' + (error or '')}")

    return {"ok": sent_ok, "metrics": metrics, "resend_id": send_id, "error": error}
