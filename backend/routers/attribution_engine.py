"""
AUREM Attribution Engine — Signed Token Tracking + Attribution Matching
Implements the 'Aurem-Ref' system: every link sent via Comm Hub gets a
signed, 30-day tracking token. When a Shopify order arrives, the system
matches the token to claim the commission.

Security:
- Tokens are HMAC-SHA256 signed with a server-side secret
- 30-day attribution window (configurable)
- Shopify webhook HMAC verification prevents spoofed orders
"""

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import hmac
import hashlib
import base64
import json
import os
import secrets
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv(override=False)

# Attribution signing secret (server-side only)
ATTRIBUTION_SECRET = os.environ.get("ATTRIBUTION_SECRET", os.environ.get("JWT_SECRET", "aurem-attr-secret-key"))
ATTRIBUTION_WINDOW_DAYS = 30
SHOPIFY_WEBHOOK_SECRET = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")


# ─── Helpers ────────────────────────────────────────────────────
def _get_user_id(authorization: str) -> str:
    if authorization and authorization.startswith("Bearer "):
        try:
            import jwt
            token = authorization.replace("Bearer ", "")
            payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
            return payload.get("user_id", "anonymous")
        except Exception:
            pass
    return "anonymous"


# ═══════════════════════════════════════════════════════════════
# 1. SIGNED TOKEN GENERATION
# ═══════════════════════════════════════════════════════════════

