"""
Smart Onboarding Service — P1
==============================
Auto-detects everything about a customer's business so onboarding becomes
a one-click confirmation instead of a form-filling chore.

Flow:
    detect_everything(business_name, website_url, city) -> dict
    start_aurem(tenant_email, form_data) -> dict
"""
import os
import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List
import httpx

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# WEBSITE PLATFORM DETECTION
# ═══════════════════════════════════════════════════════════════

PLATFORM_SIGNATURES = [
    ("shopify",     [r"cdn\.shopify\.com", r"myshopify\.com", r"Shopify\.shop", r"shopify-section"]),
    ("wordpress",   [r"/wp-content/", r"/wp-includes/", r"wp-json", r"wordpress"]),
    ("wix",         [r"wix\.com", r"wixstatic\.com", r"static\.parastorage\.com"]),
    ("squarespace", [r"squarespace\.com", r"static1\.squarespace\.com"]),
    ("webflow",     [r"assets\.website-files\.com", r"webflow\.com", r"data-wf-page"]),
    ("framer",      [r"framerusercontent\.com", r"framer\.com"]),
    ("ghost",       [r"ghost\.io", r"ghost-assets", r"content=\"Ghost"]),
    ("bigcommerce", [r"bigcommerce\.com", r"stencil-utils"]),
    ("woocommerce", [r"woocommerce", r"wc-ajax"]),
    ("react",       [r"/static/js/main\.[a-f0-9]+\.js", r"react-dom"]),
    ("nextjs",      [r"/_next/static/", r"__NEXT_DATA__"]),
    ("gatsby",      [r"__gatsby", r"gatsby-image"]),
]


async def _fetch_html(url: str, timeout: float = 12.0) -> Optional[str]:
    """Fetch HTML; returns None on any error."""
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                      headers={"User-Agent": "AUREM-Onboarding/1.0 (+https://aurem.live)"}) as c:
            r = await c.get(url)
            if r.status_code < 400:
                return r.text
    except Exception as e:
        logger.debug(f"[ONBOARD] Fetch failed for {url}: {e}")
    return None


async def detect_website_platform(url: str) -> Dict:
    """Return {platform: str, confidence: 'high'|'medium'|'none', exists: bool, screenshot_hint: str}."""
    html = await _fetch_html(url)
    if html is None:
        return {"platform": "no_website", "confidence": "high", "exists": False, "html_size": 0}

    html_lower = html.lower()
    # Multi-pattern scoring
    for plat, patterns in PLATFORM_SIGNATURES:
        hits = sum(1 for p in patterns if re.search(p, html_lower, re.IGNORECASE))
        if hits >= 2:
            return {"platform": plat, "confidence": "high", "exists": True, "html_size": len(html)}
        if hits == 1:
            return {"platform": plat, "confidence": "medium", "exists": True, "html_size": len(html)}

    return {"platform": "custom", "confidence": "medium", "exists": True, "html_size": len(html)}


# ═══════════════════════════════════════════════════════════════
# SOCIAL MEDIA DISCOVERY
# ═══════════════════════════════════════════════════════════════

SOCIAL_PATTERNS = {
    "facebook":  [r"facebook\.com/([A-Za-z0-9.\-]+)", r"fb\.com/([A-Za-z0-9.\-]+)"],
    "instagram": [r"instagram\.com/([A-Za-z0-9._\-]+)"],
    "twitter":   [r"twitter\.com/([A-Za-z0-9_]+)", r"x\.com/([A-Za-z0-9_]+)"],
    "linkedin":  [r"linkedin\.com/company/([A-Za-z0-9.\-]+)", r"linkedin\.com/in/([A-Za-z0-9.\-]+)"],
    "tiktok":    [r"tiktok\.com/@([A-Za-z0-9._]+)"],
    "youtube":   [r"youtube\.com/(?:channel/|user/|@)([A-Za-z0-9._\-]+)"],
    "pinterest": [r"pinterest\.com/([A-Za-z0-9_\-]+)"],
}

# Blacklist: share buttons, sharer links, etc. that aren't the business's own profile
SOCIAL_BLACKLIST = {"sharer", "share", "intent", "plugins", "dialog", "tr", "events"}


