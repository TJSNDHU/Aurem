"""
website_enrich.py — iter 322ad  (Retention P0)
==============================================
Layered on top of services.website_builder.generate_website() to:

  1. Replace "Real Google reviews will appear here automatically..."
     placeholder reviews with AI-generated realistic reviews using the
     FREE llm_gateway_v2 path (llama-3.3-70b:free, NOT Claude).
  2. Replace hardcoded SERVICE_HINTS with customer-supplied services
     (parsed from a comma-separated text field on signup).
  3. Optionally override theme.bg / theme.accent / theme.text with
     colors extracted from a customer-supplied website / Facebook URL
     via services.design_extractor.extract_design().

All three steps are best-effort: if any one fails we keep the original
spec value so the customer always lands on a working site.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# FREE-MODEL FALLBACK CHAIN
# ─────────────────────────────────────────────────────────────────────
# Provider-level rate-limits flap unpredictably on OpenRouter's free tier
# (llama-3.3-70b:free → frequent 429s, gpt-oss-20b:free is the most stable
# per iter 322q field-testing). We cycle through 3 free task_types so a
# single 429 doesn't degrade the customer experience.
_FREE_FALLBACK_CHAIN = ["triage_classify", "content_qa", "sentiment"]


async def _call_free_with_fallback(
    prompt: str, system: str, max_tokens: int = 800,
) -> Optional[str]:
    """Try the free model chain. Return the first non-empty `text`, or
    None if every fallback failed. Adds a short backoff between fallback
    attempts so a single OpenRouter rate-limit spike doesn't drain the
    whole chain in <1 second."""
    try:
        from services.llm_gateway_v2 import route
    except Exception as e:
        logger.warning(f"[enrich] gateway import failed: {e}")
        return None
    for idx, task_type in enumerate(_FREE_FALLBACK_CHAIN):
        if idx > 0:
            await asyncio.sleep(1.2)  # space out fallbacks to dodge 429 bursts
        try:
            result = await asyncio.wait_for(
                route(task_type, prompt, system=system, max_tokens=max_tokens),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[enrich] {task_type} timeout — trying next")
            continue
        except Exception as e:
            logger.warning(f"[enrich] {task_type} error: {e}")
            continue
        if result.get("ok") and (result.get("text") or "").strip():
            return result["text"]
        logger.info(f"[enrich] {task_type} returned ok={result.get('ok')} — trying next")
    return None


# ─────────────────────────────────────────────────────────────────────
# AI REVIEWS (free model)
# ─────────────────────────────────────────────────────────────────────
_REVIEW_SYSTEM = (
    "You write realistic Google-style customer reviews for small local "
    "businesses. Output STRICT JSON only — a single JSON array, no markdown, "
    "no prose, no fence. Each review reads like a real local customer wrote "
    "it: specific small details, varied tone, occasional minor grammar "
    "imperfection. Never use generic marketing phrases like 'highly recommend' "
    "or 'top-notch'. Names: realistic Canadian first names + last-initial."
)


def _build_review_prompt(business_name: str, industry: str, city: str) -> str:
    return (
        f"Generate exactly 3 realistic Google-style reviews for "
        f"\"{business_name}\", a {industry.replace('_',' ')} business in "
        f"{city}. Schema (exact keys):\n"
        "[\n"
        "  {\"author\": \"First L.\", \"rating\": 4 or 5, "
        "\"text\": \"2-3 sentences with specific small detail\", "
        "\"time_ago\": \"e.g. 2 weeks ago | a month ago | 3 days ago\"},\n"
        "  ... 3 items total ...\n"
        "]\n"
        "Vary ratings (mix of 4 and 5), vary length (40-120 words), and vary "
        "what they praise (1 about service quality, 1 about a person/staff, "
        "1 about value or speed). Return the JSON array only."
    )


def _coerce_review_list(text: str) -> List[Dict[str, Any]]:
    """Tolerant parser: pull the first JSON array out of the model's text."""
    if not text:
        return []
    # Strip code fence if present
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    raw = fenced.group(1) if fenced else text
    # Try direct parse, then look for first '[' ... ']' block
    try:
        parsed = json.loads(raw)
    except Exception:
        m = re.search(r"\[\s*\{.*?\}\s*\]", raw, re.S)
        if not m:
            return []
        try:
            parsed = json.loads(m.group(0))
        except Exception:
            return []
    if not isinstance(parsed, list):
        return []
    out: List[Dict[str, Any]] = []
    for r in parsed[:3]:
        if not isinstance(r, dict):
            continue
        author = str(r.get("author") or "").strip()[:40]
        try:
            rating = int(r.get("rating") or 5)
        except Exception:
            rating = 5
        rating = max(4, min(5, rating))
        txt = str(r.get("text") or "").strip()[:400]
        time_ago = str(r.get("time_ago") or "recently").strip()[:30]
        if not author or not txt:
            continue
        out.append({
            "author": author,
            "rating": rating,
            "text": txt,
            "time_ago": time_ago,
            "source": "ai_generated",
        })
    return out


