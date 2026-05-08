"""
Service Catalog Router — AUREM Hybrid Storefront (Option C)
============================================================
Endpoints:
  ADMIN (requires super_admin JWT):
    GET    /api/admin/catalog                    → list all services + bundle rules
    PATCH  /api/admin/catalog/{service_id}       → edit price/cost/status/limits
    POST   /api/admin/catalog                    → add new service
    DELETE /api/admin/catalog/{service_id}       → remove service
    GET    /api/admin/customers/{bin}/services   → popup data for customer list

  CUSTOMER (requires platform JWT):
    GET    /api/catalog/services                 → public-facing catalog
    GET    /api/customer/subscriptions           → my active add-ons
    POST   /api/customer/subscriptions/subscribe → create Stripe checkout for add-on
    POST   /api/customer/subscriptions/cancel    → cancel specific add-on
    GET    /api/customer/bundle-preview          → bundle discount calc (what-if)
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, List

from models.service_catalog_models import (
    ServiceCatalogItem, ServiceUpdateRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Service Catalog"])

# Stripe automatic_tax requires a configured "head office address" on the
# Stripe org. Production was failing with:
#   "You must have a valid head office address to enable automatic tax
#    calculation in test mode."
# Make this opt-in via env flag (default OFF) so checkout works everywhere
# out of the box. Flip STRIPE_AUTOMATIC_TAX=true once origin address is
# configured in the relevant Stripe dashboard (live AND test, separately).
# iter 280.8
def _automatic_tax_enabled() -> bool:
    return os.environ.get("STRIPE_AUTOMATIC_TAX", "").strip().lower() in ("1", "true", "yes", "on")

_db = None


def set_db(database):
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════
# Auth helpers — reuse existing patterns
# ═══════════════════════════════════════════════════════════════

def _decode_jwt(request: Request) -> dict:
    import jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = auth[7:]
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT_SECRET not configured")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")


async def _verify_super_admin(request: Request) -> dict:
    user = _decode_jwt(request)
    # Check users collection for admin role
    email = (user.get("email") or "").lower()
    if not email:
        raise HTTPException(401, "token missing email")
    if _db is None:
        raise HTTPException(503, "service not ready")
    admin = await _db.users.find_one(
        {"email": email, "$or": [{"role": "super_admin"}, {"is_admin": True}]},
        {"_id": 0, "email": 1, "role": 1}
    )
    if not admin:
        raise HTTPException(403, "super admin required")
    return admin


async def _verify_platform_user(request: Request) -> dict:
    user = _decode_jwt(request)
    email = (user.get("email") or "").lower()
    if not email:
        raise HTTPException(401, "token missing email")
    if _db is None:
        raise HTTPException(503, "service not ready")
    doc = await _db.platform_users.find_one({"email": email}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "platform user not found")
    doc["bin"] = doc.get("bin") or doc.get("business_id") or doc.get("tenant_id")
    return doc


# ═══════════════════════════════════════════════════════════════
# Bundle calculator — FULLY AUTOMATIC discount engine
# ═══════════════════════════════════════════════════════════════

async def _apply_bundle_discount(service_ids: List[str], base_total: float) -> dict:
    """
    Given a list of active service_ids + their base total,
    returns {discount_pct, discount_amount, final_total, rule_label}.
    """
    if _db is None:
        return {"discount_pct": 0, "discount_amount": 0, "final_total": base_total, "rule_label": None}
    n = len(service_ids)
    # Find best applicable rule
    rules = await _db.bundle_rules.find({}, {"_id": 0}).sort("min_services", -1).to_list(length=20)
    best = None
    for r in rules:
        if n >= r["min_services"]:
            best = r
            break
    if not best:
        return {"discount_pct": 0, "discount_amount": 0, "final_total": round(base_total, 2), "rule_label": None}
    disc = round(base_total * best["discount_pct"] / 100, 2)
    return {
        "discount_pct": best["discount_pct"],
        "discount_amount": disc,
        "final_total": round(base_total - disc, 2),
        "rule_label": best["label"],
    }


# ═══════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/admin/catalog")
async def admin_list_catalog(admin: dict = Depends(_verify_super_admin)):
    """List all services grouped by cluster, with bundle rules and live MRR per service."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    services = await _db.service_catalog.find({}, {"_id": 0}).sort([("cluster", 1), ("cluster_order", 1)]).to_list(length=100)
    rules = await _db.bundle_rules.find({}, {"_id": 0}).sort("min_services", 1).to_list(length=20)
    primitives = await _db.primitives.find({}, {"_id": 0}).to_list(length=20)

    # Attach live subscriber count + MRR per service
    for svc in services:
        sid = svc["service_id"]
        sub_count = await _db.customer_subscriptions.count_documents({"service_id": sid, "status": "active"})
        svc["active_subscribers"] = sub_count
        svc["monthly_revenue"] = round(sub_count * svc.get("price_monthly", 0), 2)

    # Group by cluster for easy admin UI rendering
    clusters = {}
    for svc in services:
        c = svc.get("cluster", "other")
        clusters.setdefault(c, []).append(svc)

    return {
        "clusters": clusters,
        "services": services,
        "bundle_rules": rules,
        "primitives": primitives,
        "total_services": len(services),
        "total_active_subs": sum(s.get("active_subscribers", 0) for s in services),
        "total_mrr": round(sum(s.get("monthly_revenue", 0) for s in services), 2),
    }


