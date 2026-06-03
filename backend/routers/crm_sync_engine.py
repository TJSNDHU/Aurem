"""
AUREM CRM Sync Engine — HubSpot & Salesforce Integration.

Pulls contacts from live HubSpot or Salesforce into the tenant Customer
Vault. NO mock data path — if credentials are missing the endpoint
returns HTTP 503 so misconfiguration is loud.
"""

import logging
import os
import secrets
from datetime import datetime, timezone

import httpx
import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET")
HUBSPOT_API_KEY = os.environ.get("HUBSPOT_API_KEY", "")
SALESFORCE_CLIENT_ID = os.environ.get("SALESFORCE_CLIENT_ID", "")


async def _get_crm_credentials(user_id: str, crm_type: str) -> dict:
    """env var first, then tenant vault."""
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


def _require_crm_credentials(creds: dict, crm_type: str) -> None:
    """Raise 503 if no usable access token is present."""
    if creds and creds.get("access_token"):
        return
    if crm_type == "hubspot":
        raise HTTPException(
            503,
            "CRM sync not configured. Add HUBSPOT_API_KEY to env "
            "or connect via Vault to enable HubSpot integration.",
        )
    raise HTTPException(
        503,
        "CRM sync not configured. Salesforce OAuth credentials missing.",
    )


# ── Connection endpoints ────────────────────────────────────────

class CRMConnectRequest(BaseModel):
    crm_type: str  # hubspot | salesforce
    api_key: Optional[str] = ""
    instance_url: Optional[str] = ""


@router.post("/api/crm-sync/connect")
async def connect_crm(body: CRMConnectRequest,
                        authorization: str = Header(None)):
    """Connect a CRM. Refuses to register a connection without a real
    access token — no mock path."""
    from server import db
    ctx = _extract_tenant(authorization)
    now = datetime.now(timezone.utc).isoformat()

    if body.crm_type not in ("hubspot", "salesforce"):
        raise HTTPException(400, "Supported CRM types: hubspot, salesforce")

    existing = await db.crm_connections.find_one(
        {"tenant_id": ctx["tenant_id"], "crm_type": body.crm_type,
         "status": "connected"},
        {"_id": 0},
    )
    if existing:
        return {"status": "already_connected",
                "crm_type": body.crm_type,
                "connected_at": existing.get("connected_at")}

    # Resolve credentials: explicit body key > env > vault. No mock path.
    if body.api_key:
        creds = {"access_token": body.api_key}
    else:
        creds = await _get_crm_credentials(ctx["user_id"], body.crm_type)
    _require_crm_credentials(creds, body.crm_type)

    connection_id = f"crm_{secrets.token_urlsafe(12)}"
    instance_url = body.instance_url or (
        "https://app.hubspot.com" if body.crm_type == "hubspot"
        else "https://login.salesforce.com"
    )
    await db.crm_connections.insert_one({
        "connection_id":   connection_id,
        "tenant_id":       ctx["tenant_id"],
        "user_id":         ctx["user_id"],
        "crm_type":        body.crm_type,
        "status":          "connected",
        "mode":            "live",
        "instance_url":    instance_url,
        "connected_at":    now,
        "created_at":      now,
        "contacts_synced": 0,
    })

    display = "HubSpot" if body.crm_type == "hubspot" else "Salesforce"
    return {
        "status":        "connected",
        "connection_id": connection_id,
        "crm_type":      body.crm_type,
        "mode":          "live",
        "message":       f"{display} connected. Ready to sync contacts.",
    }