async def find_social_media(business_name: str, website_url: Optional[str]) -> Dict:
    """Scan website HTML for social links; return dict {platform: url}."""
    socials: Dict[str, str] = {}
    if website_url:
        html = await _fetch_html(website_url)
        if html:
            for platform, patterns in SOCIAL_PATTERNS.items():
                for pat in patterns:
                    m = re.findall(pat, html, re.IGNORECASE)
                    candidates = [h for h in m if h.lower() not in SOCIAL_BLACKLIST and len(h) > 1]
                    if candidates:
                        # Take the most-mentioned handle
                        from collections import Counter
                        top = Counter(candidates).most_common(1)[0][0]
                        socials[platform] = f"https://{platform if platform != 'twitter' else 'x'}.com/{top.lstrip('@')}"
                        break
    return socials


# ═══════════════════════════════════════════════════════════════
# GOOGLE PLACES ENRICHMENT
# ═══════════════════════════════════════════════════════════════

async def get_google_places_data(business_name: str, city: str = "") -> Dict:
    """Lookup basic business info via Places Text Search (if GOOGLE_PLACES_API_KEY set)."""
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not api_key or not business_name:
        return {"available": False}

    query = f"{business_name} {city}".strip()
    try:
        async with httpx.AsyncClient(timeout=12.0) as c:
            # Text search
            r = await c.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={"query": query, "key": api_key},
            )
            if r.status_code != 200:
                return {"available": False}
            results = r.json().get("results") or []
            if not results:
                return {"available": True, "found": False}

            top = results[0]
            place_id = top.get("place_id")

            # Details
            d = await c.get(
                "https://maps.googleapis.com/maps/api/place/details/json",
                params={
                    "place_id": place_id,
                    "fields": "name,formatted_address,formatted_phone_number,opening_hours,rating,user_ratings_total,website,types",
                    "key": api_key,
                },
            )
            result = (d.json() or {}).get("result") or {}
            return {
                "available": True,
                "found": True,
                "place_id": place_id,
                "name": result.get("name", ""),
                "address": result.get("formatted_address", ""),
                "phone": result.get("formatted_phone_number", ""),
                "rating": result.get("rating"),
                "review_count": result.get("user_ratings_total", 0),
                "website": result.get("website", ""),
                "hours": (result.get("opening_hours") or {}).get("weekday_text") or [],
                "categories": result.get("types", []),
            }
    except Exception as e:
        logger.warning(f"[ONBOARD] Places failed: {e}")
        return {"available": False}


# ═══════════════════════════════════════════════════════════════
# MAIN: DETECT EVERYTHING (parallel)
# ═══════════════════════════════════════════════════════════════