@router.patch("/api/admin/catalog/{service_id}")
async def admin_update_service(service_id: str, body: ServiceUpdateRequest, admin: dict = Depends(_verify_super_admin)):
    """Update service price/cost/status/limits. Auto-recomputes margin."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(400, "no fields to update")

    # Recompute margin if price or cost changed
    current = await _db.service_catalog.find_one({"service_id": service_id}, {"_id": 0})
    if not current:
        raise HTTPException(404, "service not found")

    new_price = updates.get("price_monthly", current.get("price_monthly", 0))
    new_cost = updates.get("cost_monthly", current.get("cost_monthly", 0))
    if new_price > 0:
        updates["margin_pct"] = round(((new_price - new_cost) / new_price) * 100, 1)

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await _db.service_catalog.update_one({"service_id": service_id}, {"$set": updates})

    # Audit log
    await _db.catalog_audit_log.insert_one({
        "service_id": service_id,
        "changed_by": admin.get("email"),
        "changed_at": updates["updated_at"],
        "changes": updates,
    })

    # Broadcast change notification (customers will pick up via polling)
    await _db.catalog_events.insert_one({
        "type": "service_updated",
        "service_id": service_id,
        "at": updates["updated_at"],
    })

    updated = await _db.service_catalog.find_one({"service_id": service_id}, {"_id": 0})
    return {"ok": True, "service": updated}


@router.post("/api/admin/catalog")
async def admin_add_service(svc: ServiceCatalogItem, admin: dict = Depends(_verify_super_admin)):
    """Add a new custom service to the catalog. Auto-creates Stripe Product + Price."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    existing = await _db.service_catalog.find_one({"service_id": svc.service_id})
    if existing:
        raise HTTPException(409, "service_id already exists")

    doc = svc.dict()
    now = datetime.now(timezone.utc).isoformat()
    doc["created_at"] = now
    doc["updated_at"] = now
    if doc["price_monthly"] > 0:
        doc["margin_pct"] = round(((doc["price_monthly"] - doc["cost_monthly"]) / doc["price_monthly"]) * 100, 1)

    # Auto-create Stripe product + price (LIVE mode)
    try:
        import stripe as stripe_lib
        stripe_lib.api_key = os.environ.get("STRIPE_SECRET_KEY")
        if stripe_lib.api_key and stripe_lib.api_key.startswith("sk_"):
            product = stripe_lib.Product.create(
                name=doc["name"],
                description=doc.get("description", ""),
                metadata={"service_id": doc["service_id"], "cluster": doc.get("cluster", "other")},
            )
            price = stripe_lib.Price.create(
                product=product.id,
                unit_amount=int(doc["price_monthly"] * 100),
                currency=doc.get("currency", "cad"),
                recurring={"interval": "month"} if doc.get("billing_type") == "recurring" else None,
                tax_behavior="inclusive",
            )
            doc["stripe_product_id"] = product.id
            doc["stripe_price_id"] = price.id
            logger.info(f"[catalog] Stripe product+price created for {doc['service_id']}: {price.id}")
    except Exception as e:
        logger.warning(f"[catalog] Stripe auto-create failed (non-blocking): {e}")

    await _db.service_catalog.insert_one(doc)
    await _db.catalog_audit_log.insert_one({
        "service_id": doc["service_id"],
        "changed_by": admin.get("email"),
        "changed_at": now,
        "changes": {"action": "created"},
    })
    await _db.catalog_events.insert_one({"type": "service_added", "service_id": doc["service_id"], "at": now})
    doc.pop("_id", None)
    return {"ok": True, "service": doc}


