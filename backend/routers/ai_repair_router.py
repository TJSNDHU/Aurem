"""
ORA AI Repair Router — Autonomous SEO + Accessibility Fix Engine
Priority 2: SEO Auto-Fix via Gemini 3.1 Pro
Priority 3: Accessibility Vision via Nano Banana 2
All fixes stored in 'pending_approval' state before deployment.
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import httpx
import asyncio
import json
import os
import base64
import logging
import secrets
from bs4 import BeautifulSoup

router = APIRouter()
logger = logging.getLogger(__name__)

_stripe_checkout = None
def get_stripe_checkout():
    global _stripe_checkout
    if _stripe_checkout is None:
        try:
            from emergentintegrations.payments.stripe.checkout import (
                StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
            )
            _stripe_checkout = {
                'StripeCheckout': StripeCheckout,
                'CheckoutSessionResponse': CheckoutSessionResponse,
                'CheckoutStatusResponse': CheckoutStatusResponse,
                'CheckoutSessionRequest': CheckoutSessionRequest
            }
        except ImportError:
            _stripe_checkout = {}
    return _stripe_checkout

_llm_chat = None
def get_llm_chat():
    global _llm_chat
    if _llm_chat is None:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            _llm_chat = {'LlmChat': LlmChat, 'UserMessage': UserMessage}
        except ImportError:
            _llm_chat = {}
    return _llm_chat

# ─── LLM Setup ─────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(override=False)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    LLM_AVAILABLE = bool(EMERGENT_LLM_KEY)
except ImportError:
    LLM_AVAILABLE = False
    logger.error("emergentintegrations not installed — AI repair disabled")


# ─── Request / Response Models ──────────────────────────────────

async def _auto_double_lock(site_url: str, user_id: str, deploy_id: str = None):
    """Fire-and-forget: trigger Auto Double-Lock after deploy."""
    try:
        from services.auto_double_lock import auto_trigger_origin_write
        await auto_trigger_origin_write(site_url, user_id, deploy_id)
    except Exception as e:
        logger.warning(f"[AutoDoubleLock] Failed for {site_url}: {e}")


class RepairGenerateRequest(BaseModel):
    url: str

class FixApprovalRequest(BaseModel):
    fix_id: str

class RepairScoresResponse(BaseModel):
    url: str
    seo_before: int
    seo_after: int
    accessibility_before: int
    accessibility_after: int
    pending_fixes: int
    approved_fixes: int


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


def _require_admin_id(authorization: str) -> str:
    """Admin-only variant: rejects anonymous, non-admin, or invalid tokens."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        payload = jwt.decode(
            authorization.replace("Bearer ", ""),
            os.getenv("JWT_SECRET"),
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = (payload.get("role") or "").lower()
    is_admin = bool(payload.get("is_admin") or payload.get("is_super_admin"))
    if role not in ("admin", "super_admin") and not is_admin:
        raise HTTPException(403, "Admin role required")
    return payload.get("user_id") or payload.get("email") or "admin"


async def _fetch_html(url: str) -> str:
    """Fetch HTML content from a URL using resilient fetch (handles SSL/DNS)."""
    from utils.resilient_fetch import resilient_fetch
    result = await resilient_fetch(url)
    if result.success and result.response is not None:
        return result.text
    # Build meaningful error message
    if result.dns_error:
        raise Exception(f"Website unreachable — possible DNS issue: {result.dns_error_detail}")
    if result.ssl_error:
        raise Exception(f"SSL certificate error (scan will proceed): {result.ssl_error_detail}")
    raise Exception("Website unreachable after trying all protocols")


async def _fetch_image_base64(img_url: str) -> Optional[str]:
    """Download an image and return its base64 encoding."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(img_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"})
            if resp.status_code == 200 and len(resp.content) < 5_000_000:
                return base64.b64encode(resp.content).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to fetch image {img_url[:80]}: {e}")
    return None


def _normalize_url(raw: str) -> str:
    if not raw.startswith("http"):
        return "https://" + raw
    return raw


def _resolve_img_url(src: str, base_url: str) -> str:
    """Resolve relative image URLs to absolute."""
    if not src:
        return ""
    if src.startswith("http"):
        return src
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{src}"
    return base_url.rstrip("/") + "/" + src


# ══════════════════════════════════════════════════════════════════
# PRIORITY 2 — SEO AUTO-FIX (Gemini 3.1 Pro)
# ══════════════════════════════════════════════════════════════════

@router.post("/api/repair/seo/generate")
async def generate_seo_fixes(body: RepairGenerateRequest, authorization: str = Header(None)):
    """
    Analyze a URL for SEO issues and use Gemini 3.1 Pro to generate
    optimized H1, meta description, title, and OG tags.
    All fixes are stored as 'pending_approval'.
    """
    if not LLM_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI engine unavailable — EMERGENT_LLM_KEY not set")

    from server import db
    user_id = _get_user_id(authorization)
    url = _normalize_url(body.url)

    # Archive old pending SEO fixes for this URL so re-scan shows fresh results
    await db.repair_fixes.update_many(
        {"user_id": user_id, "scan_url": url, "category": "seo", "status": "pending_approval"},
        {"$set": {"status": "archived", "archived_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Generate a scan session id to group fixes from this scan
    scan_id = f"scan_{secrets.token_urlsafe(12)}"

    # 1. Fetch and parse the page
    try:
        html = await _fetch_html(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}")

    soup = BeautifulSoup(html, "html.parser")

    # Check which fix_types were already approved/deployed for this URL
    prev_fixed = set()
    prev_cursor = db.repair_fixes.find(
        {"user_id": user_id, "scan_url": url, "category": "seo", "status": {"$in": ["approved", "deployed"]}},
        {"_id": 0, "fix_type": 1}
    )
    async for pf in prev_cursor:
        prev_fixed.add(pf.get("fix_type"))

    # 2. Detect SEO issues
    page_text = soup.get_text(separator=" ", strip=True)[:3000]

    # Title
    title_tag = soup.find("title")
    current_title = title_tag.string.strip() if title_tag and title_tag.string else ""
    has_title_issue = (not current_title or len(current_title) < 20 or len(current_title) > 65) and "title" not in prev_fixed

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    current_meta = meta_desc.get("content", "").strip() if meta_desc else ""
    has_meta_issue = (not current_meta or len(current_meta) < 50) and "meta_description" not in prev_fixed

    # H1
    h1_tags = soup.find_all("h1")
    current_h1 = h1_tags[0].get_text(strip=True) if h1_tags else ""
    has_h1_issue = (len(h1_tags) == 0 or len(h1_tags) > 1) and "h1" not in prev_fixed

    # OG tags
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    has_og_issue = (not og_title or not og_desc) and "og_title" not in prev_fixed and "og_description" not in prev_fixed

    # Count previously fixed items for score improvement
    prev_fixed_count = len(prev_fixed)

    if not any([has_title_issue, has_meta_issue, has_h1_issue, has_og_issue]):
        # Store scan session even with no new issues
        await db.scan_sessions.insert_one({
            "scan_id": scan_id, "user_id": user_id, "scan_url": url,
            "category": "seo", "fixes_count": 0, "previously_fixed": prev_fixed_count,
            "score_before": 95, "score_after": 95,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        return {
            "message": f"No new SEO issues detected — {prev_fixed_count} issues previously fixed!" if prev_fixed_count else "No SEO issues detected — page looks optimized!",
            "url": url,
            "scan_id": scan_id,
            "fixes": [],
            "previously_fixed": prev_fixed_count,
            "seo_score_before": 95,
            "seo_score_after": 95,
        }

    # 3. Call Gemini 3.1 Pro to generate fixes
    prompt = f"""Analyze this webpage and generate SEO-optimized content. URL: {url}

Current page content (first 3000 chars):
{page_text[:2000]}

Current SEO state:
- Title: "{current_title}" (length: {len(current_title)})
- Meta Description: "{current_meta}" (length: {len(current_meta)})
- H1 Tag: "{current_h1}" (count: {len(h1_tags)})
- OG Title: {"present" if og_title else "MISSING"}
- OG Description: {"present" if og_desc else "MISSING"}

Generate optimized replacements ONLY for items that need fixing. Return STRICT JSON (no markdown):
{{
    "title": "Optimized title tag (50-60 chars)" or null if current is fine,
    "meta_description": "Compelling meta description (150-160 chars)" or null,
    "h1": "Clear, keyword-rich H1 heading" or null,
    "og_title": "Social sharing title" or null,
    "og_description": "Social sharing description (max 200 chars)" or null
}}"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"seo_{secrets.token_hex(8)}",
            system_message="You are ORA, an expert SEO optimizer. Return ONLY valid JSON. No markdown fences."
        ).with_model("gemini", "gemini-2.5-flash")

        response = await chat.send_message(UserMessage(text=prompt))

        # Parse JSON from response
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
        ai_fixes = json.loads(clean)
    except json.JSONDecodeError:
        logger.error(f"Gemini returned non-JSON for SEO: {response[:200]}")
        raise HTTPException(status_code=500, detail="AI returned invalid format — please retry")
    except Exception as e:
        logger.error(f"Gemini SEO error: {e}")
        raise HTTPException(status_code=500, detail=f"AI engine error: {str(e)}")

    # 4. Store each fix in DB as pending_approval
    fixes_created = []
    now = datetime.now(timezone.utc).isoformat()

    fix_map = {
        "title": {
            "label": "Page Title Tag",
            "original": current_title,
            "code_template": '<title>{value}</title>',
        },
        "meta_description": {
            "label": "Meta Description",
            "original": current_meta,
            "code_template": '<meta name="description" content="{value}">',
        },
        "h1": {
            "label": "H1 Heading Tag",
            "original": current_h1,
            "code_template": '<h1>{value}</h1>',
        },
        "og_title": {
            "label": "Open Graph Title",
            "original": og_title.get("content", "") if og_title else "",
            "code_template": '<meta property="og:title" content="{value}">',
        },
        "og_description": {
            "label": "Open Graph Description",
            "original": og_desc.get("content", "") if og_desc else "",
            "code_template": '<meta property="og:description" content="{value}">',
        },
    }

    for key, value in ai_fixes.items():
        if value is None or key not in fix_map:
            continue
        fm = fix_map[key]
        fix_id = f"seo_{secrets.token_urlsafe(12)}"
        doc = {
            "fix_id": fix_id,
            "scan_id": scan_id,
            "user_id": user_id,
            "scan_url": url,
            "category": "seo",
            "fix_type": key,
            "label": fm["label"],
            "status": "pending_approval",
            "original_value": fm["original"],
            "suggested_value": str(value),
            "fix_code": fm["code_template"].format(value=str(value)),
            "ai_model": "gemini-2.5-flash",
            "created_at": now,
            "approved_at": None,
        }
        await db.repair_fixes.insert_one(doc)
        fixes_created.append({
            "fix_id": fix_id,
            "fix_type": key,
            "label": fm["label"],
            "original_value": fm["original"],
            "suggested_value": str(value),
            "fix_code": fm["code_template"].format(value=str(value)),
            "status": "pending_approval",
        })

    # 5. Calculate before/after scores
    seo_before = _calc_seo_score(has_title_issue, has_meta_issue, has_h1_issue, has_og_issue)
    seo_after = _calc_seo_score(
        has_title_issue and "title" not in ai_fixes,
        has_meta_issue and "meta_description" not in ai_fixes,
        has_h1_issue and "h1" not in ai_fixes,
        has_og_issue and ("og_title" not in ai_fixes and "og_description" not in ai_fixes),
    )

    # Store scan session record
    await db.scan_sessions.insert_one({
        "scan_id": scan_id, "user_id": user_id, "scan_url": url,
        "category": "seo", "fixes_count": len(fixes_created), "previously_fixed": prev_fixed_count,
        "score_before": seo_before, "score_after": seo_after,
        "created_at": now
    })

    return {
        "url": url,
        "scan_id": scan_id,
        "fixes": fixes_created,
        "total_fixes": len(fixes_created),
        "previously_fixed": prev_fixed_count,
        "seo_score_before": seo_before,
        "seo_score_after": seo_after,
        "message": f"ORA generated {len(fixes_created)} SEO fixes via Gemini 3.1 Pro — awaiting your approval." + (f" ({prev_fixed_count} previously fixed)" if prev_fixed_count else ""),
    }


