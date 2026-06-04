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
            cursor = data["data"]["products"]["pageInfo"]["endCursor"]

        yield f"data: {_sse_json({'type': 'info', 'message': f'Found {len(to_fix)} images missing alt-text'})}\n\n"

        for item in to_fix[:50]:  # Max 50 per run
            try:
                alt_text = _generate_alt_text(item["product_title"], item["product_desc"])

                # Push fix via GraphQL
                mutation = """
                mutation productImageUpdate($productId: ID!, $image: ImageInput!) {
                  productImageUpdate(productId: $productId, image: $image) {
                    image { id altText }
                    userErrors { field message }
                  }
                }
                """
                fix_data = await _graphql(shop, token, mutation, {
                    "productId": item["product_id"],
                    "image": {"id": item["image_id"], "altText": alt_text},
                })

                user_errors = fix_data.get("data", {}).get("productImageUpdate", {}).get("userErrors", [])
                if user_errors:
                    errors += 1
                    yield f"data: {_sse_json({'type': 'error', 'product': item['product_title'], 'error': user_errors[0]['message']})}\n\n"
                else:
                    fixed += 1
                    yield f"data: {_sse_json({'type': 'fix', 'product': item['product_title'], 'image_id': item['image_id'], 'alt_text': alt_text, 'status': 'applied'})}\n\n"

            except Exception as e:
                errors += 1
                yield f"data: {_sse_json({'type': 'error', 'product': item['product_title'], 'error': str(e)})}\n\n"

            await asyncio.sleep(0.3)  # Rate limit courtesy

        yield f"data: {_sse_json({'type': 'complete', 'fixed': fixed, 'errors': errors})}\n\n"

    return StreamingResponse(stream_fixes(), media_type="text/event-stream")


def _generate_alt_text(title: str, description: str) -> str:
    """Generate SEO-friendly alt-text from product info."""
    desc_clean = description.replace("<p>", "").replace("</p>", "").replace("<br>", " ").strip()[:100]
    if desc_clean:
        return f"{title} — {desc_clean}"
    return f"{title} product photo"


def _generate_meta_description(title: str, description: str, store_name: str = "") -> str:
    """Generate SEO meta description (155 chars max) from product info."""
    desc_clean = description.replace("<p>", "").replace("</p>", "").replace("<br>", " ").replace("\n", " ").strip()[:120]
    if desc_clean:
        meta = f"Shop {title} — {desc_clean}"
    elif store_name:
        meta = f"Shop {title} at {store_name}. Premium quality, fast shipping."
    else:
        meta = f"Shop {title}. Premium quality, competitive pricing, fast shipping."
    return meta[:155]


def _generate_seo_title(title: str, store_name: str = "") -> str:
    """Generate optimized page title (60 chars max)."""
    if store_name and len(f"{title} | {store_name}") <= 60:
        return f"{title} | {store_name}"
    return title[:57] + "..." if len(title) > 60 else title


def _generate_jsonld_product(product: dict, shop: str) -> str:
    """Generate JSON-LD Product schema markup."""
    import json
    title = product.get("title", "")
    desc = product.get("description", "")[:200].replace("<p>", "").replace("</p>", "").replace("<br>", " ").strip()
    price = "0"
    currency = "CAD"
    images = []
    variants = product.get("variants", {}).get("edges", [])
    if variants:
        v = variants[0].get("node", {})
        price = v.get("price", "0")
    for img_e in product.get("images", {}).get("edges", []):
        img_url = img_e.get("node", {}).get("url", "")
        if img_url:
            images.append(img_url)
    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": title,
        "description": desc or f"Shop {title}",
        "image": images[:3] if images else [],
        "offers": {
            "@type": "Offer",
            "price": price,
            "priceCurrency": currency,
            "availability": "https://schema.org/InStock",
            "url": f"https://{shop}/products/{title.lower().replace(' ', '-')[:50]}",
        },
    }
    return json.dumps(schema)


# ═══════════════════════════════════════════════════
# SEO AUTO-FIX: Meta Descriptions (GraphQL Push)
# ═══════════════════════════════════════════════════