@router.delete("/api/admin/catalog/{service_id}")
async def admin_delete_service(service_id: str, admin: dict = Depends(_verify_super_admin)):
    """Remove a service (disable by default to preserve subscription history)."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    now = datetime.now(timezone.utc).isoformat()
    await _db.service_catalog.update_one(
        {"service_id": service_id},
        {"$set": {"status": "disabled", "updated_at": now}}
    )
    await _db.catalog_audit_log.insert_one({
        "service_id": service_id,
        "changed_by": admin.get("email"),
        "changed_at": now,
        "changes": {"action": "disabled"},
    })
    await _db.catalog_events.insert_one({"type": "service_removed", "service_id": service_id, "at": now})
    return {"ok": True, "status": "disabled"}


@router.post("/api/admin/customers/{bin_id}/services/{service_id}/cancel")
async def admin_cancel_customer_service(bin_id: str, service_id: str, admin: dict = Depends(_verify_super_admin)):
    """Admin override: cancel a specific customer's add-on subscription."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    sub = await _db.customer_subscriptions.find_one({
        "$or": [{"tenant_bin": bin_id}, {"email": bin_id}],
        "service_id": service_id,
        "status": "active",
    })
    if not sub:
        raise HTTPException(404, "active subscription not found for this customer+service")

    # Cancel on Stripe
    stripe_sub_id = sub.get("stripe_subscription_id")
    if stripe_sub_id:
        try:
            import stripe as stripe_lib
            stripe_lib.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            stripe_lib.Subscription.delete(stripe_sub_id)
        except Exception as e:
            logger.warning(f"[admin-cancel] stripe cancel failed (non-blocking): {e}")

    now = datetime.now(timezone.utc).isoformat()
    await _db.customer_subscriptions.update_one(
        {"sub_id": sub["sub_id"]},
        {"$set": {"status": "cancelled", "cancelled_at": now, "cancelled_by": admin.get("email", "admin")}}
    )
    await _db.catalog_events.insert_one({
        "type": "subscription_cancelled_by_admin",
        "email": sub.get("email", ""),
        "service_id": service_id,
        "by": admin.get("email", "admin"),
        "at": now,
    })
    return {"ok": True, "cancelled_at": now}


@router.get("/api/admin/customers/{bin_id}/services")
async def admin_customer_services_popup(bin_id: str, admin: dict = Depends(_verify_super_admin)):
    """
    Popup-window data for admin's customer list.
    Returns: trial status, active services, bundle discount, MRR, usage snapshot.
    Auto-refreshes on frontend via polling every 5s.
    """
    if _db is None:
        raise HTTPException(503, "db not ready")

    # Try platform_users first, fall back to tenant_customers
    customer = None
    by_bin = await _db.platform_users.find_one(
        {"$or": [{"bin": bin_id}, {"business_id": bin_id}, {"tenant_id": bin_id}]},
        {"_id": 0, "password_hash": 0}
    )
    if by_bin:
        customer = by_bin
        customer["_source"] = "platform_users"
    else:
        tc = await _db.tenant_customers.find_one(
            {"$or": [{"tenant_id": bin_id}, {"business_id": bin_id}]},
            {"_id": 0}
        )
        if tc:
            customer = tc
            customer["_source"] = "tenant_customers"

    if not customer:
        raise HTTPException(404, "customer not found")

    email = customer.get("email", "")

    # Active subscriptions
    subs = await _db.customer_subscriptions.find(
        {"$or": [{"tenant_bin": bin_id}, {"email": email}], "status": "active"},
        {"_id": 0}
    ).to_list(length=50)

    # Enrich with full service details
    service_ids = [s["service_id"] for s in subs]
    services_map = {}
    if service_ids:
        async for svc in _db.service_catalog.find({"service_id": {"$in": service_ids}}, {"_id": 0}):
            services_map[svc["service_id"]] = svc

    for sub in subs:
        sub["service_detail"] = services_map.get(sub["service_id"], {})

    # Bundle discount calculation
    base_total = sum(s.get("price_monthly", 0) for s in subs)
    bundle = await _apply_bundle_discount(service_ids, base_total)

    # Trial session
    trial = await _db.trial_sessions.find_one(
        {"$or": [{"tenant_bin": bin_id}, {"email": email}]},
        {"_id": 0}
    )

    return {
        "customer": {
            "bin": customer.get("bin") or customer.get("business_id") or customer.get("tenant_id"),
            "email": email,
            "full_name": customer.get("full_name") or customer.get("contact_person", ""),
            "company_name": customer.get("business_name") or customer.get("company_name", ""),
            "plan": customer.get("plan", "free"),
            "source": customer.pop("_source", None),
        },
        "trial": trial,
        "subscriptions": subs,
        "subscription_count": len(subs),
        "base_total": round(base_total, 2),
        "bundle": bundle,
        "final_mrr": bundle["final_total"],
    }


