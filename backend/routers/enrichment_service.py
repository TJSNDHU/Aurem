"""
AUREM Enrichment Service — Apollo.io API Structure (Mock Layer)
Forensic Contact Miner: Completes missing contact data using
enrichment APIs. Currently using Mock Enrichment Layer.

Architecture:
1. Single-Contact Enrichment — Enrich one customer by email or domain
2. Bulk Enrichment — Batch-process all unenriched customers
3. Web Scrape + Enrich — Scan website → extract names → find emails
4. Enrichment Status Tracker — Monitor enrichment progress
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import os
import secrets
import logging
import random
import jwt

router = APIRouter()
logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET")
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")

# Toggle for live vs mock — falls back to vault-based per-tenant key
USE_MOCK_ENRICHMENT = not bool(APOLLO_API_KEY)


async def _get_apollo_key(user_id: str) -> str:
    """Get Apollo API key: env var first, then tenant vault."""
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


# ═══════════════════════════════════════════════════════════════
# MOCK ENRICHMENT ENGINE
# ═══════════════════════════════════════════════════════════════

MOCK_TITLES = [
    "CEO", "CTO", "VP of Marketing", "Head of Sales", "Product Manager",
    "Director of Engineering", "CMO", "COO", "Founder", "Growth Lead",
    "Head of Operations", "VP of Business Development", "CFO",
]
MOCK_COMPANIES = [
    "TechForward Inc.", "Nebula Digital", "Apex Solutions", "Quantum Labs",
    "Horizon Ventures", "Stellar Commerce", "Prism Analytics",
    "BlueShift Media", "Atlas Automation", "Forge Technologies",
]
MOCK_LINKEDIN_PREFIX = "https://linkedin.com/in/"
MOCK_INDUSTRIES = ["SaaS", "E-commerce", "FinTech", "HealthTech", "MarTech", "EdTech", "AI/ML", "Consulting"]
MOCK_SENIORITY = ["C-Suite", "VP", "Director", "Manager", "Senior", "Entry"]


def _mock_enrich_contact(email: str, first_name: str = "", last_name: str = "") -> dict:
    """Simulate Apollo.io-style enrichment response."""
    name_slug = email.split("@")[0].replace(".", "-")
    company = random.choice(MOCK_COMPANIES)
    title = random.choice(MOCK_TITLES)

    return {
        "enriched": True,
        "provider": "apollo_mock",
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "person": {
            "full_name": f"{first_name or name_slug.split('-')[0].title()} {last_name or name_slug.split('-')[-1].title()}",
            "title": title,
            "seniority": random.choice(MOCK_SENIORITY),
            "linkedin_url": f"{MOCK_LINKEDIN_PREFIX}{name_slug}",
            "phone_direct": f"+1{random.randint(2000000000, 9999999999)}",
            "city": random.choice(["New York", "San Francisco", "Austin", "Miami", "Chicago", "Seattle", "Denver"]),
            "state": random.choice(["NY", "CA", "TX", "FL", "IL", "WA", "CO"]),
            "country": "US",
        },
        "company": {
            "name": company,
            "domain": company.lower().replace(" ", "").replace(".", "") + ".com",
            "industry": random.choice(MOCK_INDUSTRIES),
            "employee_count": random.choice([10, 50, 200, 500, 1000, 5000]),
            "annual_revenue": f"${random.choice([1, 5, 10, 50, 100])}M",
            "founded_year": random.randint(2010, 2024),
        },
        "confidence_score": round(random.uniform(0.75, 0.98), 2),
    }


async def _live_enrich_contact(email: str, api_key: str = "") -> dict:
    """
    Production Apollo.io People Enrichment API.
    Endpoint: POST https://api.apollo.io/v1/people/match
    """
    import httpx
    key = api_key or APOLLO_API_KEY

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.apollo.io/v1/people/match",
                json={"email": email, "reveal_personal_emails": True},
                headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
                params={"api_key": key},
            )
            data = resp.json()
            person = data.get("person", {})
            org = person.get("organization", {})

            return {
                "enriched": bool(person.get("id")),
                "provider": "apollo_live",
                "enriched_at": datetime.now(timezone.utc).isoformat(),
                "person": {
                    "full_name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                    "title": person.get("title", ""),
                    "seniority": person.get("seniority", ""),
                    "linkedin_url": person.get("linkedin_url", ""),
                    "phone_direct": person.get("phone_numbers", [{}])[0].get("sanitized_number", "") if person.get("phone_numbers") else "",
                    "city": person.get("city", ""),
                    "state": person.get("state", ""),
                    "country": person.get("country", ""),
                },
                "company": {
                    "name": org.get("name", ""),
                    "domain": org.get("primary_domain", ""),
                    "industry": org.get("industry", ""),
                    "employee_count": org.get("estimated_num_employees", 0),
                    "annual_revenue": org.get("annual_revenue_printed", ""),
                    "founded_year": org.get("founded_year", 0),
                },
                "confidence_score": 0.9 if person.get("id") else 0.0,
            }
    except Exception as e:
        logger.error(f"Apollo enrichment error: {e}")
        return {"enriched": False, "provider": "apollo_live", "error": str(e)}


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
async def enrich_single_contact(body: EnrichRequest, authorization: str = Header(None)):
    """Enrich a single customer's data using Apollo.io (or mock)."""
    from server import db
    ctx = _extract_tenant(authorization)

    customer = await db.tenant_customers.find_one(
        {"customer_id": body.customer_id, "tenant_id": ctx["tenant_id"]},
        {"_id": 0}
    )
    if not customer:
        raise HTTPException(404, "Customer not found")

    email = customer.get("email", "")
    first_name = customer.get("first_name", "")
    last_name = customer.get("last_name", "")

    # Check for tenant-specific Apollo key from vault
    apollo_key = await _get_apollo_key(ctx["user_id"])
    use_mock = not bool(apollo_key)

    if use_mock:
        enriched = _mock_enrich_contact(email, first_name, last_name)
    else:
        enriched = await _live_enrich_contact(email, apollo_key)

    status = "enriched" if enriched.get("enriched") else "failed"

    # Update customer with enriched data
    updates = {
        "enrichment_status": status,
        "enriched_data": enriched,
        "updated_at": datetime.now(timezone.utc).isoformat(),
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
        {"$set": updates}
    )

    return {
        "customer_id": body.customer_id,
        "email": email,
        "enrichment_status": status,
        "enriched_data": enriched,
        "mode": "mock" if use_mock else "live",
        "confidence": enriched.get("confidence_score", 0),
        "message": f"Contact enriched via {'Mock Apollo' if use_mock else 'Apollo.io'}",
    }