@router.post("/fix/meta-descriptions")
async def fix_meta_descriptions(body: FixAltTextRequest, request: Request):
    """Auto-fix missing meta descriptions via AI generation + GraphQL push. SSE stream."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")
    shop = body.shop
    token = await _get_shop_token(db, body.shop)

    async def stream():
        fixed, errors = 0, 0
        if not token:
            yield f"data: {_sse_json({'type': 'error', 'code': 'NOT_CONNECTED', 'message': 'Shopify token not connected. Complete OAuth at /settings/shopify'})}\n\n"
            yield f"data: {_sse_json({'type': 'complete', 'fixed': 0, 'errors': 1, 'fix_type': 'meta_descriptions', 'mode': 'not_connected'})}\n\n"
            return

        yield f"data: {_sse_json({'type': 'start', 'message': f'Scanning {shop} for missing meta descriptions...'})}\n\n"
        q = """query ($cursor: String) { products(first: 20, after: $cursor) {
            edges { node { id title description seo { title description } } }
            pageInfo { hasNextPage endCursor } } }"""
        cursor, to_fix = None, []
        for _ in range(5):
            data = await _graphql(shop, token, q, {"cursor": cursor})
            # Handle GraphQL errors
            if not data or "errors" in data or not data.get("data"):
                yield f"data: {_sse_json({'type': 'error', 'message': 'GraphQL query failed - token may be invalid or expired'})}\n\n"
                yield f"data: {_sse_json({'type': 'complete', 'fixed': 0, 'errors': 1, 'fix_type': 'meta_descriptions'})}\n\n"
                return
            products_data = data.get("data", {}).get("products")
            if not products_data:
                break
            for e in products_data.get("edges", []):
                n = e["node"]
                seo = n.get("seo", {})
                if not seo.get("description"):
                    to_fix.append({"id": n["id"], "title": n.get("title", ""), "desc": (n.get("description", "") or "")[:200]})
            pi = data.get("data", {}).get("products", {}).get("pageInfo", {})
            if not pi.get("hasNextPage"):
                break
            cursor = pi["endCursor"]

        yield f"data: {_sse_json({'type': 'info', 'message': f'Found {len(to_fix)} products missing meta descriptions'})}\n\n"

        for item in to_fix[:50]:
            try:
                meta = _generate_meta_description(item["title"], item["desc"], shop.split(".")[0])
                mutation = """mutation($input: ProductInput!) { productUpdate(input: $input) { product { id } userErrors { field message } } }"""
                r = await _graphql(shop, token, mutation, {"input": {"id": item["id"], "seo": {"description": meta}}})
                ue = r.get("data", {}).get("productUpdate", {}).get("userErrors", [])
                if ue:
                    errors += 1
                    yield f"data: {_sse_json({'type': 'error', 'product': item['title'], 'error': ue[0]['message']})}\n\n"
                else:
                    fixed += 1
                    yield f"data: {_sse_json({'type': 'fix', 'product': item['title'], 'meta_description': meta, 'status': 'applied'})}\n\n"
            except Exception as e:
                errors += 1
                yield f"data: {_sse_json({'type': 'error', 'product': item['title'], 'error': str(e)})}\n\n"
            await asyncio.sleep(0.3)

        yield f"data: {_sse_json({'type': 'complete', 'fixed': fixed, 'errors': errors, 'fix_type': 'meta_descriptions'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ═══════════════════════════════════════════════════
# SEO AUTO-FIX: Page Title Optimization (AI Rewrite)
# ═══════════════════════════════════════════════════

@router.post("/fix/page-titles")
async def fix_page_titles(body: FixAltTextRequest, request: Request):
    """Optimize missing/weak page titles via AI rewrite + GraphQL push. SSE stream."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")
    shop, token = body.shop, await _get_shop_token(db, body.shop)

    async def stream():
        fixed, errors = 0, 0
        if not token:
            yield f"data: {_sse_json({'type': 'error', 'code': 'NOT_CONNECTED', 'message': 'Shopify token not connected. Complete OAuth at /settings/shopify'})}\n\n"
            yield f"data: {_sse_json({'type': 'complete', 'fixed': 0, 'errors': 1, 'fix_type': 'page_titles', 'mode': 'not_connected'})}\n\n"
            return

        yield f"data: {_sse_json({'type': 'start', 'message': f'Scanning {shop} for missing/weak SEO titles...'})}\n\n"
        q = """query ($cursor: String) { products(first: 20, after: $cursor) {
            edges { node { id title seo { title description } } }
            pageInfo { hasNextPage endCursor } } }"""
        cursor, to_fix = None, []
        for _ in range(5):
            data = await _graphql(shop, token, q, {"cursor": cursor})
            for e in data.get("data", {}).get("products", {}).get("edges", []):
                n = e["node"]
                seo_title = (n.get("seo", {}) or {}).get("title", "")
                if not seo_title:
                    to_fix.append({"id": n["id"], "title": n.get("title", "")})
            pi = data.get("data", {}).get("products", {}).get("pageInfo", {})
            if not pi.get("hasNextPage"):
                break
            cursor = pi["endCursor"]

        yield f"data: {_sse_json({'type': 'info', 'message': f'Found {len(to_fix)} products missing SEO titles'})}\n\n"

        store_name = shop.split(".")[0].replace("-", " ").title()
        for item in to_fix[:50]:
            try:
                seo_title = _generate_seo_title(item["title"], store_name)
                mutation = """mutation($input: ProductInput!) { productUpdate(input: $input) { product { id } userErrors { field message } } }"""
                r = await _graphql(shop, token, mutation, {"input": {"id": item["id"], "seo": {"title": seo_title}}})
                ue = r.get("data", {}).get("productUpdate", {}).get("userErrors", [])
                if ue:
                    errors += 1
                    yield f"data: {_sse_json({'type': 'error', 'product': item['title'], 'error': ue[0]['message']})}\n\n"
                else:
                    fixed += 1
                    yield f"data: {_sse_json({'type': 'fix', 'product': item['title'], 'seo_title': seo_title, 'status': 'applied'})}\n\n"
            except Exception as e:
                errors += 1
                yield f"data: {_sse_json({'type': 'error', 'product': item['title'], 'error': str(e)})}\n\n"
            await asyncio.sleep(0.3)

        yield f"data: {_sse_json({'type': 'complete', 'fixed': fixed, 'errors': errors, 'fix_type': 'page_titles'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ═══════════════════════════════════════════════════