# ═══════════════════════════════════════════════════════════════
# CUSTOMER ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/catalog/services")
async def list_public_catalog():
    """Public catalog (no auth) — for marketing/pricing pages."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    services = await _db.service_catalog.find(
        {"status": "live"},
        {"_id": 0, "cost_monthly": 0, "margin_pct": 0}
    ).sort([("cluster", 1), ("cluster_order", 1)]).to_list(length=100)
    rules = await _db.bundle_rules.find({}, {"_id": 0}).sort("min_services", 1).to_list(length=20)
    return {"services": services, "bundle_rules": rules}


@router.get("/api/customer/subscriptions")
async def customer_my_subscriptions(user: dict = Depends(_verify_platform_user)):
    """My active add-ons + bundle status."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    bin_id = user.get("bin") or ""
    email = user.get("email", "")

    subs = await _db.customer_subscriptions.find(
        {"$or": [{"tenant_bin": bin_id}, {"email": email}], "status": "active"},
        {"_id": 0}
    ).to_list(length=50)

    service_ids = [s["service_id"] for s in subs]
    services_map = {}
    if service_ids:
        async for svc in _db.service_catalog.find({"service_id": {"$in": service_ids}}, {"_id": 0}):
            services_map[svc["service_id"]] = svc

    for sub in subs:
        sub["service_detail"] = services_map.get(sub["service_id"], {})

    base_total = sum(s.get("price_monthly", 0) for s in subs)
    bundle = await _apply_bundle_discount(service_ids, base_total)

    # Trial status
    trial = await _db.trial_sessions.find_one(
        {"$or": [{"tenant_bin": bin_id}, {"email": email}]},
        {"_id": 0}
    )

    return {
        "subscriptions": subs,
        "active_count": len(subs),
        "base_total": round(base_total, 2),
        "bundle": bundle,
        "trial": trial,
    }


class BundlePreviewRequest(BaseModel):
    service_ids: List[str]


