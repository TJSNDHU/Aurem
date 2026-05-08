"""
NPS Win-back Sequence (iter 315d)
==================================
Triggered automatically when a customer submits NPS score ≤ 3 on the edit
portal. 3-message escalation over a week, designed to convert a detractor
into a renewer:

  Day 1  → Apology + open question ("what went wrong?")
  Day 3  → 1-on-1 call offer (founder phone)
  Day 7  → Free domain credit ($29 CAD)

Each step is idempotent (one shot per (site_id, step)). If the customer
opens their edit portal AND saves anything between steps, the remaining
steps auto-cancel (we count it as recovered).

Public:
  await arm_winback_sequence(db, *, site_id, lead_id, score) -> dict
  await fire_due_winback_steps(db) -> dict
  await winback_scheduler(db) -> never returns
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PUBLIC_BASE = (os.environ.get("AUREM_PUBLIC_URL", "https://aurem.live")
                .rstrip("/"))
FOUNDER_CALL_LINK = os.environ.get(
    "FOUNDER_CALL_LINK", "https://cal.com/aurem/founder-15min")
DOMAIN_CREDIT_CAD = int(float(
    os.environ.get("WINBACK_DOMAIN_CREDIT_CAD", "29")))


# ─── Step definitions ────────────────────────────────────────────────
def _steps(biz: str, edit_link: str, suggested_domain: str) -> list:
    """Return the canonical 3-step sequence config."""
    return [
        {
            "step": 1, "delay_hours": 0,  # fires immediately
            "kind": "apology",
            "subject": f"{biz} — sorry we let you down",
            "wa": (
                f"Hi {biz} — TJ here, founder of AUREM.\n\n"
                f"Saw your feedback. I'm sorry we missed the mark. "
                f"Two questions, 30 seconds each:\n\n"
                f"1. What's the ONE thing that frustrated you most?\n"
                f"2. What would have made it a 5/5?\n\n"
                f"I read every reply personally."
            ),
            "html": (
                f"<div style='font-family:Georgia,serif;max-width:520px'>"
                f"<h2 style='color:#8a6d1c'>I'm sorry we let you down</h2>"
                f"<p>Hi <strong>{biz}</strong> — TJ here, founder of AUREM.</p>"
                f"<p>Saw your feedback. I'm sorry we missed the mark. "
                f"Two questions, 30 seconds each:</p>"
                f"<ol><li>What's the ONE thing that frustrated you most?</li>"
                f"<li>What would have made it a 5/5?</li></ol>"
                f"<p>I read every reply personally — just hit reply.</p>"
                f"<p style='margin-top:22px'>— TJ, Founder · AUREM</p></div>"
            ),
        },
        {
            "step": 2, "delay_hours": 48,
            "kind": "call_offer",
            "subject": f"{biz} — 15 minutes with me, on the house",
            "wa": (
                f"Hi {biz} — TJ again.\n\n"
                f"If you didn't get a chance to reply, no problem. "
                f"Easier path: 15 minutes on a call, just you and me. "
                f"I'll personally walk through your site, fix what's "
                f"broken on the spot.\n\n"
                f"Pick a slot: {FOUNDER_CALL_LINK}\n\n"
                f"No agenda. No pitch. Just fixing things."
            ),
            "html": (
                f"<div style='font-family:Georgia,serif;max-width:520px'>"
                f"<h2 style='color:#8a6d1c'>15 minutes with me, on the house</h2>"
                f"<p>Hi <strong>{biz}</strong> — TJ again.</p>"
                f"<p>If you didn't get a chance to reply, no problem. "
                f"Easier path: 15 minutes on a call, just you and me. "
                f"I'll personally walk through your site, fix what's "
                f"broken on the spot.</p>"
                f"<p style='margin:22px 0'>"
                f"<a href='{FOUNDER_CALL_LINK}' "
                f"style='background:#C9A227;color:#0A0A0A;padding:12px 22px;"
                f"border-radius:6px;font-weight:700;text-decoration:none'>"
                f"Pick a slot</a></p>"
                f"<p style='font-size:12px;color:#888'>No agenda. No pitch. "
                f"Just fixing things.</p>"
                f"<p>— TJ, Founder · AUREM</p></div>"
            ),
        },
        {
            "step": 3, "delay_hours": 168,
            "kind": "domain_credit",
            "subject": f"{biz} — ${DOMAIN_CREDIT_CAD} CAD on the house",
            "wa": (
                f"Hi {biz} — last note from me.\n\n"
                f"To make this right: a free custom domain on us "
                f"(${DOMAIN_CREDIT_CAD} CAD value), so customers can "
                f"find you at your own address — {suggested_domain}.\n\n"
                f"Claim it here:\n{edit_link or PUBLIC_BASE + '/edit'}\n\n"
                f"Code automatically applied. Zero strings."
            ),
            "html": (
                f"<div style='font-family:Georgia,serif;max-width:520px'>"
                f"<h2 style='color:#8a6d1c'>"
                f"${DOMAIN_CREDIT_CAD} CAD on the house — yours to use</h2>"
                f"<p>Hi <strong>{biz}</strong> — last note from me.</p>"
                f"<p>To make this right: a free custom domain on us "
                f"(<strong>${DOMAIN_CREDIT_CAD} CAD value</strong>), so "
                f"customers can find you at your own address — "
                f"<strong>{suggested_domain}</strong>.</p>"
                f"<p style='margin:22px 0'>"
                f"<a href='{edit_link or PUBLIC_BASE + '/edit'}' "
                f"style='background:#C9A227;color:#0A0A0A;padding:12px 22px;"
                f"border-radius:6px;font-weight:700;text-decoration:none'>"
                f"Claim {suggested_domain}</a></p>"
                f"<p style='font-size:12px;color:#888'>Code automatically "
                f"applied. Zero strings.</p>"
                f"<p>— TJ, Founder · AUREM</p></div>"
            ),
        },
    ]


# ─── Delivery helpers (mirror post_publish_triggers patterns) ────────
async def _send_email(to: str, subject: str, html: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key or not to:
        return False
    from_addr = os.environ.get(
        "RESEND_FROM_EMAIL", "TJ at AUREM <tj@aurem.live>")
    try:
        import httpx
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
        logger.warning(f"[winback] email failed: {e}")
        return False


async def _send_whatsapp(to: str, body: str) -> bool:
    if not to:
        return False
    try:
        from routers.whatsapp_alerts import send_whatsapp
        out = await send_whatsapp(to, body)
        return bool(out and out.get("ok"))
    except Exception as e:
        logger.debug(f"[winback] whatsapp failed: {e}")
        return False


def _suggest_domain(biz: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "", (biz or "").lower())
    return f"{(s or 'yourbusiness')[:24]}.com"


# ─── Public API ──────────────────────────────────────────────────────
async def arm_winback_sequence(db, *, site_id: str, lead_id: Optional[str],
                                  score: int) -> Dict[str, Any]:
    """Create a pending winback row. Idempotent per site_id."""
    existing = await db.winback_sequences.find_one(
        {"site_id": site_id, "status": {"$in": ["armed", "in_progress"]}},
        {"_id": 0, "winback_id": 1},
    )
    if existing:
        return {"ok": True, "skipped": "already_armed",
                "winback_id": existing["winback_id"]}

    site = await db.auto_built_sites.find_one(
        {"site_id": site_id}, {"_id": 0}) or {}
    biz = site.get("business_name") or "your business"
    suggested = _suggest_domain(biz)
    pp = site.get("post_publish") or {}
    edit_link = pp.get("welcome_edit_link") or ""

    # Best-effort recipient lookup
    custom = site.get("custom_content") or {}
    email = (custom.get("email") or site.get("contact_email")
              or site.get("business_email") or "")
    phone = custom.get("phone") or ""
    if (not email or not phone) and lead_id:
        lead = await db.campaign_leads.find_one(
            {"lead_id": lead_id},
            {"_id": 0, "email": 1, "phone": 1}) or {}
        email = email or lead.get("email") or ""
        phone = phone or lead.get("phone") or ""
    if (not email or not phone) and lead_id:
        scan = await db.customer_scans.find_one(
            {"lead_id": lead_id},
            {"_id": 0, "email": 1, "phone": 1, "business_email": 1},
            sort=[("created_at", -1)]) or {}
        email = email or scan.get("email") or scan.get("business_email") or ""
        phone = phone or scan.get("phone") or ""

    now = datetime.now(timezone.utc)
    steps_cfg = _steps(biz, edit_link, suggested)
    steps_state = []
    for s in steps_cfg:
        steps_state.append({
            "step": s["step"], "kind": s["kind"],
            "scheduled_at": (now + timedelta(hours=s["delay_hours"])).isoformat(),
            "sent_at": None, "email_ok": None, "whatsapp_ok": None,
            "skipped": None,
        })
    rec = {
        "winback_id": uuid.uuid4().hex[:12],
        "site_id": site_id, "lead_id": lead_id,
        "score": score, "business_name": biz,
        "to_email": (email or "").strip(),
        "to_phone": (phone or "").strip(),
        "edit_link": edit_link, "suggested_domain": suggested,
        "status": "armed", "armed_at": now.isoformat(),
        "recovered_at": None, "steps": steps_state,
    }
    await db.winback_sequences.insert_one(dict(rec))
    logger.info(f"[winback] armed for site_id={site_id} score={score}")
    return {"ok": True, "winback_id": rec["winback_id"], "scheduled": len(steps_state)}


async def _is_recovered(db, site_id: str, armed_at_iso: str) -> bool:
    """Recovery signal: customer saved an edit OR opened the portal after arm."""
    site = await db.auto_built_sites.find_one(
        {"site_id": site_id},
        {"_id": 0, "last_edited": 1, "edit_count": 1}) or {}
    le = site.get("last_edited")
    if le and le > armed_at_iso:
        return True
    sess = await db.edit_sessions.find_one(
        {"site_id": site_id, "kind": "request",
          "opened_at": {"$gt": armed_at_iso}},
        {"_id": 0, "request_id": 1}) or {}
    return bool(sess.get("request_id"))


async def _fire_step(db, wb: Dict[str, Any], step_idx: int) -> Dict[str, Any]:
    biz = wb["business_name"]
    cfg = _steps(biz, wb.get("edit_link", ""), wb.get("suggested_domain", ""))[step_idx]
    email_ok = await _send_email(wb["to_email"], cfg["subject"], cfg["html"])
    wa_ok = await _send_whatsapp(wb["to_phone"], cfg["wa"])
    delivered = bool(email_ok or wa_ok)
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.winback_sequences.update_one(
        {"winback_id": wb["winback_id"]},
        {"$set": {
            f"steps.{step_idx}.sent_at": now_iso,
            f"steps.{step_idx}.email_ok": email_ok,
            f"steps.{step_idx}.whatsapp_ok": wa_ok,
            "status": "in_progress",
            "last_step_at": now_iso,
        }},
    )
    logger.info(
        f"[winback] sent step={cfg['step']} kind={cfg['kind']} "
        f"site={wb['site_id']} delivered={delivered}")
    return {"ok": True, "step": cfg["step"], "kind": cfg["kind"],
            "delivered": delivered, "email_ok": email_ok,
            "whatsapp_ok": wa_ok}


async def fire_due_winback_steps(db) -> Dict[str, Any]:
    """Sweep all armed/in_progress winbacks, fire any due step (or close)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    fired = 0
    closed = 0
    recovered = 0

    cur = db.winback_sequences.find(
        {"status": {"$in": ["armed", "in_progress"]}},
        {"_id": 0},
    ).limit(100)
    async for wb in cur:
        try:
            # Recovery short-circuit
            if await _is_recovered(db, wb["site_id"], wb["armed_at"]):
                await db.winback_sequences.update_one(
                    {"winback_id": wb["winback_id"]},
                    {"$set": {"status": "recovered",
                               "recovered_at": now_iso}},
                )
                recovered += 1
                continue

            # Find first step due
            steps = wb.get("steps", [])
            idx = None
            for i, s in enumerate(steps):
                if s.get("sent_at") or s.get("skipped"):
                    continue
                if s.get("scheduled_at", "") <= now_iso:
                    idx = i
                    break
                # next step still in the future → pause loop here
                break

            if idx is None:
                # If all steps are sent and last sent ≥ 24h ago → close
                last = steps[-1] if steps else None
                if last and last.get("sent_at"):
                    last_sent = last["sent_at"]
                    age_hours = (
                        datetime.now(timezone.utc)
                        - datetime.fromisoformat(last_sent)
                    ).total_seconds() / 3600.0
                    if age_hours >= 24:
                        await db.winback_sequences.update_one(
                            {"winback_id": wb["winback_id"]},
                            {"$set": {"status": "completed",
                                       "completed_at": now_iso}},
                        )
                        closed += 1
                continue

            await _fire_step(db, wb, idx)
            fired += 1
        except Exception as e:
            logger.warning(
                f"[winback] tick failed for {wb.get('winback_id')}: {e}")
    return {"ok": True, "fired": fired, "recovered": recovered,
            "closed": closed}


async def winback_scheduler(db) -> None:
    """Runs forever. Fires due steps every 15 min."""
    await asyncio.sleep(60)
    while True:
        try:
            await fire_due_winback_steps(db)
        except Exception as e:
            logger.warning(f"[winback] scheduler tick failed: {e}")
        await asyncio.sleep(900)  # 15 min