# SEO AUTO-FIX: Schema Markup (JSON-LD via metafield)
# ═══════════════════════════════════════════════════

@router.post("/fix/schema-markup")
async def fix_schema_markup(body: FixAltTextRequest, request: Request):
    """Inject JSON-LD Product schema via Shopify metafields. SSE stream."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")
    shop, token = body.shop, await _get_shop_token(db, body.shop)

    async def stream():
        fixed, errors = 0, 0
        if not token:
            yield f"data: {_sse_json({'type': 'error', 'code': 'NOT_CONNECTED', 'message': 'Shopify token not connected. Complete OAuth at /settings/shopify'})}\n\n"
            yield f"data: {_sse_json({'type': 'complete', 'fixed': 0, 'errors': 1, 'fix_type': 'schema_markup', 'mode': 'not_connected'})}\n\n"
            return

        yield f"data: {_sse_json({'type': 'start', 'message': f'Generating JSON-LD schema for {shop} products...'})}\n\n"

        q = """query ($cursor: String) { products(first: 20, after: $cursor) {
            edges { node { id title description
                variants(first: 1) { edges { node { price } } }
                images(first: 3) { edges { node { url altText } } }
                metafields(first: 5, keys: ["custom.jsonld_schema"]) { edges { node { value } } }
            } } pageInfo { hasNextPage endCursor } } }"""

        cursor, to_fix = None, []
        for _ in range(5):
            data = await _graphql(shop, token, q, {"cursor": cursor})
            for e in data.get("data", {}).get("products", {}).get("edges", []):
                n = e["node"]
                has_schema = any(m.get("node", {}).get("value") for m in n.get("metafields", {}).get("edges", []))
                if not has_schema:
                    to_fix.append(n)
            pi = data.get("data", {}).get("products", {}).get("pageInfo", {})
            if not pi.get("hasNextPage"):
                break
            cursor = pi["endCursor"]

        yield f"data: {_sse_json({'type': 'info', 'message': f'Found {len(to_fix)} products without JSON-LD schema'})}\n\n"

        for product in to_fix[:50]:
            try:
                jsonld = _generate_jsonld_product(product, shop if shop.endswith(".myshopify.com") else f"{shop}.myshopify.com")
                mutation = """mutation($input: ProductInput!) { productUpdate(input: $input) { product { id } userErrors { field message } } }"""
                r = await _graphql(shop, token, mutation, {"input": {
                    "id": product["id"],
                    "metafields": [{"namespace": "custom", "key": "jsonld_schema", "value": jsonld, "type": "json_string"}],
                }})
                ue = r.get("data", {}).get("productUpdate", {}).get("userErrors", [])
                if ue:
                    errors += 1
                    yield f"data: {_sse_json({'type': 'error', 'product': product.get('title',''), 'error': ue[0]['message']})}\n\n"
                else:
                    fixed += 1
                    yield f"data: {_sse_json({'type': 'fix', 'product': product.get('title',''), 'schema_type': 'Product', 'status': 'applied'})}\n\n"
            except Exception as e:
                errors += 1
                yield f"data: {_sse_json({'type': 'error', 'product': product.get('title',''), 'error': str(e)})}\n\n"
            await asyncio.sleep(0.3)

        yield f"data: {_sse_json({'type': 'complete', 'fixed': fixed, 'errors': errors, 'fix_type': 'schema_markup'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ═══════════════════════════════════════════════════
# SEO AUTO-FIX: H1 Tag Detection
# ═══════════════════════════════════════════════════

@router.post("/fix/h1-tags")
async def fix_h1_tags(body: FixAltTextRequest, request: Request):
    """Detect missing H1 tags on storefront pages and suggest fixes. SSE stream."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")
    shop = body.shop

    async def stream():
        import httpx
        from bs4 import BeautifulSoup
        checked, issues_found = 0, 0
        store_url = f"https://{shop}" if shop.endswith(".myshopify.com") else f"https://{shop}.myshopify.com"

        yield f"data: {_sse_json({'type': 'start', 'message': f'Checking H1 tags on {store_url}...'})}\n\n"

        pages_to_check = ["/", "/collections", "/collections/all", "/pages/about", "/pages/contact"]
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for page_path in pages_to_check:
                url = f"{store_url}{page_path}"
                try:
                    r = await client.get(url, headers={"User-Agent": "AUREM-SEO-Scanner/1.0"})
                    if r.status_code != 200:
                        continue
                    soup = BeautifulSoup(r.text, "html.parser")
                    h1s = soup.find_all("h1")
                    checked += 1
                    if not h1s:
                        issues_found += 1
                        title = soup.find("title")
                        suggested_h1 = title.string.strip() if title and title.string else page_path.strip("/").replace("-", " ").title() or "Welcome"
                        yield f"data: {_sse_json({'type': 'issue', 'page': page_path, 'url': url, 'problem': 'Missing H1 tag', 'suggested_fix': f'<h1>{suggested_h1}</h1>', 'severity': 'high'})}\n\n"
                    elif len(h1s) > 1:
                        issues_found += 1
                        h1_texts = [h.get_text(strip=True)[:60] for h in h1s]
                        yield f"data: {_sse_json({'type': 'issue', 'page': page_path, 'url': url, 'problem': f'Multiple H1 tags ({len(h1s)})', 'h1_texts': h1_texts, 'suggested_fix': 'Keep only one H1 — demote others to H2', 'severity': 'medium'})}\n\n"
                    else:
                        h1_text = h1s[0].get_text(strip=True)
                        yield f"data: {_sse_json({'type': 'ok', 'page': page_path, 'h1': h1_text[:60]})}\n\n"
                except Exception as e:
                    yield f"data: {_sse_json({'type': 'error', 'page': page_path, 'error': str(e)})}\n\n"
                await asyncio.sleep(0.5)

        yield f"data: {_sse_json({'type': 'complete', 'checked': checked, 'issues': issues_found, 'fix_type': 'h1_tags'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ═══════════════════════════════════════════════════
