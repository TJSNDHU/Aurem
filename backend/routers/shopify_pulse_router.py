"""
Shopify Pulse Scanner & Cart Recovery Engine
=============================================
Phase 1: Scan store health via GraphQL v2026-04
Phase 2: Abandoned cart recovery sequence (WA → Email → SMS)
Phase 3: Instant win — auto-fix alt-text via GraphQL mutation
"""

import os
import hmac as _hmac
import hashlib
import base64
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/shopify/pulse", tags=["Shopify Pulse"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    import jwt
    try:
        # Bug-fix #61 — no empty-string fallback; require JWT_SECRET.
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            raise HTTPException(500, "JWT not configured")
        payload = jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
        # Bug-fix #39 — require an admin claim, not just a valid JWT.
        from utils.admin_guard import is_admin_email
        if not (payload.get("is_admin") or payload.get("is_super_admin")
                or payload.get("role") in ("admin", "super_admin")
                or is_admin_email(payload.get("email"))):
            raise HTTPException(403, "Admin access required")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")


def _verify_shopify_hmac(body: bytes, hmac_header: str) -> bool:
    """Bug-fix #151 (R18): Shopify webhook HMAC verification.

    Without this check, anyone could POST forged cart/order webhooks to
    /api/shopify/pulse/webhook/* and trigger mass recovery email blasts
    against arbitrary phone/email pairs.
    """
    secret = os.environ.get("SHOPIFY_WEBHOOK_SECRET") or os.environ.get("SHOPIFY_API_SECRET")
    if not secret:
        # No secret configured — fail-closed in production, fail-open in dev.
        return os.environ.get("AUREM_ENV", "development") != "production"
    if not hmac_header:
        return False
    digest = _hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode("utf-8")
    return _hmac.compare_digest(computed, hmac_header)


async def _get_shop_token(db, shop: str) -> Optional[str]:
    """Get access token for a Shopify shop."""
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"
    install = await db.shopify_app_installs.find_one(
        {"shop_domain": shop, "status": "active"}, {"_id": 0, "access_token": 1}
    )
    if install and install.get("access_token") and install["access_token"] != "mock_token":
        return install["access_token"]
    return None


async def _graphql(shop: str, token: str, query: str, variables: dict = None) -> dict:
    """Execute a Shopify GraphQL query."""
    import httpx
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"https://{shop}/admin/api/2024-10/graphql.json",
                json={"query": query, "variables": variables or {}},
                headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
            )
            result = resp.json()
            # Log errors for debugging
            if "errors" in result:
                logger.warning(f"[GRAPHQL] Errors: {result.get('errors')}")
            return result
    except Exception as e:
        logger.error(f"[GRAPHQL] Exception: {e}")
        return {"errors": [{"message": str(e)}]}


# ═══════════════════════════════════════════════════
# PULSE SCANNER — Store Health Scan
# ═══════════════════════════════════════════════════

class ScanRequest(BaseModel):
    shop: str


