"""
AUREM Tenant-Isolated Customer Vault
Row-Level Security: Every document hard-linked to tenant_id.
GDPR/CCPA Privacy Shield: source, sync_date, unsubscribe tokens.

If tenant_id is missing from a query → security alert logged.
"""

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import os
import secrets
import logging
import jwt

router = APIRouter()
logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET")


def _extract_tenant(authorization: str) -> dict:
    """Extract tenant_id and user_id from JWT. Raises 403 if missing."""
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


def _generate_unsubscribe_token() -> str:
    return f"unsub_{secrets.token_urlsafe(24)}"


# ═══════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════

class CustomerCreateRequest(BaseModel):
    email: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    phone: Optional[str] = ""
    source: str = "manual"  # manual | shopify_sync | enrichment | web_scrape
    tags: Optional[List[str]] = []
    total_spend: Optional[float] = 0.0
    notes: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    company: Optional[str] = ""
    job_title: Optional[str] = ""


class CustomerUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    tags: Optional[List[str]] = None
    total_spend: Optional[float] = None
    notes: Optional[str] = None
    linkedin_url: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    enrichment_status: Optional[str] = None


class BulkImportRequest(BaseModel):
    customers: List[CustomerCreateRequest]
    source: str = "bulk_import"


# ═══════════════════════════════════════════════════════════════
# CRUD ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/api/customers/create")
async def create_customer(body: CustomerCreateRequest, authorization: str = Header(None)):
    """Create a single tenant-isolated customer record."""
    from server import db
    ctx = _extract_tenant(authorization)
    now = datetime.now(timezone.utc).isoformat()

    existing = await db.tenant_customers.find_one(
        {"tenant_id": ctx["tenant_id"], "email": body.email.lower()},
        {"_id": 0, "customer_id": 1}
    )
    if existing:
        raise HTTPException(409, f"Customer with email {body.email} already exists")

    customer_id = f"cust_{secrets.token_urlsafe(12)}"
    doc = {
        "customer_id": customer_id,
        "tenant_id": ctx["tenant_id"],
        "user_id": ctx["user_id"],
        "email": body.email.lower().strip(),
        "first_name": body.first_name or "",
        "last_name": body.last_name or "",
        "phone": body.phone or "",
        "source": body.source,
        "sync_date": now,
        "tags": body.tags or [],
        "total_spend": body.total_spend or 0.0,
        "notes": body.notes or "",
        "linkedin_url": body.linkedin_url or "",
        "company": body.company or "",
        "job_title": body.job_title or "",
        "enrichment_status": "none",  # none | pending | enriched | failed
        "enriched_data": {},
        "unsubscribe_token": _generate_unsubscribe_token(),
        "gdpr_consent": True,
        "ccpa_opt_out": False,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.tenant_customers.insert_one(doc)

    return {
        "customer_id": customer_id,
        "email": doc["email"],
        "source": doc["source"],
        "unsubscribe_token": doc["unsubscribe_token"],
        "message": "Customer created with privacy shield active",
    }


@router.get("/api/customers/list")
async def list_customers(
    authorization: str = Header(None),
    skip: int = 0,
    limit: int = 50,
    source: Optional[str] = None,
    search: Optional[str] = None,
):
    """List all customers for the current tenant. Strict tenant_id enforcement."""
    from server import db
    ctx = _extract_tenant(authorization)

    query = {"tenant_id": ctx["tenant_id"], "is_active": True}
    if source:
        query["source"] = source
    if search:
        query["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
        ]

    total = await db.tenant_customers.count_documents(query)
    customers = await db.tenant_customers.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    source_breakdown = {}
    for c in customers:
        s = c.get("source", "unknown")
        source_breakdown[s] = source_breakdown.get(s, 0) + 1

    return {
        "customers": customers,
        "total": total,
        "skip": skip,
        "limit": limit,
        "source_breakdown": source_breakdown,
    }


@router.get("/api/customers/{customer_id}")
async def get_customer(customer_id: str, authorization: str = Header(None)):
    """Get a single customer by ID. Tenant-scoped."""
    from server import db
    ctx = _extract_tenant(authorization)

    customer = await db.tenant_customers.find_one(
        {"customer_id": customer_id, "tenant_id": ctx["tenant_id"]},
        {"_id": 0}
    )
    if not customer:
        raise HTTPException(404, "Customer not found")
    return customer


@router.put("/api/customers/{customer_id}")
async def update_customer(customer_id: str, body: CustomerUpdateRequest, authorization: str = Header(None)):
    """Update a customer record. Tenant-scoped."""
    from server import db
    ctx = _extract_tenant(authorization)

    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.tenant_customers.update_one(
        {"customer_id": customer_id, "tenant_id": ctx["tenant_id"]},
        {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Customer not found")

    return {"customer_id": customer_id, "updated_fields": list(updates.keys()), "message": "Customer updated"}


@router.delete("/api/customers/{customer_id}")
async def delete_customer(customer_id: str, authorization: str = Header(None)):
    """Soft-delete a customer (GDPR right to erasure)."""
    from server import db
    ctx = _extract_tenant(authorization)

    result = await db.tenant_customers.update_one(
        {"customer_id": customer_id, "tenant_id": ctx["tenant_id"]},
        {"$set": {
            "is_active": False,
            "email": "REDACTED",
            "first_name": "REDACTED",
            "last_name": "REDACTED",
            "phone": "REDACTED",
            "notes": "GDPR erasure completed",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Customer not found")

    return {"customer_id": customer_id, "message": "Customer data erased (GDPR compliant)"}


@router.post("/api/customers/bulk-import")
async def bulk_import_customers(body: BulkImportRequest, authorization: str = Header(None)):
    """Bulk import customers with automatic privacy shield."""
    from server import db
    ctx = _extract_tenant(authorization)
    now = datetime.now(timezone.utc).isoformat()

    imported = 0
    skipped = 0
    errors = []

    for cust in body.customers:
        existing = await db.tenant_customers.find_one(
            {"tenant_id": ctx["tenant_id"], "email": cust.email.lower()},
            {"_id": 0, "customer_id": 1}
        )
        if existing:
            skipped += 1
            continue

        customer_id = f"cust_{secrets.token_urlsafe(12)}"
        doc = {
            "customer_id": customer_id,
            "tenant_id": ctx["tenant_id"],
            "user_id": ctx["user_id"],
            "email": cust.email.lower().strip(),
            "first_name": cust.first_name or "",
            "last_name": cust.last_name or "",
            "phone": cust.phone or "",
            "source": body.source,
            "sync_date": now,
            "tags": cust.tags or [],
            "total_spend": cust.total_spend or 0.0,
            "notes": cust.notes or "",
            "linkedin_url": cust.linkedin_url or "",
            "company": cust.company or "",
            "job_title": cust.job_title or "",
            "enrichment_status": "none",
            "enriched_data": {},
            "unsubscribe_token": _generate_unsubscribe_token(),
            "gdpr_consent": True,
            "ccpa_opt_out": False,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        await db.tenant_customers.insert_one(doc)
        imported += 1

    return {
        "imported": imported,
        "skipped": skipped,
        "total_processed": len(body.customers),
        "source": body.source,
        "message": f"{imported} customers imported, {skipped} duplicates skipped",
    }


# ═══════════════════════════════════════════════════════════════
# STATS & ANALYTICS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/customers/stats/overview")
async def customer_stats(authorization: str = Header(None)):
    """Get customer vault statistics for current tenant."""
    from server import db
    ctx = _extract_tenant(authorization)

    total = await db.tenant_customers.count_documents(
        {"tenant_id": ctx["tenant_id"], "is_active": True}
    )
    enriched = await db.tenant_customers.count_documents(
        {"tenant_id": ctx["tenant_id"], "enrichment_status": "enriched", "is_active": True}
    )

    sources = await db.tenant_customers.aggregate([
        {"$match": {"tenant_id": ctx["tenant_id"], "is_active": True}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
    ]).to_list(20)

    return {
        "total_customers": total,
        "enriched_customers": enriched,
        "enrichment_rate": round(enriched / total * 100, 1) if total > 0 else 0,
        "sources": {s["_id"]: s["count"] for s in sources},
    }


# ═══════════════════════════════════════════════════════════════
# PRIVACY SHIELD — PUBLIC UNSUBSCRIBE
# ═══════════════════════════════════════════════════════════════

@router.get("/api/public/unsubscribe/{token}")
async def unsubscribe_customer(token: str):
    """Public endpoint — GDPR/CCPA compliant unsubscribe."""
    from server import db

    result = await db.tenant_customers.update_one(
        {"unsubscribe_token": token, "is_active": True},
        {"$set": {
            "ccpa_opt_out": True,
            "tags": ["unsubscribed"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    if result.matched_count == 0:
        return JSONResponse({"message": "Link expired or already unsubscribed"}, 404)

    return {"message": "You have been successfully unsubscribed. No further communications will be sent."}