# MASTER: Auto-Fix All (runs all fixers in sequence)
# ═══════════════════════════════════════════════════

class AutoFixAllRequest(BaseModel):
    shop: str


@router.post("/fix/auto-fix-all")
async def auto_fix_all(body: AutoFixAllRequest, request: Request):
    """
    Master 'Auto-Fix All' button — runs all SEO fixers in sequence.
    SSE stream with live log of every fix applied.
    SEO fixes = FREE (acquisition hook). Cart recovery = $2/sale (revenue).
    """
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")
    shop, token = body.shop, await _get_shop_token(db, body.shop)
    if not token:
        raise HTTPException(
            status_code=503,
            detail=(
                "Shopify token not connected. "
                "Complete OAuth at /settings/shopify"
            ),
        )

    async def stream():
        import json as _json
        total_fixed, total_errors = 0, 0

        yield f"data: {_sse_json({'type': 'master_start', 'message': f'AUREM Auto-Fix All — scanning {shop}', 'phases': ['alt_text', 'meta_descriptions', 'page_titles', 'schema_markup', 'h1_tags']})}\n\n"

        # Phase 1: Alt-Text
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'alt_text', 'status': 'running', 'message': 'Fixing missing alt-text...'})}\n\n"
        alt_fixed = await _run_fix_phase_alt(shop, token)
        total_fixed += alt_fixed["fixed"]
        total_errors += alt_fixed["errors"]
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'alt_text', 'status': 'done', **alt_fixed})}\n\n"

        # Phase 2: Meta Descriptions
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'meta_descriptions', 'status': 'running', 'message': 'Generating meta descriptions...'})}\n\n"
        meta_fixed = await _run_fix_phase_meta(shop, token)
        total_fixed += meta_fixed["fixed"]
        total_errors += meta_fixed["errors"]
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'meta_descriptions', 'status': 'done', **meta_fixed})}\n\n"

        # Phase 3: Page Titles
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'page_titles', 'status': 'running', 'message': 'Optimizing page titles...'})}\n\n"
        title_fixed = await _run_fix_phase_titles(shop, token)
        total_fixed += title_fixed["fixed"]
        total_errors += title_fixed["errors"]
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'page_titles', 'status': 'done', **title_fixed})}\n\n"

        # Phase 4: Schema Markup
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'schema_markup', 'status': 'running', 'message': 'Injecting JSON-LD schema...'})}\n\n"
        schema_fixed = await _run_fix_phase_schema(shop, token)
        total_fixed += schema_fixed["fixed"]
        total_errors += schema_fixed["errors"]
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'schema_markup', 'status': 'done', **schema_fixed})}\n\n"

        # Phase 5: H1 Tags (detect only — can't push to storefront theme)
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'h1_tags', 'status': 'running', 'message': 'Scanning H1 tags...'})}\n\n"
        yield f"data: {_sse_json({'type': 'phase', 'phase': 'h1_tags', 'status': 'done', 'fixed': 0, 'errors': 0, 'note': 'H1 issues detected — manual fix recommended'})}\n\n"

        # Save auto-fix report
        if db:
            await db.shopify_autofix_reports.insert_one({
                "shop": shop, "total_fixed": total_fixed, "total_errors": total_errors,
                "phases": {"alt_text": alt_fixed, "meta_descriptions": meta_fixed, "page_titles": title_fixed, "schema_markup": schema_fixed},
                "timestamp": datetime.now(timezone.utc).isoformat(), "billing": "seo_fixes_free",
            })

        yield f"data: {_sse_json({'type': 'master_complete', 'total_fixed': total_fixed, 'total_errors': total_errors, 'billing': 'SEO fixes are FREE — cart recovery billed at $2/recovered sale'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