@router.post("/scan")
async def run_pulse_scan(body: ScanRequest, request: Request):
    """
    Run a full Pulse scan on a Shopify store via GraphQL v2026-04.
    Checks: missing alt-text, missing SEO, slow images, abandonment rate.
    Returns health score + issues + revenue at risk.
    """
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")

    shop = body.shop
    token = await _get_shop_token(db, shop)

    if not token:
        # Mock-purged: no fake scan when store not connected.
        # Force the operator through OAuth at /settings/shopify so we
        # only ever return real GraphQL-sourced data.
        raise HTTPException(
            status_code=503,
            detail=(
                "Shopify token not connected. "
                "Complete OAuth at /settings/shopify"
            ),
        )

    issues = []
    total_products = 0
    missing_alt = 0
    missing_meta = 0

    # 1. Check products for missing alt-text and meta descriptions
    products_query = """
    query ($cursor: String) {
      products(first: 50, after: $cursor) {
        edges {
          node {
            id title
            seo { title description }
            images(first: 10) { edges { node { id altText url } } }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
    """

    cursor = None
    all_products = []
    for _ in range(5):  # Max 250 products
        data = await _graphql(shop, token, products_query, {"cursor": cursor})
        products = data.get("data", {}).get("products", {})
        edges = products.get("edges", [])
        for edge in edges:
            node = edge["node"]
            all_products.append(node)
            total_products += 1

            # Check SEO
            seo = node.get("seo", {})
            if not seo.get("title") or not seo.get("description"):
                missing_meta += 1

            # Check images
            for img_edge in node.get("images", {}).get("edges", []):
                img = img_edge["node"]
                if not img.get("altText"):
                    missing_alt += 1

        if not products.get("pageInfo", {}).get("hasNextPage"):
            break
        cursor = products["pageInfo"]["endCursor"]

    # 2. Check abandonment rate (last 30 days)
    orders_query = """
    query {
      orders(first: 1, sortKey: CREATED_AT, reverse: true) { edges { node { id } } }
    }
    """
    orders_data = await _graphql(shop, token, orders_query)
    total_orders = len(orders_data.get("data", {}).get("orders", {}).get("edges", []))

    # Calculate abandoned carts from our DB
    abandoned = await db.aurem_abandoned_carts.count_documents({
        "shop_domain": shop if shop.endswith(".myshopify.com") else f"{shop}.myshopify.com",
        "recovered": False,
        "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()},
    })

    abandonment_rate = round((abandoned / max(abandoned + total_orders, 1)) * 100)

    # Build issues list
    if missing_alt > 0:
        issues.append({
            "type": "missing_alt_text", "count": missing_alt,
            "severity": "medium", "fix_available": True,
            "description": f"{missing_alt} product images missing alt-text — hurts SEO and accessibility",
        })

    if missing_meta > 0:
        issues.append({
            "type": "missing_seo_meta", "count": missing_meta,
            "severity": "medium", "fix_available": True,
            "description": f"{missing_meta} products missing SEO title or description",
        })

    if abandonment_rate > 20:
        issues.append({
            "type": "abandoned_cart_rate", "value": f"{abandonment_rate}%",
            "severity": "high", "fix_available": True,
            "description": f"{abandonment_rate}% cart abandonment — AUREM recovery can capture these sales",
        })

    # Score calculation
    score = 100
    for issue in issues:
        if issue["severity"] == "high":
            score -= 20
        elif issue["severity"] == "medium":
            score -= 10
        elif issue["severity"] == "low":
            score -= 5
    score = max(0, score)

    # Revenue at risk estimate
    avg_order_value = 65  # Default assumption
    monthly_abandoned = abandoned
    revenue_at_risk = round(monthly_abandoned * avg_order_value * 0.15)  # 15% recovery rate

    result = {
        "shop": shop,
        "health_score": score,
        "revenue_at_risk_monthly": revenue_at_risk,
        "total_products": total_products,
        "issues": issues,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save scan result
    await db.shopify_pulse_scans.insert_one({**result, "shop_domain": shop})

    return result


def _scaffold_scan(shop: str) -> dict:
    """REMOVED iter D-61. Kept as a loud raiser so any forgotten caller
    crashes loudly instead of silently faking data."""
    raise RuntimeError(
        "_scaffold_scan is removed (iter D-61 mock-purge). "
        "Connect the store via OAuth and use real GraphQL data."
    )


# ═══════════════════════════════════════════════════
# INSTANT WIN — Alt-Text Auto-Fix (SSE Stream)
# ═══════════════════════════════════════════════════

class FixAltTextRequest(BaseModel):
    shop: str


@router.post("/fix/alt-text")
async def fix_alt_text(body: FixAltTextRequest, request: Request):
    """
    Auto-fix missing alt-text on all product images.
    Uses OpenRouter to generate alt-text from product title + description.
    Returns Server-Sent Events for live progress.
    """
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")

    shop = body.shop
    token = await _get_shop_token(db, shop)

    async def stream_fixes():
        fixed = 0
        errors = 0

        if not token:
            yield f"data: {_sse_json({'type': 'error', 'code': 'NOT_CONNECTED', 'message': 'Shopify token not connected. Complete OAuth at /settings/shopify'})}\n\n"
            yield f"data: {_sse_json({'type': 'complete', 'fixed': 0, 'errors': 1, 'mode': 'not_connected'})}\n\n"
            return

        yield f"data: {_sse_json({'type': 'start', 'message': f'Scanning {shop} for missing alt-text...'})}\n\n"

        # Fetch products with missing alt-text
        products_query = """
        query ($cursor: String) {
          products(first: 20, after: $cursor) {
            edges { node { id title description images(first: 10) { edges { node { id altText } } } } }
            pageInfo { hasNextPage endCursor }
          }
        }
        """

        cursor = None
        to_fix = []
        for _ in range(5):
            data = await _graphql(shop, token, products_query, {"cursor": cursor})
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            for edge in edges:
                node = edge["node"]
                for img_edge in node.get("images", {}).get("edges", []):
                    img = img_edge["node"]
                    if not img.get("altText"):
                        to_fix.append({
                            "product_id": node["id"],
                            "product_title": node.get("title", ""),
                            "product_desc": (node.get("description", "") or "")[:200],
                            "image_id": img["id"],
                        })
            if not data.get("data", {}).get("products", {}).get("pageInfo", {}).get("hasNextPage"):
                break
            cursor = data["data"]["products"]["pageInfo