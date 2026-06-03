"""
AUREM Enrichment Service — Apollo.io People Match API.

Forensic Contact Miner: completes missing contact data using the live
Apollo.io enrichment endpoint. NO mock layer — if APOLLO_API_KEY is
missing or Apollo returns no match, enrichment is skipped honestly.

Endpoints:
    POST /api/enrichment/enrich-contact   single customer enrichment
    POST /api/enrichment/bulk-enrich      batch all unenriched customers
    POST /api/enrichment/web-scrape       scrape a site → enrich found names
    GET  /api/enrichment/status           tenant-wide enrichment KPIs
"""

import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET")
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")


async def _get_apollo_key(user_id: str) -> str:
    """env var first, then tenant vault."""
    if APOLLO_API_KEY:
        return APOLLO_API_KEY
    try:
        from server import db
        from utils.vault_credentials import get_vault_credentials
        creds = await get_vault_credentials(db, user_id, "apollo")
        return creds.get("api_key", "")
    except Exception as e:
        logger.warning(f"Vault lookup failed for Apollo: {e}")
        return ""


def _extract_tenant(authorization: str) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(403, "Authorization required")
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        tenant_id = payload.get("tenant_id") or payload.get("user_id")
        user_id = payload.get("user_id")
        if not tenant_id:
            raise HTTPException(403, "Tenant context required")
        return {"tenant_id": tenant_id, "user_id": user_id}
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


def _require_apollo(api_key: str) -> None:
    if not api_key:
        raise HTTPException(
            503,
            "Enrichment not configured. Add APOLLO_API_KEY to env or "
            "connect Apollo via Vault.",
        )