def _calc_seo_score(title_bad, meta_bad, h1_bad, og_bad) -> int:
    score = 100
    if title_bad:
        score -= 25
    if meta_bad:
        score -= 20
    if h1_bad:
        score -= 20
    if og_bad:
        score -= 15
    return max(0, score)



# ══════════════════════════════════════════════════════════════════
# GEO OPTIMIZATION — Generative Engine Optimization (Gemini 3.1 Pro)
# Optimize content for AI search engines (Google AI Overview, Perplexity, ChatGPT)
# ══════════════════════════════════════════════════════════════════

def _calc_geo_score(no_jsonld, no_faq_schema, no_article_schema, no_summary, no_citations, no_semantic_html) -> int:
    score = 100
    if no_jsonld:
        score -= 25
    if no_faq_schema:
        score -= 15
    if no_article_schema:
        score -= 15
    if no_summary:
        score -= 15
    if no_citations:
        score -= 15
    if no_semantic_html:
        score -= 15
    return max(0, score)


@router.post("/api/repair/geo/generate")
async def generate_geo_fixes(body: RepairGenerateRequest, authorization: str = Header(None)):
    """
    Analyze a URL for GEO (Generative Engine Optimization) issues:
    1. Missing/weak JSON-LD structured data (FAQPage, Article, HowTo, Organization)
    2. No AI-friendly summary paragraph
    3. Missing citation/source references
    4. Poor semantic HTML structure (article, section, aside)
    5. Missing content freshness signals (datePublished/dateModified)
    """
    if not LLM_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI engine unavailable — EMERGENT_LLM_KEY not set")

    from server import db
    user_id = _get_user_id(authorization)
    url = _normalize_url(body.url)

    # Archive old pending GEO fixes for this URL
    await db.repair_fixes.update_many(
        {"user_id": user_id, "scan_url": url, "category": "geo", "status": "pending_approval"},
        {"$set": {"status": "archived", "archived_at": datetime.now(timezone.utc).isoformat()}}
    )

    scan_id = f"scan_{secrets.token_urlsafe(12)}"

    # 1. Fetch and parse the page
    try:
        html = await _fetch_html(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}")

    soup = BeautifulSoup(html, "html.parser")

    # Check previously fixed GEO items
    prev_fixed = set()
    prev_cursor = db.repair_fixes.find(
        {"user_id": user_id, "scan_url": url, "category": "geo", "status": {"$in": ["approved", "deployed"]}},
        {"_id": 0, "fix_type": 1}
    )
    async for pf in prev_cursor:
        prev_fixed.add(pf.get("fix_type"))

    prev_fixed_count = len(prev_fixed)
    page_text = soup.get_text(separator=" ", strip=True)[:4000]

    # 2. Detect GEO issues
    # Check JSON-LD structured data
    jsonld_scripts = soup.find_all("script", {"type": "application/ld+json"})
    existing_schemas = []
    for s in jsonld_scripts:
        try:
            data = json.loads(s.string or "")
            if isinstance(data, dict):
                existing_schemas.append(data.get("@type", ""))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        existing_schemas.append(item.get("@type", ""))
        except Exception:
            pass

    has_jsonld = len(jsonld_scripts) > 0
    has_faq_schema = "FAQPage" in existing_schemas
    has_article_schema = any(t in existing_schemas for t in ["Article", "NewsArticle", "BlogPosting"])

    # Check for AI-friendly summary (first paragraph or meta-like summary)
    first_p = soup.find("p")
    first_p_text = first_p.get_text(strip=True) if first_p else ""
    has_summary = len(first_p_text) >= 80

    # Check for citations/external links
    all_links = soup.find_all("a", href=True)
    from urllib.parse import urlparse
    page_domain = urlparse(url).netloc
    external_links = [a for a in all_links if a.get("href", "").startswith("http") and page_domain not in a["href"]]
    has_citations = len(external_links) >= 2

    # Check semantic HTML
    has_article_tag = soup.find("article") is not None
    has_section_tag = soup.find("section") is not None
    has_semantic_html = has_article_tag or has_section_tag

    # Check freshness signals (used for issue context in prompt)
    date_meta = soup.find("meta", {"property": "article:published_time"}) or soup.find("meta", {"name": "date"})
    _has_date = date_meta is not None or any("datePublished" in str(s.string or "") for s in jsonld_scripts)

    # Build issue flags (excluding previously fixed)
    no_jsonld = not has_jsonld and "json_ld_base" not in prev_fixed
    no_faq = not has_faq_schema and "json_ld_faq" not in prev_fixed
    no_article = not has_article_schema and "json_ld_article" not in prev_fixed
    no_summary = not has_summary and "ai_summary" not in prev_fixed
    no_citations = not has_citations and "citation_block" not in prev_fixed
    no_semantic = not has_semantic_html and "semantic_html" not in prev_fixed

    if not any([no_jsonld, no_faq, no_article, no_summary, no_citations, no_semantic]):
        await db.scan_sessions.insert_one({
            "scan_id": scan_id, "user_id": user_id, "scan_url": url,
            "category": "geo", "fixes_count": 0, "previously_fixed": prev_fixed_count,
            "score_before": 95, "score_after": 95,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        return {
            "message": f"No new GEO issues detected — {prev_fixed_count} issues previously fixed!" if prev_fixed_count else "No GEO issues detected — page is well optimized for AI search!",
            "url": url, "scan_id": scan_id, "fixes": [],
            "previously_fixed": prev_fixed_count,
            "geo_score_before": 95, "geo_score_after": 95, "total_fixes": 0,
        }

    # 3. Call Gemini 3.1 Pro to generate GEO fixes
    issues_desc = []
    if no_jsonld:
        issues_desc.append("No JSON-LD structured data found")
    if no_faq:
        issues_desc.append("No FAQPage schema — add FAQ structured data")
    if no_article:
        issues_desc.append("No Article/BlogPosting schema")
    if no_summary:
        issues_desc.append("No AI-friendly summary paragraph at top")
    if no_citations:
        issues_desc.append(f"Only {len(external_links)} external citations — AI engines prefer well-cited content")
    if no_semantic:
        issues_desc.append("No semantic HTML (<article>, <section>) found")

    prompt = f"""Analyze this webpage for GEO (Generative Engine Optimization). URL: {url}

Page content (first 4000 chars):
{page_text[:3000]}

Existing structured data: {existing_schemas if existing_schemas else 'NONE'}
Issues detected: {'; '.join(issues_desc)}

Generate fixes to optimize this page for AI-powered search engines (Google AI Overviews, Perplexity, ChatGPT search).
Return STRICT JSON (no markdown fences):
{{
    "json_ld_base": "<script type=\\"application/ld+json\\">...</script>" or null if already has JSON-LD,
    "json_ld_faq": "<script type=\\"application/ld+json\\">{{FAQPage schema with 3-5 relevant Q&As}}</script>" or null,
    "json_ld_article": "<script type=\\"application/ld+json\\">{{Article/BlogPosting schema}}</script>" or null if already has it,
    "ai_summary": "A clear, factual 2-3 sentence summary paragraph that directly answers what this page is about" or null,
    "citation_block": "<div class=\\"sources\\"><h3>Sources</h3><ul><li>Relevant source suggestions</li></ul></div>" or null,
    "semantic_html": "Suggestion for wrapping main content in <article> and sections in <section> tags" or null
}}

Rules:
- JSON-LD must be valid Schema.org markup
- FAQ questions should be genuinely useful and derived from the page content
- Summary should be factual, concise, and start with the main entity/topic
- Only return non-null for items that need fixing"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"geo_{secrets.token_hex(8)}",
            system_message="You are ORA, an expert in Generative Engine Optimization (GEO). Return ONLY valid JSON. No markdown fences."
        ).with_model("gemini", "gemini-2.5-flash")

        response = await chat.send_message(UserMessage(text=prompt))

        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
        ai_fixes = json.loads(clean)
    except json.JSONDecodeError:
        logger.error(f"Gemini returned non-JSON for GEO: {response[:200]}")
        raise HTTPException(status_code=500, detail="AI returned invalid format — please retry")
    except Exception as e:
        logger.error(f"Gemini GEO error: {e}")
        raise HTTPException(status_code=500, detail=f"AI engine error: {str(e)}")

    # 4. Store each fix
    fixes_created = []
    now = datetime.now(timezone.utc).isoformat()

    fix_labels = {
        "json_ld_base": "Organization/Website Schema",
        "json_ld_faq": "FAQ Structured Data (FAQPage)",
        "json_ld_article": "Article Schema Markup",
        "ai_summary": "AI-Friendly Summary Paragraph",
        "citation_block": "Source Citations Block",
        "semantic_html": "Semantic HTML Structure",
    }

    for key, value in ai_fixes.items():
        if value is None or key not in fix_labels:
            continue
        fix_id = f"geo_{secrets.token_urlsafe(12)}"
        doc = {
            "fix_id": fix_id,
            "scan_id": scan_id,
            "user_id": user_id,
            "scan_url": url,
            "category": "geo",
            "fix_type": key,
            "label": fix_labels[key],
            "status": "pending_approval",
            "original_value": "(missing)" if key != "ai_summary" else first_p_text[:200] if first_p_text else "(no summary)",
            "suggested_value": str(value)[:500],
            "fix_code": str(value),
            "ai_model": "gemini-2.5-flash",
            "created_at": now,
            "approved_at": None,
        }
        await db.repair_fixes.insert_one(doc)
        fixes_created.append({
            "fix_id": fix_id,
            "fix_type": key,
            "label": fix_labels[key],
            "original_value": doc["original_value"],
            "suggested_value": doc["suggested_value"],
            "fix_code": str(value),
            "status": "pending_approval",
            "ai_model": "gemini-2.5-flash",
            "category": "geo",
        })

    # 5. Calculate scores
    geo_before = _calc_geo_score(no_jsonld, no_faq, no_article, no_summary, no_citations, no_semantic)
    geo_after = _calc_geo_score(
        no_jsonld and "json_ld_base" not in ai_fixes,
        no_faq and "json_ld_faq" not in ai_fixes,
        no_article and "json_ld_article" not in ai_fixes,
        no_summary and "ai_summary" not in ai_fixes,
        no_citations and "citation_block" not in ai_fixes,
        no_semantic and "semantic_html" not in ai_fixes,
    )

    await db.scan_sessions.insert_one({
        "scan_id": scan_id, "user_id": user_id, "scan_url": url,
        "category": "geo", "fixes_count": len(fixes_created), "previously_fixed": prev_fixed_count,
        "score_before": geo_before, "score_after": geo_after,
        "created_at": now
    })

    return {
        "url": url,
        "scan_id": scan_id,
        "fixes": fixes_created,
        "total_fixes": len(fixes_created),
        "previously_fixed": prev_fixed_count,
        "geo_score_before": geo_before,
        "geo_score_after": geo_after,
        "message": f"ORA generated {len(fixes_created)} GEO fixes via Gemini 3.1 Pro — awaiting your approval." + (f" ({prev_fixed_count} previously fixed)" if prev_fixed_count else ""),
    }



# ══════════════════════════════════════════════════════════════════
# PRIORITY 3 — ACCESSIBILITY AI VISION (Nano Banana 2)
# ══════════════════════════════════════════════════════════════════

@router.post("/api/repair/accessibility/generate")
async def generate_accessibility_fixes(body: RepairGenerateRequest, authorization: str = Header(None)):
    """
    Analyze a URL for accessibility issues:
    1. Images without alt text → Nano Banana 2 generates descriptions
    2. Missing ARIA landmarks → auto-generated from page structure
    3. Missing lang attribute, skip links, form labels
    All fixes stored as 'pending_approval'.
    """
    if not LLM_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI engine unavailable — EMERGENT_LLM_KEY not set")

    from server import db
    user_id = _get_user_id(authorization)
    url = _normalize_url(body.url)

    # Archive old pending accessibility fixes for this URL
    await db.repair_fixes.update_many(
        {"user_id": user_id, "scan_url": url, "category": "accessibility", "status": "pending_approval"},
        {"$set": {"status": "archived", "archived_at": datetime.now(timezone.utc).isoformat()}}
    )

    scan_id = f"scan_{secrets.token_urlsafe(12)}"

    # Check which fix_types were already approved/deployed
    prev_fixed = set()
    prev_cursor = db.repair_fixes.find(
        {"user_id": user_id, "scan_url": url, "category": "accessibility", "status": {"$in": ["approved", "deployed"]}},
        {"_id": 0, "fix_type": 1}
    )
    async for pf in prev_cursor:
        prev_fixed.add(pf.get("fix_type"))

    try:
        html = await _fetch_html(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}")

    soup = BeautifulSoup(html, "html.parser")
    fixes_created = []
    now = datetime.now(timezone.utc).isoformat()

    # ── 1. Alt Text Generation (Nano Banana 2 Vision) ───────────
    images = soup.find_all("img")
    images_without_alt = [
        img for img in images
        if not img.get("alt") or img.get("alt", "").strip() == ""
    ]

    alt_text_fixes = []
    if images_without_alt:
        # Process up to 8 images to avoid rate limits
        batch = images_without_alt[:8]
        for img_tag in batch:
            src = img_tag.get("src", "")
            abs_url = _resolve_img_url(src, url)
            if not abs_url:
                continue

            img_b64 = await _fetch_image_base64(abs_url)
            if not img_b64:
                continue

            try:
                chat = LlmChat(
                    api_key=EMERGENT_LLM_KEY,
                    session_id=f"alt_{secrets.token_hex(6)}",
                    system_message="You are an accessibility expert. Describe images concisely for HTML alt attributes. Return ONLY the alt text string, nothing else. Max 125 characters."
                ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

                msg = UserMessage(
                    text="Describe this image in one concise sentence for use as an HTML alt attribute. Return ONLY the description text.",
                    file_contents=[ImageContent(img_b64)]
                )
                text_resp, _ = await chat.send_message_multimodal_response(msg)
                alt_text = text_resp.strip().strip('"').strip("'")[:125] if text_resp else "Decorative image"
            except Exception as e:
                logger.warning(f"Nano Banana alt-text error for {abs_url[:60]}: {e}")
                alt_text = "Image description pending"

            fix_id = f"a11y_{secrets.token_urlsafe(12)}"
            doc = {
                "fix_id": fix_id,
                "scan_id": scan_id,
                "user_id": user_id,
                "scan_url": url,
                "category": "accessibility",
                "fix_type": "alt_text",
                "label": f"Alt Text: {src[:50]}",
                "status": "pending_approval",
                "original_value": "",
                "suggested_value": alt_text,
                "fix_code": f'<img src="{src}" alt="{alt_text}">',
                "ai_model": "nano-banana-2",
                "image_src": src,
                "created_at": now,
                "approved_at": None,
            }
            await db.repair_fixes.insert_one(doc)
            alt_text_fixes.append({
                "fix_id": fix_id,
                "fix_type": "alt_text",
                "label": f"Alt Text: {src[:50]}",
                "original_value": "",
                "suggested_value": alt_text,
                "fix_code": f'<img src="{src}" alt="{alt_text}">',
                "image_src": src,
                "status": "pending_approval",
            })

    fixes_created.extend(alt_text_fixes)

    # ── 2. ARIA Landmarks (structural analysis — no vision needed) ──
    aria_fixes = _generate_aria_fixes(soup, url, user_id, now)
    for af in aria_fixes:
        await db.repair_fixes.insert_one(af["doc"])
        fixes_created.append(af["display"])

    # ── 3. Language Declaration ──────────────────────────────────
    html_tag = soup.find("html")
    if (not html_tag or not html_tag.get("lang")) and "lang_attr" not in prev_fixed:
        fix_id = f"a11y_{secrets.token_urlsafe(12)}"
        doc = {
            "fix_id": fix_id,
            "scan_id": scan_id,
            "user_id": user_id,
            "scan_url": url,
            "category": "accessibility",
            "fix_type": "lang_attr",
            "label": "Language Declaration",
            "status": "pending_approval",
            "original_value": "<html>",
            "suggested_value": '<html lang="en">',
            "fix_code": '<html lang="en">',
            "ai_model": "rule-based",
            "created_at": now,
            "approved_at": None,
        }
        await db.repair_fixes.insert_one(doc)
        fixes_created.append({
            "fix_id": fix_id,
            "fix_type": "lang_attr",
            "label": "Language Declaration",
            "original_value": "<html>",
            "suggested_value": '<html lang="en">',
            "fix_code": '<html lang="en">',
            "status": "pending_approval",
        })

    # ── 4. Skip Navigation Link ─────────────────────────────────
    skip_link = soup.find("a", href="#main-content") or soup.find("a", class_="sr-only")
    if not skip_link and "skip_nav" not in prev_fixed:
        fix_id = f"a11y_{secrets.token_urlsafe(12)}"
        code = '<a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-white focus:text-black focus:rounded">Skip to main content</a>'
        doc = {
            "fix_id": fix_id,
            "scan_id": scan_id,
            "user_id": user_id,
            "scan_url": url,
            "category": "accessibility",
            "fix_type": "skip_nav",
            "label": "Skip Navigation Link",
            "status": "pending_approval",
            "original_value": "None",
            "suggested_value": "Skip to main content link",
            "fix_code": code,
            "ai_model": "rule-based",
            "created_at": now,
            "approved_at": None,
        }
        await db.repair_fixes.insert_one(doc)
        fixes_created.append({
            "fix_id": fix_id,
            "fix_type": "skip_nav",
            "label": "Skip Navigation Link",
            "original_value": "None",
            "suggested_value": "Skip to main content link",
            "fix_code": code,
            "status": "pending_approval",
        })

    # ── 5. Form Labels ──────────────────────────────────────────
    inputs = soup.find_all(["input", "textarea", "select"])
    unlabeled = [
        inp for inp in inputs
        if inp.get("type") not in ("hidden", "submit", "button")
        and not inp.get("aria-label")
        and not (inp.get("id") and soup.find("label", attrs={"for": inp.get("id")}))
    ]
    if unlabeled and "form_labels" not in prev_fixed:
        fix_id = f"a11y_{secrets.token_urlsafe(12)}"
        sample = unlabeled[0]
        inp_type = sample.get("type", "text")
        inp_name = sample.get("name", sample.get("id", "field"))
        code = f'<label for="{inp_name}">{inp_name.replace("_", " ").title()}</label>\n<input type="{inp_type}" id="{inp_name}" name="{inp_name}" aria-label="{inp_name.replace("_", " ").title()}">'
        doc = {
            "fix_id": fix_id,
            "scan_id": scan_id,
            "user_id": user_id,
            "scan_url": url,
            "category": "accessibility",
            "fix_type": "form_labels",
            "label": f"Form Labels ({len(unlabeled)} inputs)",
            "status": "pending_approval",
            "original_value": f"{len(unlabeled)} inputs without labels",
            "suggested_value": "aria-label + visible label",
            "fix_code": code,
            "ai_model": "rule-based",
            "created_at": now,
            "approved_at": None,
        }
        await db.repair_fixes.insert_one(doc)
        fixes_created.append({
            "fix_id": fix_id,
            "fix_type": "form_labels",
            "label": f"Form Labels ({len(unlabeled)} inputs)",
            "original_value": f"{len(unlabeled)} inputs without labels",
            "suggested_value": "aria-label + visible label",
            "fix_code": code,
            "status": "pending_approval",
        })

    # Score calculation
    prev_fixed_count = len(prev_fixed)
    total_issues = len(images_without_alt) + len(aria_fixes) + (1 if (not html_tag or not html_tag.get("lang")) and "lang_attr" not in prev_fixed else 0) + (1 if not skip_link and "skip_nav" not in prev_fixed else 0) + (1 if unlabeled and "form_labels" not in prev_fixed else 0)
    a11y_before = max(0, 100 - total_issues * 12)
    a11y_after = max(0, 100 - max(0, total_issues - len(fixes_created)) * 12)

    # Store scan session
    await db.scan_sessions.insert_one({
        "scan_id": scan_id, "user_id": user_id, "scan_url": url,
        "category": "accessibility", "fixes_count": len(fixes_created), "previously_fixed": prev_fixed_count,
        "score_before": a11y_before, "score_after": a11y_after,
        "created_at": now
    })

    return {
        "url": url,
        "scan_id": scan_id,
        "fixes": fixes_created,
        "total_fixes": len(fixes_created),
        "previously_fixed": prev_fixed_count,
        "images_analyzed": len(alt_text_fixes),
        "images_without_alt_total": len(images_without_alt),
        "aria_fixes": len(aria_fixes),
        "accessibility_score_before": a11y_before,
        "accessibility_score_after": a11y_after,
        "message": f"ORA generated {len(fixes_created)} accessibility fixes ({len(alt_text_fixes)} via Nano Banana 2 vision) — awaiting your approval." + (f" ({prev_fixed_count} previously fixed)" if prev_fixed_count else ""),
    }


def _generate_aria_fixes(soup, url: str, user_id: str, now: str) -> list:
    """Generate ARIA landmark fixes based on page structure."""
    ARIA_CHECKS = [
        {"tag": "main", "role": "main", "fix_type": "aria_main", "label": "ARIA: Main Landmark",
         "code": '<main role="main" aria-label="Main content">\n  <!-- Wrap your primary content -->\n</main>',
         "suggested": '<main role="main">', "fallback_check": lambda s: s.find("div", id="content") or s.find("div", class_="content") or s.find("div", id="main") or s.find("article"),
         "original_fn": lambda el: f"<{el.name}> without role" if el else "No main content area"},
        {"tag": "nav", "role": "navigation", "fix_type": "aria_nav", "label": "ARIA: Navigation Landmark",
         "code": '<nav role="navigation" aria-label="Main navigation">\n  <!-- Wrap your navigation links -->\n</nav>',
         "suggested": '<nav role="navigation">', "fallback_check": lambda s: s.find_all("ul", class_=lambda c: c and ("nav" in str(c).lower() or "menu" in str(c).lower())),
         "original_fn": lambda el: "<ul> without nav wrapper"},
        {"tag": "header", "role": "banner", "fix_type": "aria_banner", "label": "ARIA: Banner/Header Landmark",
         "code": '<header role="banner" aria-label="Site header">\n  <!-- Wrap your site header -->\n</header>',
         "suggested": '<header role="banner">', "fallback_check": lambda s: True,
         "original_fn": lambda el: "No <header> element"},
        {"tag": "footer", "role": "contentinfo", "fix_type": "aria_footer", "label": "ARIA: Footer/ContentInfo Landmark",
         "code": '<footer role="contentinfo" aria-label="Site footer">\n  <!-- Wrap your site footer -->\n</footer>',
         "suggested": '<footer role="contentinfo">', "fallback_check": lambda s: True,
         "original_fn": lambda el: "No <footer> element"},
    ]
    results = []
    for check in ARIA_CHECKS:
        has_el = soup.find(check["tag"]) or soup.find(attrs={"role": check["role"]})
        if has_el:
            continue
        fallback = check["fallback_check"](soup)
        if not fallback:
            continue
        fix_id = f"a11y_{secrets.token_urlsafe(12)}"
        original = check["original_fn"](fallback if not isinstance(fallback, bool) else None)
        doc = {"fix_id": fix_id, "user_id": user_id, "scan_url": url, "category": "accessibility",
               "fix_type": check["fix_type"], "label": check["label"], "status": "pending_approval",
               "original_value": original, "suggested_value": check["suggested"],
               "fix_code": check["code"], "ai_model": "rule-based", "created_at": now, "approved_at": None}
        results.append({"doc": doc, "display": {
            "fix_id": fix_id, "fix_type": check["fix_type"], "label": check["label"],
            "original_value": original, "suggested_value": check["suggested"],
            "fix_code": check["code"], "status": "pending_approval"}})
    return results


# ══════════════════════════════════════════════════════════════════
# PENDING / APPROVE / REJECT / SCORES
# ══════════════════════════════════════════════════════════════════

@router.get("/api/repair/pending")
async def list_pending_fixes(url: Optional[str] = None, authorization: str = Header(None)):
    """List all pending fixes (optionally filtered by URL). Excludes archived."""
    from server import db
    user_id = _get_user_id(authorization)
    query = {"user_id": user_id, "status": {"$ne": "archived"}}
    if url:
        query["scan_url"] = _normalize_url(url)
    fixes = await db.repair_fixes.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"fixes": fixes, "total": len(fixes)}


@router.post("/api/repair/{fix_id}/approve")
async def approve_fix(fix_id: str, authorization: str = Header(None)):
    """Approve a pending fix — marks it ready for deployment."""
    from server import db
    user_id = _get_user_id(authorization)
    result = await db.repair_fixes.update_one(
        {"fix_id": fix_id, "user_id": user_id, "status": "pending_approval"},
        {"$set": {"status": "approved", "approved_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Fix not found or already processed")
    return {"fix_id": fix_id, "status": "approved", "message": "Fix approved — ready for deployment"}


@router.post("/api/repair/{fix_id}/reject")
async def reject_fix(fix_id: str, authorization: str = Header(None)):
    """Reject a pending fix."""
    from server import db
    user_id = _get_user_id(authorization)
    result = await db.repair_fixes.update_one(
        {"fix_id": fix_id, "user_id": user_id, "status": "pending_approval"},
        {"$set": {"status": "rejected", "rejected_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Fix not found or already processed")
    return {"fix_id": fix_id, "status": "rejected"}


@router.get("/api/repair/scores")
async def get_repair_scores(url: str, authorization: str = Header(None)):
    """Get before/after scores for a URL.

    iter D-71n — SSOT: REAL pixel/scan data from `scan_history` is
    authoritative for the customer's site (axis scores written by the
    AUREM scan engine when the pixel pings home or the user runs a
    scan). `repair_fixes` then provides the "score_after" projection by
    counting how many issues are already approved/deployed.

    Priority order for each axis:
      1. latest `scan_history.scores.<axis>` for this URL (pixel truth)
      2. fallback: 100 - (pending_fixes × penalty)  (legacy)
    """
    from server import db
    user_id = _get_user_id(authorization)
    normalized = _normalize_url(url)

    # ── Source 1 — REAL scan data (pixel + manual scans) ──────────
    latest_scan = await db.scan_history.find_one(  # tenant_scope_guard: admin_cross_tenant — pixel scans are URL-keyed; caller owns the URL (verified pixel install)
        {"$or": [
            {"website_url": normalized},
            {"website_url": url},
            {"website_url": normalized.rstrip("/")},
        ]},
        {"scores": 1, "overall_score": 1, "created_at": 1, "_id": 0},
        sort=[("created_at", -1)],
    ) or {}
    scan_scores = (latest_scan.get("scores") or {}) if isinstance(latest_scan, dict) else {}

    # ── Source 2 — repair_fixes for the same URL ──────────────────
    fixes = await db.repair_fixes.find(
        {"user_id": user_id, "scan_url": normalized},
        {"_id": 0, "category": 1, "status": 1, "fix_type": 1}
    ).to_list(200)

    seo_fixes = [f for f in fixes if f["category"] == "seo"]
    a11y_fixes = [f for f in fixes if f["category"] == "accessibility"]
    geo_fixes  = [f for f in fixes if f["category"] in ("geo", "geo_readiness")]
    sec_fixes  = [f for f in fixes if f["category"] in ("security", "sec")]

    def _axis(axis_key: str, fix_list: list, penalty: int) -> dict:
        """Build the {score_before, score_after, total, approved, pending}
        dict for one axis. score_before comes from REAL scan data when
        available, otherwise derived from total pending fixes."""
        total    = len(fix_list)
        approved = len([f for f in fix_list if f["status"] in ("approved", "deployed")])
        pending  = len([f for f in fix_list if f["status"] == "pending_approval"])
        # Pixel truth wins for `score_before`
        if axis_key in scan_scores and isinstance(scan_scores[axis_key], (int, float)):
            score_before = int(scan_scores[axis_key])
        else:
            score_before = max(0, 100 - total * penalty)
        # After-score = before + (penalty × approved) capped at 100
        score_after = min(100, score_before + approved * penalty) if approved else score_before
        return {
            "score_before": score_before,
            "score_after":  score_after,
            "total_fixes":  total,
            "approved":     approved,
            "pending":      pending,
        }

    return {
        "url": normalized,
        "source": "scan_history+repair_fixes" if scan_scores else "repair_fixes_only",
        "last_scan_at": latest_scan.get("created_at"),
        "overall_score": latest_scan.get("overall_score"),
        "seo":           _axis("seo",           seo_fixes, 20),
        "accessibility": _axis("accessibility", a11y_fixes, 12),
        "geo":           _axis("geo",           geo_fixes,  15),
        "security":      _axis("security",      sec_fixes,  25),
    }



# ══════════════════════════════════════════════════════════════════
# MASTER PATCH ENGINE + STRIPE SCAN-TO-PAY + GITHUB PR
# ══════════════════════════════════════════════════════════════════

from fastapi import Request
from fastapi.responses import JSONResponse

# Stripe setup
STRIPE_API_KEY = os.environ.get("STRIPE_SECRET_KEY", "")

try:
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse, CheckoutStatusResponse
    )
    STRIPE_AVAILABLE = bool(STRIPE_API_KEY)
except ImportError:
    STRIPE_AVAILABLE = False
    logger.error("Stripe checkout import failed")

# Nexus vault decryption (for GitHub token retrieval)
def _load_aurem_encryption_key() -> str:
    """Bug-fix #175 (R21): refuse the public default key in production."""
    import os as _os, secrets as _secrets
    k = _os.environ.get("AUREM_ENCRYPTION_KEY")
    if not k or k == "aurem32characterencryptionkey!":
        if _os.environ.get("AUREM_ENV") == "production":
            raise RuntimeError(
                "AUREM_ENCRYPTION_KEY not configured — refusing to use default key in production"
            )
        k = _secrets.token_urlsafe(32)
        _os.environ["AUREM_ENCRYPTION_KEY"] = k
    return k


ENCRYPTION_KEY = _load_aurem_encryption_key()

def _nexus_aes_key():
    k = ENCRYPTION_KEY.encode("utf-8")
    return (k.ljust(32, b"\0"))[:32]

def _nexus_decrypt(blob: str) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(_nexus_aes_key())
    raw = base64.b64decode(blob)
    return aesgcm.decrypt(raw[:12], raw[12:], None).decode("utf-8")

# ─── Pricing Tiers (server-side only — never from frontend) ─────
DEPLOY_TIERS = {
    "basic": {
        "name": "Basic Patch",
        "price": 29.00,
        "description": "Downloadable HTML/CSS patch — manual application",
        "includes_github": False,
    },
    "pro": {
        "name": "Pro Deploy",
        "price": 99.00,
        "description": "Auto-push to GitHub as Pull Request via Nexus",
        "includes_github": True,
    },
}


# ─── Models ─────────────────────────────────────────────────────
class DeployPreviewRequest(BaseModel):
    url: str

class DeployCheckoutRequest(BaseModel):
    deploy_id: str
    tier: str  # "basic" or "pro"
    origin_url: str  # frontend passes window.location.origin
    github_repo: Optional[str] = None  # e.g. "owner/repo" for Pro tier


# ══════ 1. DEPLOYMENT PREVIEW (Code Diff Manifest) ══════════════

@router.post("/api/repair/deploy/preview")
async def create_deploy_preview(body: DeployPreviewRequest, authorization: str = Header(None)):
    """
    Collect all approved fixes for a URL into a deployment manifest
    with side-by-side code diffs (old → new).
    """
    from server import db
    user_id = _get_user_id(authorization)
    url = _normalize_url(body.url)

    approved_fixes = await db.repair_fixes.find(
        {"user_id": user_id, "scan_url": url, "status": "approved"},
        {"_id": 0}
    ).to_list(100)

    if not approved_fixes:
        raise HTTPException(400, "No approved fixes to deploy. Approve fixes first.")

    # Build code diff entries
    diffs = []
    html_patch_lines = ['<!-- ORA Repair Engine — Auto-Generated Patch -->', '<!-- Apply these changes to your HTML <head> section -->', '']

    for fix in approved_fixes:
        diff_entry = {
            "fix_id": fix["fix_id"],
            "fix_type": fix["fix_type"],
            "label": fix["label"],
            "category": fix["category"],
            "old_code": fix.get("original_value") or "(missing)",
            "new_code": fix.get("fix_code", ""),
            "suggested_value": fix.get("suggested_value", ""),
        }
        diffs.append(diff_entry)
        html_patch_lines.append(f'<!-- [{fix["category"].upper()}] {fix["label"]} -->')
        html_patch_lines.append(fix.get("fix_code", ""))
        html_patch_lines.append('')

    # Generate deploy ID and store manifest
    deploy_id = f"deploy_{secrets.token_urlsafe(16)}"
    now = datetime.now(timezone.utc).isoformat()

    deploy_doc = {
        "deploy_id": deploy_id,
        "user_id": user_id,
        "scan_url": url,
        "fix_count": len(approved_fixes),
        "fix_ids": [f["fix_id"] for f in approved_fixes],
        "diffs": diffs,
        "html_patch": "\n".join(html_patch_lines),
        "status": "preview",  # preview → payment_pending → paid → deployed
        "tier": None,
        "payment_session_id": None,
        "github_pr_url": None,
        "created_at": now,
        "paid_at": None,
    }
    await db.repair_deployments.insert_one(deploy_doc)

    return {
        "deploy_id": deploy_id,
        "url": url,
        "fix_count": len(approved_fixes),
        "diffs": diffs,
        "tiers": DEPLOY_TIERS,
        "message": f"Deployment preview ready — {len(approved_fixes)} fixes. Select a tier to proceed.",
    }


# ══════ 2. GITHUB CONNECTION CHECK ══════════════════════════════

@router.get("/api/repair/deploy/github-check")
async def check_github_connection(authorization: str = Header(None)):
    """Check if user has a GitHub token stored in the Nexus vault."""
    from server import db
    user_id = _get_user_id(authorization)

    cred = await db.nexus_credentials.find_one(
        {"user_id": user_id, "connector_id": "github"},
        {"_id": 0, "status": 1, "connected_at": 1}
    )

    connected = cred is not None and cred.get("status") == "connected"
    return {
        "github_connected": connected,
        "connected_at": cred.get("connected_at") if cred else None,
        "message": "GitHub connected via Nexus — Pro tier available" if connected else "Connect GitHub in Nexus to unlock Pro tier",
    }


# ══════ 3. STRIPE CHECKOUT SESSION ══════════════════════════════

@router.post("/api/repair/deploy/checkout")
async def create_deploy_checkout(body: DeployCheckoutRequest, http_request: Request, authorization: str = Header(None)):
    """
    Create a Stripe checkout session for the selected tier.
    No payment = No deployment.
    """
    if not STRIPE_AVAILABLE:
        raise HTTPException(503, "Payment system unavailable")

    from server import db
    user_id = _get_user_id(authorization)

    # Validate tier
    tier = DEPLOY_TIERS.get(body.tier)
    if not tier:
        raise HTTPException(400, f"Invalid tier: {body.tier}. Use 'basic' or 'pro'.")

    # Validate deploy exists
    deploy = await db.repair_deployments.find_one(
        {"deploy_id": body.deploy_id, "user_id": user_id},
        {"_id": 0}
    )
    if not deploy:
        raise HTTPException(404, "Deployment not found")

    if deploy.get("status") == "paid":
        raise HTTPException(400, "This deployment has already been paid for")

    # For Pro tier, check GitHub connection
    if body.tier == "pro":
        cred = await db.nexus_credentials.find_one(
            {"user_id": user_id, "connector_id": "github"},
            {"_id": 0, "status": 1}
        )
        if not cred or cred.get("status") != "connected":
            raise HTTPException(400, "Pro tier requires GitHub connected in Nexus. Connect GitHub first.")

    # Build Stripe checkout
    host_url = str(http_request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/repair/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/dashboard?payment=success&session_id={{CHECKOUT_SESSION_ID}}&deploy_id={body.deploy_id}"
    cancel_url = f"{origin}/dashboard?payment=cancelled&deploy_id={body.deploy_id}"

    checkout_req = CheckoutSessionRequest(
        amount=tier["price"],
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "type": "ora_repair_deploy",
            "deploy_id": body.deploy_id,
            "user_id": user_id,
            "tier": body.tier,
            "fix_count": str(deploy["fix_count"]),
            "github_repo": body.github_repo or "",
        }
    )

    session = await stripe.create_checkout_session(checkout_req)

    # Store payment transaction
    now = datetime.now(timezone.utc).isoformat()
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "type": "ora_repair_deploy",
        "deploy_id": body.deploy_id,
        "user_id": user_id,
        "tier": body.tier,
        "amount": tier["price"],
        "currency": "usd",
        "payment_status": "pending",
        "created_at": now,
        "metadata": {
            "fix_count": deploy["fix_count"],
            "scan_url": deploy["scan_url"],
            "github_repo": body.github_repo or "",
        }
    })

    # Update deploy status
    await db.repair_deployments.update_one(
        {"deploy_id": body.deploy_id},
        {"$set": {
            "status": "payment_pending",
            "tier": body.tier,
            "payment_session_id": session.session_id,
            "github_repo": body.github_repo or "",
        }}
    )

    return {
        "checkout_url": session.url,
        "session_id": session.session_id,
        "tier": body.tier,
        "amount": tier["price"],
    }


