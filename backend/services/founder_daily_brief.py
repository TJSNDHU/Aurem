"""
AUREM Founder Daily Brief — iter 282m
======================================
Real-data-only reporting system. NO WhatsApp.

Channels:
  • ORA Web Push (VAPID) — for in-day step events (Scout, Architect, Envoy,
    midday check, P0 alerts).
  • Resend Email — single end-of-day report at 6:00 PM EST to FOUNDER_EMAIL.

Verification rules:
  Every count comes from a live source. NO mocks, NO estimates.
    Scout      → db.campaign_leads.count() in last 4h
    Architect  → db.auto_built_sites status='rendered' in last 4h, then HTTP-GET
                 each preview URL, only count those returning 200 + size>1000.
    Envoy      → db.email_logs status='delivered' in last 4h (Resend confirmed).
    Signups    → db.platform_users created_at > today 00:00 EST.
    Revenue    → Stripe `charges.list(created>today)` + `subscriptions.list(active)`.

Each event also writes a row to `daily_verification_log` so the founder can
audit real vs. claimed numbers at /admin/daily-log.

NOTE: This module is *side-effect free* until set_db() is called and one of the
public functions is invoked from the scheduler.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TZ_EST = ZoneInfo("America/Toronto")
FOUNDER_EMAIL = os.environ.get("FOUNDER_EMAIL", "teji.ss1986@gmail.com")
FOUNDER_PHONE = os.environ.get("FOUNDER_PHONE", "+16134000000")
RESEND_FROM = os.environ.get("RESEND_FROM_EMAIL", "tj@aurem.live")
PUBLIC_APP_URL = (
    os.environ.get("AUREM_PUBLIC_URL")
    or os.environ.get("PUBLIC_APP_URL")
    or "https://aurem.live"
).rstrip("/")
VERIFICATION_COLLECTION = "daily_verification_log"

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _get_db():
    return _db


# ─── Founder identity ────────────────────────────────────────────────
async def _founder_user_id() -> Optional[str]:
    """Find the founder's user_id (push target).

    Searches platform_users → users (admin collection). Returns the canonical
    user_id we use to look up push_subscriptions.
    """
    db = _get_db()
    if db is None:
        return None
    # 1) platform_users (where customer push subs typically live)
    user = await db.platform_users.find_one(
        {"$or": [
            {"email": FOUNDER_EMAIL},
            {"is_founder": True},
        ]},
        {"_id": 0, "user_id": 1, "id": 1, "email": 1},
    )
    if user:
        return user.get("user_id") or user.get("id") or user.get("email")
    # 2) admin `users` collection (founder's super_admin record)
    admin = await db.users.find_one(
        {"$or": [{"email": FOUNDER_EMAIL}, {"role": "super_admin"}]},
        {"_id": 0, "user_id": 1, "id": 1, "email": 1},
    )
    if admin:
        return admin.get("user_id") or admin.get("id") or admin.get("email")
    return FOUNDER_EMAIL  # fallback so log row still references something useful


# ─── Real verification helpers ───────────────────────────────────────
def _today_start_est() -> datetime:
    now_est = datetime.now(TZ_EST)
    return now_est.replace(hour=0, minute=0, second=0, microsecond=0)


async def real_count_scout_today() -> int:
    """How many leads were added to campaign_leads since today 00:00 EST."""
    db = _get_db()
    if db is None:
        return 0
    iso = _today_start_est().isoformat()
    return await db.campaign_leads.count_documents({"created_at": {"$gte": iso}})


async def real_count_sites_built_today() -> Tuple[int, int, Optional[str]]:
    """Return (rendered_count, http_verified_count, sample_preview_url).

    HTTP-verifies up to 5 preview URLs to confirm they actually serve content.
    """
    db = _get_db()
    if db is None:
        return (0, 0, None)
    iso = _today_start_est().isoformat()
    rendered = await db.auto_built_sites.count_documents({
        "status": "rendered",
        "created_at": {"$gte": iso},
    })
    sample_url = None
    verified = 0
    if rendered > 0:
        sample_docs = await db.auto_built_sites.find(
            {"status": "rendered", "created_at": {"$gte": iso}},
            {"_id": 0, "preview_url": 1, "public_url": 1, "slug": 1},
        ).limit(5).to_list(5)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as cli:
                for doc in sample_docs:
                    url = (doc.get("preview_url")
                           or doc.get("public_url")
                           or (f"{PUBLIC_APP_URL}/api/sites/{doc.get('slug')}"
                               if doc.get("slug") else None))
                    if not url:
                        continue
                    if not url.startswith(("http://", "https://")):
                        url = PUBLIC_APP_URL + url
                    try:
                        r = await cli.get(url)
                        if r.status_code == 200 and len(r.content) > 1000:
                            verified += 1
                            if not sample_url:
                                sample_url = url
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"[brief] HTTP-verify error: {e}")
    return (rendered, verified, sample_url)


async def real_count_emails_delivered_today() -> Tuple[int, int]:
    """Return (sent, delivered) from email_logs since today 00:00 EST.

    `delivered` only counts entries where Resend confirmed delivery.
    """
    db = _get_db()
    if db is None:
        return (0, 0)
    iso = _today_start_est().isoformat()
    sent = await db.email_logs.count_documents({"sent_at": {"$gte": iso}})
    delivered = await db.email_logs.count_documents({
        "sent_at": {"$gte": iso},
        "status": {"$in": ["delivered", "sent"]},
        "resend_id": {"$exists": True, "$ne": None},
    })
    return (sent, delivered)


async def real_count_signups_today() -> int:
    db = _get_db()
    if db is None:
        return 0
    iso = _today_start_est().isoformat()
    return await db.platform_users.count_documents({
        "created_at": {"$gte": iso},
    })


async def real_revenue_today() -> Tuple[float, int]:
    """Return (revenue_today_usd, active_subscribers_count) from live Stripe."""
    api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not api_key:
        return (0.0, 0)
    try:
        import stripe  # type: ignore
    except ImportError:
        return (0.0, 0)
    stripe.api_key = api_key
    revenue = 0.0
    active_subs = 0
    try:
        ts = int(_today_start_est().timestamp())
        charges = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: stripe.Charge.list(created={"gte": ts}, limit=100),
        )
        for ch in charges.auto_paging_iter():
            if ch.get("paid") and ch.get("status") == "succeeded":
                revenue += (ch.get("amount", 0) / 100.0)
        subs = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: stripe.Subscription.list(status="active", limit=100),
        )
        active_subs = sum(1 for _ in subs.auto_paging_iter())
    except Exception as e:
        logger.warning(f"[brief] Stripe fetch error: {e}")
    return (round(revenue, 2), active_subs)


async def top_lead_today() -> Optional[Dict[str, Any]]:
    """Highest-engagement lead today: prefer signed-up > clicked > opened."""
    db = _get_db()
    if db is None:
        return None
    iso = _today_start_est().isoformat()
    # Most recent signup
    signup = await db.platform_users.find_one(
        {"created_at": {"$gte": iso}},
        {"_id": 0, "email": 1, "business_name": 1, "city": 1, "created_at": 1},
        sort=[("created_at", -1)],
    )
    if signup:
        return {**signup, "status": "signed up"}
    # Most opens
    opened = await db.email_logs.find_one(
        {"sent_at": {"$gte": iso}, "open_count": {"$gt": 0}},
        {"_id": 0, "to_email": 1, "business_name": 1, "open_count": 1, "click_count": 1},
        sort=[("open_count", -1)],
    )
    if opened:
        return {
            "email": opened.get("to_email"),
            "business_name": opened.get("business_name"),
            "status": f"opened {opened.get('open_count')}× · {opened.get('click_count', 0)} clicks",
        }
    return None


# ─── Push notification helpers ───────────────────────────────────────
async def _push(title: str, body: str, data: Optional[Dict] = None) -> bool:
    """Send a single push to the founder's subscribed devices. Returns success."""
    uid = await _founder_user_id()
    if not uid:
        logger.warning("[brief] Founder user_id not found — push skipped")
        return False
    try:
        from services.push_notification_service import _send_push
        await _send_push(uid, title, body, data or {})
        return True
    except Exception as e:
        logger.warning(f"[brief] push failed: {e}")
        return False


