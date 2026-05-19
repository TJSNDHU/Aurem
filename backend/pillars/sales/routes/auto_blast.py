"""Sales/Campaign — Auto-Blast Controls + Sequence Runners.

Split from the former monolithic routers/campaign_router.py (2,068 LOC) as
part of Pillar 1 (Sales) logic modularization — iter 262.
"""
import logging
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pillars.sales.routes._shared import (
    _get_db, _verify_admin, _get_today_schedule,
    WHATSAPP_TEMPLATES, EMAIL_SUBJECTS, TARGET_CATEGORIES, COMPETITOR_TEMPLATES,
)

router = APIRouter(prefix="/api/campaign", tags=["AUREM Campaign"])
logger = logging.getLogger(__name__)


@router.get("/ops-status")
async def campaign_ops_status(request: Request):
    """
    Live health check for the 2 known external blockers:
      - Twilio WhatsApp Business approval
      - Google Places API enablement
    Plus the Ripple Meta Cloud fallback tier status.

    Returns structured status for the admin Pending Ops banner.
    """
    _verify_admin(request)

    # --- WHAPI probe (primary WhatsApp path per operator preference) ---
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "").strip()
    whapi_base = os.environ.get("WHAPI_API_URL", "https://gate.whapi.cloud").rstrip("/")
    whapi_wa = {
        "ok": bool(whapi_token),
        "channel": "whapi",
        "detail": "WHAPI ready (primary)" if whapi_token else "WHAPI_API_TOKEN not set",
        "pending": not bool(whapi_token),
    }
    if whapi_token:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(
                    f"{whapi_base}/settings",
                    headers={"Authorization": f"Bearer {whapi_token}"},
                )
            if r.status_code == 200:
                try:
                    j = r.json()
                    ph = j.get("phone") or j.get("phoneNumber") or ""
                    if ph:
                        whapi_wa["detail"] = f"WHAPI live · {ph}"
                except Exception:
                    pass
            else:
                whapi_wa["detail"] = f"WHAPI reachable but returned {r.status_code}"
        except Exception:
            # Network hiccup — don't flip ok=false; token presence is enough.
            pass

    # --- Twilio WhatsApp probe (secondary fallback) ---
    from services.channel_config import twilio_status
    tstat = twilio_status()
    twilio_wa = {
        "ok": tstat["whatsapp_configured"],
        "channel": "twilio_whatsapp",
        "detail": (
            f"Twilio fallback · {tstat['whatsapp_from']}"
            if tstat["whatsapp_configured"]
            else tstat["reason"]
        ),
        "number": tstat["whatsapp_from"],
        "pending": not tstat["whatsapp_configured"],
    }
    if tstat["whatsapp_configured"]:
        # Optional API reachability probe — but don't flip to false just because
        # Twilio is momentarily unreachable; credentials being present is enough
        # for the dashboard to say "connected".
        try:
            import httpx
            creds = (os.environ.get("TWILIO_ACCOUNT_SID", ""), os.environ.get("TWILIO_AUTH_TOKEN", ""))
            async with httpx.AsyncClient(timeout=6.0) as c:
                r = await c.get("https://messaging.twilio.com/v1/Services", auth=creds)
            if r.status_code != 200:
                twilio_wa["detail"] += f" (Twilio API probe returned {r.status_code})"
        except Exception:
            pass

    # --- Google Places API probe ---
    google_places = {"ok": False, "detail": "not_configured", "channel": "google_places"}
    try:
        import httpx
        key = os.environ.get("GOOGLE_PLACES_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        if key:
            url = "https://places.googleapis.com/v1/places:searchText"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": "places.displayName",
            }
            async with httpx.AsyncClient(timeout=8.0) as c:
                r = await c.post(url, headers=headers, json={"textQuery": "coffee shop Toronto"})
            if r.status_code == 200:
                google_places = {"ok": True, "detail": "Places API (New) enabled & responding", "channel": "google_places"}
            elif r.status_code == 403:
                google_places = {
                    "ok": False,
                    "detail": "403 — Places API (New) not enabled for this project. Enable in GCP Console.",
                    "channel": "google_places",
                    "pending": True,
                }
            else:
                google_places = {
                    "ok": False,
                    "detail": f"Google returned {r.status_code}: {r.text[:150]}",
                    "channel": "google_places",
                    "pending": True,
                }
        else:
            google_places = {
                "ok": False,
                "detail": "Missing GOOGLE_PLACES_API_KEY env",
                "channel": "google_places",
                "pending": True,
            }
    except Exception as e:
        google_places = {"ok": False, "detail": f"probe_error: {e}", "channel": "google_places", "pending": True}

    # --- Ripple WhatsApp fallback tier readiness ---
    ripple_wa = {"channel": "ripple_meta_cloud_fallback"}
    try:
        from services.ripple_whatsapp_fallback import ripple_whatsapp_configured
        ripple_wa["ok"] = ripple_whatsapp_configured()
        ripple_wa["detail"] = (
            "3rd-tier WhatsApp fallback ready"
            if ripple_wa["ok"]
            else "Optional: set RIPPLE_WHATSAPP_ACCESS_TOKEN + PHONE_NUMBER_ID env to enable"
        )
    except Exception as e:
        ripple_wa["ok"] = False
        ripple_wa["detail"] = f"load_error: {e}"

    # WHAPI is the primary — if it's up, we're green on WhatsApp regardless
    # of Twilio status. Twilio just serves as a secondary fallback.
    whatsapp_green = whapi_wa.get("ok") or twilio_wa.get("ok")
    pending_blockers = [c for c in (google_places,) if c.get("pending")]
    if not whatsapp_green:
        pending_blockers.append(twilio_wa)

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "all_green": len(pending_blockers) == 0,
        "pending_count": len(pending_blockers),
        "channels": {
            "whapi": whapi_wa,
            "twilio_whatsapp": twilio_wa,
            "google_places": google_places,
            "ripple_meta_cloud_fallback": ripple_wa,
        },
        "whatsapp_primary": "whapi" if whapi_wa.get("ok") else ("twilio" if twilio_wa.get("ok") else None),
        "links": {
            "whapi_dashboard": "https://panel.whapi.cloud/",
            "twilio_whatsapp_approval": "https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders",
            "meta_business_verification": "https://business.facebook.com/settings",
            "google_places_enable": "https://console.cloud.google.com/apis/library/places.googleapis.com",
        },
    }


