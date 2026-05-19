"""
AUREM Admin Business ID Management
Admin-only endpoints for managing tenant Business IDs.
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/business-id", tags=["Admin Business ID"])

_db = None
from config import JWT_SECRET  # safe 3-tier resolver (env -> file -> ephemeral)
JWT_ALGORITHM = "HS256"


def set_db(db):
    global _db
    _db = db


def _require_admin(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Admin authorization required")
    try:
        payload = jwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

    role = payload.get("role", "")
    if role not in ("super_admin", "admin"):
        raise HTTPException(403, "Admin access required")
    return payload


@router.get("s")
async def list_all_business_ids(request: Request):
    """List all tenants with business ID data."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "Database not available")

    results = []

    # Check both collections
    for coll_name in ["users", "platform_users"]:
        coll = _db[coll_name]
        cursor = coll.find(
            {"business_id": {"$exists": True, "$ne": ""}},
            {"_id": 0, "password": 0, "password_hash": 0}
        )
        async for doc in cursor:
            bid = doc.get("business_id", "")
            tid = doc.get("tenant_id") or doc.get("id") or doc.get("email", "")

            # Get connected device count
            team_count = await _db.team_connections.count_documents({"business_id": bid})

            # Get last ORA session
            wm = await _db.working_memory.find_one({"tenant_id": tid}, {"_id": 0, "context_loaded_at": 1})

            results.append({
                "email": doc.get("email", ""),
                "business_name": doc.get("company") or doc.get("company_name") or doc.get("business_name") or f"{doc.get('first_name', '')} {doc.get('last_name', '')}".strip(),
                "business_id": bid,
                "business_id_active": doc.get("business_id_active", True),
                "business_id_created": doc.get("business_id_created", ""),
                "plan": "Starter",
                "connected_devices": team_count,
                "last_ora_session": wm.get("context_loaded_at") if wm else None,
                "welcome_sent": doc.get("welcome_sent_at") is not None,
                "welcome_sent_at": doc.get("welcome_sent_at"),
                "tenant_id": tid,
                "collection": coll_name,
            })

    # Deduplicate by email
    seen = set()
    unique = []
    for r in results:
        if r["email"] not in seen:
            seen.add(r["email"])
            unique.append(r)

    return {"tenants": unique, "count": len(unique)}


@router.post("/generate-all")
async def generate_all_missing_ids(request: Request):
    """Generate Business IDs for all tenants that don't have one yet."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "Database not available")

    from routers.business_id_router import ensure_business_id

    generated = 0
    skipped = 0

    for coll_name in ["users", "platform_users"]:
        coll = _db[coll_name]
        cursor = coll.find(
            {"$or": [
                {"business_id": {"$exists": False}},
                {"business_id": ""},
                {"business_id": None}
            ]},
            {"_id": 0}
        )
        async for doc in cursor:
            if doc.get("role") in ("super_admin", "admin") and coll_name == "platform_users":
                skipped += 1
                continue
            try:
                await ensure_business_id(doc)
                generated += 1
            except Exception as e:
                logger.warning(f"[ADMIN-BID] Failed for {doc.get('email')}: {e}")
                skipped += 1

    return {"generated": generated, "skipped": skipped}


@router.post("/resend/{tenant_email}")
async def resend_welcome(tenant_email: str, request: Request):
    """Re-trigger welcome package for a tenant."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "Database not available")

    user = await _db.users.find_one({"email": tenant_email}, {"_id": 0})
    if not user:
        user = await _db.platform_users.find_one({"email": tenant_email}, {"_id": 0})
    if not user:
        raise HTTPException(404, "Tenant not found")

    tid = user.get("tenant_id") or user.get("id") or user.get("email")

    from services.welcome_package import send_welcome_package
    result = await send_welcome_package(tid, user)
    return {"message": "Welcome package resent", "email": tenant_email, "success": bool(result)}


@router.post("/regenerate/{tenant_email}")
async def admin_regenerate_id(tenant_email: str, request: Request):
    """Admin regenerates a tenant's Business ID."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "Database not available")

    from routers.business_id_router import generate_business_id

    user = await _db.users.find_one({"email": tenant_email}, {"_id": 0})
    if not user:
        user = await _db.platform_users.find_one({"email": tenant_email}, {"_id": 0})
    if not user:
        raise HTTPException(404, "Tenant not found")

    old_bid = user.get("business_id", "")
    biz_name = user.get("company") or user.get("company_name") or user.get("business_name") or user.get("first_name", "USER")

    for _ in range(10):
        new_bid = generate_business_id(biz_name)
        if new_bid != old_bid:
            existing_u = await _db.users.find_one({"business_id": new_bid})
            existing_p = await _db.platform_users.find_one({"business_id": new_bid})
            if not existing_u and not existing_p:
                update = {"$set": {
                    "business_id": new_bid,
                    "business_id_created": datetime.now(timezone.utc).isoformat(),
                    "business_id_active": True,
                }}
                await _db.users.update_one({"email": tenant_email}, update)
                await _db.platform_users.update_one({"email": tenant_email}, update)
                if old_bid:
                    await _db.team_connections.delete_many({"business_id": old_bid})

                # Trigger welcome package with new ID
                tid = user.get("tenant_id") or user.get("id") or user.get("email")
                updated_user = await _db.users.find_one({"email": tenant_email}, {"_id": 0})
                if not updated_user:
                    updated_user = await _db.platform_users.find_one({"email": tenant_email}, {"_id": 0})

                from services.welcome_package import send_welcome_package
                await send_welcome_package(tid, updated_user)

                return {"old_id": old_bid, "new_id": new_bid, "welcome_resent": True}

    raise HTTPException(500, "Failed to generate unique Business ID")


@router.get("/qr/{tenant_email}")
async def admin_get_qr(tenant_email: str, request: Request):
    """Get QR code for a specific tenant (admin only)."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "Database not available")

    user = await _db.users.find_one({"email": tenant_email}, {"_id": 0})
    if not user:
        user = await _db.platform_users.find_one({"email": tenant_email}, {"_id": 0})
    if not user:
        raise HTTPException(404, "Tenant not found")

    bid = user.get("business_id")
    if not bid:
        raise HTTPException(400, "Tenant has no Business ID")

    try:
        import qrcode
        import io
        import base64
        base_url = os.environ.get("APP_BASE_URL", "https://aurem.live")
        url = f"{base_url}/ora?id={bid}"
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#C9A84C", back_color="#050507")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {"qr_base64": b64, "url_encoded": url, "business_id": bid}
    except Exception as e:
        raise HTTPException(500, f"QR generation failed: {e}")