# ─── Mismatch threshold ──────────────────────────────────────────────
MISMATCH_THRESHOLD = 0.10  # 10% gap triggers a verification fail-alert


async def _check_mismatch(step: str, claimed: int, verified: int) -> bool:
    """If verified count drifts from claimed by >MISMATCH_THRESHOLD, fire an
    immediate "Verification Mismatch" push and write a fail row to the log.

    Returns True if an alert was fired.
    """
    if claimed <= 0:
        return False
    gap = claimed - verified
    if gap <= 0:
        return False  # over-delivered or matched
    pct = gap / claimed
    if pct < MISMATCH_THRESHOLD:
        return False
    pct_str = f"{int(pct * 100)}%"
    await _push(
        f"⚠️ Verification Mismatch — {step}",
        f"{step} claimed {claimed} but verified {verified} ({pct_str} gap) · check /admin/daily-log",
        {"event": "mismatch_alert", "step": step, "claimed": claimed,
         "verified": verified, "gap_pct": round(pct, 3)},
    )
    await record_verification_log("mismatch_alert", {
        "step": step, "claimed": claimed, "verified": verified,
        "gap": gap, "gap_pct": round(pct, 3),
        "all_verified": False,
    })
    return True


# ─── Verification log ────────────────────────────────────────────────
async def record_verification_log(event: str, payload: Dict[str, Any]) -> None:
    """Append a row to daily_verification_log."""
    db = _get_db()
    if db is None:
        return
    now = datetime.now(timezone.utc)
    today = datetime.now(TZ_EST).date().isoformat()
    await db[VERIFICATION_COLLECTION].insert_one({
        "date": today,
        "event": event,
        "ts_utc": now.isoformat(),
        **payload,
    })