@router.get("/api/crm-sync/connections")
async def list_crm_connections(authorization: str = Header(None)):
    from server import db
    ctx = _extract_tenant(authorization)
    connections = await db.crm_connections.find(
        {"tenant_id": ctx["tenant_id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(20)
    return {"connections": connections, "total": len(connections)}


@router.delete("/api/crm-sync/disconnect/{connection_id}")
async def disconnect_crm(connection_id: str,
                            authorization: str = Header(None)):
    from server import db
    ctx = _extract_tenant(authorization)
    result = await db.crm_connections.update_one(
        {"connection_id": connection_id, "tenant_id": ctx["tenant_id"]},
        {"$set": {
            "status": "disconnected",
            "disconnected_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Connection not found")
    return {"message": "CRM disconnected", "connection_id": connection_id}


# ── Sync contacts ───────────────────────────────────────────────

class CRMSyncRequest(BaseModel):
    connection_id: str


@router.post("/api/crm-sync/sync-contacts")
async def sync_crm_contacts(body: CRMSyncRequest,
                               authorization: str = Header(None)):
    """Pull contacts from the live CRM and persist into tenant vault."""
    from server import db
    ctx = _extract_tenant(authorization)
    now = datetime.now(timezone.utc).isoformat()

    conn = await db.crm_connections.find_one(
        {"connection_id": body.connection_id,
         "tenant_id": ctx["tenant_id"], "status": "connected"},
        {"_id": 0},
    )
    if not conn:
        raise HTTPException(404, "Active CRM connection not found")

    crm_type = conn.get("crm_type", "hubspot")
    sync_id = f"crmsync_{secrets.token_urlsafe(12)}"
    await db.crm_sync_jobs.insert_one({
        "sync_id":       sync_id,
        "connection_id": body.connection_id,
        "tenant_id":     ctx["tenant_id"],
        "user_id":       ctx["user_id"],
        "crm_type":      crm_type,
        "status":        "running",
        "started_at":    now,
    })

    # Guard: live credentials must exist before we hit the wire.
    creds = await _get_crm_credentials(ctx["user_id"], crm_type)
    _require_crm_credentials(creds, crm_type)
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
            {"_id": 0, "customer_id": 1},
        )
        if existing:
            await db.tenant_customers.update_one(
                {"customer_id": existing["customer_id"]},
                {"$set": {
                    "crm_data":   cc,
                    "company":    cc.get("company", ""),
                    "job_title":  cc.get("job_title", ""),
                    "updated_at": now,
                }},
            )
            skipped += 1
            continue

        display = "HubSpot" if crm_type == "hubspot" else "Salesforce"
        await db.tenant_customers.insert_one({
            "customer_id":      f"cust_{secrets.token_urlsafe(12)}",
            "tenant_id":        ctx["tenant_id"],
            "user_id":          ctx["user_id"],
            "email":            email,
            "first_name":       cc.get("first_name", ""),
            "last_name":        cc.get("last_name", ""),
            "phone":            cc.get("phone", ""),
            "source":           f"{crm_type}_sync",
            "sync_date":        now,
            "tags":             [crm_type, cc.get("lifecycle_stage", "lead")],
            "total_spend":      cc.get("deal_value", 0.0),
            "notes":            f"Synced from {display} — {cc.get('deal_stage', 'lead')}",
            "linkedin_url":     cc.get("linkedin_url", ""),
            "company":          cc.get("company", ""),
            "job_title":        cc.get("job_title", ""),
            "enrichment_status": "none",
            "enriched_data":    {},
            "crm_data":         {
                "crm_contact_id":  cc.get("crm_contact_id", ""),
                "deal_stage":      cc.get("deal_stage", ""),
                "deal_value":      cc.get("deal_value", 0),
                "lead_source":     cc.get("lead_source", ""),
                "lifecycle_stage": cc.get("lifecycle_stage", ""),
                "last_activity":   cc.get("last_activity"),
            },
            "unsubscribe_token": f"unsub_{secrets.token_urlsafe(24)}",
            "gdpr_consent":     True,
            "ccpa_opt_out":     False,
            "is_active":        True,
            "created_at":       now,
            "updated_at":       now,
        })
        imported += 1

    await db.crm_sync_jobs.update_one(
        {"sync_id": sync_id},
        {"$set": {
            "status":            "completed",
            "completed_at":      datetime.now(timezone.utc).isoformat(),
            "contacts_found":    len(crm_contacts),
            "contacts_imported": imported,
            "contacts_skipped":  skipped,
        }},
    )

    await db.crm_connections.update_one(
        {"connection_id": body.connection_id},
        {"$inc": {"contacts_synced": imported}},
    )

    return {
        "sync_id":           sync_id,
        "crm_type":          crm_type,
        "contacts_found":    len(crm_contacts),
        "contacts_imported": imported,
        "contacts_skipped":  skipped,
        "mode":              "live",
        "message":           f"Synced {imported} contacts from "
                              f"{'HubSpot' if crm_type == 'hubspot' else 'Salesforce'} "
                              "into your tenant vault",
    }


@router.get("/api/crm-sync/sync-jobs")
async def list_crm_sync_jobs(authorization: str = Header(None)):
    from server import db
    ctx = _extract_tenant(authorization)
    jobs = await db.crm_sync_jobs.find(
        {"tenant_id": ctx["tenant_id"]}, {"_id": 0},
    ).sort("started_at", -1).to_list(50)
    return {"sync_jobs": jobs, "total": len(jobs)}


# ── Live CRM fetchers (unchanged, just preserved here) ──────────

async def _fetch_live_crm_contacts(conn: dict, user_id: str = "") -> list:
    """Fetch contacts from live HubSpot or Salesforce via vault creds."""
    crm_type = conn.get("crm_type", "hubspot")
    creds = await _get_crm_credentials(user_id, crm_type)
    access_token = creds.get("access_token", "")
    if not access_token:
        logger.warning(f"No credentials found for {crm_type} live sync")
        return []

    contacts: list = []

    if crm_type == "hubspot":
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                after = ""
                while True:
                    params = {
                        "limit":      100,
                        "properties": ("email,firstname,lastname,phone,"
                                       "company,jobtitle,lifecyclestage,"
                                       "hs_lead_status"),
                    }
                    if after:
                        params["after"] = after
                    resp = await client.get(
                        "https://api.hubapi.com/crm/v3/objects/contacts",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type":  "application/json",
                        },
                        params=params,
                    )
                    if resp.status_code != 200:
                        logger.error(
                            f"HubSpot API error {resp.status_code}: "
                            f"{resp.text[:200]}"
                        )
                        break
                    data = resp.json()
                    for result in data.get("results", []):
                        props = result.get("properties", {})
                        contacts.append({
                            "crm_contact_id":  f"hs_{result.get('id', '')}",
                            "email":           props.get("email", ""),
                            "first_name":      props.get("firstname", ""),
                            "last_name":       props.get("lastname", ""),
                            "phone":           props.get("phone", ""),
                            "company":         props.get("company", ""),
                            "job_title":       props.get("jobtitle", ""),
                            "lifecycle_stage": props.get("lifecyclestage", "lead"),
                            "deal_stage":      props.get("hs_lead_status", "lead"),
                            "deal_value":      0,
                            "lead_source":     "hubspot",
                            "last_activity":   result.get("updatedAt", ""),
                            "created_at_crm":  result.get("createdAt", ""),
                        })
                    paging = data.get("paging", {}).get("next", {})
                    after = paging.get("after", "")
                    if not after or len(contacts) >= 1000:
                        break
        except Exception as e:
            logger.error(f"HubSpot live fetch error: {e}")

    elif crm_type == "salesforce":
        instance_url = creds.get("instance_url",
                                    conn.get("instance_url", ""))
        if not instance_url:
            logger.warning("Salesforce instance URL not configured")
            return []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                query = ("SELECT Id,Email,FirstName,LastName,Phone,Title,"
                          "Account.Name,LeadSource FROM Contact "
                          "WHERE Email != null LIMIT 1000")
                resp = await client.get(
                    f"{instance_url.rstrip('/')}/services/data/v59.0/query",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type":  "application/json",
                    },
                    params={"q": query},
                )
                if resp.status_code != 200:
                    logger.error(
                        f"Salesforce API error {resp.status_code}: "
                        f"{resp.text[:200]}"
                    )
                    return []
                data = resp.json()
                for rec in data.get("records", []):
                    account = rec.get("Account") or {}
                    contacts.append({
                        "crm_contact_id":  f"sf_{rec.get('Id', '')}",
                        "email":           rec.get("Email", ""),
                        "first_name":      rec.get("FirstName", ""),
                        "last_name":       rec.get("LastName", ""),
                        "phone":           rec.get("Phone", ""),
                        "company":         account.get("Name", ""),
                        "job_title":       rec.get("Title", ""),
                        "lifecycle_stage": "lead",
                        "deal_stage":      "lead",
                        "deal_value":      0,
                        "lead_source":     rec.get("LeadSource", "salesforce"),
                        "last_activity":   "",
                        "created_at_crm":  "",
                    })
        except Exception as e:
            logger.error(f"Salesforce live fetch error: {e}")

    logger.info(f"[CRM-LIVE] Fetched {len(contacts)} contacts from {crm_type}")
    return contacts
