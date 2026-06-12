"""
Post-Publish Triggers (iter 315b)
==================================
After every AWB site goes live, two automated nudges to the customer:

  1. **Edit-portal welcome** — sent immediately on `status: published`.
     Email + WhatsApp with a 24h magic link so the customer can
     personalize their new site.
  2. **Domain upsell** — sent ~2 hours later. WhatsApp + email pointing
     to `aurem.live/report/{slug}?domain_addon=true&domain={suggestion}`
     — closes the 779-sites / 0-domains gap.

Both nudges are idempotent (one shot per site_id per kind).

Public:
  await fire_onboarding_welcome(db, site_id) -> dict
  await fire_domain_upsell(db, site_id) -> dict
  await post_publish_scheduler(db) -> coroutine for asyncio.create_task
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import httpx

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

UPSELL_DELAY_HOURS = int(os.environ.get("UPSELL_DELAY_HOURS", "2"))
# iter 282 fix: previously hard-defaulted to https://aurem.live which broke
# preview-env testing — emails went out with aurem.live URLs but the sites
# were stored in preview Mongo, returning 404 in production. Prefer runtime
# env signals: AUREM_PUBLIC_URL (explicit override) → PUBLIC_APP_URL
# (set per-deployment) → aurem.live (last-resort prod fallback).
PUBLIC_BASE = (
    os.environ.get("AUREM_PUBLIC_URL")
    or os.environ.get("PUBLIC_APP_URL")
    or "https://aurem.live"
).rstrip("/")


def _suggest_domain(business_name: str) -> str:
    if not business_name:
        return "yourbusiness.com"
    s = business_name.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return f"{(s or 'yourbusiness')[:24]}.com"


async def _send_email(to: str, subject: str, html: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key or not to:
        return False
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "ORA <ora@aurem.live>")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.resend.com/emails",
                headers={"authorization": f"Bearer {api_key}",
                          "content-type": "application/json"},
                json={"from": from_addr, "to": [to],
                       "subject": subject, "html": html},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning(f"[publish-trig] email failed: {e}")
        return False


async def _send_whatsapp_safe(to: str, body: str) -> bool:
    if not to:
        return False
    try:
        from routers.whatsapp_alerts import send_whatsapp
        out = await send_whatsapp(to, body)
        return bool(out and out.get("ok"))
    except Exception as e:
        logger.debug(f"[publish-trig] whatsapp failed: {e}")
        return False


async def _site_recipient(db, site: Dict[str, Any]) -> Dict[str, str]:
    """Best-effort email + phone for the customer.
    Lookup order: site fields → campaign_leads → customer_scans → leads.
    """
    custom = site.get("custom_content") or {}
    email = (custom.get("email") or site.get("contact_email")
              or site.get("business_email") or "")
    phone = custom.get("phone") or ""
    lead_id = site.get("lead_id")
    if (not email or not phone) and lead_id:
        lead = await db.campaign_leads.find_one(
            {"lead_id": lead_id, "business_id": FOUNDER_BIN},
            {"_id": 0, "email": 1, "phone": 1},
        ) or {}
        email = email or (lead.get("email") or "")
        phone = phone or (lead.get("phone") or "")
    if (not email or not phone) and lead_id:
        scan = await db.customer_scans.find_one(
            {"lead_id": lead_id},
            {"_id": 0, "email": 1, "phone": 1,
              "business_email": 1, "contact_email": 1},
            sort=[("created_at", -1)],
        ) or {}
        email = email or (scan.get("email") or scan.get("business_email")
                            or scan.get("contact_email") or "")
        phone = phone or (scan.get("phone") or "")
    if (not email or not phone) and lead_id:
        try:
            l2 = await db.leads.find_one(
                {"$or": [{"lead_id": lead_id}, {"id": lead_id}]},
                {"_id": 0, "email": 1, "phone": 1},
            ) or {}
            email = email or (l2.get("email") or "")
            phone = phone or (l2.get("phone") or "")
        except Exception:
            pass
    return {"email": (email or "").strip(),
            "phone": (phone or "").strip()}


async def _mint_edit_link(db, site: Dict[str, Any], email: str) -> str:
    """24h magic link, same hashing rules as customer_edit_router."""
    import hashlib
    raw = secrets.token_urlsafe(28)
    rec = {
        "request_id": uuid.uuid4().hex[:12],
        "site_id": site["site_id"], "slug": site.get("slug"),
        "email_to": email, "kind": "request",
        "token_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc)
                        + timedelta(hours=24)).isoformat(),
        "consumed": False,
        "auto_triggered": "post_publish",
    }
    try:
        await db.edit_sessions.insert_one(dict(rec))
    except Exception as e:
        logger.warning(f"[publish-trig] mint failed: {e}")
    slug = site.get("slug") or site["site_id"]
    return f"{PUBLIC_BASE}/edit?token={raw}&site={slug}"


# ─── Public surface ──────────────────────────────────────────────────────
async def fire_onboarding_welcome(db, site_id: str) -> Dict[str, Any]:
    site = await db.auto_built_sites.find_one(
        {"site_id": site_id}, {"_id": 0})
    if not site:
        return {"ok": False, "error": "site_not_found"}
    if (site.get("post_publish") or {}).get("welcome_sent_at"):
        return {"ok": True, "skipped": "already_sent"}

    biz = site.get("business_name") or "your business"
    contact = await _site_recipient(db, site)
    edit_link = await _mint_edit_link(db, site, contact["email"]) \
        if contact["email"] else None

    # iter 280.9 — resolve a customer-clickable absolute URL. Older rows
    # in `auto_built_sites` stored `preview_url` as the admin endpoint
    # (`/api/admin/platform/website-builder/preview/{id}`) which required
    # super_admin auth and produced "Link Expired" pages when emailed to
    # the customer. Always normalize:
    #   1. live_url if absolute (https://...)
    #   2. {PUBLIC_BASE}/api/sites/{slug} if we have a slug
    #   3. preview_url ONLY if it's already absolute https
    #   4. final fallback: PUBLIC_BASE root
    def _resolve_site_url() -> str:
        for cand in (site.get("live_url"),):
            if cand and cand.startswith("https://"):
                return cand
        slug = site.get("slug")
        if slug:
            return f"{PUBLIC_BASE}/api/sites/{slug}"
        pv = site.get("preview_url") or ""
        if pv.startswith("https://"):
            return pv
        return PUBLIC_BASE
    live_url = _resolve_site_url()
    html_link = edit_link or f"{PUBLIC_BASE}/edit"
    # iter 282g — branded HTML template with auto-screenshot when available
    try:
        from services.brand_emails import render_site_live
        user_doc = {
            "first_name": (contact.get("first_name")
                           or (contact.get("name") or biz).split(" ")[0]),
            "business_name": biz,
            "email": contact.get("email"),
        }
        html = render_site_live(
            user_doc,
            site_url=live_url,
            screenshot_url=site.get("screenshot_url"),
            portal_url=html_link,
        )
    except Exception as _render_err:
        logger.debug(f"[post_publish] branded render failed: {_render_err}")
        html = (
            f"<div style='font-family:Georgia,serif;max-width:520px'>"
            f"<h2 style='color:#F97316'>Your AUREM site is live</h2>"
            f"<p><strong>{biz}</strong> — your new site is ready:<br>"
            f"<a href='{live_url}'>{live_url}</a></p>"
            f"<p style='margin:22px 0'>"
            f"<a href='{html_link}' style='background:#F97316;color:#0A0A00;"
            f"padding:12px 22px;border-radius:6px;font-weight:700;"
            f"text-decoration:none'>Open Edit Portal</a></p>"
            f"</div>"
        )
    sms_body = (
        f"Your AUREM site is live: {live_url}\n\n"
        f"Personalize it in 60 sec (24h link):\n{html_link}"
    )
    email_ok = await _send_email(contact["email"],
                                    f"Your {biz} site is live", html)
    wa_ok = await _send_whatsapp_safe(contact["phone"], sms_body)

    delivered = bool(email_ok or wa_ok)
    update_set = {
        "post_publish.welcome_attempt_at": datetime.now(timezone.utc).isoformat(),
        "post_publish.welcome_email_ok": email_ok,
        "post_publish.welcome_whatsapp_ok": wa_ok,
        "post_publish.welcome_edit_link": edit_link,
        "post_publish.welcome_to_email": contact["email"],
        "post_publish.welcome_to_phone": contact["phone"],
    }
    if delivered:
        update_set["post_publish.welcome_sent_at"] = datetime.now(
            timezone.utc).isoformat()
    await db.auto_built_sites.update_one(
        {"site_id": site_id}, {"$set": update_set})
    return {"ok": True, "site_id": site_id, "delivered": delivered,
            "email_ok": email_ok, "whatsapp_ok": wa_ok,
            "to_email": contact["email"], "to_phone": contact["phone"],
            "edit_link": edit_link}


async def fire_domain_upsell(db, site_id: str) -> Dict[str, Any]:
    site = await db.auto_built_sites.find_one(
        {"site_id": site_id}, {"_id": 0})
    if not site:
        return {"ok": False, "error": "site_not_found"}
    if (site.get("post_publish") or {}).get("upsell_sent_at"):
        return {"ok": True, "skipped": "already_sent"}

    # If the customer already attached a domain, skip
    if site.get("custom_domain") or site.get("custom_content", {}).get("domain"):
        await db.auto_built_sites.update_one(
            {"site_id": site_id},
            {"$set": {"post_publish.upsell_sent_at": datetime.now(timezone.utc).isoformat(),
                       "post_publish.upsell_skipped": "already_has_domain"}},
        )
        return {"ok": True, "skipped": "already_has_domain"}

    biz = site.get("business_name") or "your business"
    suggestion = _suggest_domain(biz)
    contact = await _site_recipient(db, site)

    public_slug = None
    try:
        scan = await db.customer_scans.find_one(
            {"lead_id": site.get("lead_id")},
            {"_id": 0, "public_slug": 1},
            sort=[("created_at", -1)],
        )
        public_slug = (scan or {}).get("public_slug")
    except Exception:
        pass

    if public_slug:
        upsell_link = (f"{PUBLIC_BASE}/api/repair-report/{public_slug}"
                        f"?domain_addon=true&domain={suggestion}")
    else:
        upsell_link = f"{PUBLIC_BASE}/sample/{site.get('slug', site_id)}"

    sms_body = (
        f"Your site is live 🎉  Claim your domain before someone else does.\n"
        f"{suggestion} → $29 CAD/yr\n{upsell_link}"
    )
    html = (
        f"<div style='font-family:Georgia,serif;max-width:520px'>"
        f"<h2 style='color:#8a6d1c'>Claim your domain — {suggestion}</h2>"
        f"<p>Your <strong>{biz}</strong> site is live. Add a custom "
        f"domain so customers can find you at your own address — "
        f"<strong>$29 CAD/year</strong>, auto-renews, free SSL.</p>"
        f"<p style='margin:22px 0'>"
        f"<a href='{upsell_link}' style='background:#C9A227;color:#0A0A0A;"
        f"padding:12px 22px;border-radius:6px;font-weight:700;"
        f"text-decoration:none'>Claim {suggestion}</a></p>"
        f"<p style='font-size:11px;color:#888'>One-time check — most "
        f".com names go fast.</p></div>"
    )

    email_ok = await _send_email(contact["email"],
                                    f"Claim {suggestion} — $29 CAD/yr", html)
    wa_ok = await _send_whatsapp_safe(contact["phone"], sms_body)

    delivered = bool(email_ok or wa_ok)
    update_set = {
        "post_publish.upsell_attempt_at": datetime.now(timezone.utc).isoformat(),
        "post_publish.upsell_email_ok": email_ok,
        "post_publish.upsell_whatsapp_ok": wa_ok,
        "post_publish.upsell_suggestion": suggestion,
        "post_publish.upsell_link": upsell_link,
        "post_publish.upsell_to_email": contact["email"],
        "post_publish.upsell_to_phone": contact["phone"],
    }
    if delivered:
        update_set["post_publish.upsell_sent_at"] = datetime.now(
            timezone.utc).isoformat()
    await db.auto_built_sites.update_one(
        {"site_id": site_id}, {"$set": update_set})
    return {"ok": True, "site_id": site_id, "suggestion": suggestion,
            "delivered": delivered, "email_ok": email_ok,
            "whatsapp_ok": wa_ok, "to_email": contact["email"],
            "to_phone": contact["phone"], "upsell_link": upsell_link}


FOLLOWUP_DELAY_HOURS = int(os.environ.get("EDIT_FOLLOWUP_DELAY_HOURS", "24"))


async def fire_edit_followup(db, request_id: str) -> Dict[str, Any]:
    """Single follow-up nudge if 24h after welcome the customer hasn't
    opened the edit link. WhatsApp + email. Once-only per request_id.
    """
    rec = await db.edit_sessions.find_one(
        {"request_id": request_id, "kind": "request"}, {"_id": 0})
    if not rec:
        return {"ok": False, "error": "session_not_found"}
    if rec.get("follow_up_sent_at"):
        return {"ok": True, "skipped": "already_sent"}
    if rec.get("consumed") or rec.get("opened_at"):
        return {"ok": True, "skipped": "already_opened"}
    # link expired? skip silently
    try:
        if rec.get("expires_at", "") < datetime.now(timezone.utc).isoformat():
            await db.edit_sessions.update_one(
                {"request_id": request_id},
                {"$set": {"follow_up_skipped": "expired",
                           "follow_up_sent_at": datetime.now(timezone.utc).isoformat()}},
            )
            return {"ok": True, "skipped": "expired"}
    except Exception:
        pass

    site = await db.auto_built_sites.find_one(
        {"site_id": rec.get("site_id")}, {"_id": 0}) or {}
    biz = site.get("business_name") or "your site"
    contact = await _site_recipient(db, site)
    pp = site.get("post_publish") or {}
    edit_link = pp.get("welcome_edit_link") or ""
    if not edit_link:
        return {"ok": False, "error": "no_edit_link"}

    name = ""
    custom = site.get("custom_content") or {}
    name = (custom.get("contact_name") or biz.split(" ")[0] or "there")
    sms = (
        f"Hi {name}! Your site is live 🎉\n"
        f"Personalize it in 2 min:\n{edit_link}\n"
        f"Takes 2 minutes, makes it yours."
    )
    html = (
        f"<div style='font-family:Georgia,serif;max-width:520px'>"
        f"<h2 style='color:#8a6d1c'>Hi {name} — your site is waiting 🎉</h2>"
        f"<p><strong>{biz}</strong> is live, but it's still using the "
        f"defaults we generated. 2 minutes is all it takes to make it yours: "
        f"swap the photo, tweak the headline, plug in your hours.</p>"
        f"<p style='margin:22px 0'>"
        f"<a href='{edit_link}' style='background:#C9A227;color:#0A0A0A;"
        f"padding:12px 22px;border-radius:6px;font-weight:700;"
        f"text-decoration:none'>Personalize My Site</a></p>"
        f"<p style='font-size:11px;color:#888'>This is a one-time nudge — "
        f"if the link expired, just reply and we'll mint a fresh one.</p>"
        f"</div>"
    )
    email_ok = await _send_email(contact["email"],
                                    f"{name}, your site is waiting", html)
    wa_ok = await _send_whatsapp_safe(contact["phone"], sms)
    await db.edit_sessions.update_one(
        {"request_id": request_id},
        {"$set": {
            "follow_up_sent_at": datetime.now(timezone.utc).isoformat(),
            "follow_up_email_ok": email_ok,
            "follow_up_whatsapp_ok": wa_ok,
        }},
    )
    return {"ok": True, "request_id": request_id,
            "delivered": bool(email_ok or wa_ok),
            "email_ok": email_ok, "whatsapp_ok": wa_ok}


# ─── Scheduler ───────────────────────────────────────────────────────────
async def post_publish_scheduler(db) -> None:
    """Runs forever. Every 5 min:
       · welcome any newly-published site that hasn't been welcomed
       · upsell any site published ≥ UPSELL_DELAY_HOURS ago without upsell
       · follow-up unopened edit links ≥ FOLLOWUP_DELAY_HOURS old
    """
    await asyncio.sleep(60)
    while True:
        try:
            now = datetime.now(timezone.utc)
            two_hours_ago = (now - timedelta(hours=UPSELL_DELAY_HOURS)).isoformat()
            followup_cutoff = (now - timedelta(hours=FOLLOWUP_DELAY_HOURS)).isoformat()

            # Welcome — any published site without welcome_sent_at
            welcome_q = {
                "status": {"$in": ["published", "deployed", "rendered"]},
                "$or": [
                    {"post_publish.welcome_sent_at": {"$exists": False}},
                    {"post_publish": {"$exists": False}},
                ],
            }
            welcome_cur = db.auto_built_sites.find(
                welcome_q, {"_id": 0, "site_id": 1}).limit(20)
            async for s in welcome_cur:
                try:
                    await fire_onboarding_welcome(db, s["site_id"])
                except Exception as e:
                    logger.warning(f"[publish-trig] welcome {s['site_id']}: {e}")

            # Domain upsell — published >= 2h, no upsell yet, no domain
            upsell_q = {
                "status": {"$in": ["published", "deployed", "rendered"]},
                "$or": [
                    {"created_at": {"$lte": two_hours_ago}},
                    {"published_at": {"$lte": two_hours_ago}},
                ],
                "$and": [{
                    "$or": [
                        {"post_publish.upsell_sent_at": {"$exists": False}},
                        {"post_publish": {"$exists": False}},
                    ]}],
                "custom_domain": {"$in": [None, ""]},
            }
            upsell_cur = db.auto_built_sites.find(
                upsell_q, {"_id": 0, "site_id": 1}).limit(20)
            async for s in upsell_cur:
                try:
                    await fire_domain_upsell(db, s["site_id"])
                except Exception as e:
                    logger.warning(f"[publish-trig] upsell {s['site_id']}: {e}")

            # Edit-link follow-up — auto-triggered request rows ≥ 24h old,
            # not consumed, not opened, not yet followed-up
            followup_q = {
                "kind": "request",
                "auto_triggered": "post_publish",
                "consumed": False,
                "created_at": {"$lte": followup_cutoff},
                "follow_up_sent_at": {"$exists": False},
                "$or": [
                    {"opened_at": {"$exists": False}},
                    {"opened_at": None},
                ],
            }
            fu_cur = db.edit_sessions.find(
                followup_q, {"_id": 0, "request_id": 1}).limit(50)
            async for r in fu_cur:
                try:
                    await fire_edit_followup(db, r["request_id"])
                except Exception as e:
                    logger.warning(
                        f"[publish-trig] followup {r.get('request_id')}: {e}")

        except Exception as e:
            logger.warning(f"[publish-trig] tick failed: {e}")
        await asyncio.sleep(300)  # 5 min