@router.post("/api/customer/bundle-preview")
async def bundle_preview(body: BundlePreviewRequest, user: dict = Depends(_verify_platform_user)):
    """What-if calculator — customer selects 5 services, sees preview discount."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    services = await _db.service_catalog.find(
        {"service_id": {"$in": body.service_ids}, "status": "live"},
        {"_id": 0}
    ).to_list(length=50)
    base_total = sum(s.get("price_monthly", 0) for s in services)
    bundle = await _apply_bundle_discount([s["service_id"] for s in services], base_total)
    return {
        "services": services,
        "base_total": round(base_total, 2),
        "bundle": bundle,
    }


class SubscribeRequest(BaseModel):
    service_id: str
    origin_url: Optional[str] = None


@router.post("/api/customer/subscriptions/subscribe")
async def customer_subscribe(body: SubscribeRequest, user: dict = Depends(_verify_platform_user)):
    """Creates Stripe checkout session for a specific add-on. LIVE mode."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    svc = await _db.service_catalog.find_one({"service_id": body.service_id, "status": "live"}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "service not available")

    # Already subscribed?
    existing = await _db.customer_subscriptions.find_one({
        "email": user.get("email", ""),
        "service_id": body.service_id,
        "status": "active",
    })
    if existing:
        raise HTTPException(409, "already subscribed to this service")

    api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not api_key:
        raise HTTPException(500, "Stripe not configured")

    # iter 280.12 — per-mode price caching. Previously `stripe_price_id`
    # was a single field, so prices minted in TEST mode were reused when
    # the secret key flipped to LIVE → Stripe rejected with
    # "No such price" because the price ID belonged to the test account.
    # We now cache prices per-mode and lazily mint a fresh one whenever
    # the cache for the current mode is empty.
    _mode = "live" if api_key.startswith("sk_live_") else (
        "test" if api_key.startswith("sk_test_") else "unknown"
    )
    price_field = f"stripe_price_id_{_mode}"
    product_field = f"stripe_product_id_{_mode}"

    # Backward-compat: if no per-mode field exists yet, fall back to the
    # legacy single field — but ONLY if it's verifiable. We don't trust
    # it blindly, we let Stripe reject it (handled in InvalidRequestError
    # below) which then forces a re-mint.
    price_id = svc.get(price_field) or (
        svc.get("stripe_price_id") if _mode != "unknown" and not svc.get(f"stripe_price_id_{('live' if _mode == 'test' else 'test')}") else None
    )
    try:
        import stripe as stripe_lib
        stripe_lib.api_key = api_key

        async def _mint_fresh_price():
            """Create a brand-new product + price for the current mode and
            cache them under per-mode fields. Returns the new price id."""
            new_product = stripe_lib.Product.create(
                name=svc["name"],
                description=svc.get("description", ""),
                metadata={"service_id": svc["service_id"], "mode": _mode},
            )
            new_price = stripe_lib.Price.create(
                product=new_product.id,
                unit_amount=int(svc["price_monthly"] * 100),
                currency=svc.get("currency", "cad"),
                recurring={"interval": "month"} if svc.get("billing_type") == "recurring" else None,
                tax_behavior="inclusive",
            )
            await _db.service_catalog.update_one(
                {"service_id": body.service_id},
                {"$set": {
                    product_field: new_product.id,
                    price_field: new_price.id,
                    # Keep the legacy single field in sync with the
                    # current-mode value so older code paths still work.
                    "stripe_product_id": new_product.id,
                    "stripe_price_id": new_price.id,
                    "stripe_active_mode": _mode,
                }}
            )
            logger.info(f"[subscribe] minted fresh {_mode} price for {body.service_id}: {new_price.id}")
            return new_price.id

        if not price_id:
            price_id = await _mint_fresh_price()
        else:
            # Defensive validation — if the cached id was created in a
            # different account/mode, Stripe Price.retrieve will fail
            # with InvalidRequestError. We catch that and re-mint.
            try:
                stripe_lib.Price.retrieve(price_id)
            except stripe_lib.error.InvalidRequestError as e:
                if "No such price" in str(e):
                    logger.warning(
                        f"[subscribe] cached {price_field}={price_id} not "
                        f"found in {_mode} mode — re-minting"
                    )
                    price_id = await _mint_fresh_price()
                else:
                    raise

        origin = (body.origin_url or "https://aurem.live").rstrip("/")
        session_params = {
            "mode": "subscription" if svc.get("billing_type") == "recurring" else "payment",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": f"{origin}/my/website?addon_success={body.service_id}&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{origin}/my/website?addon_cancel={body.service_id}",
            "customer_email": user.get("email"),
            "allow_promotion_codes": True,
            "metadata": {
                "service_id": body.service_id,
                "tenant_bin": user.get("bin", ""),
                "user_email": user.get("email", ""),
                "type": "addon_subscription",
            },
        }
        if _automatic_tax_enabled():
            session_params["automatic_tax"] = {"enabled": True}
        session = stripe_lib.checkout.Session.create(**session_params)

        # Log pending subscription (will be activated by webhook)
        await _db.customer_subscriptions.insert_one({
            "sub_id": f"sub_{uuid.uuid4().hex[:14]}",
            "tenant_bin": user.get("bin", ""),
            "email": user.get("email", ""),
            "service_id": body.service_id,
            "service_name": svc["name"],
            "price_monthly": svc["price_monthly"],
            "status": "pending",
            "stripe_session_id": session.id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        return {"url": session.url, "session_id": session.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[subscribe] failed: {e}")
        raise HTTPException(500, f"checkout failed: {e}")


class CancelRequest(BaseModel):
    service_id: str


@router.post("/api/customer/subscriptions/cancel")
async def customer_cancel(body: CancelRequest, user: dict = Depends(_verify_platform_user)):
    """Cancel a specific add-on subscription."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    sub = await _db.customer_subscriptions.find_one({
        "email": user.get("email", ""),
        "service_id": body.service_id,
        "status": "active",
    })
    if not sub:
        raise HTTPException(404, "no active subscription for this service")

    # Cancel on Stripe if subscription ID exists
    stripe_sub_id = sub.get("stripe_subscription_id")
    if stripe_sub_id:
        try:
            import stripe as stripe_lib
            stripe_lib.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            stripe_lib.Subscription.delete(stripe_sub_id)
        except Exception as e:
            logger.warning(f"[cancel] stripe cancel failed (will still mark cancelled locally): {e}")

    now = datetime.now(timezone.utc).isoformat()
    await _db.customer_subscriptions.update_one(
        {"sub_id": sub["sub_id"]},
        {"$set": {"status": "cancelled", "cancelled_at": now}}
    )
    await _db.catalog_events.insert_one({
        "type": "subscription_cancelled",
        "email": user.get("email", ""),
        "service_id": body.service_id,
        "at": now,
    })
    return {"ok": True, "cancelled_at": now}
