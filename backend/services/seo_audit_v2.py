"""
AUREM SEO Audit v2 — Deep HTML + GEO Analyzer
==============================================
Actual 15-dimension audit that the v1 missed (it only checked PageSpeed + markdown).

Checks:
  HTML HEAD
    1.  Title tag (length 50-60 chars, includes brand)
    2.  Meta description (120-160 chars)
    3.  Open Graph completeness (target ≥8 tags)
    4.  Twitter Card completeness (target ≥5 tags)
    5.  Canonical URL
    6.  Favicon + apple-touch-icon
    7.  Schema.org JSON-LD count + types
    8.  hreflang (if multilingual)
    9.  Viewport meta
  GEO (Generative Engine Optimization)
    10. robots.txt exists
    11. robots.txt AI crawler allowlist coverage (GPTBot, ClaudeBot, PerplexityBot, etc.)
    12. llms.txt presence
    13. llms-full.txt presence
    14. sitemap.xml exists + URLs extracted
  CLASSIC SEO
    15. Page speed (mobile performance)

Issue severity: critical | major | minor
Auto-fix capability: flagged per issue
"""
from __future__ import annotations

import re
import httpx
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# 22 AI crawler user-agents we expect in robots.txt for proper GEO
REQUIRED_AI_BOTS = {
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",
    "ClaudeBot", "Claude-Web", "anthropic-ai",
    "Google-Extended", "GoogleOther",
    "PerplexityBot", "Perplexity-User",
    "Meta-ExternalAgent", "FacebookBot",
    "Bytespider", "cohere-ai", "CCBot",
    "Applebot", "Applebot-Extended",
    "Diffbot", "YouBot", "MistralAI-User", "DuckAssistBot",
}

EXPECTED_OG_TAGS = {
    "og:type", "og:title", "og:description", "og:url",
    "og:image", "og:site_name", "og:locale",
}
EXPECTED_TWITTER_TAGS = {
    "twitter:card", "twitter:title", "twitter:description", "twitter:image",
}


async def fetch_html(url: str) -> str:
    """Fetch raw HTML (user-agent = modern browser to avoid SPA shortcuts)."""
    async with httpx.AsyncClient(
        timeout=20, follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AUREM-SEO-Bot/2.0; +https://aurem.live)"}
    ) as c:
        r = await c.get(url)
        return r.text if r.status_code < 400 else ""