async def generate_realistic_reviews(
    business_name: str, industry: str, city: str,
) -> List[Dict[str, Any]]:
    """Best-effort. Returns [] on any failure so caller can fall back."""
    text = await _call_free_with_fallback(
        _build_review_prompt(business_name, industry, city or "your area"),
        system=_REVIEW_SYSTEM,
        max_tokens=900,
    )
    if not text:
        return []
    return _coerce_review_list(text)


# ─────────────────────────────────────────────────────────────────────
# CUSTOMER-SUPPLIED SERVICES
# ─────────────────────────────────────────────────────────────────────
_SVC_DESC_SYSTEM = (
    "You write one-sentence service descriptions for local business "
    "websites. Sound natural, concrete, never generic. Maximum 14 words "
    "per description. Return STRICT JSON only — a single JSON array of "
    "strings, no markdown, no prose."
)

# Lightweight industry → icon hints (kept here so we don't reach back into
# website_builder's SERVICE_HINTS where icons are paired by index).
_SERVICE_ICONS_BY_INDUSTRY = {
    "auto_shop":     ["wrench", "settings", "shield", "zap", "truck"],
    "beauty_salon":  ["scissors", "sparkles", "heart", "smile", "star"],
    "restaurant":    ["utensils", "coffee", "leaf", "heart", "star"],
    "medical":       ["heart", "shield", "stethoscope", "users", "leaf"],
    "dental":        ["smile", "shield", "heart", "sparkles", "leaf"],
    "fitness":       ["dumbbell", "heart", "zap", "users", "trophy"],
    "real_estate":   ["home", "key", "map", "shield", "star"],
    "default":       ["check", "star", "shield", "heart", "zap"],
}


def parse_customer_services(text: str) -> List[str]:
    """Split a "service1, service2, service3" string into clean names."""
    if not text:
        return []
    parts = re.split(r"[,;|\n]+", text)
    out: List[str] = []
    for p in parts:
        p = p.strip().strip(".").strip()
        if 2 <= len(p) <= 60:
            out.append(p[:60])
        if len(out) >= 6:
            break
    return out


async def _generate_service_descriptions(
    names: List[str], industry: str, city: str,
) -> List[str]:
    """Returns one description per name. Empty string for failures —
    caller fills a safe fallback."""
    if not names:
        return []
    prompt = (
        f"For a {industry.replace('_',' ')} business in {city or 'the local area'}, "
        f"write a one-sentence customer-facing description for each of these "
        f"services. Maximum 14 words each. Return a JSON array of strings, "
        f"same order:\n\n{json.dumps(names)}"
    )
    text = await _call_free_with_fallback(
        prompt, system=_SVC_DESC_SYSTEM, max_tokens=400,
    )
    if not text:
        return ["" for _ in names]
    # Tolerant array parse
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    raw = fenced.group(1) if fenced else text
    try:
        arr = json.loads(raw)
    except Exception:
        m = re.search(r"\[.*?\]", raw, re.S)
        if not m:
            return ["" for _ in names]
        try:
            arr = json.loads(m.group(0))
        except Exception:
            return ["" for _ in names]
    if not isinstance(arr, list):
        return ["" for _ in names]
    # Coerce to the right length
    out = []
    for i, n in enumerate(names):
        if i < len(arr) and isinstance(arr[i], str):
            out.append(arr[i].strip()[:140])
        else:
            out.append("")
    return out


