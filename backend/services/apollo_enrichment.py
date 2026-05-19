"""
Lead Enrichment Orchestrator — iter 287.2 (UPGRADED — Truth-Sync honest)

Apollo free tier blocks people/search and people/match. So the "DIY"
strategy is:
  1. Website scrape (primary, always works, zero cost)
     → extract emails, phones, people names, socials from contact/about pages
  2. Apollo organizations/enrich (FREE tier, free metadata for big cos)
     → industry, LinkedIn co page, employee count, technologies
  3. Email pattern guess (fallback if website had no email but we got names)

Writes unified enrichment fields back onto the lead:
  • email + email_confidence (HIGH/MEDIUM/NONE)
  • apollo_person_name, apollo_person_title, apollo_linkedin_url
  • enrichment_sources: ["website_scrape", "apollo_org_enrich", "email_pattern"]
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("apollo_enrich")


async def enrich_lead_with_apollo_diy(
    db: Any,
    lead_id: str,
    website_url: str,
) -> dict:
    """Full DIY enrichment pipeline. Fire-and-forget safe."""
    try:
        from services.website_scraper import scrape_website
        from services.apollo_org_enrich import apollo_enrich_org
        from services.apollo_scout import _domain_from_url
        from services.email_guesser import guess_and_verify
    except ModuleNotFoundError:
        from backend.services.website_scraper import scrape_website  # type: ignore
        from backend.services.apollo_org_enrich import apollo_enrich_org  # type: ignore
        from backend.services.apollo_scout import _domain_from_url  # type: ignore
        from backend.services.email_guesser import guess_and_verify  # type: ignore

    domain = _domain_from_url(website_url)
    if not domain:
        return {"email": None, "status": "skipped",
                "skipped_reason": "no_domain", "sources": []}

    # iter 324b — Reject aggregator/social/SaaS domains before we waste
    # any cycles. These produce junk role-emails like `info@facebook.com`
    # that pass `noise_flag` filters but are unblastable. (Root cause of
    # the "421 queued, 0 eligible" funnel collapse.)
    try:
        from services.contact_quality import is_aggregator_domain
        if is_aggregator_domain(domain):
            logger.info(f"[enrich] skipping aggregator domain: {domain} (lead={lead_id})")
            # Mark the lead so the noise pipeline can act on it.
            try:
                await db.campaign_leads.update_one(
                    {"lead_id": lead_id},
                    {"$set": {
                        "enrichment_sources":  ["aggregator-skipped"],
                        "enriched_at":         datetime.now(timezone.utc).isoformat(),
                        "email_confidence":    "NONE",
                        "noise_flag":          True,
                        "noise_reason":        f"aggregator-domain:{domain} (iter-324b)",
                        "noise_filtered_at":   datetime.now(timezone.utc).isoformat(),
                    }},
                )
            except Exception:
                pass
            return {"email": None, "status": "skipped",
                    "skipped_reason": f"aggregator-domain:{domain}",
                    "sources": ["aggregator-skipped"]}
    except Exception as _e:
        logger.warning(f"[enrich] contact_quality check failed for {domain}: {_e}")

    sources_used: list[str] = []

    # ── Step 1: Website scan (primary) ──
    # iter 282al — route through webclaw-aware `scan_website()` so we
    # get brand + structured contacts when WEBCLAW_API_KEY is set, and
    # gracefully degrade to the legacy httpx scraper otherwise. The
    # legacy shape (`emails`, `people`, `socials`, `phones`) is preserved
    # so downstream enrichment keeps working.
    scrape: dict = {}
    try:
        try:
            from services.website_scraper import scan_website
        except ModuleNotFoundError:
            from backend.services.website_scraper import scan_website  # type: ignore
        scan = await scan_website(website_url)
        if scan.get("status") == "success":
            contacts = scan.get("contacts") or {}
            # webclaw path → keep legacy surface keys populated
            scrape = dict(contacts) if isinstance(contacts, dict) else {}
            # Record brand + markdown for downstream Composer usage
            if scan.get("brand"):
                scrape["brand"] = scan["brand"]
            if scan.get("content"):
                scrape["scan_content"] = scan["content"][:4000]
            scrape.setdefault("pages_scanned", 1)
            sources_used.append(f"website_scan[{scan.get('source','unknown')}]")
        else:
            # scan_website returned failed → fall back to legacy scraper
            scrape = await scrape_website(website_url)
            if scrape.get("pages_scanned", 0) > 0:
                sources_used.append("website_scrape_legacy")
    except Exception as e:
        logger.warning(f"[enrich] scan failed for {domain}: {e}")
        try:
            scrape = await scrape_website(website_url)
            if scrape.get("pages_scanned", 0) > 0:
                sources_used.append("website_scrape_legacy")
        except Exception as e2:
            logger.warning(f"[enrich] legacy scrape also failed for {domain}: {e2}")

    best_email = (scrape.get("emails") or [None])[0]
    best_email_confidence = "HIGH" if best_email else "NONE"
    scraped_people = scrape.get("people") or []
    scraped_socials = scrape.get("socials") or {}

    # ── Step 2: Apollo organizations/enrich (free tier metadata) ──
    apollo_org: dict = {}
    if os.environ.get("APOLLO_API_KEY"):
        try:
            apollo_org = await apollo_enrich_org(db, domain)
            if apollo_org:
                sources_used.append("apollo_org_enrich")
                # Iter 288.8 — Boardroom Ledger: record Apollo enrich cost
                try:
                    from services.agent_ledger import record_cost
                    await record_cost(db, "scout_ora", "apollo_enrich", 1,
                                      meta={"domain": domain, "lead_id": lead_id})
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"[enrich] apollo org enrich failed for {domain}: {e}")

    # ── Step 3: Email pattern guess (only if no email yet + we have a name) ──
    pattern_candidates: list = []
    if not best_email and scraped_people:
        person = scraped_people[0]
        try:
            result = await guess_and_verify(
                person["first_name"], person["last_name"], domain,
                max_candidates=5,
            )
            if result.get("best_email"):
                best_email = result["best_email"]
                best_email_confidence = (
                    "HIGH" if result["best_status"] == "valid"
                    else "MEDIUM" if result["best_status"] == "probably_valid"
                    else "NONE"
                )
                sources_used.append("email_pattern")
            pattern_candidates = result.get("candidates") or []
        except Exception as e:
            logger.warning(f"[enrich] email guess failed for {domain}: {e}")

    # ── Step 3b: Generic role-email fallback (iter 288.6) ──
    # Most SMBs don't expose owner names. Fall back to canonical role-mailboxes
    # (info@, contact@, hello@…) which deliver in ~70% of cases for SMBs.
    if not best_email:
        for prefix in ("info", "contact", "hello", "sales", "admin", "office"):
            candidate = f"{prefix}@{domain}"
            try:
                check = await guess_and_verify("", "", domain,
                                                max_candidates=1,
                                                override_local=prefix)
                if check.get("best_email"):
                    best_email = check["best_email"]
                    best_email_confidence = "MEDIUM" if check.get("best_status") == "valid" else "LOW"
                    sources_used.append(f"role_email:{prefix}")
                    break
            except TypeError:
                # Older guess_and_verify without override_local — assume role-email viable
                best_email = candidate
                best_email_confidence = "LOW"
                sources_used.append(f"role_email:{prefix}")
                break
            except Exception as e:
                logger.warning(f"[enrich] role-email check {candidate}: {e}")
                continue
        if best_email and best_email.endswith(f"@{domain}"):
            logger.info(f"[enrich] role-email fallback used: {best_email}")

    # ── Pick a person + linkedin to surface ──
    primary_person_name = ""
    primary_person_title = ""
    if scraped_people:
        p = scraped_people[0]
        primary_person_name = f"{p['first_name']} {p['last_name']}".strip()
        primary_person_title = p.get("title", "")
    primary_linkedin = (
        scraped_socials.get("linkedin")
        or apollo_org.get("linkedin_url")
        or ""
    )

    # ── Write back to lead (Truth-Sync) ──
    # Determine what actually gets persisted. Don't lie about confidence
    # if we didn't actually save an email.
    will_set_email = False
    if best_email:
        try:
            existing = await db.campaign_leads.find_one(
                {"lead_id": lead_id}, {"_id": 0, "email": 1},
            )
            # iter 288.6 fix — empty doc {} is falsy in Python; check None explicitly
            if existing is None or not existing.get("email"):
                will_set_email = True
        except Exception:
            will_set_email = True  # be generous on read error

    patch: dict[str, Any] = {
        "enrichment_sources":  sources_used,
        "enriched_at":         datetime.now(timezone.utc).isoformat(),
        "email_confidence":    best_email_confidence if will_set_email else "NONE",
    }
    if will_set_email:
        patch["email"] = best_email
        patch["email_source"] = sources_used[-1] if sources_used else "unknown"
    if primary_person_name:
        patch["apollo_person_name"] = primary_person_name
    if primary_person_title:
        patch["apollo_person_title"] = primary_person_title
    if primary_linkedin:
        patch["apollo_linkedin_url"] = primary_linkedin
    if scrape.get("phones"):
        patch["scraped_phones"] = scrape["phones"]
    if apollo_org.get("industry"):
        patch["apollo_industry"] = apollo_org["industry"]
    if apollo_org.get("employees"):
        patch["apollo_employees"] = apollo_org["employees"]
    if pattern_candidates:
        patch["apollo_candidates_tried"] = pattern_candidates

    try:
        await db.campaign_leads.update_one({"lead_id": lead_id}, {"$set": patch})
    except Exception as e:
        logger.warning(f"[enrich] lead update failed for {lead_id}: {e}")

    return {
        "email":          best_email,
        "status":         "enriched" if best_email else (
                           "metadata_only" if sources_used else "no_data"),
        "confidence":     best_email_confidence,
        "person":         primary_person_name or None,
        "title":          primary_person_title or None,
        "linkedin_url":   primary_linkedin or None,
        "sources":        sources_used,
        "scraped_phones": scrape.get("phones") or [],
    }