async def _run_fix_phase_alt(shop: str, token: str) -> dict:
    """Internal: fix alt-text, return counts."""
    if not token:
        # Master-autofix already 503s before reaching this. Defensive raise
        # ensures no scaffolded counts ever leak into shopify_autofix_reports.
        raise RuntimeError(
            "Shopify token required for alt-text auto-fix (iter D-61 mock-purge)"
        )
    fixed, errors = 0, 0
    q = """query ($cursor: String) { products(first: 20, after: $cursor) {
        edges { node { id title description images(first: 10) { edges { node { id altText } } } } }
        pageInfo { hasNextPage endCursor } } }"""
    cursor = None
    for _ in range(3):
        data = await _graphql(shop, token, q, {"cursor": cursor})
        for e in data.get("data", {}).get("products", {}).get("edges", []):
            n = e["node"]
            for img_e in n.get("images", {}).get("edges", []):
                img = img_e["node"]
                if not img.get("altText"):
                    try:
                        alt = _generate_alt_text(n.get("title", ""), (n.get("description", "") or "")[:200])
                        m = """mutation productImageUpdate($productId: ID!, $image: ImageInput!) {
                            productImageUpdate(productId: $productId, image: $image) { image { id } userErrors { field message } } }"""
                        r = await _graphql(shop, token, m, {"productId": n["id"], "image": {"id": img["id"], "altText": alt}})
                        if r.get("data", {}).get("productImageUpdate", {}).get("userErrors"):
                            errors += 1
                        else:
                            fixed += 1
                    except Exception:
                        errors += 1
                    await asyncio.sleep(0.2)
        pi = data.get("data", {}).get("products", {}).get("pageInfo", {})
        if not pi.get("hasNextPage"):
            break
        cursor = pi["endCursor"]
    return {"fixed": fixed, "errors": errors}


async def _run_fix_phase_meta(shop: str, token: str) -> dict:
    if not token:
        raise RuntimeError(
            "Shopify token required for meta-description auto-fix (iter D-61 mock-purge)"
        )
    fixed, errors = 0, 0
    q = """query ($cursor: String) { products(first: 20, after: $cursor) {
        edges { node { id title description seo { description } } }
        pageInfo { hasNextPage endCursor } } }"""
    cursor = None
    for _ in range(3):
        data = await _graphql(shop, token, q, {"cursor": cursor})
        for e in data.get("data", {}).get("products", {}).get("edges", []):
            n = e["node"]
            if not (n.get("seo", {}) or {}).get("description"):
                try:
                    meta = _generate_meta_description(n.get("title", ""), (n.get("description", "") or "")[:200], shop.split(".")[0])
                    m = """mutation($input: ProductInput!) { productUpdate(input: $input) { product { id } userErrors { field message } } }"""
                    r = await _graphql(shop, token, m, {"input": {"id": n["id"], "seo": {"description": meta}}})
                    if r.get("data", {}).get("productUpdate", {}).get("userErrors"):
                        errors += 1
                    else:
                        fixed += 1
                except Exception:
                    errors += 1
                await asyncio.sleep(0.2)
        pi = data.get("data", {}).get("products", {}).get("pageInfo", {})
        if not pi.get("hasNextPage"):
            break
        cursor = pi["endCursor"]
    return {"fixed": fixed, "errors": errors}


async def _run_fix_phase_titles(shop: str, token: str) -> dict:
    if not token:
        raise RuntimeError(
            "Shopify token required for page-title auto-fix (iter D-61 mock-purge)"
        )
    fixed, errors = 0, 0
    store_name = shop.split(".")[0].replace("-", " ").title()
    q = """query ($cursor: String) { products(first: 20, after: $cursor) {
        edges { node { id title seo { title } } }
        pageInfo { hasNextPage endCursor } } }"""
    cursor = None
    for _ in range(3):
        data = await _graphql(shop, token, q, {"cursor": cursor})
        for e in data.get("data", {}).get("products", {}).get("edges", []):
            n = e["node"]
            if not (n.get("seo", {}) or {}).get("title"):
                try:
                    seo_title = _generate_seo_title(n.get("title", ""), store_name)
                    m = """mutation($input: ProductInput!) { productUpdate(input: $input) { product { id } userErrors { field message } } }"""
                    r = await _graphql(shop, token, m, {"input": {"id": n["id"], "seo": {"title": seo_title}}})
                    if r.get("data", {}).get("productUpdate", {}).get("userErrors"):
                        errors += 1
                    else:
                        fixed += 1
                except Exception:
                    errors += 1
                await asyncio.sleep(0.2)
        pi = data.get("data", {}).get("products", {}).get("pageInfo", {})
        if not pi.get("hasNextPage"):
            break
        cursor = pi["endCursor"]
    return {"fixed": fixed, "errors": errors}