@router.get("/auto-blast/status")
async def auto_blast_status(request: Request):
    """Return current auto-blast config + counters."""
    payload = _verify_admin(request)
    db = _get_db()
    tenant_id = payload.get("tenant_id") or "global"
    cfg = await db.auto_blast_config.find_one({"tenant_id": tenant_id}, {"_id": 0}) or {}
    # Counts of leads in each state
    total = await db.campaign_leads.count_documents({})
    never_blasted = await db.campaign_leads.count_documents({"last_blast_at": {"$exists": False}})
    blasted = total - never_blasted

    # How many of the "queued" leads actually have NO contact info?
    # These are stuck forever until the scraper finds email/phone.
    queued_contactless = await db.campaign_leads.count_documents({
        "last_blast_at": {"$exists": False},
        "$and": [
            {"$or": [{"email": {"$in": ["", None]}}, {"email": {"$exists": False}}]},
            {"$or": [{"phone": {"$in": ["", None]}}, {"phone": {"$exists": False}}]},
        ],
    })
    queued_ready = never_blasted - queued_contactless

    # Health classification for the UI
    now_str = cfg.get("last_run_at") or ""
    health = "idle"
    if not cfg.get("enabled"):
        health = "disabled"
    elif queued_ready > 0:
        health = "ready"
    elif queued_contactless > 0:
        health = "blocked_scraper"   # scraper keeps producing contactless leads
    else:
        health = "caught_up"         # nothing to blast

    return {
        "enabled": bool(cfg.get("enabled", False)),
        "last_run_at": now_str or None,
        "last_run_processed": cfg.get("last_run_processed", 0),
        "last_run_sent": cfg.get("last_run_sent", 0),
        "last_run_note": cfg.get("last_run_note"),
        "total_leads": total,
        "queued_leads": never_blasted,
        "queued_ready": queued_ready,
        "queued_contactless": queued_contactless,
        "blasted_leads": blasted,
        "health": health,
        "tenant_id": tenant_id,
        "interval_minutes": cfg.get("interval_minutes", 5),
        "max_per_cycle": cfg.get("max_per_cycle", 10),
    }


class AutoBlastToggleRequest(BaseModel):
    enabled: bool
    max_per_cycle: Optional[int] = None
    interval_minutes: Optional[int] = None