# ══════ 4. PAYMENT STATUS CHECK ═════════════════════════════════

@router.get("/api/repair/deploy/status/{session_id}")
async def check_deploy_payment(session_id: str, http_request: Request, authorization: str = Header(None)):
    """Poll Stripe for payment status and update deployment accordingly."""
    if not STRIPE_AVAILABLE:
        raise HTTPException(503, "Payment system unavailable")

    from server import db
    _get_user_id(authorization)  # validate auth

    host_url = str(http_request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/repair/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    status = await stripe.get_checkout_status(session_id)

    # Update payment_transactions
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"payment_status": status.payment_status}}
    )

    # If paid, unlock the deployment
    if status.payment_status == "paid":
        tx = await db.payment_transactions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if tx:
            deploy_id = tx.get("deploy_id")
            # Check if already processed
            deploy = await db.repair_deployments.find_one(
                {"deploy_id": deploy_id}, {"_id": 0}
            )
            if deploy and deploy.get("status") != "paid":
                now = datetime.now(timezone.utc).isoformat()
                await db.repair_deployments.update_one(
                    {"deploy_id": deploy_id},
                    {"$set": {"status": "paid", "paid_at": now}}
                )

                # Mark all associated fixes as deployed
                await db.repair_fixes.update_many(
                    {"fix_id": {"$in": deploy.get("fix_ids", [])}},
                    {"$set": {"status": "deployed", "deployed_at": now}}
                )

    return {
        "session_id": session_id,
        "payment_status": status.payment_status,
        "amount": status.amount_total,
        "currency": status.currency,
    }