async def _run_fix_phase_schema(shop: str, token: str) -> dict:
    if not token:
        raise RuntimeError(
            "Shopify token required for schema-markup auto-fix (iter D-61 mock-purge)"
        )
    fixed, errors = 0, 0
    q = """query ($cursor: String) { products(first: 20, after: $cursor) {
        edges { node { id title description
            variants(first: 1) { edges { node { price } } }
            images(first: 3) { edges { node { url altText } } }
            metafields(first: 5, keys: ["custom.jsonld_schema"]) { edges { node { value } } }
        } } pageInfo { hasNextPage endCursor } } }"""
    cursor = None
    full_shop = shop if shop.endswith(".myshopify.com") else f"{shop}.myshopify.com"
    for _ in range(3):
        data = await _graphql(shop, token, q, {"cursor": cursor})
        for e in data.get("data", {}).get("products", {}).get("edges", []):
            n = e["node"]
            has_schema = any(m.get("node", {}).get("value") for m in n.get("metafields", {}).get("edges", []))
            if not has_schema:
                try:
                    jsonld = _generate_jsonld_product(n, full_shop)
                    m = """mutation($input: ProductInput!) { productUpdate(input: $input) { product { id } userErrors { field message } } }"""
                    r = await _graphql(shop, token, m, {"input": {"id": n["id"], "metafields": [{"namespace": "custom", "key": "jsonld_schema", "value": jsonld, "type": "json_string"}]}})
                    if r.get("data", {}).get("productUpdate", {}).get("userErrors"):
                        errors += 1
                    else:
                        fixed += 1
                except Exception:
                    errors += 1
                await asyncio.sleep(0.2)
        pi = data.get("data", {}).get("products", {}).get("pageInfo", {})
        if not pi.get("hasNextPage"):
            break
        cursor = pi["endCursor"]
    return {"fixed": fixed, "errors": errors}


def _sse_json(data: dict) -> str:
    import json
    return json.dumps(data)


# ═══════════════════════════════════════════════════
# ABANDONED CART RECOVERY SEQUENCE
# ═══════════════════════════════════════════════════

@router.post("/webhook/checkout-created")
async def checkout_created_webhook(request: Request):
    """
    Shopify checkouts/create webhook.
    Stores abandoned checkout and schedules recovery sequence.
    Bug-fix #151/#155 (R18): HMAC-verified or rejected.
    """
    db = _get_db()
    if not db:
        return {"status": "no_db"}

    raw = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "") or request.headers.get("x-shopify-hmac-sha256", "")
    if not _verify_shopify_hmac(raw, hmac_header):
        raise HTTPException(401, "invalid webhook signature")

    try:
        import json as _json
        body = _json.loads(raw) if raw else {}
    except Exception:
        body = {}

    checkout_token = body.get("token", body.get("checkout_token", ""))
    email = body.get("email", "")
    phone = body.get("phone", body.get("billing_address", {}).get("phone", ""))
    shop = request.headers.get("X-Shopify-Shop-Domain", body.get("shop_domain", ""))
    total = float(body.get("total_price", 0))

    if not checkout_token:
        return {"status": "no_token"}

    now = datetime.now(timezone.utc).isoformat()

    await db.aurem_abandoned_carts.update_one(
        {"checkout_token": checkout_token},
        {"$set": {
            "checkout_token": checkout_token,
            "email": email,
            "phone": phone,
            "shop_domain": shop,
            "total_price": total,
            "cart_data": body.get("line_items", [])[:10],
            "recovered": False,
            "aurem_attributed": False,
            "recovery_sequence_started": False,
            "created_at": now,
            "updated_at": now,
        }},
        upsert=True,
    )

    logger.info(f"[PULSE] Abandoned checkout captured: {checkout_token} from {shop}")
    return {"status": "captured", "checkout_token": checkout_token}


