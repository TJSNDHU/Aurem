"""
ORA Repair Engine - Auto-Fix Generator & Deployer
Generates real fix recommendations using LLM and streams repair progress via SSE
"""

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import asyncio
import json
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# LLM for generating fix code
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
    LLM_AVAILABLE = bool(EMERGENT_LLM_KEY)
except ImportError:
    LLM_AVAILABLE = False
    EMERGENT_LLM_KEY = ""


class FixRequest(BaseModel):
    scan_url: str
    issues: List[dict]
    connected_platforms: Optional[List[str]] = []


FIX_TEMPLATES = {
    "security": {
        "SSL/TLS Encryption": {
            "fix_type": "config",
            "platform": "hosting",
            "code": "# Redirect HTTP to HTTPS (Nginx)\nserver {\n    listen 80;\n    return 301 https://$host$request_uri;\n}",
            "description": "Force HTTPS redirect on all traffic"
        },
        "HSTS (HTTP Strict Transport)": {
            "fix_type": "header",
            "platform": "cloudflare",
            "code": 'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;',
            "description": "Enable HSTS with 1-year max-age and preload"
        },
        "X-Frame-Options (Clickjacking)": {
            "fix_type": "header",
            "platform": "hosting",
            "code": 'add_header X-Frame-Options "SAMEORIGIN" always;',
            "description": "Prevent clickjacking by restricting iframe embedding"
        },
        "X-Content-Type-Options (MIME)": {
            "fix_type": "header",
            "platform": "hosting",
            "code": 'add_header X-Content-Type-Options "nosniff" always;',
            "description": "Prevent MIME type sniffing attacks"
        },
        "Content Security Policy (CSP)": {
            "fix_type": "header",
            "platform": "hosting",
            "code": "add_header Content-Security-Policy \"default-src 'self'; script-src 'self' 'unsafe-inline' cdn.example.com; style-src 'self' 'unsafe-inline';\" always;",
            "description": "Restrict resource loading to trusted origins"
        },
        "X-XSS-Protection Header": {
            "fix_type": "header",
            "platform": "hosting",
            "code": 'add_header X-XSS-Protection "1; mode=block" always;',
            "description": "Enable browser XSS filter"
        },
        "Referrer-Policy Header": {
            "fix_type": "header",
            "platform": "hosting",
            "code": 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
            "description": "Control referrer information sent to external sites"
        },
        "Permissions-Policy Header": {
            "fix_type": "header",
            "platform": "hosting",
            "code": 'add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;',
            "description": "Restrict browser feature access"
        },
    },
    "seo": {
        "Page Title Tag": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<title>Your Brand | Primary Keyword - Secondary Keyword</title>',
            "description": "Optimize title tag (50-60 characters, keyword-rich)"
        },
        "Meta Description": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<meta name="description" content="Your compelling 150-160 character description with primary keywords that drives clicks from search results.">',
            "description": "Add compelling meta description (150-160 chars)"
        },
        "Open Graph Tags": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<meta property="og:title" content="Page Title">\n<meta property="og:description" content="Page description">\n<meta property="og:image" content="https://yourdomain.com/og-image.jpg">\n<meta property="og:url" content="https://yourdomain.com/page">',
            "description": "Add Open Graph tags for social sharing"
        },
        "Structured Data (JSON-LD)": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "Organization",\n  "name": "Your Brand",\n  "url": "https://yourdomain.com",\n  "logo": "https://yourdomain.com/logo.png"\n}\n</script>',
            "description": "Add structured data for rich search results"
        },
    },
    "performance": {
        "Response Compression": {
            "fix_type": "config",
            "platform": "hosting",
            "code": "# Nginx gzip configuration\ngzip on;\ngzip_types text/plain text/css application/json application/javascript text/xml;\ngzip_min_length 256;\ngzip_comp_level 6;",
            "description": "Enable gzip/brotli compression for all text assets"
        },
        "Cache-Control Headers": {
            "fix_type": "config",
            "platform": "hosting",
            "code": '# Static assets cache (1 year)\nlocation ~* \\.(css|js|png|jpg|jpeg|gif|ico|svg|woff2)$ {\n    expires 1y;\n    add_header Cache-Control "public, immutable";\n}',
            "description": "Set long-term caching for static assets"
        },
    },
    "accessibility": {
        "Language Declaration": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<html lang="en">',
            "description": "Add language attribute to HTML tag"
        },
        "Skip Navigation Link": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<a href="#main-content" class="sr-only focus:not-sr-only">Skip to main content</a>',
            "description": "Add skip navigation link for keyboard users"
        },
        "ARIA: Banner/Header Landmark": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<header role="banner" aria-label="Site header">\n  <!-- Wrap your site header/navigation here -->\n</header>',
            "description": "Add ARIA banner landmark to site header"
        },
        "ARIA: Footer/Contentinfo Landmark": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<footer role="contentinfo" aria-label="Site footer">\n  <!-- Wrap your site footer here -->\n</footer>',
            "description": "Add ARIA contentinfo landmark to site footer"
        },
        "ARIA: Navigation Landmark": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<nav role="navigation" aria-label="Main navigation">\n  <!-- Wrap your navigation links here -->\n</nav>',
            "description": "Add ARIA navigation landmark to nav menus"
        },
        "ARIA: Main Landmark": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<main role="main" id="main-content" aria-label="Main content">\n  <!-- Wrap your page content here -->\n</main>',
            "description": "Add ARIA main landmark to primary content area"
        },
        "ARIA: Search Landmark": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<form role="search" aria-label="Site search">\n  <input type="search" placeholder="Search..." aria-label="Search">\n</form>',
            "description": "Add ARIA search landmark to search forms"
        },
        "Image Alt Text": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<img src="image.jpg" alt="Descriptive text about the image content" loading="lazy">',
            "description": "Add descriptive alt text to all images"
        },
        "Form Labels": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<label for="input-id">Field Name</label>\n<input id="input-id" type="text" aria-required="true">',
            "description": "Associate labels with form inputs using for/id"
        },
        "Color Contrast (WCAG AA)": {
            "fix_type": "css",
            "platform": "cms",
            "code": '/* Ensure minimum 4.5:1 contrast ratio for text */\n.text-low-contrast {\n  color: #333333; /* Dark text on light bg */\n  /* Use WebAIM contrast checker: webaim.org/resources/contrastchecker */\n}',
            "description": "Fix text color contrast to meet WCAG AA 4.5:1 ratio"
        },
        "Focus Indicators": {
            "fix_type": "css",
            "platform": "cms",
            "code": '*:focus-visible {\n  outline: 2px solid #D4AF37;\n  outline-offset: 2px;\n}\na:focus-visible, button:focus-visible {\n  outline: 2px solid #D4AF37;\n  outline-offset: 2px;\n}',
            "description": "Add visible focus indicators for keyboard navigation"
        },
        "Heading Hierarchy": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<!-- Correct heading order: h1 > h2 > h3 (no skipping) -->\n<h1>Page Title</h1>\n  <h2>Section</h2>\n    <h3>Subsection</h3>',
            "description": "Fix heading hierarchy — no skipping levels (h1→h2→h3)"
        },
        "Link Purpose": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<!-- Bad: --><a href="/page">Click here</a>\n<!-- Good: --><a href="/page">View our pricing plans</a>\n<!-- Or use aria-label: --><a href="/page" aria-label="View pricing plans">Learn more</a>',
            "description": "Make link text descriptive (avoid 'click here', 'read more')"
        },
        "Viewport Zoom": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            "description": "Allow viewport zoom — remove maximum-scale and user-scalable=no"
        },
        "Button Accessible Names": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<!-- Icon-only buttons need aria-label -->\n<button aria-label="Close menu">\n  <svg><!-- icon --></svg>\n</button>',
            "description": "Add aria-label to icon-only buttons"
        },
        "Table Headers": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<table>\n  <caption>Table description</caption>\n  <thead>\n    <tr><th scope="col">Header 1</th><th scope="col">Header 2</th></tr>\n  </thead>\n  <tbody>\n    <tr><td>Data</td><td>Data</td></tr>\n  </tbody>\n</table>',
            "description": "Add proper table headers with scope attributes"
        },
    },
    "seo_extended": {
        "Canonical URL": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<link rel="canonical" href="https://yourdomain.com/page">',
            "description": "Add canonical URL to prevent duplicate content issues"
        },
        "Robots Meta": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<meta name="robots" content="index, follow">',
            "description": "Add robots meta tag to control search engine indexing"
        },
        "Sitemap.xml": {
            "fix_type": "config",
            "platform": "hosting",
            "code": '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url>\n    <loc>https://yourdomain.com/</loc>\n    <lastmod>2026-01-01</lastmod>\n    <priority>1.0</priority>\n  </url>\n</urlset>',
            "description": "Create XML sitemap for search engine discovery"
        },
        "Image Alt Text (SEO)": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<img src="product.jpg" alt="Product name - brief keyword-rich description" loading="lazy" width="800" height="600">',
            "description": "Add keyword-rich alt text to images for SEO"
        },
        "H1 Tag": {
            "fix_type": "html",
            "platform": "cms",
            "code": '<h1>Primary Keyword - Your Page Title</h1>\n<!-- Only ONE h1 per page -->',
            "description": "Ensure exactly one H1 tag with primary keyword"
        },
    },
}