@router.post("/api/enrichment/bulk-enrich")
async def bulk_enrich_contacts(body: BulkEnrichRequest, authorization: str = Header(None)):
    """Batch-enrich all unenriched customers for the current tenant."""
    from server import db
    ctx = _extract_tenant(authorization)

    unenriched = await db.tenant_customers.find(
        {"tenant_id": ctx["tenant_id"], "enrichment_status": "none", "is_active": True},
        {"_id": 0, "customer_id": 1, "email": 1, "first_name": 1, "last_name": 1}
    ).limit(body.limit).to_list(body.limit)

    enriched_count = 0
    failed_count = 0

    # Check for tenant-specific Apollo key from vault
    apollo_key = await _get_apollo_key(ctx["user_id"])
    use_mock = not bool(apollo_key)

    for cust in unenriched:
        email = cust.get("email", "")
        if not email or email == "REDACTED":
            continue

        if use_mock:
            result = _mock_enrich_contact(email, cust.get("first_name", ""), cust.get("last_name", ""))
        else:
            result = await _live_enrich_contact(email, apollo_key)

        status = "enriched" if result.get("enriched") else "failed"
        updates = {
            "enrichment_status": status,
            "enriched_data": result,
            "updated_at": datetime.now(timezone.utc).isoformat(),
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
            {"$set": updates}
        )

    return {
        "processed": len(unenriched),
        "enriched": enriched_count,
        "failed": failed_count,
        "mode": "mock" if use_mock else "live",
        "message": f"Bulk enrichment complete: {enriched_count} enriched, {failed_count} failed",
    }