# ══════ 5. STRIPE WEBHOOK ═══════════════════════════════════════

@router.post("/api/repair/webhook/stripe")
async def repair_stripe_webhook(request: Request):
    """Handle Stripe webhook for repair deployments."""
    if not STRIPE_AVAILABLE:
        return JSONResponse({"error": "Not configured"}, 500)

    from server import db
    body = await request.body()
    sig = request.headers.get("Stripe-Signature")

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/repair/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    try:
        event = await stripe.handle_webhook(body, sig)

        if event.payment_status == "paid":
            meta = event.metadata or {}
            if meta.get("type") == "ora_repair_deploy":
                deploy_id = meta.get("deploy_id")

                # Prevent duplicate processing
                deploy = await db.repair_deployments.find_one(
                    {"deploy_id": deploy_id}, {"_id": 0}
                )
                if deploy and deploy.get("status") != "paid":
                    now = datetime.now(timezone.utc).isoformat()
                    await db.repair_deployments.update_one(
                        {"deploy_id": deploy_id},
                        {"$set": {"status": "paid", "paid_at": now}}
                    )
                    await db.payment_transactions.update_one(
                        {"session_id": event.session_id},
                        {"$set": {"payment_status": "paid"}}
                    )
                    await db.repair_fixes.update_many(
                        {"fix_id": {"$in": deploy.get("fix_ids", [])}},
                        {"$set": {"status": "deployed", "deployed_at": now}}
                    )

                    # Auto Double-Lock: trigger Origin-Write pipeline
                    asyncio.create_task(_auto_double_lock(
                        deploy.get("scan_url", ""), meta.get("user_id", ""), deploy_id
                    ))

                    # Auto-create GitHub PR for Pro tier
                    if deploy.get("tier") == "pro" and meta.get("github_repo"):
                        try:
                            pr_url = await _create_github_pr(
                                user_id=meta.get("user_id"),
                                deploy_id=deploy_id,
                                repo=meta["github_repo"],
                                db=db,
                            )
                            if pr_url:
                                await db.repair_deployments.update_one(
                                    {"deploy_id": deploy_id},
                                    {"$set": {"github_pr_url": pr_url, "status": "deployed"}}
                                )
                        except Exception as e:
                            logger.error(f"GitHub PR creation failed: {e}")

        return JSONResponse({"received": True})
    except Exception as e:
        logger.error(f"Repair webhook error: {e}")
        return JSONResponse({"error": str(e)}, 400)