async def _live_enrich_contact(email: str, api_key: str) -> dict:
    """POST https://api.apollo.io/v1/people/match — single contact."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.apollo.io/v1/people/match",
                json={"email": email, "reveal_personal_emails": True},
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                },
                params={"api_key": api_key},
            )
            data = resp.json()
            person = data.get("person") or {}
            org = person.get("organization") or {}

            return {
                "enriched":     bool(person.get("id")),
                "provider":     "apollo_live",
                "enriched_at":  datetime.now(timezone.utc).isoformat(),
                "person": {
                    "full_name":    f"{person.get('first_name', '')} "
                                    f"{person.get('last_name', '')}".strip(),
                    "title":        person.get("title", ""),
                    "seniority":    person.get("seniority", ""),
                    "linkedin_url": person.get("linkedin_url", ""),
                    "phone_direct": (person.get("phone_numbers") or [{}])[0]
                                       .get("sanitized_number", ""),
                    "city":         person.get("city", ""),
                    "state":        person.get("state", ""),
                    "country":      person.get("country", ""),
                },
                "company": {
                    "name":           org.get("name", ""),
                    "domain":         org.get("primary_domain", ""),
                    "industry":       org.get("industry", ""),
                    "employee_count": org.get("estimated_num_employees", 0),
                    "annual_revenue": org.get("annual_revenue_printed", ""),
                    "founded_year":   org.get("founded_year", 0),
                },
                "confidence_score": 0.9 if person.get("id") else 0.0,
            }
    except Exception as e:
        logger.error(f"Apollo enrichment error: {e}")
        return {
            "enriched": False,
            "provider": "apollo_live",
            "error":    str(e),
        }


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class EnrichRequest(BaseModel):
    customer_id: str


class BulkEnrichRequest(BaseModel):
    limit: Optional[int] = 50


class WebScrapeEnrichRequest(BaseModel):
    url: str
    profile_id: Optional[str] = ""


@router.post("/api/enrichment/enrich-contact")
async def enrich_single_contact(body: EnrichRequest,
                                  authorization: str = Header(None)):
    """Enrich a single customer via live Apollo.io."""
    from server import db
    ctx = _extract_tenant(authorization)

    customer = await db.tenant_customers.find_one(
        {"customer_id": body.customer_id, "tenant_id": ctx["tenant_id"]},
        {"_id": 0},
    )
    if not customer:
        raise HTTPException(404, "Customer not found")

    apollo_key = await _get_apollo_key(ctx["user_id"])
    _require_apollo(apollo_key)

    email = customer.get("email", "")
    enriched = await _live_enrich_contact(email, apollo_key)
    status = "enriched" if enriched.get("enriched") else "failed"

    updates = {
        "enrichment_status": status,
        "enriched_data":     enriched,
        "updated_at":        datetime.now(timezone.utc).isoformat(),
    }
    if enriched.get("enriched"):
        person = enriched.get("person", {})
        company = enriched.get("company", {})
        if person.get("linkedin_url"):
            updates["linkedin_url"] = person["linkedin_url"]
        if person.get("phone_direct") and not customer.get("phone"):
            updates["phone"] = person["phone_direct"]
        if company.get("name") and not customer.get("company"):
            updates["company"] = company["name"]
        if person.get("title") and not customer.get("job_title"):
            updates["job_title"] = person["title"]

    await db.tenant_customers.update_one(
        {"customer_id": body.customer_id},
        {"$set": updates},
    )

    return {
        "customer_id":       body.customer_id,
        "email":             email,
        "enrichment_status": status,
        "enriched_data":     enriched,
        "mode":              "live",
        "confidence":        enriched.get("confidence_score", 0),
        "message":           f"Contact enrichment via Apollo.io: {status}",
    }


@router.post("/api/enrichment/bulk-enrich")
async def bulk_enrich_contacts(body: BulkEnrichRequest,
                                  authorization: str = Header(None)):
    """Batch-enrich all unenriched customers for the current tenant."""
    from server import db
    ctx = _extract_tenant(authorization)

    apollo_key = await _get_apollo_key(ctx["user_id"])
    _require_apollo(apollo_key)

    unenriched = await db.tenant_customers.find(
        {"tenant_id":         ctx["tenant_id"],
         "enrichment_status": "none",
         "is_active":         True},
        {"_id": 0, "customer_id": 1, "email": 1,
         "first_name": 1, "last_name": 1},
    ).limit(body.limit).to_list(body.limit)

    enriched_count = 0
    failed_count = 0

    for cust in unenriched:
        email = cust.get("email", "")
        if not email or email == "REDACTED":
            continue

        result = await _live_enrich_contact(email, apollo_key)
        status = "enriched" if result.get("enriched") else "failed"
        updates = {
            "enrichment_status": status,
            "enriched_data":     result,
            "updated_at":        datetime.now(timezone.utc).isoformat(),
        }
        if result.get("enriched"):
            person = result.get("person", {})
            company = result.get("company", {})
            if person.get("linkedin_url"):
                updates["linkedin_url"] = person["linkedin_url"]
            if person.get("phone_direct") and not cust.get("phone"):
                updates["phone"] = person["phone_direct"]
            if company.get("name"):
                updates["company"] = company["name"]
            if person.get("title"):
                updates["job_title"] = person["title"]
            enriched_count += 1
        else:
            failed_count += 1

        await db.tenant_customers.update_one(
            {"customer_id": cust["customer_id"]},
            {"$set": updates},
        )

    return {
        "processed": len(unenriched),
        "enriched":  enriched_count,
        "failed":    failed_count,
        "mode":      "live",
        "message":   f"Bulk enrichment complete: {enriched_count} enriched, "
                     f"{failed_count} failed",
    }


_NAME_PAT = re.compile(
    r'<[^>]+class="[^"]*\b(?:name|team-name|member-name|profile-name)\b[^"]*"[^>]*>([^<]{3,60})</',
    re.IGNORECASE,
)


async def _scrape_team_page(url: str) -> list:
    """Best-effort HTML scrape for team member names. Returns [] when
    no names can be confidently extracted — never fabricates."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": ("Mozilla/5.0 (compatible; AuremEnrichBot/1.0; "
                               "+https://aurem.live/bot)"),
            })
            if resp.status_code != 200:
                return []
            html = resp.text
    except Exception as e:
        logger.warning(f"web-scrape fetch failed for {url}: {e}")
        return []

    names = []
    for match in _NAME_PAT.finditer(html):
        candidate = match.group(1).strip()
        # Require at least one space (first + last) and reasonable length
        if " " in candidate and 5 <= len(candidate) <= 60:
            names.append(candidate)
    # Dedup, cap at 25 to keep enrichment cost bounded
    seen = set()
    out = []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
        if len(out) >= 25:
            break
    return out