@router.post("/auto-blast/toggle")
async def auto_blast_toggle(data: AutoBlastToggleRequest, request: Request):
    """Flip auto-blast engine ON/OFF for the caller's tenant."""
    payload = _verify_admin(request)
    db = _get_db()
    tenant_id = payload.get("tenant_id") or "global"
    update = {
        "enabled": bool(data.enabled),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if data.max_per_cycle is not None:
        update["max_per_cycle"] = max(1, min(50, int(data.max_per_cycle)))
    if data.interval_minutes is not None:
        update["interval_minutes"] = max(1, min(60, int(data.interval_minutes)))
    await db.auto_blast_config.update_one(
        {"tenant_id": tenant_id},
        {"$set": update, "$setOnInsert": {"tenant_id": tenant_id}},
        upsert=True,
    )
    return {"ok": True, "enabled": update["enabled"], "tenant_id": tenant_id}


@router.post("/auto-blast/run-now")
async def auto_blast_run_now(request: Request):
    """Manually trigger ONE auto-blast cycle (admin/debug).

    Fire-and-forget: schedules the cycle as a background task and returns
    immediately so the admin UI never stalls. Progress/results are visible
    via GET /auto-blast/status (last_run_at, last_run_processed, last_run_sent).
    """
    _verify_admin(request)
    from services.auto_blast_engine import run_auto_blast_cycle

    async def _runner():
        try:
            result = await asyncio.wait_for(run_auto_blast_cycle(force=True), timeout=180.0)
            logging.info(f"[auto-blast/run-now] done: {result}")
        except asyncio.TimeoutError:
            logging.warning("[auto-blast/run-now] cycle exceeded 180s cap")
        except Exception as e:
            logging.error(f"[auto-blast/run-now] failed: {e}")

    asyncio.create_task(_runner())
    return {
        "ok": True,
        "started": True,
        "message": "Auto-blast cycle scheduled — poll /auto-blast/status for progress",
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


# ── iter 323p — campaign diagnostic + manual noise unflag ────────────
@router.get("/why-not-sending")
async def why_not_sending(request: Request):
    """Read-only deep diagnostic: WHY are cycles producing sent=0?

    Returns the funnel from total_leads → final_eligible_for_blast and
    points at the single blocking filter, plus sample lead docs for spot
    inspection. Use this when the watchdog's `zero_sent_streak` is high
    (the screenshot user saw: streak=180 for 6 days).
    """
    _verify_admin(request)
    from services.auto_blast_engine import diagnose_blocker
    return await diagnose_blocker()


@router.post("/auto-blast/unflag-all-noise")
async def auto_blast_unflag_all_noise(request: Request):
    """Reset `noise_flag` on every queued lead. Pair with /why-not-sending
    when blocking_reason == 'all_queued_noise_flagged'. Returns the count
    of leads cleared. Idempotent and reversible by next cycle's heuristic.
    """
    _verify_admin(request)
    from services.auto_blast_engine import unflag_all_noise
    return await unflag_all_noise()


# ── iter 323u — manual watchdog reset ────────────────────────────────
@router.post("/auto-blast/reset-watchdog")
async def auto_blast_reset_watchdog(request: Request):
    """Reset the campaign watchdog: zero_sent_streak → 0 and clear `tripped`
    flags on ora_campaign_health._id='global'. Use when the watchdog has
    latched after a long zero-send window (e.g. streak=369) and is
    preventing subsequent cycles from running even though `final_eligible`
    is non-zero and `blocking_reason` is null.

    Returns the prior state for audit; idempotent. Detection logic is NOT
    changed — this only clears the latched state so the next cycle can run.
    """
    _verify_admin(request)
    from services.auto_blast_engine import reset_watchdog
    return await reset_watchdog()


# ── iter 324b — aggregator-email scrub (P0 funnel unblocker) ─────────
@router.post("/auto-blast/scrub-aggregator-emails")
async def auto_blast_scrub_aggregator_emails(request: Request, dry_run: bool = False):
    """Clear `email` field on queued leads whose email is on the
    aggregator/social/SaaS blocklist (info@facebook.com, info@fresha.com,
    info@google.com, etc.). Root cause of the "421 queued, 0 eligible"
    funnel collapse — the role-email fallback in apollo_enrichment.py
    built `info@<aggregator>` when the lead's website_url was a social
    page instead of an actual business domain.

    Pass `?dry_run=true` to preview without modifying. The original
    junk value is preserved in `email_scrubbed_from` for audit.
    """
    _verify_admin(request)
    from services.auto_blast_engine import scrub_aggregator_emails
    return await scrub_aggregator_emails(dry_run=dry_run)


# ── iter 324c — internal/test traffic scrub (QA leakage purge) ───────
@router.post("/auto-blast/scrub-internal-test-traffic")
async def auto_blast_scrub_internal_test_traffic(request: Request, dry_run: bool = False):
    """Mark `noise_flag=True` on every queued lead that came from QA/test
    harnesses or has a test-only email domain.

    Catches:
      • source ∈ {no_website_signup, awb_e2e_test, a2a_e2e_test,
                  playwright_test, qa_smoke}
      • email @aurem-test.com / @example.com / @test.com / *.test / *.invalid

    These should never have entered the production blaster. Pair with
    /auto-blast/scrub-aggregator-emails for full queue hygiene.
    """
    _verify_admin(request)
    from services.auto_blast_engine import scrub_internal_test_traffic
    return await scrub_internal_test_traffic(dry_run=dry_run)


# ── iter 324e — listicle / HTML-title scrub (Tavily/DDG junk purge) ──
@router.post("/auto-blast/scrub-listicle-titles")
async def auto_blast_scrub_listicle_titles(request: Request, dry_run: bool = False):
    """Mark `noise_flag=True` on every queued lead whose `business_name`
    is actually an HTML page title, SEO listicle, or aggregator listing.

    Examples that get flagged:
      • "Dental Care That Feels Like Self-Care | Boston Dental"
      • "Top 10 Plumbers in Toronto (2025 Edition) - HomeStars"
      • "Buy a Well-established Spa And Salon - Eastern Canada"
      • "Mississauga Plumbing - Yelp"

    Root cause: Tavily/DuckDuckGo web fallback in `_discover_businesses`
    was grabbing SERP titles as business names. Web fallback now
    disabled by default; this endpoint cleans up the historical damage.
    """
    _verify_admin(request)
    from services.auto_blast_engine import scrub_listicle_titles
    return await scrub_listicle_titles(dry_run=dry_run)


# ── iter 324h — burnt-domains emergency quarantine ───────────────────
@router.post("/auto-blast/quarantine-burnt-domains")
async def auto_blast_quarantine_burnt_domains(request: Request, dry_run: bool = False):
    """EMERGENCY: walks the last 24h of BLASTED leads, identifies those
    whose `business_name` is a listicle / HTML title (per iter-324e
    detector), and inserts their email addresses into `do_not_contact`.

    Why this matters: prod's `auto_blast_engine._eligible_leads()` reads
    `do_not_contact` every cycle (already-deployed code). Inserts made
    via this endpoint take effect on the NEXT scheduled cycle — no
    redeploy required. Buys time while the iter-324e listicle filter
    waits for a proper deploy.
    """
    _verify_admin(request)
    from services.auto_blast_engine import quarantine_burnt_domains_24h
    return await quarantine_burnt_domains_24h(dry_run=dry_run)





# ══════════════════════════════════════════════
# Lead Scraping (Google Maps via Camofox)
# ══════════════════════════════════════════════
class ScrapeRequest(BaseModel):
    location: str = "Mississauga, Ontario"
    category: str = "hair salon"
    limit: int = 10


@router.post("/scrape")
async def scrape_leads(data: ScrapeRequest, request: Request):
    """Scrape businesses from Google Maps using Camofox/httpx."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    # Check do-not-contact
    dnc_list = set()
    async for doc in db.do_not_contact.find({}, {"_id": 0, "phone": 1, "email": 1}):
        if doc.get("phone"):
            dnc_list.add(doc["phone"])
        if doc.get("email"):
            dnc_list.add(doc["email"].lower())

    try:
        from services.camofox_client import google_maps_leads
        result = await google_maps_leads(data.category, data.location)
    except Exception as e:
        logger.warning(f"Camofox scrape failed: {e}")
        result = {"success": False, "leads": [], "error": str(e)}

    saved = 0
    leads_out = []
    raw_leads = result.get("leads", [])[:data.limit]

    for lead_data in raw_leads:
        name = lead_data.get("name", "").strip()
        if not name:
            continue

        # Check if already in DB
        existing = await db.campaign_leads.find_one({"business_name": name, "location": data.location})
        if existing:
            continue

        lead_id = f"lead-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "lead_id": lead_id,
            "tenant_id": "aurem_platform",
            "campaign_id": "aurem-acquisition-001",
            "business_name": name,
            "category": lead_data.get("category", data.category),
            "location": data.location,
            "website_url": lead_data.get("website", ""),
            "phone": lead_data.get("phone", ""),
            "email": lead_data.get("email", ""),
            "contact_name": "",
            "score": None,
            "issues_count": 0,
            "status": "new",
            "source": "google_maps",
            "whatsapp_sent": False,
            "email_sent": False,
            "outreach_history": [],
            "created_at": now,
            "updated_at": now,
        }

        # Skip if in do-not-contact
        if doc["phone"] in dnc_list or doc.get("email", "").lower() in dnc_list:
            continue

        # iter 322p — stamp dedup keys so future Scout runs skip duplicates.
        try:
            from services.scout_enrichment import annotate_dedup_fields
            annotate_dedup_fields(doc)
        except Exception:
            pass

        await db.campaign_leads.insert_one(doc)
        saved += 1
        leads_out.append({"lead_id": lead_id, "business_name": name, "category": doc["category"]})

    # Update campaign stats
    await db.campaigns.update_one(
        {"campaign_id": "aurem-acquisition-001"},
        {"$inc": {"stats.leads_scraped": saved}},
    )

    return {
        "success": True,
        "scraped": len(raw_leads),
        "saved": saved,
        "leads": leads_out,
        "source": result.get("source", "unknown"),
        "engine": "camofox" if result.get("success") else "fallback",
    }


# ══════════════════════════════════════════════
# Email Outreach
# ══════════════════════════════════════════════
@router.post("/pause")
async def pause_campaign(request: Request):
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")
    await db.campaigns.update_one(
        {"campaign_id": "aurem-acquisition-001"},
        {"$set": {"status": "paused"}},
    )
    return {"success": True, "status": "paused"}


@router.post("/resume")
async def resume_campaign(request: Request):
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")
    await db.campaigns.update_one(
        {"campaign_id": "aurem-acquisition-001"},
        {"$set": {"status": "active"}},
    )
    return {"success": True, "status": "active"}


# ══════════════════════════════════════════════
# WhatsApp STOP handler (public webhook)
# ══════════════════════════════════════════════
async def run_daily_scrape(categories: list = None, location: str = "Mississauga, Ontario", limit: int = 50):
    """Called by APScheduler — scrape leads via Google Places (with OSM fallback)."""
    db = _get_db()
    if db is None:
        logger.warning("[CAMPAIGN] Scrape: DB not available")
        return

    campaign = await db.campaigns.find_one({"campaign_id": "aurem-acquisition-001"})
    if not campaign or campaign.get("status") != "active":
        logger.info("[CAMPAIGN] Scrape skipped — campaign not active")
        return

    cats = categories or TARGET_CATEGORIES
    total_saved = 0
    total_skipped_noise = 0
    total_skipped_no_contact = 0

    for cat in cats[:3]:  # 3 categories per day rotation
        try:
            # ── iter 282u — REAL businesses via Google Places API ──
            # Replaces the camofox/scrape-Google-Maps path which returned
            # Reddit threads & forum posts as "leads". Places API gives us
            # phone+website+address attached to each result so Envoy/Blast
            # has actual contact data on day 1.
            from services.google_places_scout import (
                google_places_leads,
                is_valid_lead,
                _is_blocked_url,
            )
            result = await google_places_leads(cat, location, limit=limit // max(len(cats[:3]), 1))
            for lead_data in result.get("leads", []):
                name = (lead_data.get("business_name") or lead_data.get("name") or "").strip()
                if not name:
                    continue
                # Defense-in-depth: skip noise domains even if upstream missed them
                site = (lead_data.get("website") or "").strip()
                if site and _is_blocked_url(site):
                    total_skipped_noise += 1
                    continue
                # Validation gate — never queue a contactless lead
                if not is_valid_lead(lead_data):
                    total_skipped_no_contact += 1
                    continue

                existing = await db.campaign_leads.find_one({"business_name": name, "location": location})
                if existing:
                    continue
                dnc = await db.do_not_contact.find_one({"$or": [
                    {"phone": lead_data.get("phone", "NONE")},
                    {"email": (lead_data.get("email") or "NONE").lower()},
                ]})
                if dnc:
                    continue
                lead_id = f"lead-{uuid.uuid4().hex[:8]}"
                now = datetime.now(timezone.utc).isoformat()
                _new_doc = {
                    "lead_id": lead_id,
                    "tenant_id": "aurem_platform",
                    "campaign_id": "aurem-acquisition-001",
                    "business_name": name,
                    "category": cat,
                    "location": location,
                    "website_url": site,
                    "phone": lead_data.get("phone", ""),
                    "email": lead_data.get("email", ""),
                    "address": lead_data.get("address", ""),
                    "postal_code": lead_data.get("postal_code", ""),
                    "rating": lead_data.get("rating"),
                    "review_count": lead_data.get("review_count"),
                    "place_id": lead_data.get("place_id"),
                    "google_url": lead_data.get("google_url"),
                    "types": lead_data.get("types") or [],
                    "contact_name": "",
                    "score": None,
                    "issues_count": 0,
                    "status": "new",
                    "source": (lead_data.get("source") or "google_places"),
                    "whatsapp_sent": False,
                    "email_sent": False,
                    "outreach_history": [],
                    "created_at": now,
                    "updated_at": now,
                }
                # iter 322p — stamp dedup keys for future Scout runs
                try:
                    from services.scout_enrichment import annotate_dedup_fields
                    annotate_dedup_fields(_new_doc)
                except Exception:
                    pass
                await db.campaign_leads.insert_one(_new_doc)
                total_saved += 1
        except Exception as e:
            logger.warning(f"[CAMPAIGN] Scrape error for {cat}: {e}")

    if total_saved > 0:
        await db.campaigns.update_one(
            {"campaign_id": "aurem-acquisition-001"},
            {"$inc": {"stats.leads_scraped": total_saved}},
        )
    logger.info(
        f"[CAMPAIGN] Daily scrape complete: {total_saved} new leads saved | "
        f"skipped: {total_skipped_no_contact} contactless, {total_skipped_noise} noise-domains"
    )
    return {
        "saved": total_saved,
        "skipped_no_contact": total_skipped_no_contact,
        "skipped_noise": total_skipped_noise,
    }


async def run_website_scans():
    """Scan websites of new leads to generate scores."""
    db = _get_db()
    if not db:
        return

    campaign = await db.campaigns.find_one({"campaign_id": "aurem-acquisition-001"})
    if not campaign or campaign.get("status") != "active":
        return

    leads = await db.campaign_leads.find(
        {"status": "new", "website_url": {"$ne": ""}, "score": None}
    ).limit(20).to_list(20)

    scanned = 0
    for lead in leads:
        try:
            from services.camofox_client import browse_url
            result = await browse_url(lead["website_url"])
            text = result.get("text", "")
            # Simple heuristic scoring
            score = 50
            issues = []
            if len(text) < 500:
                score -= 15
                issues.append("Very little content detected")
            if "ssl" not in str(result.get("url", "")).lower() and "https" not in str(result.get("url", "")):
                score -= 10
                issues.append("No SSL certificate")
            if len(text) > 2000:
                score += 10
            score = max(10, min(score, 95))

            await db.campaign_leads.update_one(
                {"lead_id": lead["lead_id"]},
                {"$set": {
                    "score": score,
                    "issues_count": len(issues),
                    "scan_issues": issues,
                    "status": "scanned",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            scanned += 1
        except Exception as e:
            logger.warning(f"[CAMPAIGN] Scan error for {lead.get('business_name')}: {e}")

    if scanned > 0:
        await db.campaigns.update_one(
            {"campaign_id": "aurem-acquisition-001"},
            {"$inc": {"stats.websites_scanned": scanned}},
        )
    logger.info(f"[CAMPAIGN] Website scan complete: {scanned} leads scanned")


async def run_email_sequence():
    """Send email sequence to scanned leads."""
    db = _get_db()
    if db is None:
        return

    campaign = await db.campaigns.find_one({"campaign_id": "aurem-acquisition-001"})
    if not campaign or campaign.get("status") != "active":
        return

    # Use Email Engine instead of direct Resend httpx calls
    try:
        from services.email_engine import EmailEngine
        email_engine = EmailEngine(db)
    except ImportError:
        logger.warning("[CAMPAIGN] Email engine not available")
        return

    # iter 282al-11 — pipeline filter fix.
    # Prior filter `status=="scanned"` produced 0 matches because the scout
    # already sets `score` at intake, so `run_website_scans` skips every
    # lead (score=None precondition) and nothing ever transitions to
    # "scanned". Broaden: any lead with an email, a score, not DNC,
    # and not previously contacted in the last 72h gets an email.
    from datetime import timedelta
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
    leads = await db.campaign_leads.find({
        "email":     {"$regex": "^.+@.+\\..+$"},
        "dnc":       {"$ne": True},
        "score":     {"$ne": None},
        "status":    {"$nin": ["replied", "not_interested", "unsubscribed",
                                "bounced"]},
        # Re-email OK as long as last touch was >72h ago (or never).
        "$or": [
            {"last_email_at": {"$exists": False}},
            {"last_email_at": {"$lt": cutoff_iso}},
        ],
    }).sort("score", -1).limit(campaign.get("daily_email_limit", 100)).to_list(100)

    sent = 0
    for lead in leads:
        try:
            template_path = Path(__file__).parent.parent / "templates" / "outbound_email_1.html"
            html = template_path.read_text()
            html = html.replace("{{first_name}}", lead.get("contact_name") or "Business Owner")
            html = html.replace("{{website}}", lead.get("website_url", ""))
            html = html.replace("{{score}}", str(lead.get("score", 50)))
            html = html.replace("{{issues_count}}", str(lead.get("issues_count", 0)))
            html = html.replace("{{issue_1}}", (lead.get("scan_issues", ["Issue detected"]) or ["Issue detected"])[0])
            html = html.replace("{{issue_2}}", "Mobile responsiveness needs improvement")
            html = html.replace("{{issue_3}}", "Page load time exceeds 3 seconds")
            html = html.replace("{{report_link}}", f"https://aurem.live/report/{lead.get('lead_id', 'test')}")
            html = html.replace("{{unsubscribe_link}}", f"https://aurem.live/api/campaign/unsubscribe?email={lead.get('email', '')}")

            import random
            subject = random.choice(EMAIL_SUBJECTS["outbound_1"]).format(
                score=lead.get("score", 50),
                issues_count=lead.get("issues_count", 0),
                business_name=lead.get("business_name", "your business"),
            )

            result = await email_engine.send_message("polaris-built-001", lead["email"], subject, html)
            if result.get("success"):
                    sent += 1
                    now_iso = datetime.now(timezone.utc).isoformat()
                    await db.campaign_leads.update_one(
                        {"lead_id": lead["lead_id"]},
                        {
                            "$set": {"status": "emailed",
                                      "last_email_at": now_iso,
                                      "updated_at": now_iso},
                            "$push": {"outreach_history": {"type": "email", "template": "outbound_1", "sent_at": now_iso, "engine": result.get("engine", "resend")}},
                        },
                    )
            # iter 282al-11 — throttle to 4 req/s to stay under Resend's
            # 5/s rate limit. Without this the loop burns ~90% of attempts
            # on 429s.
            await asyncio.sleep(0.25)
        except Exception as e:
            logger.warning(f"[CAMPAIGN] Email error: {e}")

    if sent > 0:
        await db.campaigns.update_one(
            {"campaign_id": "aurem-acquisition-001"},
            {"$inc": {"stats.emails_sent": sent}},
        )
    logger.info(f"[CAMPAIGN] Email sequence complete: {sent} emails sent")


async def run_whatsapp_sequence():
    """Send WhatsApp messages to scanned leads."""
    db = _get_db()
    if not db:
        return

    campaign = await db.campaigns.find_one({"campaign_id": "aurem-acquisition-001"})
    if not campaign or campaign.get("status") != "active":
        return

    # Use WhatsApp Hybrid Engine instead of direct WHAPI
    try:
        from services.whatsapp_engine import WhatsAppEngine
        wa_engine = WhatsAppEngine(db)
    except ImportError:
        logger.warning("[CAMPAIGN] WhatsApp engine not available")
        return

    leads = await db.campaign_leads.find(
        {"status": {"$in": ["scanned", "emailed"]}, "phone": {"$ne": ""}, "dnc": {"$ne": True}}
    ).limit(campaign.get("daily_whatsapp_limit", 50)).to_list(50)

    sent = 0
    for lead in leads:
        try:
            message = WHATSAPP_TEMPLATES["initial"].format(
                first_name=lead.get("contact_name") or "there",
                business_name=lead.get("business_name", ""),
                score=lead.get("score", 50),
                issues_count=lead.get("issues_count", 0),
                report_link=f"https://aurem.live/report/{lead.get('lead_id', 'test')}",
                top_issue="Website performance below average",
            )
            # iter 323d — strict phone normalization (was leaking letters/dots to WHAPI)
            from utils.phone_format import to_whapi_format
            phone = to_whapi_format(lead.get("phone", ""))
            if not phone:
                logger.debug(f"[CAMPAIGN] skipping lead {lead.get('lead_id')} — invalid phone")
                continue
            result = await wa_engine.send_message("polaris-built-001", phone, message)
            if result.get("success"):
                    sent += 1
                    await db.campaign_leads.update_one(
                        {"lead_id": lead["lead_id"]},
                        {
                            "$set": {"status": "whatsapp_sent", "updated_at": datetime.now(timezone.utc).isoformat()},
                            "$push": {"outreach_history": {"type": "whatsapp", "template": "initial", "sent_at": datetime.now(timezone.utc).isoformat(), "engine": result.get("engine", "unknown")}},
                        },
                    )
        except Exception as e:
            logger.warning(f"[CAMPAIGN] WhatsApp error: {e}")

    if sent > 0:
        await db.campaigns.update_one(
            {"campaign_id": "aurem-acquisition-001"},
            {"$inc": {"stats.whatsapp_sent": sent}},
        )
    logger.info(f"[CAMPAIGN] WhatsApp sequence complete: {sent} messages sent")


async def run_sms_sequence():
    """Send SMS to leads on Day 4 of outreach — short punchy message."""
    db = _get_db()
    if not db:
        return

    campaign = await db.campaigns.find_one({"campaign_id": "aurem-acquisition-001"})
    if not campaign or campaign.get("status") != "active":
        return

    try:
        from services.sms_engine import SMSEngine
        sms_engine = SMSEngine(db)
    except ImportError:
        logger.warning("[CAMPAIGN] SMS engine not available")
        return

    # Day 4: leads that got email + whatsapp but not yet SMS'd
    leads = await db.campaign_leads.find(
        {"status": {"$in": ["emailed", "whatsapp_sent"]}, "phone": {"$ne": ""}, "dnc": {"$ne": True}, "sms_sent": {"$ne": True}}
    ).limit(campaign.get("daily_sms_limit", 50)).to_list(50)

    sent = 0
    for lead in leads:
        try:
            name = lead.get("contact_name") or "there"
            website = lead.get("website_url", "your site")
            issues = lead.get("issues_count", 0)
            lead_id = lead.get("lead_id", "test")

            message = f"Hi {name}, ORA here. Scanned {website}. Found {issues} issues. Report: aurem.live/report/{lead_id}"

            phone = lead["phone"].replace("+", "").replace("-", "").replace(" ", "")
            result = await sms_engine.send_message("polaris-built-001", phone, message)
            if result.get("success"):
                sent += 1
                await db.campaign_leads.update_one(
                    {"lead_id": lead_id},
                    {
                        "$set": {"sms_sent": True, "updated_at": datetime.now(timezone.utc).isoformat()},
                        "$push": {"outreach_history": {
                            "type": "sms", "sent_at": datetime.now(timezone.utc).isoformat(),
                            "message_sid": result.get("message_sid", ""),
                            "engine": "twilio",
                        }},
                    },
                )
        except Exception as e:
            logger.warning(f"[CAMPAIGN] SMS error: {e}")

    if sent > 0:
        await db.campaigns.update_one(
            {"campaign_id": "aurem-acquisition-001"},
            {"$inc": {"stats.sms_sent": sent}},
        )
    logger.info(f"[CAMPAIGN] SMS sequence complete: {sent} messages sent")


async def run_voice_sequence():
    """Day 7: Trigger ORA voice calls to leads that haven't responded."""
    db = _get_db()
    if not db:
        return

    campaign = await db.campaigns.find_one({"campaign_id": "aurem-acquisition-001"})
    if not campaign or campaign.get("status") != "active":
        return

    try:
        from services.voice_engine import VoiceEngine
        voice_engine = VoiceEngine(db)
    except ImportError:
        logger.warning("[CAMPAIGN] Voice engine not available")
        return

    # Day 7: leads that got email + WA + SMS but no response
    leads = await db.campaign_leads.find(
        {"status": {"$in": ["emailed", "whatsapp_sent"]}, "sms_sent": True, "voice_called": {"$ne": True},
         "phone": {"$ne": ""}, "dnc": {"$ne": True}}
    ).limit(campaign.get("daily_voice_limit", 20)).to_list(20)

    called = 0
    for lead in leads:
        try:
            lead_id = lead.get("lead_id", "")
            phone = lead["phone"].replace("+", "").replace("-", "").replace(" ", "")
            result = await voice_engine.make_call("polaris-built-001", phone, lead_id)
            if result.get("success"):
                called += 1
                await db.campaign_leads.update_one(
                    {"lead_id": lead_id},
                    {
                        "$set": {"voice_called": True, "updated_at": datetime.now(timezone.utc).isoformat()},
                        "$push": {"outreach_history": {
                            "type": "voice_call", "sent_at": datetime.now(timezone.utc).isoformat(),
                            "call_sid": result.get("call_sid", ""), "engine": "twilio_voice",
                        }},
                    },
                )
        except Exception as e:
            logger.warning(f"[CAMPAIGN] Voice call error: {e}")

    if called > 0:
        await db.campaigns.update_one(
            {"campaign_id": "aurem-acquisition-001"},
            {"$inc": {"stats.voice_calls": called}},
        )
    logger.info(f"[CAMPAIGN] Voice sequence complete: {called} calls made")