# ══════ 5b. FREE TIER DEPLOY ═════════════════════════════════════

@router.post("/api/repair/deploy/free/{deploy_id}")
async def free_tier_deploy(deploy_id: str, authorization: str = Header(None), x_repair_pin: str = Header(None, alias="X-Repair-PIN")):
    """Deploy fixes for free tier.

    Bug-fix 143 — previously trusted that the frontend had verified a PIN
    before calling this endpoint, which meant any authenticated user could
    POST directly and bypass the Basic ($49) / Pro ($99) Stripe tiers. Now
    requires a server-issued PIN token (HMAC-signed against AUREM_ADMIN_KEY).
    The frontend obtains the PIN via /pin-token after legitimate unlock.
    Admin JWTs may also bypass the PIN check for support / testing.
    """
    from server import db
    user_id = _get_user_id(authorization)

    # Admin bypass
    is_admin_bypass = False
    try:
        import jwt as _jwt
        secret = os.environ.get("JWT_SECRET") or ""
        payload = _jwt.decode((authorization or "").replace("Bearer ", "").strip(), secret, algorithms=["HS256"])
        from utils.admin_guard import is_admin_email
        is_admin_bypass = bool(
            payload.get("is_admin") or payload.get("is_super_admin")
            or payload.get("role") in ("admin", "super_admin")
            or is_admin_email(payload.get("email"))
        )
    except Exception:
        pass

    if not is_admin_bypass:
        # Require valid server-signed PIN token for non-admin callers.
        import hmac as _hmac
        import hashlib as _hl
        admin_key = (os.environ.get("AUREM_ADMIN_KEY") or "").strip()
        if not admin_key:
            raise HTTPException(503, "Free-tier deploy PIN gate not configured")
        if not x_repair_pin:
            raise HTTPException(402, "X-Repair-PIN required. Unlock at /repair/pin-token first.")
        # PIN format: <deploy_id>.<unix_ts>.<hmac-sha256>
        try:
            d_id, ts, sig = x_repair_pin.split(".", 2)
        except ValueError:
            raise HTTPException(401, "Malformed PIN token")
        if d_id != deploy_id:
            raise HTTPException(401, "PIN does not match deploy_id")
        import time as _t
        if abs(_t.time() - int(ts)) > 900:  # 15-minute window
            raise HTTPException(401, "PIN expired")
        expected = _hmac.new(admin_key.encode(), f"{d_id}.{ts}".encode(), _hl.sha256).hexdigest()
        if not _hmac.compare_digest(sig, expected):
            raise HTTPException(401, "PIN signature invalid")

    deploy = await db.repair_deployments.find_one(
        {"deploy_id": deploy_id, "user_id": user_id},
        {"_id": 0}
    )
    if not deploy:
        raise HTTPException(404, "Deployment not found")
    if deploy.get("status") in ("paid", "deployed"):
        return {"message": "Already deployed", "deploy_id": deploy_id, "status": "deployed"}

    now = datetime.now(timezone.utc).isoformat()
    await db.repair_deployments.update_one(
        {"deploy_id": deploy_id},
        {"$set": {"status": "paid", "tier": "free", "paid_at": now}}
    )
    await db.repair_fixes.update_many(
        {"fix_id": {"$in": deploy.get("fix_ids", [])}},
        {"$set": {"status": "deployed", "deployed_at": now}}
    )

    # Auto Double-Lock: trigger Origin-Write pipeline
    asyncio.create_task(_auto_double_lock(deploy.get("scan_url", ""), user_id, deploy_id))

    return {
        "deploy_id": deploy_id,
        "status": "deployed",
        "fix_count": deploy.get("fix_count", 0),
        "message": f"Free tier deployment complete — {deploy.get('fix_count', 0)} fixes deployed!",
    }