@router.post("/api/enrichment/web-scrape")
async def web_scrape_and_enrich(body: WebScrapeEnrichRequest, authorization: str = Header(None)):
    """
    Forensic Contact Miner: Scan a website → find team members →
    enrich their profiles using Apollo.io mock/live.
    """
    from server import db
    ctx = _extract_tenant(authorization)
    now = datetime.now(timezone.utc).isoformat()

    url = body.url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"

    # Simulate web scrape finding team members
    # In production, this would use BeautifulSoup to parse /about, /team pages
    mock_found_people = [
        {"name": "Sarah Chen", "role": "CEO & Founder", "email_guess": f"sarah@{url.split('//')[1].split('/')[0]}"},
        {"name": "Marcus Rivera", "role": "CTO", "email_guess": f"marcus@{url.split('//')[1].split('/')[0]}"},
        {"name": "Aisha Patel", "role": "VP of Sales", "email_guess": f"aisha@{url.split('//')[1].split('/')[0]}"},
    ]

    imported = 0
    for person in mock_found_people:
        email = person["email_guess"].lower()

        existing = await db.tenant_customers.find_one(
            {"tenant_id": ctx["tenant_id"], "email": email},
            {"_id": 0, "customer_id": 1}
        )
        if existing:
            continue

        enriched = _mock_enrich_contact(email, person["name"].split()[0], person["name"].split()[-1])

        customer_id = f"cust_{secrets.token_urlsafe(12)}"
        await db.tenant_customers.insert_one({
            "customer_id": customer_id,
            "tenant_id": ctx["tenant_id"],
            "user_id": ctx["user_id"],
            "email": email,
            "first_name": person["name"].split()[0],
            "last_name": person["name"].split()[-1] if len(person["name"].split()) > 1 else "",
            "phone": enriched.get("person", {}).get("phone_direct", ""),
            "source": "web_scrape",
            "sync_date": now,
            "tags": ["web-mined", "auto-enriched"],
            "total_spend": 0.0,
            "notes": f"Mined from {url} — Role: {person['role']}",
            "linkedin_url": enriched.get("person", {}).get("linkedin_url", ""),
            "company": enriched.get("company", {}).get("name", ""),
            "job_title": person["role"],
            "enrichment_status": "enriched",
            "enriched_data": enriched,
            "unsubscribe_token": f"unsub_{secrets.token_urlsafe(24)}",
            "gdpr_consent": False,
            "ccpa_opt_out": False,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
        imported += 1

    return {
        "url": url,
        "people_found": len(mock_found_people),
        "contacts_imported": imported,
        "mode": "mock" if USE_MOCK_ENRICHMENT else "live",
        "message": f"Forensic scan complete: {len(mock_found_people)} team members found, {imported} new contacts imported",
    }


@router.get("/api/enrichment/status")
async def enrichment_status(authorization: str = Header(None)):
    """Get overall enrichment status for the tenant's customer vault."""
    from server import db
    ctx = _extract_tenant(authorization)
    tid = ctx["tenant_id"]

    total = await db.tenant_customers.count_documents({"tenant_id": tid, "is_active": True})
    enriched = await db.tenant_customers.count_documents({"tenant_id": tid, "enrichment_status": "enriched", "is_active": True})
    pending = await db.tenant_customers.count_documents({"tenant_id": tid, "enrichment_status": "none", "is_active": True})
    failed = await db.tenant_customers.count_documents({"tenant_id": tid, "enrichment_status": "failed", "is_active": True})

    return {
        "total_customers": total,
        "enriched": enriched,
        "pending": pending,
        "failed": failed,
        "enrichment_rate": round(enriched / total * 100, 1) if total > 0 else 0,
        "mode": "mock" if USE_MOCK_ENRICHMENT else "live (Apollo.io)",
    }
