"""
Public Booking Router — iter 322as
=========================================
Public-facing booking surface called by the embeddable widget (widget.js).

The widget sends `Authorization: Bearer sk_aurem_<live|test>_xxx` from any
customer website. We validate the key via the existing AuremKeyService,
resolve the tenant (business_id / BIN), then expose 3 endpoints:

    GET  /api/public/booking/types         service catalogue
    GET  /api/public/booking/availability  open slots for a date
    POST /api/public/booking/book          confirm slot → bookings collection

The booking is written under `bookings` with the tenant's business_id so it
shows up in the customer's existing dashboard.  No PII is logged beyond what
the tenant explicitly chose to capture.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public/booking", tags=["Public Booking Widget"])

_db = None


def set_db(database):
    global _db
    _db = database


# ──────────────────────────────────────────────────────────────
# Default catalogue used when tenant has no custom services yet.
# Real customisation lives in db.tenant_booking_services (per-bin).
# ──────────────────────────────────────────────────────────────
DEFAULT_SERVICE_TYPES: List[Dict[str, Any]] = [
    {"id": "consultation", "name": "Initial Consultation", "duration": 30},
    {"id": "followup",     "name": "Follow-up",            "duration": 20},
    {"id": "service",      "name": "Standard Service",     "duration": 60},
    {"id": "premium",      "name": "Premium Session",      "duration": 90},
]

DEFAULT_HOURS = {"start": "09:00", "end": "18:00", "slot_minutes": 30}


# ──────────────────────────────────────────────────────────────
# API-key → tenant resolver
# ──────────────────────────────────────────────────────────────
async def _resolve_tenant(authorization: Optional[str]) -> Dict[str, Any]:
    """Validate sk_aurem_ key and return tenant context."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    api_key = authorization[7:].strip()
    if not (api_key.startswith("sk_aurem_live_") or api_key.startswith("sk_aurem_test_")):
        raise HTTPException(401, "Invalid AUREM API key prefix")
    if _db is None:
        raise HTTPException(503, "DB unavailable")

    # Try the canonical key service first.
    try:
        from shared.commercial.key_service import AuremKeyService
        key_doc = await AuremKeyService(_db).validate_key(api_key)
        if key_doc:
            return {
                "business_id": key_doc.get("business_id") or "",
                "key_id": key_doc.get("key_id") or "",
            }
    except Exception as e:
        logger.warning(f"[public-booking] key_service unavailable: {e}")

    # Fallback: lookup in customer_api_keys (legacy) or tenant_api_keys.
    for coll in ("customer_api_keys", "tenant_api_keys", "api_keys"):
        try:
            doc = await _db[coll].find_one({"key": api_key, "active": True}, {"_id": 0})
            if doc:
                return {
                    "business_id": doc.get("business_id") or doc.get("bin") or doc.get("tenant_id") or "",
                    "key_id": doc.get("key_id") or doc.get("id") or "",
                }
        except Exception:
            continue

    raise HTTPException(401, "API key not recognised")


async def _get_tenant_services(business_id: str) -> List[Dict[str, Any]]:
    if not business_id or _db is None:
        return DEFAULT_SERVICE_TYPES
    try:
        cur = _db.tenant_booking_services.find(
            {"business_id": business_id, "active": {"$ne": False}},
            {"_id": 0},
        )
        items = await cur.to_list(length=50)
        return items if items else DEFAULT_SERVICE_TYPES
    except Exception:
        return DEFAULT_SERVICE_TYPES


# ──────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────
class BookingPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=3, max_length=80)      # phone OR email accepted
    service_type: str = Field(min_length=1, max_length=80)
    date: str  = Field(min_length=10, max_length=10)      # YYYY-MM-DD
    slot: str  = Field(min_length=1, max_length=40)       # HH:MM or ISO


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────
@router.get("/types")
async def list_service_types(authorization: Optional[str] = Header(default=None)):
    tenant = await _resolve_tenant(authorization)
    types = await _get_tenant_services(tenant["business_id"])
    return {"ok": True, "types": types}


@router.get("/availability")
async def get_availability(
    service_type: str,
    date: str,
    authorization: Optional[str] = Header(default=None),
):
    tenant = await _resolve_tenant(authorization)
    try:
        day = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Invalid date — expected YYYY-MM-DD")

    services = await _get_tenant_services(tenant["business_id"])
    svc = next((s for s in services if s.get("id") == service_type or s.get("slug") == service_type), None)
    duration = int((svc or {}).get("duration", 30))

    # Read booked slots from `bookings` collection (compatible with existing storage)
    booked = set()
    if _db is not None:
        try:
            cur = _db.bookings.find(
                {"business_id": tenant["business_id"], "date": date, "status": {"$ne": "cancelled"}},
                {"_id": 0, "slot": 1, "time": 1},
            )
            async for r in cur:
                booked.add(str(r.get("slot") or r.get("time") or ""))
        except Exception:
            pass

    start = datetime.strptime(DEFAULT_HOURS["start"], "%H:%M")
    end   = datetime.strptime(DEFAULT_HOURS["end"], "%H:%M")
    step  = timedelta(minutes=DEFAULT_HOURS["slot_minutes"])
    now   = datetime.now(timezone.utc)
    same_day = day.date() == now.date()

    slots: List[Dict[str, Any]] = []
    cursor = start
    while cursor + timedelta(minutes=duration) <= end:
        hhmm = cursor.strftime("%H:%M")
        skip = hhmm in booked
        if same_day:
            slot_dt = day.replace(hour=cursor.hour, minute=cursor.minute, tzinfo=timezone.utc)
            if slot_dt <= now:
                skip = True
        if not skip:
            slots.append({"time": hhmm, "duration": duration})
        cursor += step

    return {"ok": True, "slots": slots, "service_type": service_type, "date": date}


@router.post("/book")
async def create_booking(
    payload: BookingPayload,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    tenant = await _resolve_tenant(authorization)

    booking_id = f"book_{secrets.token_urlsafe(10)}"
    now_iso = datetime.now(timezone.utc).isoformat()
    contact = payload.phone.strip()
    is_email = "@" in contact

    doc = {
        "booking_id": booking_id,
        "business_id": tenant["business_id"],
        "name":  payload.name.strip(),
        "phone": "" if is_email else contact,
        "email": contact if is_email else "",
        "service_type": payload.service_type,
        "service": payload.service_type,         # mirrored for legacy readers
        "date":  payload.date,
        "slot":  payload.slot,
        "time":  payload.slot,                    # legacy
        "status": "confirmed",
        "source": "widget",
        "key_id": tenant.get("key_id", ""),
        "created_at": now_iso,
        "ip": (request.client.host if request.client else "") or "",
    }

    if _db is not None:
        try:
            await _db.bookings.insert_one(doc)
        except Exception as e:
            logger.exception("[public-booking] insert failed")
            raise HTTPException(500, f"Booking failed: {e}")

        # Best-effort ORA learning hook — never blocks user.
        try:
            from services import ora_universal_learner as _oul
            await _oul.ora_learn({
                "source": "widget_booking",
                "event": "BOOKING_CONFIRMED",
                "category": "customer_lifecycle",
                "summary": f"booking via widget for {payload.service_type}",
                "outcome": "confirmed",
                "bin_id": tenant["business_id"],
            })
        except Exception:
            pass

    return {
        "ok": True,
        "booking_id": booking_id,
        "confirmation": f"Booked for {payload.date} at {payload.slot}.",
    }