# ══════ 6. DOWNLOAD PATCH (Basic Tier) ══════════════════════════

@router.get("/api/repair/deploy/download/{deploy_id}")
async def download_patch(deploy_id: str, authorization: str = Header(None)):
    """Download the HTML patch file (available after Basic/Pro payment)."""
    from server import db
    user_id = _get_user_id(authorization)

    deploy = await db.repair_deployments.find_one(
        {"deploy_id": deploy_id, "user_id": user_id},
        {"_id": 0}
    )
    if not deploy:
        raise HTTPException(404, "Deployment not found")
    if deploy.get("status") not in ("paid", "deployed"):
        raise HTTPException(402, "Payment required — complete checkout first")

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=deploy.get("html_patch", ""),
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="ora-patch-{deploy_id}.html"'
        }
    )


# ══════ 7. GITHUB PR CREATION (Pro Tier) ════════════════════════

async def _create_github_pr(user_id: str, deploy_id: str, repo: str, db) -> Optional[str]:
    """
    Create a GitHub Pull Request using the token stored in Nexus vault.
    Returns the PR URL on success, None on failure.
    """
    # Get GitHub token from Nexus vault
    cred = await db.nexus_credentials.find_one(
        {"user_id": user_id, "connector_id": "github"},
        {"_id": 0}
    )
    if not cred or not cred.get("encrypted_data"):
        logger.error(f"No GitHub token found for user {user_id}")
        return None

    try:
        raw_creds = _nexus_decrypt(cred["encrypted_data"])
        import ast
        creds_dict = ast.literal_eval(raw_creds)
        github_token = creds_dict.get("access_token") or creds_dict.get("token") or creds_dict.get("api_key", "")
    except Exception as e:
        logger.error(f"Failed to decrypt GitHub token: {e}")
        return None

    if not github_token:
        return None

    # Get deployment manifest
    deploy = await db.repair_deployments.find_one(
        {"deploy_id": deploy_id}, {"_id": 0}
    )
    if not deploy:
        return None

    # Build PR body with all fix diffs
    pr_body = "## ORA Repair Engine — Automated Fixes\n\n"
    pr_body += f"**URL Scanned:** {deploy['scan_url']}\n"
    pr_body += f"**Fixes Applied:** {deploy['fix_count']}\n"
    pr_body += f"**Deploy ID:** `{deploy_id}`\n\n"
    pr_body += "---\n\n"

    for diff in deploy.get("diffs", []):
        pr_body += f"### {diff['label']} (`{diff['category']}`)\n"
        pr_body += f"**Before:**\n```html\n{diff['old_code']}\n```\n"
        pr_body += f"**After (ORA-Optimized):**\n```html\n{diff['new_code']}\n```\n\n"

    pr_body += "\n---\n*Generated by ORA Repair Engine — AUREM AI Platform*\n"

    # Create a Gist with the patch (works without repo write access)
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First try: Create a Gist with the patch content
        gist_resp = await client.post(
            "https://api.github.com/gists",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "description": f"ORA Repair Patch — {deploy['scan_url']}",
                "public": False,
                "files": {
                    f"ora-patch-{deploy_id}.html": {
                        "content": deploy.get("html_patch", "")
                    },
                    "ORA_REPAIR_REPORT.md": {
                        "content": pr_body
                    },
                },
            },
        )

        if gist_resp.status_code in (200, 201):
            gist_data = gist_resp.json()
            return gist_data.get("html_url", "")

        logger.warning(f"Gist creation failed ({gist_resp.status_code}): {gist_resp.text[:200]}")

        # Fallback: Try to create an actual PR if repo is specified
        if "/" in repo:
            try:
                # Create a fork/branch + PR
                # For MVP, create an issue with the patch content
                issue_resp = await client.post(
                    f"https://api.github.com/repos/{repo}/issues",
                    headers={
                        "Authorization": f"token {github_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    json={
                        "title": f"[ORA] Automated SEO + Accessibility Fixes — {deploy['fix_count']} patches",
                        "body": pr_body,
                        "labels": ["ora-repair", "automated"],
                    },
                )
                if issue_resp.status_code in (200, 201):
                    issue_data = issue_resp.json()
                    return issue_data.get("html_url", "")
            except Exception as e:
                logger.error(f"GitHub issue creation failed: {e}")

    return None


@router.post("/api/repair/deploy/github-pr/{deploy_id}")
async def trigger_github_pr(deploy_id: str, authorization: str = Header(None)):
    """Manually trigger GitHub PR creation for a paid Pro deployment."""
    from server import db
    user_id = _get_user_id(authorization)

    deploy = await db.repair_deployments.find_one(
        {"deploy_id": deploy_id, "user_id": user_id},
        {"_id": 0}
    )
    if not deploy:
        raise HTTPException(404, "Deployment not found")
    if deploy.get("status") not in ("paid", "deployed"):
        raise HTTPException(402, "Payment required first")
    if deploy.get("tier") != "pro":
        raise HTTPException(400, "GitHub PR requires Pro tier")

    repo = deploy.get("github_repo", "")
    pr_url = await _create_github_pr(user_id, deploy_id, repo, db)

    if pr_url:
        await db.repair_deployments.update_one(
            {"deploy_id": deploy_id},
            {"$set": {"github_pr_url": pr_url, "status": "deployed"}}
        )
        return {"github_pr_url": pr_url, "status": "deployed"}
    else:
        raise HTTPException(500, "GitHub PR creation failed — check your Nexus GitHub connection")


# ══════ 8. GET DEPLOYMENT STATUS ════════════════════════════════

@router.get("/api/repair/deploy/{deploy_id}")
async def get_deployment(deploy_id: str, authorization: str = Header(None)):
    """Get full deployment status including payment and GitHub PR info."""
    from server import db
    user_id = _get_user_id(authorization)

    deploy = await db.repair_deployments.find_one(
        {"deploy_id": deploy_id, "user_id": user_id},
        {"_id": 0}
    )
    if not deploy:
        raise HTTPException(404, "Deployment not found")

    return deploy



# ══════════════════════════════════════════════════════════════════
# 9. PULSE HISTORY — Scan History with Re-Scan + Trend Sparkline
# ══════════════════════════════════════════════════════════════════

