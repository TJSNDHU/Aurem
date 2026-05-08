"""
AUREM CRM Sync Engine — HubSpot & Salesforce Integration
Connect any CRM to sync contacts into the tenant-isolated Customer Vault.
Mock Data Layer for testing without live CRM credentials.

Components:
1. HubSpot OAuth + Contact Sync
2. Salesforce OAuth + Contact Sync  
3. Mock CRM Data Generator
4. Unified CRM Connection Manager
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import os
import secrets
import logging
import random
import jwt

router = APIRouter()
logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET")
HUBSPOT_API_KEY = os.environ.get("HUBSPOT_API_KEY", "")
SALESFORCE_CLIENT_ID = os.environ.get("SALESFORCE_CLIENT_ID", "")


async def _get_crm_credentials(user_id: str, crm_type: str) -> dict:
    """Get CRM credentials: env var first, then tenant vault."""
    if crm_type == "hubspot" and HUBSPOT_API_KEY:
        return {"access_token": HUBSPOT_API_KEY}
    try:
        from server import db
        from utils.vault_credentials import get_vault_credentials
        return await get_vault_credentials(db, user_id, crm_type)
    except Exception as e:
        logger.warning(f"Vault lookup failed for {crm_type}: {e}")
        return {}


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
# MOCK CRM DATA
# ═══════════════════════════════════════════════════════════════

TITLES_B2B = [
    "CEO", "CTO", "VP Marketing", "Head of Sales", "Director of Ops",
    "Product Manager", "CMO", "COO", "Growth Lead", "Account Executive",
    "Customer Success Manager", "Engineering Manager", "CFO", "VP Engineering",
]
COMPANIES_B2B = [
    "Apex Solutions", "Quantum Labs", "Prism Analytics", "Nebula Digital",
    "BlueShift Media", "Forge Technologies", "Atlas Automation",
    "Stellar Commerce", "Horizon Ventures", "TechForward Inc.",
    "DataWave AI", "CloudPeak Systems", "NovaTech Group", "Zenith Digital",
]
DEAL_STAGES = ["lead", "contacted", "qualified", "proposal", "negotiation", "closed_won", "closed_lost"]
LEAD_SOURCES = ["website", "referral", "linkedin", "trade_show", "cold_outreach", "inbound", "partner"]
FIRST_NAMES = ["Sarah", "Marcus", "Aisha", "James", "Elena", "David", "Priya", "Carlos",
    "Maya", "Robert", "Zara", "Michael", "Leila", "Thomas", "Nina", "Kevin"]
LAST_NAMES = ["Chen", "Rivera", "Patel", "Williams", "Kim", "Johnson", "Singh",
    "Garcia", "Thompson", "Lee", "Anderson", "Martinez", "Taylor", "Wilson"]


def _generate_mock_crm_contacts(count: int, crm_type: str) -> list:
    contacts = []
    for i in range(count):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        company = random.choice(COMPANIES_B2B)
        domain = company.lower().replace(" ", "").replace(".", "") + ".com"
        email = f"{first.lower()}.{last.lower()}@{domain}"
        days_ago = random.randint(0, 365)
        created = datetime.now(timezone.utc) - timedelta(days=days_ago)

        contact = {
            "crm_contact_id": f"{'hs' if crm_type == 'hubspot' else 'sf'}_{7000000 + i}",
            "email": email,
            "first_name": first,
            "last_name": last,
            "phone": f"+1{random.randint(2000000000, 9999999999)}",
            "company": company,
            "job_title": random.choice(TITLES_B2B),
            "deal_stage": random.choice(DEAL_STAGES),
            "deal_value": round(random.uniform(5000, 250000), 2),
            "lead_source": random.choice(LEAD_SOURCES),
            "last_activity": (created + timedelta(days=random.randint(0, days_ago))).isoformat(),
            "created_at_crm": created.isoformat(),
            "lifecycle_stage": random.choice(["subscriber", "lead", "mql", "sql", "opportunity", "customer"]),
            "linkedin_url": f"https://linkedin.com/in/{first.lower()}-{last.lower()}-{random.randint(100,999)}",
        }
        contacts.append(contact)
    return contacts


# ═══════════════════════════════════════════════════════════════
# CONNECTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class CRMConnectRequest(BaseModel):
    crm_type: str  # hubspot | salesforce
    api_key: Optional[str] = ""
    instance_url: Optional[str] = ""


@router.post("/api/crm-sync/connect")
async def connect_crm(body: CRMConnectRequest, authorization: str = Header(None)):
    """Connect a CRM (HubSpot or Salesforce). Mock mode if no API key."""
    from server import db
    ctx = _extract_tenant(authorization)
    now = datetime.now(timezone.utc).isoformat()

    if body.crm_type not in ("hubspot", "salesforce"):
        raise HTTPException(400, "Supported CRM types: hubspot, salesforce")

    existing = await db.crm_connections.find_one(
        {"tenant_id": ctx["tenant_id"], "crm_type": body.crm_type, "status": "connected"},
        {"_id": 0}
    )
    if existing:
        return {"status": "already_connected", "crm_type": body.crm_type, "connected_at": existing.get("connected_at")}

    connection_id = f"crm_{secrets.token_urlsafe(12)}"
    
    # Determine mode: explicit key > vault key > mock
    has_explicit_key = bool(body.api_key)
    vault_creds = {}
    if not has_explicit_key:
        vault_creds = await _get_crm_credentials(ctx["user_id"], body.crm_type)
    has_vault_key = bool(vault_creds.get("access_token"))
    is_mock = not has_explicit_key and not has_vault_key

    conn_doc = {
        "connection_id": connection_id,
        "tenant_id": ctx["tenant_id"],
        "user_id": ctx["user_id"],
        "crm_type": body.crm_type,
        "status": "connected",
        "mode": "mock" if is_mock else "live",
        "instance_url": body.instance_url or f"https://app.{'hubspot' if body.crm_type == 'hubspot' else 'salesforce'}.com",
        "connected_at": now,
        "created_at": now,
        "contacts_synced": 0,
    }
    await db.crm_connections.insert_one(conn_doc)

    display_name = "HubSpot" if body.crm_type == "hubspot" else "Salesforce"
    return {
        "status": "connected",
        "connection_id": connection_id,
        "crm_type": body.crm_type,
        "mode": "mock" if is_mock else "live",
        "message": f"{display_name} connected {'(Mock Mode)' if is_mock else ''}. Ready to sync contacts.",
    }


@router.get("/api/crm-sync/connections")
async def list_crm_connections(authorization: str = Header(None)):
    """List all CRM connections for the current tenant."""
    from server import db
    ctx = _extract_tenant(authorization)

    connections = await db.crm_connections.find(
        {"tenant_id": ctx["tenant_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(20)

    return {"connections": connections, "total": len(connections)}


@router.delete("/api/crm-sync/disconnect/{connection_id}")
async def disconnect_crm(connection_id: str, authorization: str = Header(None)):
    """Disconnect a CRM."""
    from server import db
    ctx = _extract_tenant(authorization)

    result = await db.crm_connections.update_one(
        {"connection_id": connection_id, "tenant_id": ctx["tenant_id"]},
        {"$set": {"status": "disconnected", "disconnected_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Connection not found")
    return {"message": "CRM disconnected", "connection_id": connection_id}


# ═══════════════════════════════════════════════════════════════
# SYNC CONTACTS
# ═══════════════════════════════════════════════════════════════

class CRMSyncRequest(BaseModel):
    connection_id: str
    mock_count: Optional[int] = 200


@router.post("/api/crm-sync/sync-contacts")
async def sync_crm_contacts(body: CRMSyncRequest, authorization: str = Header(None)):
    """Pull contacts from CRM and store in tenant_customers vault."""
    from server import db
    ctx = _extract_tenant(authorization)
    now = datetime.now(timezone.utc).isoformat()

    conn = await db.crm_connections.find_one(
        {"connection_id": body.connection_id, "tenant_id": ctx["tenant_id"], "status": "connected"},
        {"_id": 0}
    )
    if not conn:
        raise HTTPException(404, "Active CRM connection not found")

    crm_type = conn.get("crm_type", "hubspot")
    is_mock = conn.get("mode") == "mock"

    sync_id = f"crmsync_{secrets.token_urlsafe(12)}"
    await db.crm_sync_jobs.insert_one({
        "sync_id": sync_id,
        "connection_id": body.connection_id,
        "tenant_id": ctx["tenant_id"],
        "user_id": ctx["user_id"],
        "crm_type": crm_type,
        "status": "running",
        "started_at": now,
    })

    if is_mock:
        crm_contacts = _generate_mock_crm_contacts(body.mock_count or 200, crm_type)
    else:
        crm_contacts = await _fetch_live_crm_contacts(conn, ctx["user_id"])

    imported = 0
    skipped = 0

    for cc in crm_contacts:
        email = (cc.get("email") or "").lower().strip()
        if not email:
            skipped += 1
            continue

        existing = await db.tenant_customers.find_one(
            {"tenant_id": ctx["tenant_id"], "email": email},
            {"_id": 0, "customer_id": 1}
        )
        if existing:
            await db.tenant_customers.update_one(
                {"customer_id": existing["customer_id"]},
                {"$set": {
                    "crm_data": cc,
                    "company": cc.get("company", ""),
                    "job_title": cc.get("job_title", ""),
                    "updated_at": now,
                }}
            )
            skipped += 1
            continue

        customer_id = f"cust_{secrets.token_urlsafe(12)}"
        source = f"{crm_type}_sync"
        display = "HubSpot" if crm_type == "hubspot" else "Salesforce"
        doc = {
            "customer_id": customer_id,
            "tenant_id": ctx["tenant_id"],
            "user_id": ctx["user_id"],
            "email": email,
            "first_name": cc.get("first_name", ""),
            "last_name": cc.get("last_name", ""),
            "phone": cc.get("phone", ""),
            "source": source,
            "sync_date": now,
            "tags": [crm_type, cc.get("lifecycle_stage", "lead")],
            "total_spend": cc.get("deal_value", 0.0),
            "notes": f"Synced from {display} — {cc.get('deal_stage', 'lead')}",
            "linkedin_url": cc.get("linkedin_url", ""),
            "company": cc.get("company", ""),
            "job_title": cc.get("job_title", ""),
            "enrichment_status": "none",
            "enriched_data": {},
            "crm_data": {
                "crm_contact_id": cc.get("crm_contact_id", ""),
                "deal_stage": cc.get("deal_stage", ""),
                "deal_value": cc.get("deal_value", 0),
                "lead_source": cc.get("lead_source", ""),
                "lifecycle_stage": cc.get("lifecycle_stage", ""),
                "last_activity": cc.get("last_activity"),
            },
            "unsubscribe_token": f"unsub_{secrets.token_urlsafe(24)}",
            "gdpr_consent": True,
            "ccpa_opt_out": False,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        await db.tenant_customers.insert_one(doc)
        imported += 1

    await db.crm_sync_jobs.update_one(
        {"sync_id": sync_id},
        {"$set": {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "contacts_found": len(crm_contacts),
            "contacts_imported": imported,
            "contacts_skipped": skipped,
        }}
    )

    await db.crm_connections.update_one(
        {"connection_id": body.connection_id},
        {"$inc": {"contacts_synced": imported}}
    )

    return {
        "sync_id": sync_id,
        "crm_type": crm_type,
        "contacts_found": len(crm_contacts),
        "contacts_imported": imported,
        "contacts_skipped": skipped,
        "mode": "mock" if is_mock else "live",
        "message": f"Synced {imported} contacts from {'HubSpot' if crm_type == 'hubspot' else 'Salesforce'} into your tenant vault",
    }


@router.get("/api/crm-sync/sync-jobs")
async def list_crm_sync_jobs(authorization: str = Header(None)):
    """List CRM sync job history."""
    from server import db
    ctx = _extract_tenant(authorization)
    jobs = await db.crm_sync_jobs.find(
        {"tenant_id": ctx["tenant_id"]}, {"_id": 0}
    ).sort("started_at", -1).to_list(50)
    return {"sync_jobs": jobs, "total": len(jobs)}


async def _fetch_live_crm_contacts(conn: dict, user_id: str = "") -> list:
    """Fetch contacts from live HubSpot or Salesforce API using vault credentials."""
    import httpx
    crm_type = conn.get("crm_type", "hubspot")
    
    # Get credentials from vault
    creds = await _get_crm_credentials(user_id, crm_type)
    access_token = creds.get("access_token", "")
    if not access_token:
        logger.warning(f"No credentials found for {crm_type} live sync")
        return []

    contacts = []

    if crm_type == "hubspot":
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                after = ""
                while True:
                    params = {"limit": 100, "properties": "email,firstname,lastname,phone,company,jobtitle,lifecyclestage,hs_lead_status"}
                    if after:
                        params["after"] = after
                    resp = await client.get(
                        "https://api.hubapi.com/crm/v3/objects/contacts",
                        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                        params=params,
                    )
                    if resp.status_code != 200:
                        logger.error(f"HubSpot API error {resp.status_code}: {resp.text[:200]}")
                        break
                    data = resp.json()
                    for result in data.get("results", []):
                        props = result.get("properties", {})
                        contacts.append({
                            "crm_contact_id": f"hs_{result.get('id', '')}",
                            "email": props.get("email", ""),
                            "first_name": props.get("firstname", ""),
                            "last_name": props.get("lastname", ""),
                            "phone": props.get("phone", ""),
                            "company": props.get("company", ""),
                            "job_title": props.get("jobtitle", ""),
                            "lifecycle_stage": props.get("lifecyclestage", "lead"),
                            "deal_stage": props.get("hs_lead_status", "lead"),
                            "deal_value": 0,
                            "lead_source": "hubspot",
                            "last_activity": result.get("updatedAt", ""),
                            "created_at_crm": result.get("createdAt", ""),
                        })
                    paging = data.get("paging", {}).get("next", {})
                    after = paging.get("after", "")
                    if not after or len(contacts) >= 1000:
                        break
        except Exception as e:
            logger.error(f"HubSpot live fetch error: {e}")

    elif crm_type == "salesforce":
        instance_url = creds.get("instance_url", conn.get("instance_url", ""))
        if not instance_url:
            logger.warning("Salesforce instance URL not configured")
            return []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                query = "SELECT Id,Email,FirstName,LastName,Phone,Title,Account.Name,LeadSource FROM Contact WHERE Email != null LIMIT 1000"
                resp = await client.get(
                    f"{instance_url.rstrip('/')}/services/data/v59.0/query",
                    headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                    params={"q": query},
                )
                if resp.status_code != 200:
                    logger.error(f"Salesforce API error {resp.status_code}: {resp.text[:200]}")
                    return []
                data = resp.json()
                for rec in data.get("records", []):
                    account = rec.get("Account") or {}
                    contacts.append({
                        "crm_contact_id": f"sf_{rec.get('Id', '')}",
                        "email": rec.get("Email", ""),
                        "first_name": rec.get("FirstName", ""),
                        "last_name": rec.get("LastName", ""),
                        "phone": rec.get("Phone", ""),
                        "company": account.get("Name", ""),
                        "job_title": rec.get("Title", ""),
                        "lifecycle_stage": "lead",
                        "deal_stage": "lead",
                        "deal_value": 0,
                        "lead_source": rec.get("LeadSource", "salesforce"),
                        "last_activity": "",
                        "created_at_crm": "",
                    })
        except Exception as e:
            logger.error(f"Salesforce live fetch error: {e}")

    logger.info(f"[CRM-LIVE] Fetched {len(contacts)} contacts from {crm_type}")
    return contacts