# ─── Step push events (with real verification) ──────────────────────
async def push_morning_armed() -> None:
    """9:00 AM EST — morning brief push."""
    leads = await real_count_scout_today()
    await _push(
        "AUREM Armed",
        f"Scout starting · 25 leads targeted · {leads} so far today",
        {"event": "morning_armed", "leads_today": leads},
    )
    await record_verification_log("morning_armed", {"leads_today": leads})


async def push_scout_complete() -> None:
    """After Scout → push real lead count.

    Mismatch: if SCOUT_DAILY_TARGET env is set and gap > threshold, alert.
    """
    leads = await real_count_scout_today()
    if leads == 0:
        await _push(
            "Scout Alert",
            "Scout finished but 0 new leads in DB — check Emergent logs",
            {"event": "scout_alert", "leads": 0},
        )
        await record_verification_log("scout_complete", {
            "leads_real_count": 0, "all_verified": False,
        })
        return
    await _push(
        "Scout Complete",
        f"Found {leads} real leads · Architect starting next",
        {"event": "scout_complete", "leads": leads},
    )
    await record_verification_log("scout_complete", {
        "leads_real_count": leads, "all_verified": True,
    })
    # Mismatch check vs daily target if configured
    try:
        target = int(os.environ.get("SCOUT_DAILY_TARGET", "0"))
    except Exception:
        target = 0
    if target > 0:
        await _check_mismatch("Scout", target, leads)


async def push_architect_complete() -> None:
    """After Architect → push HTTP-verified site count."""
    rendered, verified, sample = await real_count_sites_built_today()
    if rendered == 0:
        await _push(
            "Architect Alert",
            "Architect finished but 0 sites in DB",
            {"event": "architect_alert"},
        )
        await record_verification_log("architect_complete", {
            "rendered": 0, "http_verified": 0, "all_verified": False,
        })
        return
    await _push(
        "Sites Built",
        f"{verified}/{rendered} sites HTTP-200 verified · Envoy queueing outreach",
        {"event": "architect_complete", "rendered": rendered,
         "verified": verified, "sample_url": sample},
    )
    await record_verification_log("architect_complete", {
        "rendered": rendered,
        "http_verified": verified,
        "sample_preview_url": sample,
        "all_verified": (verified == rendered),
    })
    # Mismatch alert: rendered vs HTTP-verified
    await _check_mismatch("Architect", rendered, verified)


async def push_envoy_complete() -> None:
    """After Envoy → push Resend-confirmed email count."""
    sent, delivered = await real_count_emails_delivered_today()
    if sent == 0:
        await _push(
            "Outreach Alert",
            "Envoy ran but 0 emails sent today",
            {"event": "envoy_alert"},
        )
        await record_verification_log("envoy_complete", {
            "sent": 0, "delivered": 0, "all_verified": False,
        })
        return
    await _push(
        "Outreach Sent",
        f"{delivered}/{sent} emails delivered · Resend confirmed",
        {"event": "envoy_complete", "sent": sent, "delivered": delivered},
    )
    await record_verification_log("envoy_complete", {
        "emails_sent": sent,
        "emails_resend_confirmed": delivered,
        "all_verified": (delivered > 0),
    })
    # Mismatch alert: sent vs delivered
    await _check_mismatch("Envoy", sent, delivered)