async def detect_everything(business_name: str, website_url: str, city: str = "") -> Dict:
    """Parallel fan-out of all detection jobs. Returns a smart-form-ready dict."""
    platform_task = asyncio.create_task(detect_website_platform(website_url))
    socials_task = asyncio.create_task(find_social_media(business_name, website_url))
    places_task = asyncio.create_task(get_google_places_data(business_name, city))

    platform = await platform_task
    socials = await socials_task
    places = await places_task

    # Recommend connection method based on platform
    platform_name = platform.get("platform", "custom")
    if platform_name == "wordpress":
        recommended_connection = "wordpress_plugin"
    elif platform_name == "shopify":
        recommended_connection = "shopify_app"
    elif platform_name in ("wix", "squarespace"):
        recommended_connection = "manual_code"
    elif platform_name == "no_website":
        recommended_connection = "aurem_free_site"
    else:
        recommended_connection = "gtm"  # Google Tag Manager fallback

    return {
        "business_name": business_name,
        "website": {
            "url": website_url,
            "exists": platform.get("exists", False),
            "platform": platform_name,
            "confidence": platform.get("confidence", "none"),
        },
        "social_media": socials,
        "google_places": places,
        "recommended_connection": recommended_connection,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# START AUREM — single button to kick everything off
# ═══════════════════════════════════════════════════════════════

async def start_aurem(db, tenant_email: str, form_data: Dict) -> Dict:
    """Kick off all subsystems based on confirmed form data."""
    email = tenant_email.lower()
    now = datetime.now(timezone.utc).isoformat()
    user = await db.platform_users.find_one({"email": email}, {"_id": 0}) \
        or await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        return {"success": False, "error": "user_not_found"}

    tenant_id = user.get("id") or user.get("tenant_id") or email
    business_name = form_data.get("business_name") or user.get("company_name") or ""
    platform = form_data.get("platform", "custom")
    website_url = form_data.get("website_url", "")
    socials = form_data.get("social_media", {})  # {facebook: url, instagram: url, ...}
    connection_method = form_data.get("connection_method", "gtm")

    actions = []

    # 1. Website connection
    try:
        if platform == "wordpress" or connection_method == "wordpress_plugin":
            from routers.whatsapp_alerts import send_whatsapp
            phone = user.get("phone") or ""
            if phone:
                msg = ("🎉 AUREM is connecting to your WordPress site!\n\n"
                       f"Install this plugin: https://aurem.live/wp-plugin\n"
                       f"Activation key: {form_data.get('api_key', '')}\n\n"
                       "2-minute setup. Reply STOP to unsubscribe.")
                try: await send_whatsapp(phone, msg)
                except Exception: pass
            actions.append("wordpress_plugin_sent")
        elif platform == "no_website" or connection_method == "aurem_free_site":
            slug = re.sub(r'[^a-z0-9-]', '-', business_name.lower())[:40].strip('-') or tenant_id
            free_url = f"https://aurem.live/{slug}"
            await db.customer_sites.update_one(
                {"email": email},
                {"$set": {
                    "email": email, "url": free_url, "platform": "aurem_hosted",
                    "auto_generated": True, "created_at": now,
                }}, upsert=True,
            )
            actions.append(f"free_site_queued:{free_url}")
        elif connection_method == "gtm":
            actions.append("gtm_snippet_ready")
        elif connection_method == "manual_code":
            actions.append("manual_snippet_ready")
    except Exception as e:
        logger.warning(f"[ONBOARD] Website connect failed: {e}")

    # 2. Social connections (queue for Postiz / manual)
    if socials:
        await db.customer_social.update_one(
            {"email": email},
            {"$set": {
                "email": email, "accounts": [{"platform": k, "url": v} for k, v in socials.items() if v],
                "enabled": False, "updated_at": now,
            }}, upsert=True,
        )
        actions.append(f"socials_queued:{len(socials)}")

    # 3. Google Places — store place_id for reviews cron
    place = form_data.get("google_places") or {}
    if place.get("place_id"):
        await db.aurem_workspaces.update_one(
            {"owner_email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}},
            {"$set": {
                "google_place_id": place["place_id"],
                "google_rating": place.get("rating"),
                "google_total_reviews": place.get("review_count", 0),
            }}, upsert=False,
        )
        actions.append("places_wired")

    # 4. Mark smart-onboarding complete (separate flag from first-login wizard_complete)
    await db.platform_users.update_one(
        {"email": email},
        {"$set": {
            "smart_onboarding_complete": True,
            "smart_onboarded_at": now,
            "onboarded_platform": platform,
        }},
    )

    # 4a. Invalidate cached customer-context (Iter 206)
    try:
        from services.aurem_cache import cache_delete
        await cache_delete(f"ctx:{email}")
    except Exception:
        pass

    # 5. Log to audit
    try:
        await db.audit_chain.insert_one({
            "event_type": "customer.onboarded",
            "email": email,
            "tenant_id": tenant_id,
            "actions": actions,
            "form_data": {k: v for k, v in form_data.items() if k != "api_key"},
            "timestamp": now,
        })
    except Exception:
        pass

    # 6. Welcome WhatsApp
    try:
        from routers.whatsapp_alerts import send_whatsapp
        phone = user.get("phone") or ""
        if phone:
            msg = (f"🎉 Welcome to AUREM, {business_name}!\n\n"
                   "Your AI agents are live:\n"
                   "✅ Scanner running nightly\n"
                   "✅ Review requests on autopilot\n"
                   "✅ Morning briefs at 8 AM\n\n"
                   "Dashboard: https://aurem.live/my\n\n"
                   "Reply STOP to unsubscribe.")
            await send_whatsapp(phone, msg)
            actions.append("welcome_whatsapp_sent")
    except Exception as e:
        logger.debug(f"[ONBOARD] Welcome WA failed: {e}")

    return {"success": True, "tenant_id": tenant_id, "actions": actions}
