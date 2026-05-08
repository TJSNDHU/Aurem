"""
AUREM Admin Customer Management Router
Unified customer records in tenant_customers collection.
Includes migration, CRUD, performance data, audit logging.
"""
import logging
import os
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/customers", tags=["Admin Customers"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            raise HTTPException(500, "JWT not configured")
        payload = jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except Exception:
        raise HTTPException(401, "Invalid token")


def _generate_business_id(name: str) -> str:
    prefix = name[:4].upper().replace(" ", "")
    if len(prefix) < 4:
        prefix = prefix.ljust(4, "X")
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"{prefix}-{suffix}"


PLAN_PRICES = {"starter": 97, "growth": 297, "enterprise": 997}
PLAN_LIMITS = {
    "starter": {"actions_limit": 500, "pipeline_runs_limit": 3},
    "growth": {"actions_limit": 2000, "pipeline_runs_limit": 10},
    "enterprise": {"actions_limit": 10000, "pipeline_runs_limit": 50},
}


@router.post("/migrate", tags=["Migration"])
async def run_migration(request: Request):
    """One-time migration: business_profiles -> tenant_customers with enhanced schema."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "Database not initialized")

    profiles = await _db.business_profiles.find({}, {"_id": 0}).to_list(100)
    if not profiles:
        return {"migrated": 0, "message": "No business profiles found"}

    migrated = 0
    for p in profiles:
        tenant_id = p.get("tenant_id") or p.get("profile_id")
        existing = await _db.tenant_customers.find_one({"tenant_id": tenant_id})
        if existing:
            continue

        plan = p.get("plan", "starter")
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])
        onboarded = p.get("onboarded_at") or p.get("created_at") or datetime.now(timezone.utc).isoformat()

        # Pull latest scan score
        latest_scan = await _db.client_scan_results.find_one(
            {"tenant_id": tenant_id}, sort=[("scanned_at", -1)]
        )
        total_scans = await _db.client_scan_results.count_documents({"tenant_id": tenant_id})
        system_scans = await _db.system_scans.count_documents({"website_url": {"$regex": p.get("website_url", "NONE")}})
        total_scans = max(total_scans, system_scans)

        website_score = 0
        last_scan_date = None
        if latest_scan:
            website_score = latest_scan.get("overall_score", 0)
            last_scan_date = latest_scan.get("scanned_at")
        else:
            sys_scan = await _db.system_scans.find_one(
                {"website_url": {"$regex": p.get("website_url", "NONE")}},
                sort=[("scan_date", -1)]
            )
            if sys_scan:
                website_score = sys_scan.get("overall_score", 0)
                last_scan_date = sys_scan.get("scan_date")

        # Count repairs
        repairs = await _db.repair_fixes.count_documents({"tenant_id": tenant_id})
        auto_repairs = await _db.system_auto_repairs.count_documents({})

        location = p.get("location", "")
        city, province, country = "", "", ""
        if location:
            parts = [x.strip() for x in location.split(",")]
            city = parts[0] if len(parts) > 0 else ""
            province = parts[1] if len(parts) > 1 else ""
            country = parts[2] if len(parts) > 2 else ""

        business_id = _generate_business_id(p.get("business_name", "CUST"))

        doc = {
            "tenant_id": tenant_id,
            "profile_id": p.get("profile_id"),
            "business_id": business_id,
            "full_name": p.get("owner_name", ""),
            "company_name": p.get("business_name", ""),
            "company_address": {"city": city, "province": province, "country": country},
            "website_url": p.get("website_url", ""),
            "email": p.get("email", ""),
            "phone": "",
            "industry": p.get("industry", ""),
            "category": p.get("category", ""),
            "sub_category": p.get("sub_category", ""),
            "plan": plan,
            "plan_price_cad": PLAN_PRICES.get(plan, 97),
            "plan_started": onboarded,
            "plan_ends": (datetime.fromisoformat(onboarded.replace("Z", "+00:00")) + timedelta(days=30)).isoformat() if onboarded else None,
            "plan_status": p.get("status", "active"),
            "billing_cycle": "monthly",
            "usage": {
                "actions_limit": limits["actions_limit"],
                "actions_used": 0,
                "actions_remaining": limits["actions_limit"],
                "pipeline_runs_today": 0,
                "pipeline_runs_limit": limits["pipeline_runs_limit"],
                "last_reset_date": datetime.now(timezone.utc).isoformat(),
                "reset_cycle": "daily",
            },
            "performance": {
                "website_score": website_score,
                "last_scan_date": last_scan_date,
                "total_scans": total_scans,
                "leads_found": 0,
                "leads_converted": 0,
                "invoices_sent": 0,
                "invoices_paid": 0,
                "revenue_tracked": 0,
                "automations_run": 0,
                "issues_fixed": repairs,
            },
            "joined_date": onboarded,
            "last_active": datetime.now(timezone.utc).isoformat(),
            "created_by": "migration",
            "notes": "",
            "is_active": True,
            "is_self_client": p.get("is_self_client", False),
        }

        await _db.tenant_customers.insert_one(doc)
        migrated += 1

    return {"migrated": migrated, "total_profiles": len(profiles)}


@router.get("")
async def list_customers(request: Request, search: str = "", page: int = 1, limit: int = 50):
    """List all tenant customers with pagination and search."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    query = {}
    if search:
        query["$or"] = [
            {"company_name": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]

    total = await _db.tenant_customers.count_documents(query)
    skip = (page - 1) * limit
    docs = await _db.tenant_customers.find(query, {"_id": 0}).sort("joined_date", -1).skip(skip).limit(limit).to_list(limit)

    return {"customers": docs, "total": total, "page": page, "limit": limit}


@router.get("/stats")
async def customer_stats(request: Request):
    """Overview stats for the customer dashboard."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    total = await _db.tenant_customers.count_documents({})
    active = await _db.tenant_customers.count_documents({"is_active": True})
    starter = await _db.tenant_customers.count_documents({"plan": "starter"})
    growth = await _db.tenant_customers.count_documents({"plan": "growth"})
    enterprise = await _db.tenant_customers.count_documents({"plan": "enterprise"})

    return {
        "total": total, "active": active,
        "by_plan": {"starter": starter, "growth": growth, "enterprise": enterprise}
    }


@router.get("/{tenant_id}")
async def get_customer(tenant_id: str, request: Request):
    """Full customer profile with latest scan score."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    doc = await _db.tenant_customers.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Customer not found")
    return doc


