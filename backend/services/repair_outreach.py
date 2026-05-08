"""
Repair Outreach Trigger (iter 304)
==================================
Polls db.campaign_leads for `audit_score < 60 AND repair_outreach_sent != true`,
fires a "website_repair_offer" template via WhatsApp + Email, then stamps the
lead. CASL-safe: only sends to leads with channel_gating allowing the channel.

Public API:
  await fire_due_repair_outreach(db) -> dict
  await repair_outreach_scheduler() -> never returns
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 600   # every 10 min
BATCH_PER_CYCLE = 10
MIN_OUTREACH_GAP_HOURS = 24

REPORT_BASE = os.environ.get("AUREM_PUBLIC_BASE", "https://aurem.live")

_db = None


def set_db(db):
    global _db
    _db = db


def _icon_for(kind: str) -> str:
    return {
        "ssl": "🔒", "speed": "⚡", "mobile": "📱",
        "broken_links": "🔗", "contact_form": "📝",
        "social_links": "📣", "copyright_year": "📅",
        "google_maps": "📍",
    }.get(kind, "•")


def _build_whatsapp(lead: Dict[str, Any], audit: Dict[str, Any], slug: str) -> str:
    biz = lead.get("business_name") or "there"
    site = audit.get("website") or lead.get("website_url") or ""
    score = audit.get("overall_score") or 0
    issues = (audit.get("issues") or [])[:3]
    if issues:
        bullets = "\n".join(
            f"{_icon_for(i.get('kind',''))} {i.get('title','')}" for i in issues
        )
    else:
        bullets = "• Multiple performance + UX issues"
    return (
        f"Hi {biz}! 👋\n\n"
        f"I just analyzed {site} and found {len(audit.get('issues') or [])} issues:\n\n"
        f"{bullets}\n\n"
        f"Your site scored {score}/100.\n\n"
        f"AUREM can fix this automatically:\n"
        f"✅ SSL repair\n"
        f"✅ Mobile + speed optimization\n"
        f"✅ Broken link cleanup\n"
        f"✅ Contact form + social links\n\n"
        f"Starting at $149 CAD — done in 24h.\n\n"
        f"See your full report:\n{REPORT_BASE}/api/repair-report/{slug}\n\n"
        f"Reply YES to get started 🚀"
    )


def _build_email(lead: Dict[str, Any], audit: Dict[str, Any], slug: str) -> Dict[str, str]:
    biz = lead.get("business_name") or "your business"
    site = audit.get("website") or ""
    score = audit.get("overall_score") or 0
    issues = (audit.get("issues") or [])[:5]
    li = "".join(
        f"<li><strong>{_icon_for(i.get('kind',''))} {i.get('title','')}</strong>"
        f"<br><small style='color:#666'>{(i.get('detail') or '')[:140]}</small></li>"
        for i in issues
    ) or "<li>Multiple issues affecting visibility, conversion, and trust.</li>"
    report_url = f"{REPORT_BASE}/api/repair-report/{slug}"
    html = (
        f"<div style='font-family:Inter,system-ui,sans-serif;max-width:560px;"
        f"margin:0 auto;padding:24px;color:#1a1a1a'>"
        f"<h2 style='font:600 24px Cormorant Garamond,serif;margin:0 0 8px'>"
        f"Hi {biz},</h2>"
        f"<p>I analyzed <a href='{site}'>{site}</a> and found {len(audit.get('issues') or [])} "
        f"issues hurting your visibility and conversions.</p>"
        f"<p style='font-size:18px;margin:16px 0 8px'><strong>Score: {score}/100</strong></p>"
        f"<ul style='line-height:1.6'>{li}</ul>"
        f"<p>AUREM fixes all of this automatically — SSL, mobile, speed, broken links, "
        f"contact form, social signals — starting at <strong>$149 CAD</strong>, "
        f"delivered in 24 hours.</p>"
        f"<p><a href='{report_url}' "
        f"style='display:inline-block;padding:12px 24px;background:#C9A227;"
        f"color:#0A0A0A;text-decoration:none;border-radius:6px;font-weight:700'>"
        f"View Full Report →</a></p>"
        f"<p style='color:#666;font-size:12px;margin-top:24px'>"
        f"Reply STOP to opt out · AUREM · Polaris Built Inc.</p>"
        f"</div>"
    )
    subj = f"Found {len(audit.get('issues') or [])} issues on {site} — repair $149"
    return {"subject": subj, "html": html}


async def fire_due_repair_outreach(db) -> Dict[str, Any]:
    """Fire outreach to up to BATCH_PER_CYCLE eligible leads."""
    if db is None:
        return {"ok": False, "error": "db_unset"}
    sent = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []

    cursor = db.campaign_leads.find(
        {
            "audit_score": {"$lt": 60, "$exists": True},
            "$or": [{"repair_outreach_sent": {"$ne": True}},
                    {"repair_outreach_sent": {"$exists": False}}],
        },
        {"_id": 0},
    ).limit(BATCH_PER_CYCLE * 3)

    leads = await cursor.to_list(length=BATCH_PER_CYCLE * 3)
    for lead in leads:
        if sent >= BATCH_PER_CYCLE:
            break
        lead_id = lead.get("lead_id")
        scan_id = lead.get("audit_id")
        if not (lead_id and scan_id):
            skipped += 1
            continue
        audit = await db.customer_scans.find_one(
            {"scan_id": scan_id}, {"_id": 0}
        )
        if not audit:
            skipped += 1
            continue
        # generate slug for unauth report
        slug = audit.get("public_slug")
        if not slug:
            import uuid as _u
            slug = f"r-{_u.uuid4().hex[:10]}"
            await db.customer_scans.update_one(
                {"scan_id": scan_id}, {"$set": {"public_slug": slug}}
            )

        gating = (lead.get("verification") or {}).get("channel_gating") or {}
        wa_ok = email_ok = False

        # WhatsApp
        phone = (lead.get("phone") or "").strip()
        if phone and gating.get("whatsapp", True):
            try:
                from services.drip_sequencer import _send_wa
                wa_ok = await _send_wa(phone, _build_whatsapp(lead, audit, slug))
            except Exception as e:
                errors.append({"lead_id": lead_id, "channel": "whatsapp", "err": str(e)[:120]})

        # Email
        em = (lead.get("email") or "").strip()
        if em and gating.get("email", True):
            try:
                from services.drip_sequencer import _send_email
                msg = _build_email(lead, audit, slug)
                email_ok = await _send_email(em, msg["subject"], msg["html"])
            except Exception as e:
                errors.append({"lead_id": lead_id, "channel": "email", "err": str(e)[:120]})

        if wa_ok or email_ok:
            sent += 1
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "repair_outreach_sent": True,
                    "repair_outreach_at": now_iso,
                    "repair_outreach_slug": slug,
                    "repair_outreach_channels": {
                        "whatsapp": wa_ok, "email": email_ok,
                    },
                }},
            )
            try:
                await db.outreach_log.insert_one({
                    "lead_id": lead_id, "campaign_type": "website_repair_offer",
                    "sent_at": now_iso, "channels": {"whatsapp": wa_ok, "email": email_ok},
                    "score": audit.get("overall_score"),
                })
            except Exception:
                pass
        else:
            skipped += 1

    return {"ok": True, "sent": sent, "skipped": skipped, "errors": errors[:5]}


async def repair_outreach_scheduler() -> None:
    print("[repair-outreach] scheduler alive — 600s poll", flush=True)
    await asyncio.sleep(30)
    while True:
        try:
            if _db is not None:
                res = await fire_due_repair_outreach(_db)
                if res.get("sent"):
                    print(f"[repair-outreach] fired {res['sent']}, "
                          f"skipped {res['skipped']}", flush=True)
        except Exception as e:
            print(f"[repair-outreach] tick error: {e}", flush=True)
        await asyncio.sleep(INTERVAL_SECONDS)