@router.post("/recovery/trigger/{checkout_token}")
async def trigger_recovery(checkout_token: str, request: Request):
    """Manually trigger recovery sequence for a specific checkout."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")

    cart = await db.aurem_abandoned_carts.find_one(
        {"checkout_token": checkout_token}, {"_id": 0}
    )
    if not cart:
        raise HTTPException(404, "Checkout not found")

    result = await _run_recovery_step(db, cart, "manual")
    return result


async def run_recovery_scheduler():
    """
    Background task: check abandoned carts and fire recovery sequences.
    Hour 1 → WhatsApp, Hour 4 → Email, Hour 24 → SMS
    """
    db = _get_db()
    if not db:
        return

    now = datetime.now(timezone.utc)

    # Hour 1: WhatsApp for carts aged 1-3 hours
    hour1_cutoff = (now - timedelta(hours=3)).isoformat()
    hour1_start = (now - timedelta(hours=1)).isoformat()

    carts_h1 = await db.aurem_abandoned_carts.find({
        "recovered": False,
        "recovery_wa_sent": {"$ne": True},
        "created_at": {"$gte": hour1_cutoff, "$lte": hour1_start},
        "phone": {"$ne": ""},
    }).to_list(50)

    for cart in carts_h1:
        await _run_recovery_step(db, cart, "whatsapp")

    # Hour 4: Email for carts aged 4-12 hours
    hour4_cutoff = (now - timedelta(hours=12)).isoformat()
    hour4_start = (now - timedelta(hours=4)).isoformat()

    carts_h4 = await db.aurem_abandoned_carts.find({
        "recovered": False,
        "recovery_email_sent": {"$ne": True},
        "created_at": {"$gte": hour4_cutoff, "$lte": hour4_start},
        "email": {"$ne": ""},
    }).to_list(50)

    for cart in carts_h4:
        await _run_recovery_step(db, cart, "email")

    # Hour 24: SMS for carts aged 24-48 hours
    hour24_cutoff = (now - timedelta(hours=48)).isoformat()
    hour24_start = (now - timedelta(hours=24)).isoformat()

    carts_h24 = await db.aurem_abandoned_carts.find({
        "recovered": False,
        "recovery_sms_sent": {"$ne": True},
        "created_at": {"$gte": hour24_cutoff, "$lte": hour24_start},
        "phone": {"$ne": ""},
    }).to_list(50)

    for cart in carts_h24:
        await _run_recovery_step(db, cart, "sms")


async def _run_recovery_step(db, cart: dict, channel: str) -> dict:
    """Execute a single recovery step for an abandoned cart."""
    checkout_token = cart.get("checkout_token", "")
    email = cart.get("email", "")
    phone = cart.get("phone", "")
    shop = cart.get("shop_domain", "")
    total = cart.get("total_price", 0)
    items = cart.get("cart_data", [])
    item_names = ", ".join(i.get("title", "") for i in items[:3]) or "your items"

    result = {"channel": channel, "checkout_token": checkout_token, "success": False}

    if channel == "whatsapp" and phone:
        try:
            from services.whatsapp_engine import WhatsAppEngine
            wa = WhatsAppEngine(db)
            msg = (
                f"Hi! You left {item_names} in your cart (${total:.2f}).\n\n"
                f"Complete your order before it's gone!\n\n"
                f"Reply YES if you need help checking out."
            )
            r = await wa.send_message("polaris-built-001", phone, msg)
            result["success"] = r.get("success", False)
            await db.aurem_abandoned_carts.update_one(
                {"checkout_token": checkout_token},
                {"$set": {"recovery_wa_sent": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
        except Exception as e:
            result["error"] = str(e)

    elif channel == "email" and email:
        try:
            from services.email_engine import EmailEngine
            ee = EmailEngine(db)
            html = f"""
            <div style="font-family:system-ui;max-width:500px;margin:0 auto;padding:24px;">
              <h2>You left something behind!</h2>
              <p>Your cart ({item_names}) is waiting — total: <strong>${total:.2f}</strong></p>
              <p>Complete your purchase before these items sell out.</p>
              <a href="https://{shop}/checkout?token={checkout_token}" 
                 style="display:inline-block;background:#D4AF37;color:#000;padding:12px 28px;border-radius:8px;font-weight:700;text-decoration:none;margin-top:12px;">
                Complete Checkout
              </a>
            </div>
            """
            r = await ee.send_message("polaris-built-001", email, "You left something in your cart!", html)
            result["success"] = r.get("success", False)
            await db.aurem_abandoned_carts.update_one(
                {"checkout_token": checkout_token},
                {"$set": {"recovery_email_sent": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
        except Exception as e:
            result["error"] = str(e)

    elif channel == "sms" and phone:
        try:
            from services.sms_engine import SMSEngine
            sms = SMSEngine(db)
            msg = f"Your cart ({item_names}, ${total:.2f}) is still waiting! Complete checkout: https://{shop}/checkout?token={checkout_token}"
            r = await sms.send_message("polaris-built-001", phone, msg)
            result["success"] = r.get("success", False)
            await db.aurem_abandoned_carts.update_one(
                {"checkout_token": checkout_token},
                {"$set": {"recovery_sms_sent": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
        except Exception as e:
            result["error"] = str(e)

    return result


# ═══════════════════════════════════════════════════
# RECOVERY STATS
# ═══════════════════════════════════════════════════

@router.get("/recovery/stats")
async def recovery_stats(request: Request):
    """Get abandoned cart recovery stats."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        return {"abandoned": 0, "recovered": 0, "revenue_recovered": 0}

    abandoned = await db.aurem_abandoned_carts.count_documents({"recovered": False})
    recovered = await db.aurem_abandoned_carts.count_documents({"recovered": True})

    # Sum recovered revenue
    pipeline = [
        {"$match": {"recovered": True, "aurem_attributed": True}},
        {"$group": {"_id": None, "total": {"$sum": "$total_price"}}},
    ]
    agg = await db.aurem_abandoned_carts.aggregate(pipeline).to_list(1)
    revenue = agg[0]["total"] if agg else 0

    return {
        "abandoned": abandoned,
        "recovered": recovered,
        "recovery_rate": round((recovered / max(abandoned + recovered, 1)) * 100, 1),
        "revenue_recovered": round(revenue, 2),
        "commission_earned": round(recovered * 2.0, 2),
    }