@router.get("/{tenant_id}/performance")
async def get_performance(tenant_id: str, request: Request):
    """Scan history grouped by date for recharts."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    customer = await _db.tenant_customers.find_one({"tenant_id": tenant_id}, {"_id": 0, "website_url": 1, "profile_id": 1})
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Pull from client_scan_results
    scans = await _db.client_scan_results.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("scanned_at", 1).to_list(500)

    # Also pull system_scans by website URL
    website = customer.get("website_url", "")
    if website and not scans:
        sys_scans = await _db.system_scans.find(
            {"website_url": {"$regex": website.rstrip("/")}}, {"_id": 0}
        ).sort("scan_date", 1).to_list(500)
        for s in sys_scans:
            scans.append({
                "scanned_at": s.get("scan_date"),
                "overall_score": s.get("overall_score", 0),
                "scores": {
                    "performance": s.get("performance", {}).get("score", 0),
                    "seo": s.get("seo", {}).get("score", 0),
                    "security": s.get("security", {}).get("score", 0),
                    "accessibility": s.get("accessibility", {}).get("score", 0),
                },
                "issues_count": s.get("issues_found", 0),
                "critical_count": s.get("critical_issues", 0),
            })

    chart_data = []
    for s in scans:
        dt = s.get("scanned_at", "")
        if isinstance(dt, str):
            date_str = dt[:10]
        else:
            date_str = dt.isoformat()[:10] if dt else ""
        scores = s.get("scores", {})
        chart_data.append({
            "date": date_str,
            "overall": s.get("overall_score", 0),
            "performance": scores.get("performance", 0),
            "seo": scores.get("seo", 0),
            "security": scores.get("security", 0),
            "accessibility": scores.get("accessibility", 0),
            "issues": s.get("issues_count", 0),
            "critical": s.get("critical_count", 0),
        })

    return {"scans": chart_data, "total": len(chart_data)}


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    company_address: Optional[dict] = None
    website_url: Optional[str] = None
    plan: Optional[str] = None
    plan_price_cad: Optional[int] = None
    plan_started: Optional[str] = None
    plan_ends: Optional[str] = None
    plan_status: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.put("/{tenant_id}")
async def update_customer(tenant_id: str, data: CustomerUpdate, request: Request):
    """Update customer fields + log changes to audit."""
    admin = _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    existing = await _db.tenant_customers.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Customer not found")

    updates = {}
    audit_entries = []
    for field, value in data.dict(exclude_unset=True).items():
        if value is not None and existing.get(field) != value:
            audit_entries.append({
                "tenant_id": tenant_id,
                "changed_by": admin.get("email", "admin"),
                "changed_at": datetime.now(timezone.utc).isoformat(),
                "field": field,
                "old_value": str(existing.get(field, "")),
                "new_value": str(value),
            })
            updates[field] = value

    if not updates:
        return {"success": True, "message": "No changes"}

    # If plan changed, update limits
    if "plan" in updates:
        new_plan = updates["plan"]
        limits = PLAN_LIMITS.get(new_plan, PLAN_LIMITS["starter"])
        updates["plan_price_cad"] = PLAN_PRICES.get(new_plan, 97)
        updates["usage.actions_limit"] = limits["actions_limit"]
        updates["usage.actions_remaining"] = limits["actions_limit"]
        updates["usage.pipeline_runs_limit"] = limits["pipeline_runs_limit"]

    updates["last_active"] = datetime.now(timezone.utc).isoformat()
    await _db.tenant_customers.update_one({"tenant_id": tenant_id}, {"$set": updates})

    if audit_entries:
        await _db.customer_audit_log.insert_many(audit_entries)

    return {"success": True, "changes": len(audit_entries)}


@router.get("/{tenant_id}/audit")
async def get_audit_log(tenant_id: str, request: Request):
    """Get change history for a customer."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    logs = await _db.customer_audit_log.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("changed_at", -1).limit(50).to_list(50)

    return {"logs": logs}


