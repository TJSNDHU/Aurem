"""
Auto-Blast Eligibility Forensics
=================================
When `_eligible_leads` returns 0 but `total_queued >> 0`, the operator
needs to know EXACTLY which filter is killing each lead. The existing
`/api/campaign/why-not-sending` gives high-level funnel numbers but
no per-lead breakdown.

This module:
  • Re-runs the _eligible_leads filter manually on every queued lead.
  • Tags each lead with its FIRST rejection reason.
  • Returns top-N rejection reasons + sample lead names per reason.

Endpoint: `GET /api/admin/campaign/eligibility-forensics`
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/admin/campaign",
    tags=["Admin · Campaign Forensics"],
)

_db = None


def set_db(db):
    global _db
    _db = db


def _classify_lead(
    lead: Dict[str, Any],
    dnc_phones: set,
    dnc_emails: set,
    blocked_domains: tuple,
    is_blocked_url,
    noise_name_substr: tuple,
    noise_domain_substr: tuple,
    internal_test_sources: set,
    test_email_domains: set,
) -> str:
    """Return the FIRST rejection reason for a lead, or 'eligible'."""
    name = (lead.get("business_name") or "").lower()
    email = (lead.get("email") or "").lower()
    phone = lead.get("phone") or ""
    site = (lead.get("website_url") or lead.get("website") or "").lower()
    status = lead.get("status") or ""
    source = lead.get("source") or ""

    if not email and not phone:
        return "no_contact_info"

    # Status block — only user-driven or auto-noise reasons re-allow
    if status in ("signed_up",):
        return "status_signed_up"
    if status == "not_interested":
        noise_reason = lead.get("noise_reason")
        if noise_reason not in ("pre-282u-scrape-residue", "listicle-or-directory"):
            return "status_not_interested"
    if status == "unsubscribed":
        return "status_unsubscribed"

    if lead.get("noise_flag") is True:
        return "noise_flag_set"

    if lead.get("last_blast_at"):
        return "already_blasted"

    if source in internal_test_sources:
        return f"internal_test_source({source})"

    if email and "@" in email:
        dom = email.partition("@")[2]
        if dom in test_email_domains or dom.endswith(".test") or dom.endswith(".invalid"):
            return f"test_email_domain({dom})"

    if phone in dnc_phones:
        return "dnc_phone"
    if email and email in dnc_emails:
        return "dnc_email"

    # Noise name patterns
    if any(s in name for s in noise_name_substr):
        return "noise_business_name"
    if (name.startswith("find ") and " in " in name) or \
       (" companies in " in name) or (" companies near " in name):
        return "listicle_business_name"

    if site and is_blocked_url(site):
        return "blocked_website_url"

    if email and "@" in email:
        dom = email.partition("@")[2]
        if any(d in dom for d in blocked_domains):
            return f"blocked_email_domain_substr({dom})"
        if any(dom == d for d in noise_domain_substr):
            return f"noise_email_domain_exact({dom})"
        if dom in {"autozone.com", "walmart.com", "amazon.com",
                   "homedepot.com", "lowes.com", "costco.com"}:
            return f"big_box_chain({dom})"
        user = email.partition("@")[0]
        if user in {"yelp.guest", "noreply", "no-reply", "postmaster"}:
            return f"generic_email_user({user})"

    return "eligible"


@router.get("/eligibility-forensics")
async def eligibility_forensics(limit: int = 1000):
    """Walk every queued lead, classify rejection reason, return histogram.

    Pass `?limit=N` to bound the scan (default 1000, max 5000).
    """
    if _db is None:
        raise HTTPException(503, "Database unavailable")

    limit = max(10, min(int(limit), 5000))

    # Pull filter inputs (same as _eligible_leads).
    dnc_phones: set = set()
    dnc_emails: set = set()
    async for d in _db.do_not_contact.find(
        {}, {"_id": 0, "phone": 1, "email": 1}
    ):
        if d.get("phone"):
            dnc_phones.add(d["phone"])
        if d.get("email"):
            dnc_emails.add(d["email"].lower())

    try:
        from services.google_places_scout import (
            BLOCKED_DOMAINS,
            _is_blocked_url,
        )
    except Exception:
        BLOCKED_DOMAINS = ()
        _is_blocked_url = lambda _u: False  # noqa: E731

    from services.auto_blast_engine import (
        _INTERNAL_TEST_SOURCES,
        _TEST_EMAIL_DOMAINS,
    )

    noise_name_substr = _NOISE_NAME_SUBSTR
    noise_domain_substr = _NOISE_DOMAIN_SUBSTR

    reasons: Counter = Counter()
    samples: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    scanned = 0
    eligible_count = 0

    cursor = _db.campaign_leads.find(
        {"last_blast_at": {"$exists": False}},
        {"_id": 0, "lead_id": 1, "business_name": 1, "email": 1,
         "phone": 1, "website_url": 1, "website": 1, "status": 1,
         "source": 1, "noise_flag": 1, "noise_reason": 1, "category": 1,
         "city": 1},
    ).limit(limit)

    async for lead in cursor:
        scanned += 1
        reason = _classify_lead(
            lead, dnc_phones, dnc_emails, BLOCKED_DOMAINS, _is_blocked_url,
            noise_name_substr, noise_domain_substr,
            _INTERNAL_TEST_SOURCES, _TEST_EMAIL_DOMAINS,
        )
        reasons[reason] += 1
        if reason == "eligible":
            eligible_count += 1
        if len(samples[reason]) < 5:
            samples[reason].append({
                "name": (lead.get("business_name") or "")[:42],
                "email": (lead.get("email") or "")[:50],
                "phone": (lead.get("phone") or "")[:18],
                "category": lead.get("category") or "",
                "status": lead.get("status") or "",
                "source": lead.get("source") or "",
            })

    return {
        "scanned": scanned,
        "eligible": eligible_count,
        "ineligible_breakdown": [
            {"reason": r, "count": c, "samples": samples[r]}
            for r, c in reasons.most_common()
            if r != "eligible"
        ],
        "actionable_hint": (
            "Top reason is the bottleneck. If it's 'no_contact_info' with "
            "listicle/wikipedia names → POST /purge-legacy-junk to nuke. "
            "If 'noise_email_domain_exact' with facebook/instagram → Apollo "
            "enrichment scraped social pages. If 'status_not_interested' "
            "with junk emails → also in /purge-legacy-junk scope."
        ),
    }


# ──────────────────────────────────────────────────────────────────────
# Safe Purge — removes obvious junk that the scrapers (pre-iter-324)
# ingested before the noise filter was hardened. Idempotent. Dry-run by
# default; pass `?apply=true` to actually delete.
# ──────────────────────────────────────────────────────────────────────
_NOISE_NAME_SUBSTR = (
    "the best 10 ", " - wikipedia", " - reddit",
    "nail salons for sale", "businesses for sale",
    "yelp.com/search", "r/",
)
_NOISE_DOMAIN_SUBSTR = (
    "yelp.com", "wikipedia.org", "reddit.com", "justia.com",
    "intently.co", "hvaclocal.com", "procore.com",
    "findbusinesses4sale.com", "bizbuysell.com",
    "fresha.com", "rew.ca", "desiforce.com",
    "facebook.com", "instagram.com", "tiktok.com", "twitter.com",
    "linkedin.com", "youtube.com", "pinterest.com",
    "yellowpages", "tripadvisor", "thumbtack", "houzz.com",
    "angi.com", "trustpilot", "glassdoor", "crunchbase",
    "google.com", "googleusercontent", "g.page",
    "homestars", "bbb.org", "indeed.com", "ziprecruiter",
    "weebly.com", "wix.com", "squarespace.com",
    "shopify.com", "etsy.com", "ebay.com", "kijiji.ca",
    "realtor.ca", "realtor.com", "zolo.ca", "zillow.com",
    "remax.ca", "remax.com", "century21",
    "aurem.live",
)


@router.post("/purge-legacy-junk")
async def purge_legacy_junk(apply: bool = False, max_delete: int = 5000):
    """
    Remove `campaign_leads` rows that are obvious legacy scraper junk:
      • Source = 'ora_hunt_command' (fully replaced by OSM admin hunt).
        That entire scraper ingested Wikipedia / Reddit / TikTok / listicle
        titles as "businesses" — none are real SMBs.
      • Plus belt-and-suspenders kills for any non-ora_hunt rows that
        still match obvious junk patterns (listicle names, junk email
        domains).

    DRY-RUN by default. Pass `?apply=true` to actually delete.
    NEVER touches `osm_overpass_admin_hunt` (the good source).
    Returns the count + sample of what was matched.
    """
    if _db is None:
        raise HTTPException(503, "Database unavailable")

    max_delete = max(10, min(int(max_delete), 50000))

    # The legacy ora_hunt_command source IS the junk. OSM admin hunt has
    # replaced it. Nuke everything from that source plus anything else
    # matching obvious junk patterns. Defensive: never touch the good
    # OSM admin source even if its leads accidentally got flagged.
    kill_filter = {
        "$and": [
            {"last_blast_at": {"$exists": False}},
            {"$or": [
                # The single biggest junk source
                {"source": "ora_hunt_command"},
                # Legacy scrapers we don't trust anymore
                {"source": {"$in": ["tavily_search", "ddg_search", "qa_bot_probe"]}},
                # No contact info — useless regardless of source
                {"$and": [
                    {"$or": [{"email": ""}, {"email": None}]},
                    {"$or": [{"phone": ""}, {"phone": None}]},
                ]},
                # Listicle / Wikipedia / Reddit names (case-insensitive)
                {"business_name": {"$regex":
                    "wikipedia|reddit| - r/|the best 10|nail salons for sale|"
                    "businesses for sale|companies in|companies near|"
                    "locations archive|tiktok|rating the best|secretly|"
                    "for sale in [a-z]{2,}|find .* in [a-z]{2,}",
                    "$options": "i"}},
                # Junk email domains (no trailing-dot anchor this time)
                {"email": {"$regex":
                    "@(facebook|instagram|tiktok|twitter|linkedin|youtube|"
                    "pinterest|yellowpages|tripadvisor|thumbtack|houzz|"
                    "angi|trustpilot|glassdoor|crunchbase|googleusercontent|"
                    "g\\.page|homestars|bbb|indeed|ziprecruiter|"
                    "findbusinesses4sale|bizbuysell|bizsold|fslocal|"
                    "fresha|rew\\.ca|desiforce|autozone|walmart|amazon|"
                    "homedepot|lowes|costco|realtor|zolo|zillow|remax|"
                    "century21|aurem\\.live)(\\.|$)",
                    "$options": "i"}},
            ]},
            # SACRED — never delete the good OSM admin-hunt leads.
            {"source": {"$ne": "osm_overpass_admin_hunt"}},
        ]
    }

    sample_cursor = _db.campaign_leads.find(
        kill_filter,
        {"_id": 0, "business_name": 1, "email": 1, "phone": 1,
         "source": 1, "status": 1, "category": 1},
    ).limit(15)
    samples = [d async for d in sample_cursor]
    total_match = await _db.campaign_leads.count_documents(kill_filter)

    if not apply:
        return {
            "dry_run": True,
            "would_delete": total_match,
            "samples": samples,
            "next_step": (
                f"Looks right? POST same endpoint with `?apply=true` to "
                f"actually delete (capped at max_delete={max_delete})."
            ),
        }

    if total_match > max_delete:
        ids = []
        async for d in _db.campaign_leads.find(kill_filter, {"_id": 1}).limit(max_delete):
            ids.append(d["_id"])
        result = await _db.campaign_leads.delete_many({"_id": {"$in": ids}})
    else:
        result = await _db.campaign_leads.delete_many(kill_filter)

    deleted = result.deleted_count
    remaining_queued = await _db.campaign_leads.count_documents(
        {"last_blast_at": {"$exists": False}}
    )

    # Safety check: confirm OSM admin-hunt leads survived
    osm_survived = await _db.campaign_leads.count_documents(
        {"source": "osm_overpass_admin_hunt"}
    )

    logger.warning(
        f"[forensics] purge-legacy-junk applied — deleted={deleted}, "
        f"queue_remaining={remaining_queued}, "
        f"osm_admin_hunt_survived={osm_survived}"
    )

    return {
        "dry_run": False,
        "deleted": deleted,
        "queue_remaining_after_purge": remaining_queued,
        "osm_admin_hunt_survived": osm_survived,
        "samples_of_deleted": samples,
    }
