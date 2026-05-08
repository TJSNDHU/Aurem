"""
iter 282al-15 — Website Repair Service
======================================
For leads who ALREADY have a website, this module:
  1. Scans their site (scan_website + webclaw)
  2. Scores it 5–100
  3. Extracts prioritised issues
  4. Scans for unlinked brand mentions
  5. Persists to `db.site_audits`
After the lead pays $197 via the existing repair_checkout flow, the
`repair_existing_site()` coroutine is invoked to drive AWB re-render
and trigger the QA-repair loop; on success an email + Telegram ping
fire.  iter 282al-16 — if QA fails after 3 attempts AND the lead
paid, we auto-refund via Stripe and mark the order/lead refunded.

Public API
----------
    calculate_site_score(scan)            -> int
    extract_issues(scan, lead)            -> list[dict]
    get_cta_type(score)                   -> str  ("repair"|"tuneup"|"widget")
    audit_existing_site(db, lead)         -> dict
    repair_existing_site(db, lead)        -> dict
    auto_refund_paid_repair(
        db, lead, reason, order=None)     -> dict
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Pure scoring helpers (unit-testable, no I/O)
# ─────────────────────────────────────────────────────────────────────
def calculate_site_score(scan: Dict[str, Any]) -> int:
    """
    Start at 100, subtract for gaps. Floor at 5.
      thin content (<200 chars)   → -25
      no phone                     → -15
      no logo                      → -10
      no mobile signals            → -15
      no services                  → -20
    """
    score = 100
    content = str((scan or {}).get("content") or "")
    contacts = (scan or {}).get("contacts") or {}
    brand    = (scan or {}).get("brand") or {}
    mobile   = (scan or {}).get("mobile") or {}

    if len(content.strip()) < 200:
        score -= 25
    if not (contacts.get("phone") or contacts.get("phones")):
        score -= 15
    if not (brand.get("logo_url") or brand.get("logo")):
        score -= 10

    has_mobile_signal = bool(
        mobile.get("viewport")
        or mobile.get("responsive")
        or "<meta" in content.lower() and "viewport" in content.lower()
    )
    if not has_mobile_signal:
        score -= 15

    services = contacts.get("services") or (scan or {}).get("services") or []
    if not services:
        score -= 20

    return max(5, score)


def extract_issues(scan: Dict[str, Any], lead: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return prioritised list of issues with {title, impact, priority, fix}."""
    issues: List[Dict[str, Any]] = []
    contacts = (scan or {}).get("contacts") or {}
    brand    = (scan or {}).get("brand") or {}
    mobile   = (scan or {}).get("mobile") or {}
    content  = str((scan or {}).get("content") or "")

    if not (contacts.get("phone") or contacts.get("phones")):
        issues.append({
            "title":    "No phone number found",
            "impact":   "Visitors can't call — lost leads daily.",
            "priority": "critical",
            "fix":      "Add a click-to-call phone button in the header and hero.",
        })
    if not (contacts.get("services") or scan.get("services")):
        issues.append({
            "title":    "No services listed",
            "impact":   "Google can't categorise the business — hurts local SEO.",
            "priority": "high",
            "fix":      "Add a 'Services' section with 3–6 offerings.",
        })
    if not (brand.get("logo_url") or brand.get("logo")):
        issues.append({
            "title":    "No logo detected",
            "impact":   "Low trust — 72% of visitors bounce without brand signal.",
            "priority": "medium",
            "fix":      "Add a logo image to the header.",
        })
    has_mobile = bool(
        mobile.get("viewport") or mobile.get("responsive")
        or ("<meta" in content.lower() and "viewport" in content.lower())
    )
    if not has_mobile:
        issues.append({
            "title":    "Not mobile responsive",
            "impact":   "60% of visits are on phones — broken layout = instant exit.",
            "priority": "critical",
            "fix":      "Add viewport meta tag + CSS breakpoints for 375px width.",
        })
    if len(content.strip()) < 200:
        issues.append({
            "title":    "Thin content",
            "impact":   "Google de-ranks pages under 200 words.",
            "priority": "high",
            "fix":      "Expand the home page copy with service details + trust signals.",
        })
    if not (scan or {}).get("contact_form"):
        issues.append({
            "title":    "No contact form",
            "impact":   "No way to capture visitor info after-hours.",
            "priority": "medium",
            "fix":      "Add a form with name + phone + message fields.",
        })
    return issues


def get_cta_type(score: int) -> str:
    """Map site score to the upsell CTA shown on the public report page."""
    if not score:  # None / 0 / missing → no audit yet → generic
        return "generic"
    if score < 60:
        return "repair"
    if score < 80:
        return "tuneup"
    return "widget"