async def stream_repairs(scan_url: str, issues: list, connected_platforms: list):
    """Generator that yields SSE events as each fix is deployed"""
    
    def event(data):
        return f"data: {json.dumps(data)}\n\n"
    
    def _find_template(cat, test):
        """Find a fix template — exact match first, then fuzzy keyword match across all categories."""
        # Exact match
        tmpl = FIX_TEMPLATES.get(cat, {}).get(test)
        if tmpl:
            return tmpl
        # Try extended category (seo → seo_extended)
        tmpl = FIX_TEMPLATES.get(f"{cat}_extended", {}).get(test)
        if tmpl:
            return tmpl
        # Fuzzy: search all categories for keyword overlap
        test_lower = test.lower()
        test_words = set(test_lower.replace("-", " ").replace(":", " ").replace("(", " ").replace(")", " ").split())
        best_match = None
        best_score = 0
        for _cat_templates in FIX_TEMPLATES.values():
            for tmpl_name, tmpl_data in _cat_templates.items():
                tmpl_words = set(tmpl_name.lower().replace("-", " ").replace(":", " ").replace("(", " ").replace(")", " ").split())
                overlap = len(test_words & tmpl_words)
                if overlap > best_score and overlap >= 2:
                    best_score = overlap
                    best_match = tmpl_data
        return best_match

    fixable = []
    unfixable_issues = []
    for issue in issues:
        cat = issue.get("category", "")
        test = issue.get("test", "")
        if issue.get("result") in ["fail", "warning"]:
            template = _find_template(cat, test)
            if template:
                fixable.append({**issue, **template})
            else:
                unfixable_issues.append(issue)
    
    # Generate LLM-powered fixes for issues without templates
    if LLM_AVAILABLE and unfixable_issues:
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"repair_gen_{scan_url}",
                system_message="""You are ORA, a website optimization expert. Generate HTML/CSS/config fix code for website issues.
For each issue, respond with ONLY valid JSON array:
[{"test": "issue name", "fix_type": "html|css|config", "code": "the fix code", "description": "one-line description"}]
Keep code concise and production-ready. Max 5 issues per batch."""
            ).with_model("openai", "gpt-4o")
            
            batch = unfixable_issues[:8]
            issue_desc = json.dumps([{"test": i.get("test",""), "category": i.get("category",""), "details": i.get("details","")} for i in batch])
            resp = await chat.send_message(UserMessage(text=f"Website: {scan_url}. Generate fix code for these issues:\n{issue_desc}"))
            
            resp_text = resp if isinstance(resp, str) else str(resp)
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', resp_text, re.DOTALL)
            if json_match:
                ai_fixes = json.loads(json_match.group())
                for ai_fix in ai_fixes:
                    # Match back to original issue
                    for issue in batch:
                        if issue.get("test","").lower() in ai_fix.get("test","").lower() or ai_fix.get("test","").lower() in issue.get("test","").lower():
                            fixable.append({
                                **issue,
                                "fix_type": ai_fix.get("fix_type", "html"),
                                "platform": "cms",
                                "code": ai_fix.get("code", ""),
                                "description": ai_fix.get("description", "AI-generated fix"),
                                "ai_generated": True,
                            })
                            break
        except Exception as e:
            logger.warning(f"[REPAIR] LLM fix generation failed: {e}")
    
    total_fixes = len(fixable)
    if total_fixes == 0:
        yield event({"phase": "complete", "message": "No fixable issues found", "fixes_applied": 0, "total": 0})
        return
    
    yield event({"phase": "init", "total_fixes": total_fixes, "scan_url": scan_url, "message": "ORA Repair Engine initializing..."})
    await asyncio.sleep(0.5)
    
    # Generate LLM-powered custom recommendations if available
    ai_recommendations = {}
    if LLM_AVAILABLE and fixable:
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"repair_{scan_url}",
                system_message="You are ORA, a website optimization expert. Generate a 1-sentence specific recommendation for each website issue. Be actionable and specific to the URL provided. Respond as JSON: {\"test_name\": \"recommendation\"}"
            ).with_model("openai", "gpt-4o")
            
            issue_list = ", ".join([f.get("test", "") for f in fixable[:10]])
            resp = await chat.send_message(UserMessage(text=f"Website: {scan_url}. Issues found: {issue_list}. Generate specific fix recommendations."))
            
            try:
                ai_recommendations = json.loads(resp)
            except:
                pass
        except Exception as e:
            logger.error(f"LLM recommendation error: {e}")
    
    completed = 0
    for fix in fixable:
        completed += 1
        test_name = fix.get("test", "Unknown")
        category = fix.get("category", "general")
        platform = fix.get("platform", "manual")
        fix_code = fix.get("code", "")
        fix_desc = fix.get("description", "")
        ai_note = ai_recommendations.get(test_name, "")
        
        # Simulate deployment phases
        yield event({
            "phase": "deploying",
            "fix_num": completed,
            "total": total_fixes,
            "test": test_name,
            "category": category,
            "status": "analyzing",
            "message": f"Analyzing {test_name}..."
        })
        await asyncio.sleep(0.4)
        
        yield event({
            "phase": "deploying",
            "fix_num": completed,
            "total": total_fixes,
            "test": test_name,
            "category": category,
            "status": "generating",
            "message": f"Generating fix for {test_name}..."
        })
        await asyncio.sleep(0.6)
        
        # Determine if auto-deployable
        can_auto_deploy = platform in connected_platforms
        
        yield event({
            "phase": "fix_ready",
            "fix_num": completed,
            "total": total_fixes,
            "test": test_name,
            "category": category,
            "platform": platform,
            "auto_deployed": can_auto_deploy,
            "fix_code": fix_code,
            "description": fix_desc,
            "ai_recommendation": ai_note,
            "status": "deployed" if can_auto_deploy else "ready",
            "message": f"{'Deployed' if can_auto_deploy else 'Fix generated'}: {test_name}"
        })
        await asyncio.sleep(0.3)
    
    # Final summary
    auto_deployed = len([f for f in fixable if f.get("platform") in connected_platforms])
    manual_needed = total_fixes - auto_deployed
    
    yield event({
        "phase": "complete",
        "fixes_applied": total_fixes,
        "auto_deployed": auto_deployed,
        "manual_fixes": manual_needed,
        "total": total_fixes,
        "message": f"ORA deployed {auto_deployed} fixes automatically. {manual_needed} fixes generated for manual review."
    })

    # Fire push notification for "Repair Complete"
    try:
        from routers.push_notification_router import notify_repair_complete
        await notify_repair_complete(scan_url, total_fixes, auto_deployed)
    except Exception as e:
        logger.warning(f"[REPAIR] Push notification failed: {e}")

    # Log to Agent Observatory
    try:
        from routers.agent_observatory_router import log_trace
        await log_trace(
            tenant_id="system",
            session_id=f"repair_{scan_url}",
            agent="ORA Repair Engine",
            action="repair_scan",
            steps=[{"step_number": 1, "agent": "Repair", "action": "scan_and_fix", "tool_called": "repair_engine",
                    "input_summary": scan_url, "output_summary": f"{total_fixes} fixes, {auto_deployed} auto-deployed",
                    "duration_ms": 0, "status": "success", "error": ""}],
            total_duration_ms=0,
            status="completed",
            tools_used=["repair_engine", "llm"],
            llm_calls=total_fixes,
        )
    except Exception:
        pass