async def build_customer_services(
    raw_text: str, industry: str, city: str,
) -> List[Dict[str, str]]:
    """Returns a list of {name, description, icon} dicts shaped exactly
    like generate_website()'s `services` field. Falls back to a safe
    one-line description if the LLM call fails."""
    names = parse_customer_services(raw_text)
    if not names:
        return []
    descs = await _generate_service_descriptions(names, industry, city)
    icons = _SERVICE_ICONS_BY_INDUSTRY.get(industry, _SERVICE_ICONS_BY_INDUSTRY["default"])
    out: List[Dict[str, str]] = []
    for i, name in enumerate(names):
        desc = descs[i] if i < len(descs) and descs[i] else (
            f"Professional {name.lower()} for {city or 'local'} customers."
        )
        icon = icons[i % len(icons)]
        out.append({"name": name, "description": desc, "icon": icon})
    return out


# ─────────────────────────────────────────────────────────────────────
# BRAND COLOR EXTRACTION FROM URL
# ─────────────────────────────────────────────────────────────────────
_HEX = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def _norm_hex(c: Optional[str]) -> Optional[str]:
    if not c:
        return None
    c = c.strip()
    # Accept "#rrggbb" or "rgb(r,g,b)"
    if c.startswith("#") and _HEX.match(c):
        return c.lower()
    if _HEX.match(c):
        return f"#{c.lower()}"
    m = re.match(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", c)
    if m:
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return None


def _is_dark(hex6: str) -> bool:
    try:
        h = hex6.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) < 128
    except Exception:
        return False