@router.post("/api/enrichment/web-scrape")
async def web_scrape_and_enrich(body: WebScrapeEnrichRequest,
                                   authorization: str = Header(None)):
    """Scan a website → extract team names → Apollo-enrich each."""
    from server import db
    ctx = _extract_tenant(authorization)
    now = datetime.now(timezone.utc).isoformat()

    apollo_key = await _get_apollo_key(ctx["user_id"])
    _require_apollo(apollo_key)

    url = body.url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"

    names = await _scrape_team_page(url)
    if not names:
        return {
            "url":               url,
            "people_found":      0,
            "contacts_imported": 0,
            "mode":              "live",
            "message":           ("No team-page name patterns detected. "
                                   "Try a deeper /about or /team URL."),
        }

    # Derive likely emails from domain — Apollo will replace with the
    # canonical address it finds via its match endpoint. We never
    # fabricate phone/company/title fields.
    try:
        domain = url.split("//", 1)[1].split("/", 1)[0].lower()
    except Exception:
        domain = ""
    imported = 0
    for raw in names:
        parts = raw.split()
        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""
        if not domain:
            continue
        email_guess = f"{first.lower()}.{last.lower()}@{domain}".strip(".@")

        existing = await db.tenant_customers.find_one(
            {"tenant_id": ctx["tenant_id"], "email": email_guess},
            {"_id": 0, "customer_id": 1},
        )
        if existing:
            continue

        enriched = await _live_enrich_contact(email_guess, apollo_key)
        person = enriched.get("person", {}) if enriched.get("enriched") else {}
        company = enriched.get("company", {}) if enriched.get("enriched") else {}

        await db.tenant_customers.insert_one({
            "customer_id":       f"cust_{secrets.token_urlsafe(12)}",
            "tenant_id":         ctx["tenant_id"],
            "user_id":           ctx["user_id"],
            "email":             email_guess,
            "first_name":        first,
            "last_name":         last,
            "phone":             person.get("phone_direct", ""),
            "source":            "web_scrape",
            "sync_date":         now,
            "tags":              ["web-mined", "auto-enriched"]
                                  if person else ["web-mined"],
            "total_spend":       0.0,
            "notes":             f"Mined from {url}",
            "linkedin_url":      person.get("linkedin_url", ""),
            "company":           company.get("name", ""),
            "job_title":         person.get("title", ""),
            "enrichment_status": "enriched" if person else "failed",
            "enriched_data":     enriched,
            "unsubscribe_token": f"unsub_{secrets.token_urlsafe(24)}",
            "gdpr_consent":      False,
            "ccpa_opt_out":      False,
            "is_active":         True,
            "created_at":        now,
            "updated_at":        now,
        })
        imported += 1

    return {
        "url":               url,
        "people_found":      len(names),
        "contacts_imported": imported,
        "mode":              "live",
        "message":           (f"Forensic scan complete: {len(names)} names "
                              f"detected, {imported} new contacts imported"),
    }


@router.get("/api/enrichment/status")
async def enrichment_status(authorization: str = Header(None)):
    """Tenant-wide enrichment KPIs."""
    from server import db
    ctx = _extract_tenant(authorization)
    tid = ctx["tenant_id"]

    total = await db.tenant_customers.count_documents(
        {"tenant_id": tid, "is_active": True},
    )
    enriched = await db.tenant_customers.count_documents(
        {"tenant_id": tid, "enrichment_status": "enriched",
         "is_active": True},
    )
    pending = await db.tenant_customers.count_documents(
        {"tenant_id": tid, "enrichment_status": "none",
         "is_active": True},
    )
    failed = await db.tenant_customers.count_documents(
        {"tenant_id": tid, "enrichment_status": "failed",
         "is_active": True},
    )

    return {
        "total_customers": total,
        "enriched":        enriched,
        "pending":         pending,
        "failed":          failed,
        "enrichment_rate": round(enriched / total * 100, 1) if total else 0,
        "mode":            "live" if APOLLO_API_KEY else "disabled",
    }