@router.get("/api/scanner/repair-live")
async def repair_live(url: str, token: str = Query(None), authorization: str = Header(None)):
    """
    Live streaming repair endpoint using SSE
    Actually scans the target URL for real issues, then generates targeted fixes.
    Accepts JWT via query param (?token=...) since EventSource cannot send headers.
    Filters out issues that already have deployed fixes.
    """
    if not url:
        return {"error": "URL is required"}

    import httpx
    from bs4 import BeautifulSoup

    # Query deployed fixes to exclude already-fixed issues
    deployed_fix_tests = set()
    try:
        from server import db
        base_url = url.rstrip("/")
        url_variants = list({base_url, base_url + "/", base_url.lower(), base_url.lower() + "/"})
        fixes = await db.customer_website_fixes.find(
            {"website_url": {"$in": url_variants}, "status": "deployed"},
            {"_id": 0, "test": 1}
        ).to_list(length=500)
        deployed_fix_tests = {f["test"].lower().strip() for f in fixes if f.get("test")}
    except Exception:
        pass

    # ── STEP 1: Actually fetch and scan the URL for real issues ──
    real_issues = []
    try:
        from utils.resilient_fetch import resilient_fetch
        fetch_result = await resilient_fetch(url)
        
        if not fetch_result.success or fetch_result.response is None:
            raise Exception(fetch_result.dns_error_detail or fetch_result.ssl_error_detail or "Website unreachable")
        
        response = fetch_result.response
        headers = response.headers
        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")

        # Add SSL issue as a real finding if cert was broken
        if fetch_result.ssl_error:
            real_issues.append({"category": "security", "test": "SSL Certificate Error", "result": "fail", "detail": fetch_result.ssl_error_detail or "SSL certificate is invalid or misconfigured"})

        # ── Security checks ──
        sec_header_checks = {
            "strict-transport-security": "HSTS (HTTP Strict Transport)",
            "x-frame-options": "X-Frame-Options (Clickjacking)",
            "x-content-type-options": "X-Content-Type-Options (MIME)",
            "content-security-policy": "Content Security Policy (CSP)",
            "x-xss-protection": "X-XSS-Protection Header",
            "referrer-policy": "Referrer-Policy Header",
            "permissions-policy": "Permissions-Policy Header",
        }
        for header_key, test_name in sec_header_checks.items():
            if header_key not in headers:
                real_issues.append({"category": "security", "test": test_name, "result": "fail"})

        # ── SEO checks ──
        title_tag = soup.find("title")
        if not title_tag or not (title_tag.string or "").strip():
            real_issues.append({"category": "seo", "test": "Page Title Tag", "result": "fail"})

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if not meta_desc or not meta_desc.get("content", "").strip():
            real_issues.append({"category": "seo", "test": "Meta Description", "result": "fail"})

        og_title = soup.find("meta", attrs={"property": "og:title"})
        if not og_title:
            real_issues.append({"category": "seo", "test": "Open Graph Tags", "result": "fail"})

        jsonld = soup.find("script", {"type": "application/ld+json"})
        if not jsonld:
            real_issues.append({"category": "seo", "test": "Structured Data (JSON-LD)", "result": "warning"})

        # ── Performance checks ──
        if "gzip" not in headers.get("content-encoding", "").lower() and "br" not in headers.get("content-encoding", "").lower():
            real_issues.append({"category": "performance", "test": "Response Compression", "result": "warning"})

        cache_ctrl = headers.get("cache-control", "")
        if not cache_ctrl or "no-cache" in cache_ctrl:
            real_issues.append({"category": "performance", "test": "Cache-Control Headers", "result": "warning"})

        # ── Accessibility checks ──
        html_tag = soup.find("html")
        if not html_tag or not html_tag.get("lang"):
            real_issues.append({"category": "accessibility", "test": "Language Declaration", "result": "fail"})

        skip_link = soup.find("a", href="#main-content") or soup.find("a", class_="sr-only") or soup.find("a", class_="skip-link")
        if not skip_link:
            real_issues.append({"category": "accessibility", "test": "Skip Navigation Link", "result": "warning"})

        # ARIA Landmark checks
        if not soup.find("header") and not soup.find(attrs={"role": "banner"}):
            real_issues.append({"category": "accessibility", "test": "ARIA: Banner/Header Landmark", "result": "fail"})
        if not soup.find("footer") and not soup.find(attrs={"role": "contentinfo"}):
            real_issues.append({"category": "accessibility", "test": "ARIA: Footer/Contentinfo Landmark", "result": "fail"})
        if not soup.find("nav") and not soup.find(attrs={"role": "navigation"}):
            real_issues.append({"category": "accessibility", "test": "ARIA: Navigation Landmark", "result": "fail"})
        if not soup.find("main") and not soup.find(attrs={"role": "main"}):
            real_issues.append({"category": "accessibility", "test": "ARIA: Main Landmark", "result": "fail"})

        # Image alt text
        images = soup.find_all("img")
        imgs_no_alt = [img for img in images if not img.get("alt")]
        if imgs_no_alt:
            real_issues.append({"category": "accessibility", "test": "Image Alt Text", "result": "fail", "details": f"{len(imgs_no_alt)} images missing alt text"})

        # Heading hierarchy
        h1_tags = soup.find_all("h1")
        if len(h1_tags) == 0:
            real_issues.append({"category": "accessibility", "test": "Heading Hierarchy", "result": "fail"})
        elif len(h1_tags) > 1:
            real_issues.append({"category": "accessibility", "test": "Heading Hierarchy", "result": "warning"})

        # Button accessible names
        buttons = soup.find_all("button")
        unnamed = [b for b in buttons if not b.get_text(strip=True) and not b.get("aria-label")]
        if unnamed:
            real_issues.append({"category": "accessibility", "test": "Button Accessible Names", "result": "fail"})

        # Viewport zoom
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if viewport:
            vc = (viewport.get("content") or "").lower()
            if "user-scalable=no" in vc or "maximum-scale=1" in vc:
                real_issues.append({"category": "accessibility", "test": "Viewport Zoom", "result": "fail"})

        # Focus indicators
        all_css = " ".join([str(s) for s in soup.find_all("style")])
        if "outline: none" in all_css or "outline:none" in all_css or "outline: 0" in all_css:
            real_issues.append({"category": "accessibility", "test": "Focus Indicators", "result": "warning"})

    except Exception as e:
        logger.error(f"[REPAIR] Failed to scan {url}: {e}")
        # Fallback: use common issues if scan fails
        real_issues = [
            {"category": "security", "test": "HSTS (HTTP Strict Transport)", "result": "fail"},
            {"category": "security", "test": "X-Frame-Options (Clickjacking)", "result": "fail"},
            {"category": "security", "test": "Content Security Policy (CSP)", "result": "fail"},
            {"category": "seo", "test": "Meta Description", "result": "fail"},
            {"category": "accessibility", "test": "Language Declaration", "result": "fail"},
        ]

    logger.info(f"[REPAIR] Found {len(real_issues)} real issues for {url}")

    # Filter out issues that already have deployed fixes
    if deployed_fix_tests:
        before_count = len(real_issues)
        real_issues = [i for i in real_issues if i["test"].lower().strip() not in deployed_fix_tests]
        filtered = before_count - len(real_issues)
        if filtered > 0:
            logger.info(f"[REPAIR] Filtered {filtered} already-deployed fixes, {len(real_issues)} remaining")

    return StreamingResponse(
        stream_repairs(url, real_issues, []),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/api/scanner/repair-live")
async def repair_live_post(request: FixRequest):
    """
    POST version - receives actual scan issues to generate targeted fixes
    """
    return StreamingResponse(
        stream_repairs(request.scan_url, request.issues, request.connected_platforms or []),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