class CustomerCreate(BaseModel):
    company_name: str
    full_name: str = ""
    email: str = ""
    phone: str = ""
    website_url: str = ""
    industry: str = ""
    plan: str = "starter"
    city: str = ""
    province: str = ""
    country: str = "Canada"
    notes: str = ""


@router.post("")
async def create_customer(data: CustomerCreate, request: Request):
    """Create a new customer in tenant_customers."""
    admin = _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    tenant_id = data.company_name.lower().replace(" ", "-")[:20] + "-" + secrets.token_hex(4)
    business_id = _generate_business_id(data.company_name)
    plan = data.plan or "starter"
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "tenant_id": tenant_id,
        "profile_id": tenant_id,
        "business_id": business_id,
        "full_name": data.full_name,
        "company_name": data.company_name,
        "company_address": {"city": data.city, "province": data.province, "country": data.country},
        "website_url": data.website_url,
        "email": data.email,
        "phone": data.phone,
        "industry": data.industry,
        "category": "",
        "sub_category": "",
        "plan": plan,
        "plan_price_cad": PLAN_PRICES.get(plan, 97),
        "plan_started": now,
        "plan_ends": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "plan_status": "active",
        "billing_cycle": "monthly",
        "usage": {
            "actions_limit": limits["actions_limit"],
            "actions_used": 0,
            "actions_remaining": limits["actions_limit"],
            "pipeline_runs_today": 0,
            "pipeline_runs_limit": limits["pipeline_runs_limit"],
            "last_reset_date": now,
            "reset_cycle": "daily",
        },
        "performance": {
            "website_score": 0,
            "last_scan_date": None,
            "total_scans": 0,
            "leads_found": 0,
            "leads_converted": 0,
            "invoices_sent": 0,
            "invoices_paid": 0,
            "revenue_tracked": 0,
            "automations_run": 0,
            "issues_fixed": 0,
        },
        "joined_date": now,
        "last_active": now,
        "created_by": admin.get("email", "admin"),
        "notes": data.notes,
        "is_active": True,
        "is_self_client": False,
    }

    await _db.tenant_customers.insert_one(doc)

    # Audit
    await _db.customer_audit_log.insert_one({
        "tenant_id": tenant_id,
        "changed_by": admin.get("email", "admin"),
        "changed_at": now,
        "field": "created",
        "old_value": "",
        "new_value": data.company_name,
    })

    return {"success": True, "tenant_id": tenant_id, "business_id": business_id}


@router.post("/reset-daily-usage")
async def reset_daily_usage(request: Request):
    """Manual trigger for daily usage reset (also called by scheduler)."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    result = await _db.tenant_customers.update_many(
        {},
        {"$set": {
            "usage.actions_used": 0,
            "usage.pipeline_runs_today": 0,
            "usage.actions_remaining": 500,
            "usage.last_reset_date": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"success": True, "reset_count": result.modified_count}


# ═══════════════════════════════════════════════════════════════
# HEALTH SCORE ENGINE
# ═══════════════════════════════════════════════════════════════

@router.post("/{tenant_id}/recalculate-health")
async def recalculate_health(tenant_id: str, request: Request):
    """
    Recalculate health score for a specific tenant.
    Runs 5 weighted signal checks against live MongoDB data,
    writes result to tenant_customers.health_score, and logs to audit trail.
    """
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    from services.health_score_engine import calculate_health_score
    result = await calculate_health_score(_db, tenant_id)

    if "error" in result:
        raise HTTPException(404, result["error"])

    return result


@router.post("/recalculate-health-all")
async def recalculate_all_health(request: Request):
    """Recalculate health scores for ALL active tenants."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    from services.health_score_engine import recalculate_all
    result = await recalculate_all(_db)
    return result


@router.get("/{tenant_id}/health-breakdown")
async def get_health_breakdown(tenant_id: str, request: Request):
    """Get the stored health score breakdown for a tenant."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    doc = await _db.tenant_customers.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "health_score": 1, "health_breakdown": 1, "health_calculated_at": 1}
    )
    if not doc:
        raise HTTPException(404, "Customer not found")

    return {
        "tenant_id": tenant_id,
        "health_score": doc.get("health_score"),
        "breakdown": doc.get("health_breakdown"),
        "calculated_at": doc.get("health_calculated_at"),
    }