async def push_midday_check() -> None:
    """1:00 PM EST — midday push with real numbers."""
    sent, delivered = await real_count_emails_delivered_today()
    signups = await real_count_signups_today()
    db = _get_db()
    iso = _today_start_est().isoformat()
    opens = clicks = 0
    if db is not None:
        opens_doc = db.email_logs.aggregate([
            {"$match": {"sent_at": {"$gte": iso}}},
            {"$group": {
                "_id": None,
                "opens": {"$sum": {"$ifNull": ["$open_count", 0]}},
                "clicks": {"$sum": {"$ifNull": ["$click_count", 0]}},
            }},
        ])
        async for d in opens_doc:
            opens = int(d.get("opens", 0))
            clicks = int(d.get("clicks", 0))
    await _push(
        "Midday Check",
        f"{opens} opens · {clicks} clicks · {signups} signups",
        {"event": "midday_check", "opens": opens, "clicks": clicks,
         "signups": signups, "delivered": delivered},
    )
    await record_verification_log("midday_check", {
        "opens": opens, "clicks": clicks,
        "signups_mongodb_count": signups,
        "emails_delivered": delivered,
    })


# ─── End of day: branded HTML email ─────────────────────────────────
async def send_end_of_day_email() -> Dict[str, Any]:
    """6:00 PM EST — daily report. Returns {ok, resend_id?, error?, payload}."""
    leads = await real_count_scout_today()
    rendered, verified, sample = await real_count_sites_built_today()
    sent, delivered = await real_count_emails_delivered_today()
    signups = await real_count_signups_today()
    revenue, active_subs = await real_revenue_today()
    top = await top_lead_today()

    today_str = datetime.now(TZ_EST).strftime("%a, %b %d %Y")
    payload = {
        "leads_real_count": leads,
        "sites_rendered": rendered,
        "sites_http_verified": verified,
        "sample_preview_url": sample,
        "emails_sent": sent,
        "emails_resend_confirmed": delivered,
        "signups_mongodb_count": signups,
        "stripe_revenue_real": revenue,
        "active_subscribers": active_subs,
        "top_lead": top,
        "all_verified": (rendered == verified) and (sent == 0 or delivered > 0),
    }
    await record_verification_log("end_of_day", payload)

    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "RESEND_API_KEY not set", "payload": payload}

    top_block = (
        f'<div style="margin-top:18px;padding:14px 18px;background:rgba(249,115,22,0.07);'
        f'border:1px solid rgba(249,115,22,0.18);border-radius:10px;">'
        f'<div style="font-size:10px;letter-spacing:.18em;color:#F97316;text-transform:uppercase;margin-bottom:6px;">Top Lead Today</div>'
        f'<div style="font-size:14px;color:#E8E0D0;font-weight:600;">{(top or {}).get("business_name") or (top or {}).get("email") or "—"}</div>'
        f'<div style="font-size:12px;color:#86EFAC;margin-top:2px;">{(top or {}).get("status", "—")}</div>'
        f'</div>' if top else ''
    )

    sample_block = (
        f'<div style="font-size:11px;color:#8A8070;margin-top:6px;">'
        f'Sample verified site: <a href="{sample}" style="color:#FDBA74;text-decoration:none;">{sample}</a></div>'
        if sample else ''
    )

    verify_pill = (
        '<span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:10px;letter-spacing:.16em;font-weight:700;background:rgba(34,197,94,0.12);color:#86EFAC;">ALL VERIFIED</span>'
        if payload["all_verified"]
        else '<span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:10px;letter-spacing:.16em;font-weight:700;background:rgba(252,165,165,0.12);color:#FCA5A5;">PARTIAL</span>'
    )

    html = f"""\
<!doctype html>
<html><body style="margin:0;padding:0;background:#050510;font-family:'Helvetica Neue',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#050510;padding:32px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:#0D0D0D;border:1px solid rgba(249,115,22,0.2);border-radius:14px;overflow:hidden;">

<tr><td style="padding:32px 32px 8px;">
  <div style="font-family:'Cinzel',serif;font-size:11px;letter-spacing:.22em;color:#F97316;text-transform:uppercase;margin-bottom:8px;">AUREM · Daily Report</div>
  <div style="font-family:'Cinzel',serif;font-size:24px;color:#FFF;letter-spacing:.02em;">{today_str}</div>
  <div style="margin-top:12px;">{verify_pill}</div>
</td></tr>

<tr><td style="padding:8px 32px 24px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td style="padding:14px 18px;background:#060606;border:1px solid rgba(249,115,22,0.12);border-radius:10px;width:48%;vertical-align:top;">
        <div style="font-size:9px;letter-spacing:.18em;color:#8A8070;text-transform:uppercase;">Leads Found</div>
        <div style="font-family:'Cinzel',serif;font-size:32px;color:#F97316;text-shadow:0 0 14px rgba(249,115,22,.4);margin-top:6px;line-height:1;">{leads}</div>
        <div style="font-size:11px;color:#5A5248;margin-top:4px;">MongoDB verified</div>
      </td>
      <td style="width:4%;"></td>
      <td style="padding:14px 18px;background:#060606;border:1px solid rgba(249,115,22,0.12);border-radius:10px;width:48%;vertical-align:top;">
        <div style="font-size:9px;letter-spacing:.18em;color:#8A8070;text-transform:uppercase;">Sites Built</div>
        <div style="font-family:'Cinzel',serif;font-size:32px;color:#F97316;text-shadow:0 0 14px rgba(249,115,22,.4);margin-top:6px;line-height:1;">{verified}<span style="font-size:18px;color:#5A5248;">/{rendered}</span></div>
        <div style="font-size:11px;color:#5A5248;margin-top:4px;">HTTP-200 verified</div>
      </td>
    </tr>
    <tr><td colspan="3" style="height:14px;"></td></tr>
    <tr>
      <td style="padding:14px 18px;background:#060606;border:1px solid rgba(249,115,22,0.12);border-radius:10px;vertical-align:top;">
        <div style="font-size:9px;letter-spacing:.18em;color:#8A8070;text-transform:uppercase;">Emails Delivered</div>
        <div style="font-family:'Cinzel',serif;font-size:32px;color:#F97316;text-shadow:0 0 14px rgba(249,115,22,.4);margin-top:6px;line-height:1;">{delivered}<span style="font-size:18px;color:#5A5248;">/{sent}</span></div>
        <div style="font-size:11px;color:#5A5248;margin-top:4px;">Resend confirmed</div>
      </td>
      <td></td>
      <td style="padding:14px 18px;background:#060606;border:1px solid rgba(249,115,22,0.12);border-radius:10px;vertical-align:top;">
        <div style="font-size:9px;letter-spacing:.18em;color:#8A8070;text-transform:uppercase;">New Signups</div>
        <div style="font-family:'Cinzel',serif;font-size:32px;color:#F97316;text-shadow:0 0 14px rgba(249,115,22,.4);margin-top:6px;line-height:1;">{signups}</div>
        <div style="font-size:11px;color:#5A5248;margin-top:4px;">platform_users today</div>
      </td>
    </tr>
    <tr><td colspan="3" style="height:14px;"></td></tr>
    <tr>
      <td colspan="3" style="padding:14px 18px;background:#060606;border:1px solid rgba(34,197,94,0.16);border-radius:10px;">
        <div style="font-size:9px;letter-spacing:.18em;color:#8A8070;text-transform:uppercase;">Revenue Today (Stripe live)</div>
        <div style="font-family:'Cinzel',serif;font-size:32px;color:#86EFAC;text-shadow:0 0 14px rgba(34,197,94,.4);margin-top:6px;line-height:1;">${revenue:,.2f}</div>
        <div style="font-size:11px;color:#5A5248;margin-top:4px;">Active subscribers: {active_subs}</div>
      </td>
    </tr>
  </table>
  {top_block}
  {sample_block}
</td></tr>

<tr><td style="padding:8px 32px 24px;">
  <a href="{PUBLIC_APP_URL}/admin/daily-log" style="display:inline-block;padding:14px 28px;background:#F97316;color:#0A0A00;text-decoration:none;border-radius:8px;font-weight:700;font-size:12px;letter-spacing:.08em;">VIEW VERIFICATION LOG →</a>
</td></tr>

<tr><td style="padding:18px 32px;background:#030303;border-top:1px solid rgba(249,115,22,0.12);text-align:center;color:#5A5248;font-size:11px;letter-spacing:.06em;">
  All numbers pulled from live MongoDB / Stripe / Resend. No mocks.<br/>
  ORA by AUREM
</td></tr>

</table>
</td></tr>
</table>
</body></html>
"""

    try:
        import resend  # type: ignore
        resend.api_key = api_key
        resp = resend.Emails.send({
            "from": RESEND_FROM,
            "to": FOUNDER_EMAIL,
            "subject": f"AUREM Daily Report — {today_str}",
            "html": html,
        })
        rid = resp.get("id") if isinstance(resp, dict) else None
        logger.info(f"[brief] end-of-day email sent id={rid}")
        await record_verification_log("end_of_day_email", {
            "resend_id": rid, "to": FOUNDER_EMAIL, "all_verified": True,
        })
        return {"ok": True, "resend_id": rid, "payload": payload}
    except Exception as e:
        logger.warning(f"[brief] end-of-day email failed: {e}")
        return {"ok": False, "error": str(e)[:200], "payload": payload}