def generate_aurem_ref(user_id: str, scan_url: str, channel: str, campaign_id: str = "") -> dict:
    """
    Generate a signed, time-bound attribution token.
    Returns: { token, ref_id, expires_at, tracking_url_param }
    """
    ref_id = f"TRACK-{secrets.token_hex(8).upper()}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=ATTRIBUTION_WINDOW_DAYS)

    payload = {
        "ref": ref_id,
        "uid": user_id,
        "url": scan_url,
        "ch": channel,  # email, whatsapp, sms
        "cid": campaign_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    # Sign the payload with HMAC-SHA256
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = hmac.new(
        ATTRIBUTION_SECRET.encode("utf-8"),
        payload_json.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:16]

    token = base64.urlsafe_b64encode(
        f"{payload_json}|{signature}".encode("utf-8")
    ).decode("utf-8").rstrip("=")

    return {
        "ref_id": ref_id,
        "token": token,
        "expires_at": expires_at.isoformat(),
        "tracking_param": f"aurem_ref={ref_id}",
        "channel": channel,
    }


def verify_aurem_ref(ref_id: str, token: str) -> Optional[dict]:
    """
    Verify a signed attribution token. Returns payload if valid, None if expired/tampered.
    """
    try:
        # Pad base64
        padded = token + "=" * (4 - len(token) % 4) if len(token) % 4 else token
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        payload_json, signature = decoded.rsplit("|", 1)

        # Verify signature
        expected_sig = hmac.new(
            ATTRIBUTION_SECRET.encode("utf-8"),
            payload_json.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()[:16]

        if not hmac.compare_digest(signature, expected_sig):
            logger.warning(f"[ATTRIBUTION] Invalid signature for ref {ref_id}")
            return None

        payload = json.loads(payload_json)

        # Check expiry
        exp = payload.get("exp", 0)
        if datetime.now(timezone.utc).timestamp() > exp:
            logger.info(f"[ATTRIBUTION] Token expired for ref {ref_id}")
            return None

        return payload
    except Exception as e:
        logger.error(f"[ATTRIBUTION] Token verification failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# 2. LINK TRACKING ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class TrackingLinkRequest(BaseModel):
    scan_url: str
    destination_url: str
    channel: str = "email"  # email | whatsapp | sms
    campaign_id: Optional[str] = ""


@router.post("/api/attribution/create-link")
async def create_tracking_link(body: TrackingLinkRequest, authorization: str = Header(None)):
    """Create a signed tracking link for the Comm Hub."""
    from server import db
    user_id = _get_user_id(authorization)

    ref_data = generate_aurem_ref(user_id, body.scan_url, body.channel, body.campaign_id or "")

    # Build tracked URL
    separator = "&" if "?" in body.destination_url else "?"
    tracked_url = f"{body.destination_url}{separator}aurem_ref={ref_data['ref_id']}"

    # Store the tracking record
    now = datetime.now(timezone.utc).isoformat()
    await db.attribution_links.insert_one({
        "ref_id": ref_data["ref_id"],
        "token": ref_data["token"],
        "user_id": user_id,
        "scan_url": body.scan_url,
        "destination_url": body.destination_url,
        "tracked_url": tracked_url,
        "channel": body.channel,
        "campaign_id": body.campaign_id or "",
        "expires_at": ref_data["expires_at"],
        "created_at": now,
        "clicked": False,
        "clicked_at": None,
        "converted": False,
        "converted_at": None,
        "order_id": None,
        "commission_amount": None,
    })

    return {
        "ref_id": ref_data["ref_id"],
        "tracked_url": tracked_url,
        "channel": body.channel,
        "expires_at": ref_data["expires_at"],
        "message": "Tracking link created — 30-day attribution window active",
    }


@router.get("/api/attribution/click/{ref_id}")
async def track_click(ref_id: str):
    """Record a click event on a tracked link."""
    from server import db
    now = datetime.now(timezone.utc).isoformat()

    link = await db.attribution_links.find_one(
        {"ref_id": ref_id}, {"_id": 0}
    )
    if not link:
        raise HTTPException(404, "Tracking link not found")

    # Record click
    await db.attribution_links.update_one(
        {"ref_id": ref_id},
        {"$set": {"clicked": True, "clicked_at": now}}
    )

    # Store click event
    await db.attribution_events.insert_one({
        "ref_id": ref_id,
        "event_type": "click",
        "user_id": link.get("user_id"),
        "channel": link.get("channel"),
        "timestamp": now,
    })

    # Redirect to destination
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=link.get("destination_url", "/"))


# ═══════════════════════════════════════════════════════════════
# 3. SHOPIFY WEBHOOK — orders/paid (HMAC Verified)
# ═══════════════════════════════════════════════════════════════

def _verify_shopify_hmac(body: bytes, hmac_header: str) -> bool:
    """Verify Shopify webhook HMAC-SHA256 signature."""
    if not SHOPIFY_WEBHOOK_SECRET:
        # In test mode, accept all webhooks but log warning
        logger.warning("[ATTRIBUTION] Shopify HMAC verification skipped (no secret configured)")
        return True

    digest = hmac.new(
        SHOPIFY_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    computed = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(computed, hmac_header)


@router.post("/api/webhook/shopify/orders-paid")
async def shopify_order_paid(request: Request):
    """
    Shopify orders/paid webhook receiver.
    1. Verifies HMAC signature
    2. Extracts aurem_ref from order note_attributes / landing_site / referring_site
    3. Matches to attribution link
    4. Claims commission and sends to Revenue Engine
    """
    from server import db
    body = await request.body()

    # Verify Shopify HMAC
    shopify_hmac = request.headers.get("X-Shopify-Hmac-Sha256", "")
    if not _verify_shopify_hmac(body, shopify_hmac):
        logger.warning("[ATTRIBUTION] Shopify HMAC verification failed")
        return JSONResponse({"error": "HMAC verification failed"}, 401)

    try:
        order = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, 400)

    now = datetime.now(timezone.utc).isoformat()
    order_id = str(order.get("id", ""))
    order_total = float(order.get("total_price", 0))
    order_email = order.get("email", "")
    # 2026-04: Use checkout_token instead of deprecated checkout_id
    checkout_token = order.get("checkout_token", "") or str(order.get("checkout_id", ""))

    # Extract aurem_ref from multiple locations
    aurem_ref = None

    # Check note_attributes
    for attr in order.get("note_attributes", []):
        if attr.get("name") == "aurem_ref":
            aurem_ref = attr.get("value")
            break

    # Check landing_site URL params
    if not aurem_ref:
        landing = order.get("landing_site", "") or ""
        if "aurem_ref=" in landing:
            aurem_ref = landing.split("aurem_ref=")[1].split("&")[0]

    # Check referring_site
    if not aurem_ref:
        referring = order.get("referring_site", "") or ""
        if "aurem_ref=" in referring:
            aurem_ref = referring.split("aurem_ref=")[1].split("&")[0]

    # Check discount_codes (if aurem discount was used)
    if not aurem_ref:
        for dc in order.get("discount_codes", []):
            code = dc.get("code", "")
            if code.startswith("AUREM-"):
                # Try to find associated tracking link
                link = await db.attribution_links.find_one(
                    {"campaign_id": code}, {"_id": 0, "ref_id": 1}
                )
                if link:
                    aurem_ref = link["ref_id"]
                    break

    if not aurem_ref:
        # No attribution — log and return
        logger.info(f"[ATTRIBUTION] Order {order_id} has no aurem_ref — not attributed")
        return JSONResponse({"received": True, "attributed": False})

    # Match to attribution link
    link = await db.attribution_links.find_one(
        {"ref_id": aurem_ref}, {"_id": 0}
    )
    if not link:
        logger.warning(f"[ATTRIBUTION] Ref {aurem_ref} not found in database")
        return JSONResponse({"received": True, "attributed": False})

    # Verify token hasn't expired
    token_payload = verify_aurem_ref(aurem_ref, link.get("token", ""))
    if not token_payload:
        logger.info(f"[ATTRIBUTION] Ref {aurem_ref} token expired or invalid")
        return JSONResponse({"received": True, "attributed": False, "reason": "token_expired"})

    # Check if already attributed (idempotency)
    existing = await db.attributed_sales.find_one(
        {"order_id": order_id}, {"_id": 0, "ref_id": 1}
    )
    if existing:
        return JSONResponse({"received": True, "attributed": True, "duplicate": True})

    # Determine commission rate based on user's active plan
    user_id = link.get("user_id", "")
    activation = await db.agent_activations.find_one(
        {"user_id": user_id, "status": "activated"},
        {"_id": 0, "tier_id": 1},
        sort=[("activated_at", -1)],
    )

    tier_id = activation.get("tier_id", "starter") if activation else "starter"
    commission_rates = {
        "starter": {"flat": 2.00, "percent": 0},
        "explorer": {"flat": 2.00, "percent": 0},
        "builder": {"flat": 0.50, "percent": 0},
        "enterprise": {"flat": 0, "percent": 5},  # 5% of order total
    }
    rate = commission_rates.get(tier_id, commission_rates["starter"])
    commission = rate["flat"] if rate["flat"] else round(order_total * rate["percent"] / 100, 2)

    # Store attributed sale
    sale_doc = {
        "sale_id": f"sale_{secrets.token_urlsafe(12)}",
        "ref_id": aurem_ref,
        "user_id": user_id,
        "order_id": order_id,
        "order_total": order_total,
        "order_email": order_email,
        "commission_amount": commission,
        "commission_rate": rate,
        "tier_id": tier_id,
        "channel": link.get("channel", ""),
        "scan_url": link.get("scan_url", ""),
        "attribution_chain": {
            "link_created": link.get("created_at"),
            "link_clicked": link.get("clicked_at"),
            "order_paid": now,
        },
        "status": "confirmed",
        "billed": False,
        "created_at": now,
    }
    await db.attributed_sales.insert_one(sale_doc)

    # Update attribution link
    await db.attribution_links.update_one(
        {"ref_id": aurem_ref},
        {"$set": {
            "converted": True,
            "converted_at": now,
            "order_id": order_id,
            "commission_amount": commission,
        }}
    )

    # Store attribution event
    await db.attribution_events.insert_one({
        "ref_id": aurem_ref,
        "event_type": "conversion",
        "user_id": user_id,
        "order_id": order_id,
        "order_total": order_total,
        "commission": commission,
        "timestamp": now,
    })

    logger.info(f"[ATTRIBUTION] Sale attributed: order={order_id}, ref={aurem_ref}, commission=${commission}")

    return JSONResponse({
        "received": True,
        "attributed": True,
        "ref_id": aurem_ref,
        "order_id": order_id,
        "commission": commission,
    })


# ═══════════════════════════════════════════════════════════════
# 4. ATTRIBUTION DASHBOARD DATA
# ═══════════════════════════════════════════════════════════════

@router.get("/api/attribution/sales")
async def list_attributed_sales(authorization: str = Header(None)):
    """List all attributed sales with full attribution chain (proof)."""
    from server import db
    user_id = _get_user_id(authorization)

    sales = await db.attributed_sales.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    total_commission = sum(s.get("commission_amount", 0) for s in sales)
    total_revenue = sum(s.get("order_total", 0) for s in sales)

    return {
        "sales": sales,
        "total_sales": len(sales),
        "total_commission": round(total_commission, 2),
        "total_revenue_generated": round(total_revenue, 2),
    }


@router.get("/api/attribution/links")
async def list_tracking_links(authorization: str = Header(None)):
    """List all tracking links with click/conversion status."""
    from server import db
    user_id = _get_user_id(authorization)

    links = await db.attribution_links.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    return {
        "links": links,
        "total": len(links),
        "clicked": len([l for l in links if l.get("clicked")]),
        "converted": len([l for l in links if l.get("converted")]),
    }


@router.get("/api/attribution/events/{ref_id}")
async def get_attribution_events(ref_id: str, authorization: str = Header(None)):
    """Get the full event timeline for an attribution chain (proof of work)."""
    from server import db
    user_id = _get_user_id(authorization)

    events = await db.attribution_events.find(
        {"ref_id": ref_id, "user_id": user_id}, {"_id": 0}
    ).sort("timestamp", 1).to_list(100)

    link = await db.attribution_links.find_one(
        {"ref_id": ref_id, "user_id": user_id}, {"_id": 0}
    )

    return {
        "ref_id": ref_id,
        "link": link,
        "events": events,
        "timeline_count": len(events),
    }


@router.get("/api/attribution/summary")
async def get_attribution_summary(authorization: str = Header(None)):
    """Get a high-level attribution summary for the Revenue Dashboard."""
    from server import db
    user_id = _get_user_id(authorization)

    if user_id == "anonymous":
        raise HTTPException(401, "Authentication required")

    sales = await db.attributed_sales.find(
        {"user_id": user_id}, {"_id": 0, "commission_amount": 1, "order_total": 1, "channel": 1, "created_at": 1}
    ).to_list(1000)

    links = await db.attribution_links.find(
        {"user_id": user_id}, {"_id": 0, "clicked": 1, "converted": 1, "channel": 1}
    ).to_list(1000)

    # Channel breakdown
    from collections import defaultdict
    channel_stats = defaultdict(lambda: {"sent": 0, "clicked": 0, "converted": 0, "revenue": 0, "commission": 0})
    for l in links:
        ch = l.get("channel", "unknown")
        channel_stats[ch]["sent"] += 1
        if l.get("clicked"):
            channel_stats[ch]["clicked"] += 1
        if l.get("converted"):
            channel_stats[ch]["converted"] += 1

    for s in sales:
        ch = s.get("channel", "unknown")
        channel_stats[ch]["revenue"] += s.get("order_total", 0)
        channel_stats[ch]["commission"] += s.get("commission_amount", 0)

    total_commission = sum(s.get("commission_amount", 0) for s in sales)
    total_revenue = sum(s.get("order_total", 0) for s in sales)
    total_links = len(links)
    total_clicks = len([l for l in links if l.get("clicked")])
    total_conversions = len([l for l in links if l.get("converted")])

    return {
        "total_links_sent": total_links,
        "total_clicks": total_clicks,
        "total_conversions": total_conversions,
        "conversion_rate": round(total_conversions / total_clicks * 100, 1) if total_clicks > 0 else 0,
        "total_revenue_generated": round(total_revenue, 2),
        "total_commission_earned": round(total_commission, 2),
        "channel_breakdown": dict(channel_stats),
    }