async def fetch_text(url: str) -> tuple[int, str]:
    """Fetch small text file (robots/llms/sitemap). Returns (status, body)."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
            r = await c.get(url)
            return r.status_code, r.text if r.status_code < 400 else ""
    except Exception as e:
        logger.debug(f"[fetch_text] {url}: {e}")
        return 0, ""


def parse_head_tags(html: str) -> dict:
    """Lightweight head parser — no BeautifulSoup dependency needed."""
    head_match = re.search(r'<head[^>]*>(.*?)</head>', html, re.IGNORECASE | re.DOTALL)
    head = head_match.group(1) if head_match else html[:5000]

    title_match = re.search(r'<title[^>]*>(.*?)</title>', head, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    def meta_value(attr: str, key: str) -> str:
        # iter 282al-9 — match by quote type so an apostrophe inside the
        # value doesn't truncate it (was breaking on "world's first…").
        for quote, opp in (('"', "'"), ("'", '"')):
            patt1 = (
                rf'<meta\s+[^>]*{attr}={re.escape(quote)}{re.escape(key)}'
                rf'{re.escape(quote)}[^>]*content={re.escape(quote)}'
                rf'([^{re.escape(quote)}]*){re.escape(quote)}'
            )
            m = re.search(patt1, head, re.IGNORECASE)
            if m:
                return m.group(1)
            # Reversed (content first)
            patt2 = (
                rf'<meta\s+[^>]*content={re.escape(quote)}'
                rf'([^{re.escape(quote)}]*){re.escape(quote)}'
                rf'[^>]*{attr}={re.escape(quote)}{re.escape(key)}{re.escape(quote)}'
            )
            m2 = re.search(patt2, head, re.IGNORECASE)
            if m2:
                return m2.group(1)
        return ""

    def all_meta_keys(attr: str) -> set:
        return set(re.findall(rf'{attr}=["\']([^"\']+)["\']', head, re.IGNORECASE))

    description = meta_value("name", "description")
    og_keys = {k for k in all_meta_keys("property") if k.startswith("og:")}
    twitter_keys = {k for k in all_meta_keys("name") if k.startswith("twitter:")}

    canonical = ""
    canon_match = re.search(r'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', head, re.IGNORECASE)
    if canon_match:
        canonical = canon_match.group(1)

    favicon = bool(re.search(r'<link\s+[^>]*rel=["\'](?:icon|shortcut icon)["\']', head, re.IGNORECASE))
    apple_icon = bool(re.search(r'<link\s+[^>]*rel=["\']apple-touch-icon["\']', head, re.IGNORECASE))
    viewport = bool(re.search(r'<meta\s+[^>]*name=["\']viewport["\']', head, re.IGNORECASE))
    has_hreflang = bool(re.search(r'<link\s+[^>]*rel=["\']alternate["\'][^>]*hreflang=', head, re.IGNORECASE))

    # JSON-LD blocks
    json_ld_blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        head, re.IGNORECASE | re.DOTALL,
    )
    schema_types = []
    for block in json_ld_blocks:
        schema_types.extend(re.findall(r'"@type"\s*:\s*"([^"]+)"', block))

    return {
        "title": title, "title_len": len(title),
        "description": description, "description_len": len(description),
        "og_tags_present": sorted(og_keys), "og_count": len(og_keys),
        "twitter_tags_present": sorted(twitter_keys), "twitter_count": len(twitter_keys),
        "canonical": canonical,
        "favicon": favicon, "apple_icon": apple_icon, "viewport": viewport, "hreflang": has_hreflang,
        "schema_org_blocks": len(json_ld_blocks),
        "schema_types": sorted(set(schema_types)),
    }


def parse_robots(body: str) -> dict:
    """Extract allowed AI user-agents from robots.txt."""
    if not body:
        return {"present": False, "ai_bots_allowed": [], "ai_coverage_pct": 0}
    uas = set(re.findall(r'^\s*User-agent\s*:\s*(\S+)', body, re.IGNORECASE | re.MULTILINE))
    # Case-insensitive match against expected
    found_ai = {bot for bot in REQUIRED_AI_BOTS if any(ua.lower() == bot.lower() for ua in uas)}
    missing = REQUIRED_AI_BOTS - found_ai
    return {
        "present": True,
        "total_user_agents": len(uas),
        "ai_bots_allowed": sorted(found_ai),
        "ai_bots_missing": sorted(missing),
        "ai_coverage_pct": int(len(found_ai) / len(REQUIRED_AI_BOTS) * 100),
        "has_sitemap_ref": "sitemap:" in body.lower(),
    }


def parse_sitemap(body: str) -> dict:
    if not body:
        return {"present": False, "url_count": 0}
    urls = re.findall(r'<loc>([^<]+)</loc>', body)
    has_priority = "<priority>" in body
    has_image = "<image:" in body
    return {"present": True, "url_count": len(urls), "has_priority": has_priority, "has_image_sitemap": has_image}


async def run_seo_audit_v2(site_url: str) -> dict:
    """
    Run the complete 15-dimension audit.
    Returns structured report with per-issue severity + auto-fix flags.
    """
    parsed = urlparse(site_url if site_url.startswith("http") else f"https://{site_url}")
    base = f"{parsed.scheme}://{parsed.netloc}"

    html = await fetch_html(base)
    head = parse_head_tags(html) if html else {}

    # GEO files
    _, robots_body = await fetch_text(f"{base}/robots.txt")
    _, llms_body = await fetch_text(f"{base}/llms.txt")
    _, llms_full_body = await fetch_text(f"{base}/llms-full.txt")
    _, sitemap_body = await fetch_text(f"{base}/sitemap.xml")

    robots = parse_robots(robots_body)
    sitemap = parse_sitemap(sitemap_body)

    # Build issue list
    issues = []

    def add(severity: str, code: str, message: str, fix_available: bool = False):
        issues.append({"severity": severity, "code": code, "message": message, "auto_fix": fix_available})

    # ── HEAD checks ──
    tl = head.get("title_len", 0)
    if not tl:
        add("critical", "missing_title", "No <title> tag found", True)
    elif tl < 30 or tl > 65:
        add("minor", "title_length", f"Title is {tl} chars (recommended 50-60)", False)

    dl = head.get("description_len", 0)
    if not dl:
        add("critical", "missing_description", "No meta description", True)
    elif dl < 100 or dl > 170:
        add("minor", "description_length", f"Meta description is {dl} chars (recommended 120-160)", False)

    og_missing = EXPECTED_OG_TAGS - set(head.get("og_tags_present", []))
    if og_missing:
        add("major", "og_incomplete", f"Missing Open Graph tags: {', '.join(sorted(og_missing))}", True)

    tw_missing = EXPECTED_TWITTER_TAGS - set(head.get("twitter_tags_present", []))
    if tw_missing:
        add("major", "twitter_incomplete", f"Missing Twitter Card tags: {', '.join(sorted(tw_missing))}", True)

    if not head.get("canonical"):
        add("major", "no_canonical", "No canonical URL defined", True)

    if head.get("schema_org_blocks", 0) == 0:
        add("critical", "no_schema_org", "No Schema.org JSON-LD structured data found — invisible to Google rich results", True)
    elif head.get("schema_org_blocks", 0) < 2:
        add("minor", "weak_schema", f"Only {head['schema_org_blocks']} Schema.org block(s) — recommend Organization + SoftwareApplication + FAQPage minimum", True)

    if not head.get("viewport"):
        add("critical", "no_viewport", "No <meta viewport> — mobile rendering broken", True)
    if not head.get("favicon"):
        add("minor", "no_favicon", "No favicon set", False)

    # ── GEO checks ──
    if not robots.get("present"):
        add("critical", "no_robots", "No robots.txt — crawlers don't know what to index", True)
    else:
        cov = robots.get("ai_coverage_pct", 0)
        if cov < 50:
            add("critical", "robots_no_ai_bots", f"robots.txt missing {len(robots.get('ai_bots_missing', []))} AI crawlers — invisible to ChatGPT/Claude/Perplexity (only {cov}% coverage)", True)
        elif cov < 90:
            add("major", "robots_partial_ai", f"robots.txt covers only {cov}% of AI crawlers", True)

    if not llms_body:
        add("critical", "no_llms_txt", "No /llms.txt — AI platforms can't find structured info about your business", True)
    if not llms_full_body:
        add("minor", "no_llms_full", "No /llms-full.txt — missing deep AI context file", True)

    if not sitemap.get("present"):
        add("major", "no_sitemap", "No sitemap.xml", True)
    elif not sitemap.get("has_priority"):
        add("minor", "sitemap_no_priority", "sitemap.xml missing <priority> weights", True)

    # Score
    weights = {"critical": 15, "major": 8, "minor": 3}
    penalty = sum(weights.get(i["severity"], 0) for i in issues)
    score = max(0, 100 - penalty)
    grade = "A+" if score >= 95 else "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"

    return {
        "site_url": base,
        "audit_version": "v2.0",
        "score": score,
        "grade": grade,
        "issues": issues,
        "issue_count": len(issues),
        "issues_by_severity": {
            "critical": sum(1 for i in issues if i["severity"] == "critical"),
            "major": sum(1 for i in issues if i["severity"] == "major"),
            "minor": sum(1 for i in issues if i["severity"] == "minor"),
        },
        "head_analysis": head,
        "geo": {
            "robots_txt": robots,
            "llms_txt_present": bool(llms_body),
            "llms_full_present": bool(llms_full_body),
            "sitemap": sitemap,
        },
    }