@router.get("/api/repair/history")
async def get_scan_history(authorization: str = Header(None)):
    """
    Returns all scan history for the user with fix counts, scores,
    payment status, and sparkline-ready trend data.
    Excludes archived fixes from active counts.
    """
    from server import db
    user_id = _get_user_id(authorization)

    # Aggregate fixes by scan_url — exclude archived fixes
    pipeline = [
        {"$match": {"user_id": user_id, "status": {"$ne": "archived"}}},
        {"$group": {
            "_id": "$scan_url",
            "total_fixes": {"$sum": 1},
            "pending": {"$sum": {"$cond": [{"$eq": ["$status", "pending_approval"]}, 1, 0]}},
            "approved": {"$sum": {"$cond": [{"$eq": ["$status", "approved"]}, 1, 0]}},
            "deployed": {"$sum": {"$cond": [{"$eq": ["$status", "deployed"]}, 1, 0]}},
            "rejected": {"$sum": {"$cond": [{"$eq": ["$status", "rejected"]}, 1, 0]}},
            "seo_count": {"$sum": {"$cond": [{"$eq": ["$category", "seo"]}, 1, 0]}},
            "a11y_count": {"$sum": {"$cond": [{"$eq": ["$category", "accessibility"]}, 1, 0]}},
            "geo_count": {"$sum": {"$cond": [{"$eq": ["$category", "geo"]}, 1, 0]}},
            "first_scan": {"$min": "$created_at"},
            "last_scan": {"$max": "$created_at"},
            "fix_types": {"$addToSet": "$fix_type"},
        }},
        {"$sort": {"last_scan": -1}},
    ]

    scans = await db.repair_fixes.aggregate(pipeline).to_list(100)

    # Enrich with deployment + payment data
    history = []
    for scan in scans:
        url = scan["_id"]
        if not url:
            continue

        # Get latest deployment for this URL
        deploy = await db.repair_deployments.find_one(
            {"user_id": user_id, "scan_url": url},
            {"_id": 0, "deploy_id": 1, "status": 1, "tier": 1, "paid_at": 1, "github_pr_url": 1},
            sort=[("created_at", -1)],
        )

        # Calculate overall health score (weighted: SEO 33%, GEO 33%, A11y 33%)
        total = scan["total_fixes"]

        # Score: starts at baseline, improves with fixes
        seo_issues = scan["seo_count"]
        a11y_issues = scan["a11y_count"]
        geo_issues = scan["geo_count"]
        seo_score_before = max(0, 100 - seo_issues * 20)
        a11y_score_before = max(0, 100 - a11y_issues * 12)
        geo_score_before = max(0, 100 - geo_issues * 17)

        seo_score_after = max(0, 100 - max(0, seo_issues - min(seo_issues, scan["deployed"] + scan["approved"])) * 20)
        a11y_score_after = max(0, 100 - max(0, a11y_issues - min(a11y_issues, scan["deployed"] + scan["approved"])) * 12)
        geo_score_after = max(0, 100 - max(0, geo_issues - min(geo_issues, scan["deployed"] + scan["approved"])) * 17)

        # Weighted overall: equal thirds when all categories present, graceful fallback otherwise
        cats_present = sum([1 for c in [seo_issues, geo_issues, a11y_issues] if c > 0])
        if cats_present == 0:
            overall_before, overall_after = 100, 100
        elif cats_present == 1:
            overall_before = seo_score_before if seo_issues else (geo_score_before if geo_issues else a11y_score_before)
            overall_after = seo_score_after if seo_issues else (geo_score_after if geo_issues else a11y_score_after)
        elif cats_present == 2:
            scores_b = [s for s, i in [(seo_score_before, seo_issues), (geo_score_before, geo_issues), (a11y_score_before, a11y_issues)] if i > 0]
            scores_a = [s for s, i in [(seo_score_after, seo_issues), (geo_score_after, geo_issues), (a11y_score_after, a11y_issues)] if i > 0]
            overall_before = int(sum(scores_b) / 2)
            overall_after = int(sum(scores_a) / 2)
        else:
            overall_before = int(seo_score_before / 3 + geo_score_before / 3 + a11y_score_before / 3)
            overall_after = int(seo_score_after / 3 + geo_score_after / 3 + a11y_score_after / 3)

        entry = {
            "url": url,
            "total_fixes": total,
            "pending": scan["pending"],
            "approved": scan["approved"],
            "deployed": scan["deployed"],
            "rejected": scan["rejected"],
            "seo_fixes": scan["seo_count"],
            "a11y_fixes": scan["a11y_count"],
            "geo_fixes": scan["geo_count"],
            "fix_types": scan["fix_types"],
            "first_scan": scan["first_scan"],
            "last_scan": scan["last_scan"],
            "overall_score_before": overall_before,
            "overall_score_after": overall_after,
            "score_improvement": overall_after - overall_before,
            "deploy_status": deploy.get("status") if deploy else None,
            "deploy_tier": deploy.get("tier") if deploy else None,
            "deploy_id": deploy.get("deploy_id") if deploy else None,
            "paid_at": deploy.get("paid_at") if deploy else None,
            "github_pr_url": deploy.get("github_pr_url") if deploy else None,
        }
        history.append(entry)

    # Build sparkline data: overall + per-category scores per day — exclude archived
    all_fixes = await db.repair_fixes.find(
        {"user_id": user_id, "status": {"$ne": "archived"}},
        {"_id": 0, "created_at": 1, "status": 1, "category": 1}
    ).sort("created_at", 1).to_list(500)

    # Group by day for sparkline
    from collections import defaultdict
    daily = defaultdict(lambda: {"total": 0, "fixed": 0, "seo_t": 0, "seo_f": 0, "geo_t": 0, "geo_f": 0, "a11y_t": 0, "a11y_f": 0})
    for f in all_fixes:
        day = f.get("created_at", "")[:10]
        cat = f.get("category", "")
        daily[day]["total"] += 1
        if cat == "seo":
            daily[day]["seo_t"] += 1
        elif cat == "geo":
            daily[day]["geo_t"] += 1
        elif cat == "accessibility":
            daily[day]["a11y_t"] += 1
        if f.get("status") in ("approved", "deployed"):
            daily[day]["fixed"] += 1
            if cat == "seo":
                daily[day]["seo_f"] += 1
            elif cat == "geo":
                daily[day]["geo_f"] += 1
            elif cat == "accessibility":
                daily[day]["a11y_f"] += 1

    sparkline = []
    cum = {"total": 0, "fixed": 0, "seo_t": 0, "seo_f": 0, "geo_t": 0, "geo_f": 0, "a11y_t": 0, "a11y_f": 0}
    for day in sorted(daily.keys()):
        for k in cum:
            cum[k] += daily[day][k]
        overall = int(100 * cum["fixed"] / cum["total"]) if cum["total"] > 0 else 100
        seo_s = int(100 * cum["seo_f"] / cum["seo_t"]) if cum["seo_t"] > 0 else None
        geo_s = int(100 * cum["geo_f"] / cum["geo_t"]) if cum["geo_t"] > 0 else None
        a11y_s = int(100 * cum["a11y_f"] / cum["a11y_t"]) if cum["a11y_t"] > 0 else None
        sparkline.append({"date": day, "score": overall, "seo": seo_s, "geo": geo_s, "a11y": a11y_s})

    return {
        "history": history,
        "total_scans": len(history),
        "total_fixes_all_time": sum(s["total_fixes"] for s in history),
        "total_deployed": sum(s["deployed"] for s in history),
        "sparkline": sparkline,
    }



# ══════════════════════════════════════════════════════════════════
# SITE HEALTH LEADERBOARD
# ══════════════════════════════════════════════════════════════════

@router.get("/api/repair/health/leaderboard")
async def site_health_leaderboard(authorization: str = Header(None)):
    """
    Site Health Leaderboard — shows all customer sites ranked by repair health.
    Phase 1 = Pixel deployed, Phase 2 = Origin-Write committed + verified.
    Sites missing Phase 2 are ranked lower.

    ADMIN-ONLY — cross-tenant view of every customer site.
    """
    from server import db
    user_id = _require_admin_id(authorization)

    # Get all unique scanned URLs for this user
    pipeline = [
        {"$match": {"user_id": user_id, "status": {"$ne": "archived"}}},
        {"$group": {
            "_id": "$scan_url",
            "total_fixes": {"$sum": 1},
            "deployed": {"$sum": {"$cond": [{"$eq": ["$status", "deployed"]}, 1, 0]}},
            "approved": {"$sum": {"$cond": [{"$eq": ["$status", "approved"]}, 1, 0]}},
            "pending": {"$sum": {"$cond": [{"$eq": ["$status", "pending_approval"]}, 1, 0]}},
            "rejected": {"$sum": {"$cond": [{"$eq": ["$status", "rejected"]}, 1, 0]}},
            "seo_fixes": {"$sum": {"$cond": [{"$eq": ["$category", "seo"]}, 1, 0]}},
            "geo_fixes": {"$sum": {"$cond": [{"$eq": ["$category", "geo"]}, 1, 0]}},
            "a11y_fixes": {"$sum": {"$cond": [{"$eq": ["$category", "accessibility"]}, 1, 0]}},
            "last_fix_at": {"$max": "$created_at"},
        }},
        {"$sort": {"last_fix_at": -1}},
    ]

    sites_raw = await db.repair_fixes.aggregate(pipeline).to_list(100)

    sites = []
    for site in sites_raw:
        url = site["_id"]
        if not url:
            continue

        # Get origin commit status
        origin = await db.origin_commits.find_one(
            {"scan_url": url, "user_id": user_id},
            {"_id": 0, "status": 1, "committed_at": 1, "verified_at": 1,
             "verification_scores": 1, "verification_match": 1, "fix_count": 1,
             "url_slug": 1, "double_lock_status": 1}
        )

        # Phase 1: Pixel deployed?
        phase1 = site["deployed"] > 0
        # Phase 2: Origin committed?
        phase2_committed = origin is not None and origin.get("status") == "committed"
        # Phase 2b: Verified by PageSpeed?
        phase2_verified = origin is not None and origin.get("verification_match") is True
        # Double-lock status from auto_double_lock
        double_lock = origin.get("double_lock_status") if origin else None

        # Calculate health score (0-100)
        health = 0
        if site["total_fixes"] > 0:
            deploy_ratio = site["deployed"] / site["total_fixes"]
            health += int(deploy_ratio * 40)  # 40pts for deployment coverage
        if phase1:
            health += 20  # 20pts for Phase 1
        if phase2_committed:
            health += 25  # 25pts for Phase 2 commit
        if phase2_verified:
            health += 15  # 15pts for verification

        # PageSpeed scores
        psi_scores = origin.get("verification_scores", {}) if origin else {}

        sites.append({
            "url": url,
            "total_fixes": site["total_fixes"],
            "deployed": site["deployed"],
            "approved": site["approved"],
            "pending": site["pending"],
            "rejected": site["rejected"],
            "seo_fixes": site["seo_fixes"],
            "geo_fixes": site["geo_fixes"],
            "a11y_fixes": site["a11y_fixes"],
            "phase1_pixel": phase1,
            "phase2_origin": phase2_committed,
            "phase2_verified": phase2_verified,
            "double_lock_status": double_lock,
            "health_score": health,
            "pagespeed_scores": psi_scores,
            "origin_committed_at": origin.get("committed_at") if origin else None,
            "origin_verified_at": origin.get("verified_at") if origin else None,
            "origin_fix_count": origin.get("fix_count", 0) if origin else 0,
            "url_slug": origin.get("url_slug", "") if origin else "",
            "last_activity": site["last_fix_at"],
        })

    # Sort: Phase 2 missing → lower rank, then by health score desc
    sites.sort(key=lambda s: (
        0 if not s["phase1_pixel"] else (1 if not s["phase2_origin"] else (2 if not s["phase2_verified"] else 3)),
        s["health_score"],
    ), reverse=True)

    # Summary stats
    total_sites = len(sites)
    phase1_count = sum(1 for s in sites if s["phase1_pixel"])
    phase2_count = sum(1 for s in sites if s["phase2_origin"])
    verified_count = sum(1 for s in sites if s["phase2_verified"])
    avg_health = int(sum(s["health_score"] for s in sites) / total_sites) if total_sites > 0 else 0

    return {
        "sites": sites,
        "summary": {
            "total_sites": total_sites,
            "phase1_deployed": phase1_count,
            "phase2_committed": phase2_count,
            "phase2_verified": verified_count,
            "average_health": avg_health,
        },
    }


class MarkPixelRequest(BaseModel):
    url: str


@router.post("/api/repair/health/mark-pixel-deployed")
async def mark_pixel_deployed(body: MarkPixelRequest, authorization: str = Header(None)):
    """Admin shortcut: mark all pending/approved fixes for this URL as `deployed`."""
    from server import db
    user_id = _require_admin_id(authorization)
    url = _normalize_url(body.url)

    now_iso = datetime.now(timezone.utc).isoformat()
    res = await db.repair_fixes.update_many(
        {
            "user_id": user_id,
            "scan_url": url,
            "status": {"$in": ["pending_approval", "approved"]},
        },
        {"$set": {"status": "deployed", "deployed_at": now_iso, "deploy_method": "pixel_manual"}},
    )

    # Also ensure an origin_commits entry exists so Phase 2 stays consistent;
    # do NOT mark as verified (that still requires PSI recheck).
    await db.origin_commits.update_one(
        {"scan_url": url, "user_id": user_id},
        {"$setOnInsert": {
            "scan_url": url, "user_id": user_id,
            "status": "pending", "committed_at": None,
            "verified_at": None, "verification_match": False,
        }},
        upsert=True,
    )

    return {
        "ok": True,
        "url": url,
        "marked_deployed": int(res.modified_count),
        "deployed_at": now_iso,
    }