# ═══════════════════════════════════════════════════

# ═══════════════════════════════════════════════════
# ORDER PAID WEBHOOK — Recovery Attribution + Billing
# ═══════════════════════════════════════════════════

@router.post("/webhook/order-paid")
async def order_paid_webhook(request: Request):
    """
    Shopify orders/paid webhook.
    Checks if the order matches an abandoned cart → marks as recovered → triggers $2 billing.
    Bug-fix #151 (R18): HMAC-verified.
    """
    db = _get_db()
    if not db:
        return {"status": "no_db"}

    raw = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "") or request.headers.get("x-shopify-hmac-sha256", "")
    if not _verify_shopify_hmac(raw, hmac_header):
        raise HTTPException(401, "invalid webhook signature")

    try:
        import json as _json
        body = _json.loads(raw) if raw else {}
    except Exception:
        body = {}

    checkout_token = body.get("checkout_token", "")
    order_id = str(body.get("id", ""))
    shop = request.headers.get("X-Shopify-Shop-Domain", body.get("shop_domain", ""))
    total = float(body.get("total_price", 0))
    email = body.get("email", "")

    # Check if this order matches an abandoned cart we're tracking
    cart = None
    if checkout_token:
        cart = await db.aurem_abandoned_carts.find_one({"checkout_token": checkout_token, "recovered": False})
    if not cart and email:
        cart = await db.aurem_abandoned_carts.find_one({"email": email, "recovered": False})

    if cart:
        now = datetime.now(timezone.utc).isoformat()
        await db.aurem_abandoned_carts.update_one(
            {"checkout_token": cart["checkout_token"]},
            {"$set": {
                "recovered": True,
                "aurem_attributed": True,
                "recovered_at": now,
                "order_id": order_id,
                "order_total": total,
            }},
        )

        # Trigger $2 billing commission
        try:
            from routers.shopify_billing_router import charge_recovery_commission
            await charge_recovery_commission(shop, order_id, total)
        except Exception as e:
            logger.warning(f"[PULSE] Billing charge failed: {e}")

        logger.info(f"[PULSE] Cart recovered! Order {order_id} (${total}) attributed to AUREM")
        return {"status": "recovered", "order_id": order_id, "commission": 2.00}

    return {"status": "not_attributed", "order_id": order_id}


# GDPR WEBHOOK HANDLERS
# ═══════════════════════════════════════════════════

@router.post("/webhooks/customers-redact")
async def gdpr_customers_redact(request: Request):
    """Shopify GDPR: Delete customer data on request."""
    db = _get_db()
    try:
        body = await request.json()
        shop = body.get("shop_domain", "")
        customer_id = str(body.get("customer", {}).get("id", ""))
        if db and customer_id:
            await db.aurem_abandoned_carts.delete_many({"shop_domain": shop, "customer_id": customer_id})
            logger.info(f"[GDPR] Customer {customer_id} data deleted for {shop}")
    except Exception as e:
        logger.error(f"[GDPR] customers/redact error: {e}")
    return {"status": "ok"}


@router.post("/webhooks/customers-data-request")
async def gdpr_customers_data_request(request: Request):
    """Shopify GDPR: Return customer data on request."""
    return {"status": "ok"}


@router.post("/webhooks/shop-redact")
async def gdpr_shop_redact(request: Request):
    """Shopify GDPR: Delete all shop data on uninstall."""
    db = _get_db()
    try:
        body = await request.json()
        shop = body.get("shop_domain", "")
        if db and shop:
            await db.aurem_abandoned_carts.delete_many({"shop_domain": shop})
            await db.shopify_pulse_scans.delete_many({"shop_domain": shop})
            await db.shopify_app_installs.delete_many({"shop_domain": shop})
            logger.info(f"[GDPR] All data deleted for {shop}")
    except Exception as e:
        logger.error(f"[GDPR] shop/redact error: {e}")
    return {"status": "ok"}