async def extract_brand_theme(url: str, db=None) -> Optional[Dict[str, str]]:
    """Return {bg, accent, text} if extraction succeeds, else None.
    Caller merges these into the spec.theme dict."""
    if not url or not url.strip():
        return None
    try:
        from services.design_extractor import extract_design
    except Exception as e:
        logger.warning(f"[enrich.brand] design_extractor import failed: {e}")
        return None
    try:
        result = await asyncio.wait_for(
            extract_design(url, timeout=45, db=db),
            timeout=50.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[enrich.brand] design extractor timeout for {url}")
        return None
    except Exception as e:
        logger.warning(f"[enrich.brand] extractor error for {url}: {e}")
        return None
    if not result or not result.get("ok"):
        return None
    colors = result.get("colors") or {}
    accent = _norm_hex(colors.get("primary")) or _norm_hex(colors.get("accent"))
    bg = _norm_hex(colors.get("bg"))
    text = _norm_hex(colors.get("text"))
    if not accent:
        # No usable brand color → bail rather than half-merge
        return None
    # Reasonable bg/text defaults if extractor missed them
    if not bg:
        bg = "#0A0A0A"
    if not text:
        text = "#FFFFFF" if _is_dark(bg) else "#0B0B0F"
    out = {"bg": bg, "accent": accent, "text": text, "source": "extracted",
           "source_url": result.get("source_url"), "score": result.get("score")}
    return out


# ─────────────────────────────────────────────────────────────────────
# TOP-LEVEL ENRICH WRAPPER
# ─────────────────────────────────────────────────────────────────────
async def enrich_website(
    website: Dict[str, Any], lead: Dict[str, Any], db=None,
) -> Dict[str, Any]:
    """In-place layered enrichment over a generate_website() spec.

    Reads from `lead`:
      - customer_services : optional comma-separated string
      - website_url       : optional URL for brand-color extraction
      - google_reviews    : if already present we DO NOT overwrite

    Mutates and returns `website`.

    Pacing: LLM calls are serialized (services → 1.5s → reviews) so back-to-back
    OpenRouter rate-limits don't drain both at once. Brand extraction (CLI, no
    LLM) is fired in parallel with the LLM steps to keep total wall-time low.
    """
    industry = website.get("industry") or "default"
    city = (website.get("business") or {}).get("city") or "your area"
    name = (website.get("business") or {}).get("name") or "this business"

    # ── Brand-color extraction (npx CLI — no LLM) runs concurrent ──
    brand_task = None
    site_url = (lead.get("website_url") or "").strip()
    if site_url:
        brand_task = asyncio.create_task(extract_brand_theme(site_url, db=db))

    # ── 1) Customer-supplied services (serialized — LLM call) ──
    customer_services_raw = (lead.get("customer_services") or "").strip()
    used_llm = False
    if customer_services_raw:
        try:
            cs = await build_customer_services(customer_services_raw, industry, city)
            used_llm = True
            if cs:
                website["services"] = cs
                website["services_source"] = "customer_supplied"
        except Exception as e:
            logger.warning(f"[enrich] customer_services failed: {e}")

    # Space LLM calls out — OpenRouter free tier rate-limits ~1 req/sec/key.
    if used_llm:
        await asyncio.sleep(1.5)

    # ── 2) AI reviews (serialized — LLM call) ──
    existing_reviews = website.get("reviews") or []
    has_real_reviews = any(
        r.get("source") == "google" for r in existing_reviews
    )
    if not has_real_reviews:
        # iter 322ae — try the FREE Birdeye scraper first. Two paths:
        #   1. Customer pasted a direct Birdeye / Google Business URL into
        #      the signup form (`reviews_url` lead field) — we skip DDG
        #      discovery and scrape that URL directly. Most reliable.
        #   2. No URL — fall back to DDG-based discovery for their biz.
        # If either yields reviews we get REAL Google reviews (zero cost).
        # Otherwise fall through to AI-generated reviews.
        real_reviews: List[Dict[str, Any]] = []
        aggregate_meta: Optional[Dict[str, Any]] = None
        try:
            direct_url = (lead.get("reviews_url") or "").strip()
            from services.birdeye_scraper import (
                pull_real_reviews,
                scrape_birdeye_profile,
            )
            birdeye = None
            if direct_url and "birdeye.com" in direct_url.lower():
                # Path 1: direct scrape (no DDG, no rate-limit risk)
                scrape = await asyncio.wait_for(
                    scrape_birdeye_profile(direct_url, limit=5), timeout=20.0,
                )
                if scrape.get("ok") and scrape.get("reviews"):
                    birdeye = {
                        "found": True,
                        "url": direct_url,
                        "aggregate_rating": scrape.get("aggregate_rating"),
                        "total_count": scrape.get("total_count"),
                        "reviews": scrape.get("reviews"),
                    }
            if birdeye is None:
                # Path 2: DDG-based discovery + scrape
                birdeye = await asyncio.wait_for(
                    pull_real_reviews(name, city, limit=5),
                    timeout=25.0,
                )
            if birdeye and birdeye.get("found") and birdeye.get("reviews"):
                real_reviews = birdeye["reviews"]
                aggregate_meta = {
                    "aggregate_rating": birdeye.get("aggregate_rating"),
                    "total_count": birdeye.get("total_count"),
                    "source_url": birdeye.get("url"),
                }
                logger.info(
                    f"[enrich.reviews] birdeye HIT: {name} → "
                    f"{len(real_reviews)} reviews, agg={aggregate_meta}"
                )
        except asyncio.TimeoutError:
            logger.info("[enrich.reviews] birdeye timeout → AI fallback")
        except Exception as e:
            logger.info(f"[enrich.reviews] birdeye error: {e} → AI fallback")

        if real_reviews:
            website["reviews"] = real_reviews
            website["reviews_source"] = "birdeye_scraped"
            if aggregate_meta:
                website["reviews_aggregate"] = aggregate_meta
        else:
            # AI fallback path
            try:
                ai_reviews = await generate_realistic_reviews(name, industry, city)
            except Exception as e:
                logger.warning(f"[enrich.reviews] AI generation failed: {e}")
                ai_reviews = []
            if ai_reviews:
                website["reviews"] = ai_reviews
                website["reviews_source"] = "ai_generated"

    # ── 3) Await brand extraction (if running) ──
    if brand_task is not None:
        try:
            brand = await brand_task
        except Exception as e:
            logger.warning(f"[enrich.brand] await failed: {e}")
            brand = None
        if brand:
            theme = dict(website.get("theme") or {})
            theme["bg"] = brand["bg"]
            theme["accent"] = brand["accent"]
            theme["text"] = brand["text"]
            theme["source"] = "extracted_from_url"
            theme["source_url"] = brand.get("source_url")
            website["theme"] = theme
            website["theme_source"] = "extracted"

    return website