@router.post("/api/repair/health/unmark-pixel-deployed")
async def unmark_pixel_deployed(body: MarkPixelRequest, authorization: str = Header(None)):
    """Admin rollback — flip previously marked fixes back to approved."""
    from server import db
    user_id = _require_admin_id(authorization)
    url = _normalize_url(body.url)
    res = await db.repair_fixes.update_many(
        {
            "user_id": user_id,
            "scan_url": url,
            "status": "deployed",
            "deploy_method": "pixel_manual",
        },
        {"$set": {"status": "approved"}, "$unset": {"deployed_at": "", "deploy_method": ""}},
    )
    return {"ok": True, "url": url, "unmarked": int(res.modified_count)}


@router.post("/api/repair/health/verify-pixel")
async def verify_pixel_on_live_site(body: MarkPixelRequest, authorization: str = Header(None)):
    """
    Live-fetch the customer site and check whether the AUREM pixel snippet
    is present in the rendered HTML. If detected, auto-mark all pending/
    approved fixes as deployed (same effect as mark-pixel-deployed but with
    proof — sets deploy_method='pixel_verified_live').

    The AUREM pixel snippet looks like:
        <script src=".../api/pixel/aurem-pixel.js" data-aurem-key="..."></script>
    """
    import httpx
    from server import db
    user_id = _require_admin_id(authorization)
    url = _normalize_url(body.url)

    # Fetch the URL's HTML. Use a short timeout + desktop UA to avoid WAF blocks.
    html = ""
    fetched = False
    fetch_err = None
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AUREM-PixelVerifier/1.0)"},
        ) as client:
            resp = await client.get(url)
            html = resp.text or ""
            fetched = resp.status_code < 400
            if not fetched:
                fetch_err = f"HTTP {resp.status_code}"
    except Exception as e:
        fetch_err = str(e)[:200]

    # Pixel signatures — be lenient about how it was embedded (direct, proxied, CDN).
    signatures = [
        "aurem-pixel.js",
        "data-aurem-key",
        "/api/pixel/aurem-pixel",
        "window.aurem",
        "AUREM_PIXEL",
    ]
    hay = html.lower()
    matched = [s for s in signatures if s.lower() in hay]
    detected = bool(matched)

    # Count fixes that WOULD be marked
    pending_approved_count = await db.repair_fixes.count_documents({
        "user_id": user_id,
        "scan_url": url,
        "status": {"$in": ["pending_approval", "approved"]},
    })

    auto_marked = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    if detected and pending_approved_count > 0:
        res = await db.repair_fixes.update_many(
            {
                "user_id": user_id,
                "scan_url": url,
                "status": {"$in": ["pending_approval", "approved"]},
            },
            {"$set": {
                "status": "deployed",
                "deployed_at": now_iso,
                "deploy_method": "pixel_verified_live",
                "pixel_verified_signatures": matched,
            }},
        )
        auto_marked = int(res.modified_count)

    # Audit trail — store the verification attempt regardless of outcome
    try:
        await db.pixel_verification_log.insert_one({
            "url": url,
            "user_id": user_id,
            "verified_at": now_iso,
            "detected": detected,
            "matched_signatures": matched,
            "fetched": fetched,
            "fetch_error": fetch_err,
            "auto_marked": auto_marked,
            "html_bytes": len(html),
        })
    except Exception:
        pass

    return {
        "ok": True,
        "url": url,
        "detected": detected,
        "matched_signatures": matched,
        "fetched": fetched,
        "fetch_error": fetch_err,
        "pending_approved_count": pending_approved_count,
        "auto_marked": auto_marked,
        "verified_at": now_iso,
    }


# ══════════════════════════════════════════════════════════════════
# ORIGIN-WRITE — "The Anchor" (Phase 2 of Double-Lock Fix)
# ══════════════════════════════════════════════════════════════════

class OriginCommitRequest(BaseModel):
    url: str


@router.post("/api/repair/origin/commit")
async def origin_commit(body: OriginCommitRequest, authorization: str = Header(None)):
    """
    Commit to Origin — compile all pixel-patched fixes into origin-ready files
    and store them for permanent serving. The Anchor phase of Double-Lock Fix.
    """
    from services.origin_write_engine import commit_to_origin
    user_id = _get_user_id(authorization)
    url = _normalize_url(body.url)
    result = await commit_to_origin(url, user_id)
    if "error" in result and "fix_count" not in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/api/repair/health/heartbeat/run")
async def trigger_pixel_heartbeat(authorization: str = Header(None)):
    """Admin-triggered manual run of the pixel heartbeat scan."""
    from server import db
    _ = _require_admin_id(authorization)
    from services.pixel_heartbeat import run_pixel_heartbeat
    summary = await run_pixel_heartbeat(db)
    return {"ok": True, **summary}


@router.get("/api/repair/health/heartbeat/last")
async def get_last_heartbeat(authorization: str = Header(None)):
    """Return most recent heartbeat run summary for the leaderboard."""
    from server import db
    _ = _require_admin_id(authorization)
    doc = await db.pixel_heartbeat_runs.find_one(
        {}, {"_id": 0, "per_site": 0}, sort=[("started_at", -1)]
    )
    return doc or {"scanned": 0, "auto_marked": 0, "auto_reverted": 0}


@router.get("/api/repair/origin/compile")
async def origin_compile(url: str, authorization: str = Header(None)):
    """Preview the compiled origin files without committing."""
    from services.origin_write_engine import compile_origin_files
    user_id = _get_user_id(authorization)
    url = _normalize_url(url)
    result = await compile_origin_files(url, user_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/api/repair/origin/serve/{url_slug}/fixes.css")
async def serve_origin_css(url_slug: str):
    """Serve compiled CSS as a static file. Permanent URL for <link> tag."""
    from server import db
    from fastapi.responses import Response

    commit = await db.origin_commits.find_one(
        {"url_slug": url_slug}, {"_id": 0, "css": 1}
    )
    if not commit:
        raise HTTPException(404, "No origin commit found for this URL")

    return Response(
        content=commit.get("css", "/* No CSS fixes */"),
        media_type="text/css",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": os.environ.get("CORS_PRIMARY", "https://aurem.live"),
        },
    )


@router.get("/api/repair/origin/serve/{url_slug}/head.html")
async def serve_origin_head(url_slug: str):
    """Serve compiled HTML head snippet."""
    from server import db
    from fastapi.responses import Response

    commit = await db.origin_commits.find_one(
        {"url_slug": url_slug}, {"_id": 0, "head_html": 1}
    )
    if not commit:
        raise HTTPException(404, "No origin commit found for this URL")

    return Response(
        content=commit.get("head_html", "<!-- No head fixes -->"),
        media_type="text/html",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": os.environ.get("CORS_PRIMARY", "https://aurem.live"),
        },
    )


@router.get("/api/repair/origin/serve/{url_slug}/body.html")
async def serve_origin_body(url_slug: str):
    """Serve compiled HTML body snippet."""
    from server import db
    from fastapi.responses import Response

    commit = await db.origin_commits.find_one(
        {"url_slug": url_slug}, {"_id": 0, "body_html": 1}
    )
    if not commit:
        raise HTTPException(404, "No origin commit found for this URL")

    return Response(
        content=commit.get("body_html", "<!-- No body fixes -->"),
        media_type="text/html",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": os.environ.get("CORS_PRIMARY", "https://aurem.live"),
        },
    )


@router.get("/api/repair/origin/status")
async def origin_status(url: str, authorization: str = Header(None)):
    """Get origin commit status for a URL."""
    from server import db
    user_id = _get_user_id(authorization)
    url = _normalize_url(url)

    commit = await db.origin_commits.find_one(
        {"scan_url": url, "user_id": user_id},
        {"_id": 0}
    )
    if not commit:
        return {"status": "not_committed", "scan_url": url}

    return {
        "status": commit.get("status", "unknown"),
        "commit_id": commit.get("commit_id"),
        "fix_count": commit.get("fix_count", 0),
        "committed_at": commit.get("committed_at"),
        "verified_at": commit.get("verified_at"),
        "verification_scores": commit.get("verification_scores"),
        "verification_match": commit.get("verification_match"),
        "serve_urls": {
            "css": f"/api/repair/origin/serve/{commit.get('url_slug', '')}/fixes.css",
            "head": f"/api/repair/origin/serve/{commit.get('url_slug', '')}/head.html",
            "body": f"/api/repair/origin/serve/{commit.get('url_slug', '')}/body.html",
        },
    }


@router.post("/api/repair/origin/verify")
async def origin_verify(body: OriginCommitRequest, authorization: str = Header(None)):
    """
    Truth-Sync Verifier — trigger external PageSpeed scan and compare
    to internal AUREM scores. Loop only closes when they match.
    """
    from services.origin_write_engine import verify_origin_commit
    user_id = _get_user_id(authorization)
    url = _normalize_url(body.url)
    return await verify_origin_commit(url, user_id)


# ══════════════════════════════════════════════════════════════════
# SELF-SCAN — AUREM Repairs Itself (Eating Our Own Dogfood)
# ══════════════════════════════════════════════════════════════════

@router.post("/api/repair/self-scan")
async def trigger_self_scan(authorization: str = Header(None)):
    """Run SEO + GEO + A11y scan on AUREM's own platform."""
    _get_user_id(authorization)
    from services.self_scan_automation import run_self_scan
    return await run_self_scan()


@router.post("/api/repair/self-repair")
async def trigger_self_repair(authorization: str = Header(None)):
    """
    Full self-repair pipeline: Scan → Auto-Approve → Deploy → Origin-Write.
    AUREM fixes itself like it fixes its customers.
    """
    _get_user_id(authorization)
    from services.self_scan_automation import run_full_self_repair
    return await run_full_self_repair()


@router.get("/api/repair/self-scan/status")
async def self_scan_status(authorization: str = Header(None)):
    """Get the current self-scan/repair status for AUREM."""
    from server import db
    import os
    _get_user_id(authorization)  # validate auth
    aurem_url = os.environ.get("AUREM_PUBLIC_URL", "https://aurem.live")

    # Get fix counts
    total = await db.repair_fixes.count_documents({"scan_url": aurem_url, "source": "self_scan"})
    deployed = await db.repair_fixes.count_documents({"scan_url": aurem_url, "source": "self_scan", "status": "deployed"})
    pending = await db.repair_fixes.count_documents({"scan_url": aurem_url, "source": "self_scan", "status": "pending_approval"})

    # Get origin status
    origin = await db.origin_commits.find_one({"scan_url": aurem_url}, {"_id": 0, "status": 1, "committed_at": 1, "fix_count": 1})

    # Get last self-repair event
    last_repair = await db.auto_heal_log.find_one(
        {"type": "self_repair"}, {"_id": 0}, sort=[("timestamp", -1)]
    )

    return {
        "url": aurem_url,
        "total_fixes": total,
        "deployed": deployed,
        "pending": pending,
        "origin_committed": origin.get("status") == "committed" if origin else False,
        "origin_fix_count": origin.get("fix_count", 0) if origin else 0,
        "last_repair": last_repair.get("timestamp") if last_repair else None,
    }
