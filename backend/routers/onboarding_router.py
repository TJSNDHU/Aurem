"""
Onboarding / Quick Start Wizard Router
Tracks tenant onboarding progress through 3 key activation steps.

iter D-81b — also serves the BIN-scoped customer activation flow:
  POST /api/onboarding/business-profile  — capture business_url + industry
                                            + target_city + target_country
                                            → write customer_business_profile
                                            keyed by BIN → fire welcome email
  GET  /api/onboarding/business-profile  — read back current profile + status
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db

ONBOARDING_STEPS = [
    {"id": "connect_crm", "title": "Connect Your CRM", "description": "Link HubSpot, Salesforce, Pipedrive, or Zoho to sync your contacts and deals automatically.", "nav_target": "crm-connect"},
    {"id": "setup_pipeline", "title": "Set Up Your Pipeline", "description": "Configure your sales stages and import your first deals to start tracking revenue.", "nav_target": "sales-pipeline"},
    {"id": "activate_ora", "title": "Activate ORA AI", "description": "Start a conversation with ORA to experience AI-powered business intelligence.", "nav_target": "ai-conversation"},
    {"id": "review_catalog", "title": "Review Service Catalog", "description": "Check the 17-service AUREM catalog, bundle rules, and platform MRR in the unified Command Hub.", "nav_target": "command-hub"},
    {"id": "configure_voice", "title": "Configure Voice Agent", "description": "Set up the AI inbound call handler (Retell AI). Add RETELL_API_KEY to enable live mode.", "nav_target": "command-hub"},
]


# iter 326k — silence the 404 spam from services/warm_prober.py which
# intentionally probes /api/onboarding/status-health to keep the router
# warm. The probe doesn't care about the response — it just needs ANY
# 2xx so the route is loaded. Without this, every warm tick logs
# "404 Not Found" which pollutes prod log streams.
@router.get("/status-health")
async def status_health():
    return {"status": "ok", "service": "onboarding", "warm": True}


def _get_user_id(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth.split(" ", 1)[1]
    secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("user_id") or payload.get("sub") or payload.get("id")
    except Exception:
        raise HTTPException(401, "Invalid token")


@router.get("/status")
async def get_onboarding_status(request: Request):
    user_id = _get_user_id(request)
    db = get_db()

    record = await db.onboarding.find_one({"user_id": user_id}, {"_id": 0})

    if not record:
        record = {
            "user_id": user_id,
            "completed_steps": [],
            "dismissed": False,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.onboarding.insert_one({**record})

    steps_with_status = []
    for step in ONBOARDING_STEPS:
        steps_with_status.append({
            **step,
            "completed": step["id"] in record.get("completed_steps", []),
        })

    total = len(ONBOARDING_STEPS)
    done = len(record.get("completed_steps", []))

    return {
        "steps": steps_with_status,
        "progress": done / total if total > 0 else 0,
        "completed_count": done,
        "total": total,
        "all_complete": done >= total,
        "dismissed": record.get("dismissed", False),
    }


@router.post("/complete-step")
async def complete_step(request: Request):
    user_id = _get_user_id(request)
    db = get_db()
    body = await request.json()
    step_id = body.get("step_id")

    if not step_id:
        raise HTTPException(400, "step_id required")

    valid_ids = [s["id"] for s in ONBOARDING_STEPS]
    if step_id not in valid_ids:
        raise HTTPException(400, "Invalid step_id")

    await db.onboarding.update_one(
        {"user_id": user_id},
        {
            "$addToSet": {"completed_steps": step_id},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {"started_at": datetime.now(timezone.utc).isoformat(), "dismissed": False},
        },
        upsert=True,
    )

    return {"success": True, "step_id": step_id}


@router.post("/dismiss")
async def dismiss_wizard(request: Request):
    user_id = _get_user_id(request)
    db = get_db()

    await db.onboarding.update_one(
        {"user_id": user_id},
        {"$set": {"dismissed": True, "dismissed_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )

    return {"success": True}


# ═══════════════════════════════════════════════════════════════════
# iter D-81b — BIN-scoped customer activation flow.
# The frontend `/onboarding` page captures the freshly-subscribed
# customer's business context and writes it to customer_business_profile
# keyed by BIN. Welcome email fired best-effort (never blocks success).
# ═══════════════════════════════════════════════════════════════════

_ALLOWED_INDUSTRIES = {
    "hvac", "plumbing", "electrical", "roofing", "landscaping",
    "cleaning", "auto_repair", "salon", "spa", "fitness",
    "restaurant", "retail", "real_estate", "legal", "accounting",
    "medical_clinic", "dental", "construction", "moving", "pest_control",
    "other",
}

_ALLOWED_COUNTRIES = {"CA", "US", "GB", "AU", "IN", "OTHER"}


async def _get_bin_ctx(request: Request) -> dict:
    """Pull (user_id, email, business_id) from JWT, with DB fallback for
    legacy tokens.

    iter D-81e — existing customer JWTs issued before D-81b don't carry
    `business_id` on the claim set. Re-logging in every customer is
    operationally hostile. Instead we mirror what `_require_user` in
    `me_pwa_router` does: decode the token, look up the user in
    `platform_users` by email, and derive the BIN from that record.

    Returns dict with email, user_id, business_id. 401 if token invalid.
    403 only if the user genuinely has no BIN on record (account never
    properly provisioned).
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT not configured")
    try:
        claims = jwt.decode(auth[7:], secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")

    email = (claims.get("email") or claims.get("sub") or "").lower()
    user_id = claims.get("user_id") or claims.get("sub") or claims.get("id") or ""
    bin_id = claims.get("business_id") or claims.get("bin")

    # Fallback: derive BIN from platform_users by email (legacy tokens).
    if not bin_id and email:
        try:
            db = get_db()
            u = await db.platform_users.find_one(
                {"email": email}, {"_id": 0, "bin": 1, "user_id": 1}
            )
            if u:
                bin_id = u.get("bin") or "AURE-CUSTOMER"
                user_id = user_id or u.get("user_id") or email
        except Exception:
            pass

    if not bin_id:
        raise HTTPException(403, "No business_id (BIN) on token — re-login required")
    return {
        "user_id":     user_id,
        "email":       email,
        "business_id": bin_id,
    }


async def _send_welcome_email(*, email: str, business_name: str, dashboard_url: str) -> None:
    """Fire welcome email via Resend. Never raises — onboarding success
    must not depend on email delivery."""
    if not email:
        return
    try:
        from services.email_service_resend import send_email
    except Exception:
        return
    html = f"""
    <div style="font-family:Inter,system-ui,sans-serif;max-width:560px;margin:auto;padding:32px;background:#0A0A0A;color:#f4f4f5;border-radius:12px">
      <h1 style="color:#C9A227;font-size:24px;margin:0 0 16px">Welcome to AUREM</h1>
      <p style="color:#d4d4d8;line-height:1.6;font-size:15px">
        Your business <b>{business_name}</b> is now activated on AUREM.
        ORA is already scoping your market. Hop into the dashboard to see
        your first scout run.
      </p>
      <p style="margin:24px 0">
        <a href="{dashboard_url}" style="display:inline-block;padding:12px 24px;background:#C9A227;color:#0A0A0A;text-decoration:none;border-radius:8px;font-weight:600">
          Open your dashboard →
        </a>
      </p>
      <p style="color:#71717a;font-size:12px;margin-top:32px">
        Polaris Built Inc. · Mississauga, Ontario · PIPEDA / Law 25 compliant.
        Reply to this email to reach a human.
      </p>
    </div>
    """.strip()
    try:
        await send_email(
            to=email,
            subject=f"Welcome to AUREM — {business_name} is activated",
            html=html,
        )
    except Exception:
        logger.exception("[onboarding] welcome email send failed")


@router.post("/business-profile")
async def save_business_profile(request: Request):
    """D-81b — persist new customer's business context, keyed by BIN.

    Body: {
      business_name: str (required),
      business_url:  str (required, must look like a URL),
      industry:      str (required, from _ALLOWED_INDUSTRIES),
      target_city:   str (required),
      target_country: str (required, from _ALLOWED_COUNTRIES),
    }
    Returns { ok: true, business_id, redirect_to: "/dashboard" }.
    """
    ctx = await _get_bin_ctx(request)
    body = await request.json()

    business_name = (body.get("business_name") or "").strip()
    business_url = (body.get("business_url") or "").strip()
    industry = (body.get("industry") or "").strip().lower()
    target_city = (body.get("target_city") or "").strip()
    target_country = (body.get("target_country") or "").strip().upper()

    # ── Validation ────────────────────────────────────────────────
    if not business_name:
        raise HTTPException(400, "business_name required")
    if not business_url or not (business_url.startswith("http://") or business_url.startswith("https://")):
        raise HTTPException(400, "business_url must start with http:// or https://")
    if industry not in _ALLOWED_INDUSTRIES:
        raise HTTPException(400, f"industry must be one of {sorted(_ALLOWED_INDUSTRIES)}")
    if not target_city:
        raise HTTPException(400, "target_city required")
    if target_country not in _ALLOWED_COUNTRIES:
        raise HTTPException(400, f"target_country must be one of {sorted(_ALLOWED_COUNTRIES)}")

    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Idempotent upsert keyed by BIN — never lets one BIN overwrite another.
    profile = {
        "business_id": ctx["business_id"],
        "user_id": ctx["user_id"],
        "email": ctx["email"],
        "business_name": business_name,
        "business_url": business_url,
        "industry": industry,
        "target_city": target_city,
        "target_country": target_country,
        "updated_at": now_iso,
    }
    result = await db.customer_business_profile.update_one(
        {"business_id": ctx["business_id"]},
        {"$set": profile, "$setOnInsert": {"created_at": now_iso}},
        upsert=True,
    )

    # Mark the onboarding wizard step done so the in-app checklist updates.
    await db.onboarding.update_one(
        {"user_id": ctx["user_id"]},
        {
            "$addToSet": {"completed_steps": "business_profile"},
            "$set": {"updated_at": now_iso},
            "$setOnInsert": {"started_at": now_iso, "dismissed": False},
        },
        upsert=True,
    )

    # Audit trail — survives even when business_id is the founder.
    try:
        await db.audit_trail.insert_one({
            "event": "onboarding.business_profile.saved",
            "business_id": ctx["business_id"],
            "user_id": ctx["user_id"],
            "email": ctx["email"],
            "is_new": result.upserted_id is not None,
            "at": now_iso,
        })
    except Exception:
        logger.exception("[onboarding] audit insert failed")

    # Fire welcome email — best-effort. Only on first-time creation.
    if result.upserted_id is not None:
        base_url = os.environ.get("APP_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "https://aurem.live"
        await _send_welcome_email(
            email=ctx["email"],
            business_name=business_name,
            dashboard_url=f"{base_url.rstrip('/')}/dashboard",
        )

    return {
        "ok": True,
        "business_id": ctx["business_id"],
        "is_new": result.upserted_id is not None,
        "redirect_to": "/dashboard",
    }


@router.get("/business-profile")
async def get_business_profile(request: Request):
    """D-81b — read back the BIN's profile. Returns 404 if not yet saved
    so the frontend knows to show the onboarding form."""
    ctx = await _get_bin_ctx(request)
    db = get_db()
    doc = await db.customer_business_profile.find_one(
        {"business_id": ctx["business_id"]}, {"_id": 0}
    )
    if not doc:
        return {"exists": False, "business_id": ctx["business_id"]}
    return {"exists": True, "profile": doc}