# ─────────────────────────────────────────────────────────────────────
# Audit entry point (I/O)
# ─────────────────────────────────────────────────────────────────────
async def audit_existing_site(db, lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan + score + issue-extract + unlinked mentions. Persists to
    db.site_audits and returns the full audit dict.
    """
    website = (lead or {}).get("website") or ""
    if not website:
        return {"error": "no_website"}

    # 1) scan
    scan: Dict[str, Any] = {}
    try:
        from services.webclaw_client import scan_website
        scan = await scan_website(website, db) or {}
    except Exception as e:
        logger.warning(f"[repair] scan_website failed: {e}")

    # 2) score
    overall_score = calculate_site_score(scan)

    # 3) issues
    issues = extract_issues(scan, lead)

    # 4) unlinked mentions
    mentions: List[Dict[str, Any]] = []
    try:
        from services.unlinked_mentions import scan_for_unlinked_mentions
        mentions = await scan_for_unlinked_mentions(
            lead.get("business_name") or "",
            website, db, limit=5,
        ) or []
    except Exception as e:
        logger.debug(f"[repair] unlinked_mentions skipped: {e}")

    audit_doc = {
        "lead_id":           str(lead.get("_id") or lead.get("lead_id") or ""),
        "website_url":       website,
        "overall_score":     overall_score,
        "issues":            issues,
        "unlinked_mentions": mentions,
        "scan_data":         {k: scan.get(k) for k in ("contacts", "brand", "mobile") if k in scan},
        "cta_type":          get_cta_type(overall_score),
        "audit_ts":          datetime.now(timezone.utc),
    }

    if db is not None:
        try:
            await db.site_audits.insert_one(dict(audit_doc))
        except Exception as e:
            logger.debug(f"[repair] audit persist failed: {e}")

    return audit_doc


# ─────────────────────────────────────────────────────────────────────
# Paid repair flow (triggered by Stripe webhook)
# ─────────────────────────────────────────────────────────────────────
async def repair_existing_site(db, lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Called AFTER the $197 repair payment is confirmed by Stripe webhook.
    Uses the latest audit to re-render the site via AWB, then kicks
    the QA-repair loop. Sends success email or sentinel alert.
    """
    from services.site_qa_service import qa_repair_loop

    lead_id = str(lead.get("_id") or lead.get("lead_id") or "")
    if db is None or not lead_id:
        return {"ok": False, "reason": "no_db_or_lead"}

    audit = None
    try:
        audit = await db.site_audits.find_one(
            {"lead_id": lead_id}, {"_id": 0}, sort=[("audit_ts", -1)],
        )
    except Exception as e:
        logger.warning(f"[repair] audit lookup failed: {e}")
    if not audit:
        return {"ok": False, "reason": "no_audit"}

    # Build repair instructions from critical + high issues
    fixes = [i["fix"] for i in audit.get("issues", [])
             if i.get("priority") in ("critical", "high") and i.get("fix")]
    instructions = "\n- " + "\n- ".join(fixes) if fixes else "General refresh."
    repair_prompt = f"REPAIR_EXISTING_SITE\nApply these fixes:{instructions}"

    # Trigger AWB re-render
    site_row = None
    try:
        from services.auto_website_builder import build_site_for_lead
        site_row = await build_site_for_lead(
            db, lead_id, style_hint=repair_prompt,
        )
    except Exception as e:
        logger.warning(f"[repair] AWB rebuild failed: {e}")

    slug = (site_row or {}).get("slug") or ""
    live_url = (
        (site_row or {}).get("live_url")
        or (site_row or {}).get("preview_url")
        or lead.get("website") or ""
    )

    qa_result = await qa_repair_loop(db, slug, live_url, max_attempts=3)

    if qa_result.get("ready_to_send"):
        subject = (
            f"Your website has been fixed — {lead.get('business_name') or 'your business'}"
        )
        body = (
            f"Hi {(lead.get('business_name') or '').split()[0] or 'there'},\n\n"
            f"Your website has been repaired — all QA tests passed.\n\n"
            f"Live site: {live_url}\n\n"
            f"Want ongoing fixes + the ORA AI chat widget? Growth plan is "
            f"$297/month — reply YES to start."
        )
        try:
            from services.email_service_resend import send_email
            if lead.get("email"):
                await send_email(to=lead["email"], subject=subject, body=body)
        except Exception as e:
            logger.debug(f"[repair] email skipped: {e}")
        try:
            from services.telegram_bot_service import send_telegram_alert
            await send_telegram_alert(
                f"Repair done! $197 collected\n"
                f"{lead.get('business_name') or '—'} · {lead.get('city') or '—'}\n"
                f"Live: {live_url}"
            )
        except Exception as e:
            logger.debug(f"[repair] telegram skipped: {e}")
        return {"ok": True, "slug": slug, "live_url": live_url, "qa": qa_result}

    # QA failed after 3 attempts — sentinel alert (they already paid)
    try:
        from services.telegram_bot_service import send_telegram_alert
        await send_telegram_alert(
            f"Paid repair QA FAILED — manual review needed\n"
            f"{lead.get('business_name') or '—'} · paid $197\n"
            f"Lead: {lead_id} · slug: {slug}"
        )
    except Exception:
        pass
    try:
        await db.sentinel_alerts.insert_one({
            "kind":    "paid_repair_qa_failed",
            "lead_id": lead_id,
            "slug":    slug,
            "ts":      datetime.now(timezone.utc),
        })
    except Exception:
        pass
    # iter 282al-16 — auto-refund if this lead/order is paid
    refund = await auto_refund_paid_repair(
        db, lead, reason="qa_failed_3_attempts",
    )
    return {"ok": False, "reason": "qa_failed",
            "qa": qa_result, "refund": refund}


# ─────────────────────────────────────────────────────────────────────
# Auto-refund (iter 282al-16)
# ─────────────────────────────────────────────────────────────────────
async def auto_refund_paid_repair(
    db, lead: Dict[str, Any], reason: str,
    order: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Issue a Stripe refund for a paid website-repair order, mark the
    order + lead as refunded, email the customer, and ping Telegram.

    Returns {ok, skipped?, reason?, refund_id?}. Never raises.

    Fires only when:
      - `order["status"] == "paid"` (or lead.repair_paid is True), AND
      - `order["stripe_payment_intent"]` exists.
    Both conditions are lookup-safe so tests can mock DB.
    """
    lead_id = str(lead.get("_id") or lead.get("lead_id") or "")
    if db is None or not lead_id:
        return {"ok": False, "skipped": "no_db_or_lead"}

    # Locate the paid order if not supplied
    if order is None:
        try:
            order = await db.repair_orders.find_one(
                {"lead_id": lead_id, "status": "paid"},
                sort=[("paid_at", -1)],
            )
        except Exception as e:
            logger.warning(f"[refund] order lookup failed: {e}")
            order = None

    # Guard: only refund if actually paid
    paid = bool(order and order.get("status") == "paid") or bool(lead.get("repair_paid"))
    if not paid:
        return {"ok": False, "skipped": "not_paid"}

    payment_intent = (
        (order or {}).get("stripe_payment_intent")
        or lead.get("repair_payment_intent_id")
    )
    if not payment_intent:
        return {"ok": False, "skipped": "no_payment_intent"}

    # Fire Stripe refund
    refund_id = None
    refund_err = None
    try:
        import os as _os
        import stripe as _stripe  # type: ignore
        _stripe.api_key = _os.environ.get("STRIPE_SECRET_KEY", "")
        if not _stripe.api_key:
            return {"ok": False, "skipped": "no_stripe_key"}
        _ref = _stripe.Refund.create(payment_intent=payment_intent)
        refund_id = getattr(_ref, "id", None) or (
            _ref.get("id") if isinstance(_ref, dict) else None
        )
    except Exception as e:
        refund_err = str(e)
        logger.warning(f"[refund] Stripe refund failed: {e}")

    now = datetime.now(timezone.utc)

    # Mark order refunded
    if order and order.get("order_id"):
        try:
            await db.repair_orders.update_one(
                {"order_id": order["order_id"]},
                {"$set": {
                    "status":      "refunded",
                    "refunded_at": now,
                    "refund_id":   refund_id,
                    "refund_err":  refund_err,
                }},
            )
        except Exception:
            pass

    # Mark lead refunded + queue for second-chance outreach in 14 days
    # (iter 282al-17). Existing refund already happened in Stripe; this
    # flag drives the daily 10:00 UTC cron in second_chance_service.
    from datetime import timedelta as _td_sc
    if lead.get("_id"):
        try:
            await db.campaign_leads.update_one(
                {"_id": lead["_id"]},
                {"$set": {
                    "repair_status":           "refunded",
                    "refunded_at":             now,
                    "second_chance_eligible":  True,
                    "second_chance_after":     now + _td_sc(days=14),
                }},
            )
        except Exception:
            pass

    # Log to refunds
    try:
        await db.refunds.insert_one({
            "lead_id":          lead_id,
            "order_id":         (order or {}).get("order_id"),
            "payment_intent":   payment_intent,
            "refund_id":        refund_id,
            "amount_cad":       (order or {}).get("amount_cad"),
            "reason":           reason,
            "refund_err":       refund_err,
            "ts":               now,
        })
    except Exception:
        pass

    # Customer email
    try:
        from services.email_service_resend import send_email
        if lead.get("email"):
            body = (
                f"Hi {(lead.get('business_name') or '').split()[0] or 'there'},\n\n"
                "We couldn't fix all issues on your website to our standard, "
                "so we've refunded your $197 in full — no action needed on "
                "your side. It will appear in 3–5 business days.\n\n"
                "We're sorry for the bumpy ride. If you'd like us to take "
                "another look manually, reply to this email."
            )
            await send_email(
                to=lead["email"],
                subject="Sorry — full refund issued",
                body=body,
            )
    except Exception as e:
        logger.debug(f"[refund] email skipped: {e}")

    # Telegram
    try:
        from services.telegram_bot_service import send_telegram_alert
        amt = (order or {}).get("amount_cad")
        amt_str = f"${amt/100:.0f} CAD" if amt else "$197"
        await send_telegram_alert(
            f"Auto-refund issued\n"
            f"{lead.get('business_name') or '—'} · {amt_str}\n"
            f"Reason: {reason}\n"
            f"Manual review still recommended"
        )
    except Exception:
        pass

    return {
        "ok":         refund_err is None,
        "refund_id":  refund_id,
        "error":      refund_err,
        "reason":     reason,
    }
