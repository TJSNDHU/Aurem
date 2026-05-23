"""
services/apollo_discovery.py — iter 330e

Apollo.io organization discovery as PRIMARY lead source.

Background
──────────
The earlier `apollo_scout.py` does *enrichment only* (find a person at a
known-domain company). What we need for daily_hunt is the inverse:
discover Canadian SMB companies by industry + city BEFORE we know their
domain. That's what `POST /v1/organizations/search` does.

Tier
────
The current $65/mo plan grants:
  ✅ /v1/organizations/search       → primary discovery
  ✅ /v1/organizations/enrich       → fill in emails per org
  ❌ /v1/mixed_companies/search     → enterprise only
  ❌ /v1/mixed_people/search        → enterprise only

Strategy
────────
1) Search returns 5–25 orgs/request with name + website + phone + city.
2) For each org, enrich() returns the org's primary contact emails.
3) Result is normalised into the standard `{lead_id, business_name,
   email, phone, website, city, ...}` schema used by daily_hunt.

API spec (verified live 2026-02-23)
───────────────────────────────────
POST https://api.apollo.io/v1/organizations/search
headers: Content-Type: application/json
         Cache-Control: no-cache
         x-api-key: <APOLLO_API_KEY>
body:
  {
    "q_organization_keyword_tags": ["roofing"],
    "organization_locations":      ["Mississauga, Ontario, Canada"],
    "organization_num_employees_ranges": ["1,50"],
    "per_page": 25,
    "page":     1
  }
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List

import httpx

logger = logging.getLogger("apollo_discovery")

APOLLO_SEARCH_URL = "https://api.apollo.io/v1/organizations/search"


def _headers() -> dict:
    return {
        "Content-Type":  "application/json",
        "Cache-Control": "no-cache",
        "x-api-key":     (os.environ.get("APOLLO_API_KEY") or "").strip(),
    }


async def discover_organizations(
    *,
    industry_keyword: str,
    city:             str,
    province:         str = "Ontario",
    country:          str = "Canada",
    per_page:         int = 25,
    employee_ranges:  list[str] | None = None,
) -> List[Dict[str, Any]]:
    """One Apollo /organizations/search call → normalised lead rows.

    `industry_keyword` is matched against Apollo's `q_organization_keyword_tags`
    (e.g. "roofing", "dental", "plumbing"). `employee_ranges` uses Apollo's
    string format e.g. ["1,50"] for SMBs.
    """
    if not os.environ.get("APOLLO_API_KEY"):
        return []
    if employee_ranges is None:
        employee_ranges = ["1,50"]
    body = {
        "q_organization_keyword_tags": [industry_keyword],
        "organization_locations":       [f"{city}, {province}, {country}"],
        "organization_num_employees_ranges": employee_ranges,
        "per_page": max(1, min(int(per_page), 100)),
        "page":     1,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(APOLLO_SEARCH_URL, headers=_headers(), json=body)
    except Exception as e:
        logger.warning(f"[apollo-discovery] request failed: {e}")
        return []

    if r.status_code != 200:
        # Surface auth/quota issues to founder Telegram.
        try:
            from services.api_key_health_watcher import record_api_failure
            await record_api_failure(
                provider="apollo_discovery",
                status_code=r.status_code,
                body=r.text[:400],
                key_hint=(os.environ.get("APOLLO_API_KEY") or "")[-6:],
            )
        except Exception:
            pass
        logger.warning(f"[apollo-discovery] HTTP {r.status_code} on {industry_keyword}/{city}: {r.text[:200]}")
        return []

    try:
        data = r.json()
    except Exception:
        return []
    orgs = data.get("organizations") or []
    leads: List[Dict[str, Any]] = []
    for o in orgs:
        primary_phone = (o.get("primary_phone") or {}).get("sanitized_number") \
                          or o.get("sanitized_phone") \
                          or o.get("phone")
        lead = {
            "lead_id":       f"AURE-APL-{uuid.uuid4().hex[:6].upper()}",
            "business_name": o.get("name") or "",
            "website":       o.get("website_url") or "",
            "domain":        o.get("primary_domain") or "",
            "phone":         primary_phone or "",
            "email":         "",   # filled by enrichment downstream
            "city":          o.get("city") or city,
            "province":      o.get("state") or province,
            "country":       o.get("country") or country,
            "industry":      o.get("industry") or industry_keyword,
            "employees":     int(o.get("estimated_num_employees") or 0),
            "linkedin_url":  o.get("linkedin_url") or "",
            "founded_year":  o.get("founded_year"),
            "short_desc":    (o.get("short_description") or "")[:300],
            "source":        "apollo_discovery",
            "source_meta":   {"apollo_org_id": o.get("id")},
        }
        leads.append(lead)
    logger.info(f"[apollo-discovery] {industry_keyword}/{city}: returned {len(leads)} orgs")
    return leads


# ── Higher-level helper used by daily_hunt ───────────────────────────


# A tight list of SMB-friendly industries the founder explicitly named.
DEFAULT_INDUSTRY_KEYWORDS = [
    "roofing", "dental", "restaurant", "hvac", "plumbing",
    "landscaping", "accounting",
]

DEFAULT_GTA_CITIES = [
    "Mississauga", "Brampton", "Toronto",
    "Scarborough", "North York", "Etobicoke",
]


async def discover_for_default_targets(
    *,
    industries: list[str] | None = None,
    cities:     list[str] | None = None,
    per_combo:  int = 10,
) -> List[Dict[str, Any]]:
    """Loop over every (industry, city) combo and concat the results.

    This is what daily_hunt calls. Caps to `per_combo` per pair to spread
    credit cost. Returns one flat list of normalised lead dicts.
    """
    industries = industries or DEFAULT_INDUSTRY_KEYWORDS
    cities     = cities     or DEFAULT_GTA_CITIES
    all_leads: List[Dict[str, Any]] = []
    for ind in industries:
        for city in cities:
            try:
                rows = await discover_organizations(
                    industry_keyword=ind, city=city, per_page=per_combo,
                )
            except Exception as e:
                logger.warning(f"[apollo-discovery] combo failed {ind}/{city}: {e}")
                rows = []
            all_leads.extend(rows)
    return all_leads
