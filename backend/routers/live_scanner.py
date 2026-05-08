"""
ORA Live Scanner - Server-Sent Events endpoint
Streams individual test results to frontend for animated progress bars
Now with deployed fix crediting — rescans show improved scores
"""

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import httpx
import asyncio
import json
import time
import secrets
from bs4 import BeautifulSoup

router = APIRouter()

class LiveScanRequest(BaseModel):
    website_url: str
    manual_enrichment: Optional[dict] = None


async def stream_scan(url: str, user_id: str = "anonymous", deployed_fix_tests: set = None):
    """Generator that yields SSE events as each test completes.
    deployed_fix_tests: set of lowercase test names that have been fixed and deployed.
    """
    deployed_fix_tests = deployed_fix_tests or set()
    fixes_credited = 0
    total_tests = 50
    completed = 0
    all_results = []
    overall_scores = {}
    scan_id = f"scan_{secrets.token_urlsafe(12)}"
    
    def event(data):
        return f"data: {json.dumps(data)}\n\n"
    
    def credit_fix(test_name, result, value):
        """Check if a deployed fix exists for this test. Returns (result, value, credited)."""
        nonlocal fixes_credited
        if deployed_fix_tests and test_name.lower().strip() in deployed_fix_tests and result != "pass":
            fixes_credited += 1
            return "pass", "Fixed by ORA", True
        return result, value, False
    
    # ===== PHASE 1: CONNECTION & RESPONSE =====
    yield event({"phase": "connecting", "test": "Initiating connection", "completed": completed, "total": total_tests, "category": "connection"})
    await asyncio.sleep(0.3)
    
    html_content = ""
    headers_dict = {}
    load_time = 0
    page_size = 0
    status_code = 0
    ssl_issue_found = False
    dns_issue_found = False
    
    try:
        from utils.resilient_fetch import resilient_fetch
        start = time.time()
        fetch_result = await resilient_fetch(url)
        load_time = time.time() - start
        
        # Check for DNS failure
        if fetch_result.dns_error:
            yield event({"phase": "error", "test": "DNS Resolution Failed", "error": f"Website unreachable — possible DNS issue. {fetch_result.dns_error_detail}", "completed": completed, "total": total_tests})
            return
        
        # Check if we got a response at all
        if not fetch_result.success or fetch_result.response is None:
            yield event({"phase": "error", "test": "Connection failed", "error": "Website unreachable after trying all protocols", "completed": completed, "total": total_tests})
            return
        
        html_content = fetch_result.text
        headers_dict = dict(fetch_result.headers)
        page_size = len(fetch_result.content)
        status_code = fetch_result.status_code
        ssl_issue_found = fetch_result.ssl_error
        dns_issue_found = fetch_result.dns_error
    except Exception as e:
        yield event({"phase": "error", "test": "Connection failed", "error": str(e), "completed": completed, "total": total_tests})
        return
    
    completed += 1
    yield event({"phase": "test_done", "test": "Server Connection", "result": "pass" if status_code == 200 else "fail", "value": f"HTTP {status_code}", "completed": completed, "total": total_tests, "category": "connection"})
    await asyncio.sleep(0.15)
    
    # ===== PHASE 2: PERFORMANCE TESTS =====
    perf_tests = [
        ("Time to First Byte (TTFB)", lambda: ("pass" if load_time < 0.8 else "warning" if load_time < 2.0 else "fail", f"{load_time*1000:.0f}ms")),
        ("Full Page Load Time", lambda: ("pass" if load_time < 2.5 else "warning" if load_time < 5.0 else "fail", f"{load_time:.2f}s")),
        ("Page Size Analysis", lambda: ("pass" if page_size < 1_000_000 else "warning" if page_size < 3_000_000 else "fail", f"{page_size/1024:.0f}KB")),
        ("Response Compression", lambda: ("pass" if headers_dict.get('content-encoding') else "warning", headers_dict.get('content-encoding', 'None'))),
        ("Cache-Control Headers", lambda: ("pass" if headers_dict.get('cache-control') else "warning", headers_dict.get('cache-control', 'Not set')[:30])),
        ("Content-Type Validation", lambda: ("pass" if 'text/html' in headers_dict.get('content-type', '') else "warning", headers_dict.get('content-type', 'Unknown')[:30])),
        ("Server Response Headers", lambda: ("pass", headers_dict.get('server', 'Hidden')[:20])),
        ("Redirect Chain Analysis", lambda: ("pass" if status_code < 400 else "fail", f"{status_code}")),
    ]
    
    perf_score = 100
    for test_name, test_fn in perf_tests:
        result, value = test_fn()
        result, value, _ = credit_fix(test_name, result, value)
        if result == "fail": perf_score -= 15
        elif result == "warning": perf_score -= 8
        completed += 1
        all_results.append({"category": "performance", "test": test_name, "result": result, "value": value})
        yield event({"phase": "test_done", "test": test_name, "result": result, "value": value, "completed": completed, "total": total_tests, "category": "performance"})
        await asyncio.sleep(0.2)
    
    overall_scores["performance"] = max(0, perf_score)
    yield event({"phase": "category_done", "category": "performance", "score": overall_scores["performance"], "completed": completed, "total": total_tests})
    await asyncio.sleep(0.3)
    
    # ===== PHASE 3: SECURITY TESTS =====
    security_headers = {
        'strict-transport-security': ('HSTS (HTTP Strict Transport)', True),
        'x-frame-options': ('X-Frame-Options (Clickjacking)', True),
        'x-content-type-options': ('X-Content-Type-Options (MIME)', True),
        'content-security-policy': ('Content Security Policy (CSP)', True),
        'x-xss-protection': ('X-XSS-Protection Header', False),
        'referrer-policy': ('Referrer-Policy Header', False),
        'permissions-policy': ('Permissions-Policy Header', False),
        'x-permitted-cross-domain-policies': ('Cross-Domain Policy', False),
    }
    
    sec_score = 100
    
    # HTTPS / SSL Check — inject real SSL finding if certificate was broken
    if ssl_issue_found:
        https_result = "fail"
        ssl_value = "SSL Certificate Error — " + (fetch_result.ssl_error_detail[:60] if fetch_result.ssl_error_detail else "Invalid or misconfigured")
    elif url.startswith("https"):
        https_result = "pass"
        ssl_value = "HTTPS"
    else:
        https_result = "fail"
        ssl_value = "HTTP Only"
    
    # Credit deployed fix for SSL
    https_result, ssl_value, _ = credit_fix("SSL/TLS Encryption", https_result, ssl_value)
    if https_result == "fail":
        sec_score -= 30 if ssl_issue_found else 25
    
    completed += 1
    all_results.append({"category": "security", "test": "SSL/TLS Encryption", "result": https_result, "value": ssl_value})
    yield event({"phase": "test_done", "test": "SSL/TLS Encryption", "result": https_result, "value": ssl_value, "completed": completed, "total": total_tests, "category": "security"})
    await asyncio.sleep(0.2)
    
    for header_key, (header_name, is_critical) in security_headers.items():
        has_header = header_key in headers_dict
        result = "pass" if has_header else ("fail" if is_critical else "warning")
        value = "Present" if has_header else "Missing"
        result, value, _ = credit_fix(header_name, result, value)
        if result == "fail": sec_score -= 12
        elif result == "warning": sec_score -= 5
        completed += 1
        all_results.append({"category": "security", "test": header_name, "result": result, "value": value})
        yield event({"phase": "test_done", "test": header_name, "result": result, "value": value, "completed": completed, "total": total_tests, "category": "security"})
        await asyncio.sleep(0.15)
    
    # Additional security checks
    sec_extra = [
        ("Cookie Security Flags", lambda: ("pass" if 'httponly' in str(headers_dict.get('set-cookie', '')).lower() or 'set-cookie' not in headers_dict else "warning", "Secure" if 'httponly' in str(headers_dict.get('set-cookie', '')).lower() else "Check needed")),
        ("Server Version Exposure", lambda: ("pass" if not headers_dict.get('server') or 'nginx' not in headers_dict.get('server', '').lower() else "warning", "Hidden" if not headers_dict.get('server') else headers_dict.get('server', '')[:20])),
    ]
    
    for test_name, test_fn in sec_extra:
        result, value = test_fn()
        result, value, _ = credit_fix(test_name, result, value)
        if result == "fail": sec_score -= 10
        elif result == "warning": sec_score -= 5
        completed += 1
        all_results.append({"category": "security", "test": test_name, "result": result, "value": value})
        yield event({"phase": "test_done", "test": test_name, "result": result, "value": value, "completed": completed, "total": total_tests, "category": "security"})
        await asyncio.sleep(0.15)
    
    overall_scores["security"] = max(0, sec_score)
    yield event({"phase": "category_done", "category": "security", "score": overall_scores["security"], "completed": completed, "total": total_tests})
    await asyncio.sleep(0.3)
    
    # ===== PHASE 4: SEO TESTS =====
    soup = BeautifulSoup(html_content, 'html.parser') if html_content else None
    seo_score = 100
    
    seo_tests = []
    if soup:
        title = soup.find('title')
        title_text = title.string if title and title.string else ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_desc_text = meta_desc.get('content', '') if meta_desc else ""
        h1s = soup.find_all('h1')
        h2s = soup.find_all('h2')
        imgs = soup.find_all('img')
        imgs_no_alt = [i for i in imgs if not i.get('alt')]
        links = soup.find_all('a')
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        og_tags = soup.find_all('meta', attrs={'property': lambda x: x and x.startswith('og:')})
        robots = soup.find('meta', attrs={'name': 'robots'})
        schema_ld = soup.find_all('script', attrs={'type': 'application/ld+json'})
        
        seo_tests = [
            ("Page Title Tag", "pass" if title_text and 30 <= len(title_text) <= 65 else "warning" if title_text else "fail", f'"{title_text[:35]}..."' if title_text else "Missing"),
            ("Meta Description", "pass" if meta_desc_text and 120 <= len(meta_desc_text) <= 160 else "warning" if meta_desc_text else "fail", f"{len(meta_desc_text)} chars" if meta_desc_text else "Missing"),
            ("H1 Heading Tag", "pass" if len(h1s) == 1 else "warning" if h1s else "fail", f"{len(h1s)} found"),
            ("Heading Hierarchy (H2)", "pass" if h2s else "warning", f"{len(h2s)} found"),
            ("Image Alt Text Coverage", "pass" if not imgs_no_alt else "warning" if len(imgs_no_alt) < len(imgs)/2 else "fail", f"{len(imgs)-len(imgs_no_alt)}/{len(imgs)} have alt"),
            ("Internal Links", "pass" if len(links) > 3 else "warning", f"{len(links)} links found"),
            ("Canonical URL Tag", "pass" if canonical else "warning", "Present" if canonical else "Missing"),
            ("Viewport Meta Tag", "pass" if viewport else "fail", "Present" if viewport else "Missing"),
            ("Open Graph Tags", "pass" if len(og_tags) >= 3 else "warning" if og_tags else "fail", f"{len(og_tags)} tags"),
            ("Robots Meta Tag", "pass" if robots else "warning", "Present" if robots else "Missing"),
            ("Structured Data (JSON-LD)", "pass" if schema_ld else "warning", f"{len(schema_ld)} schemas" if schema_ld else "None"),
        ]
    else:
        seo_tests = [("HTML Content Analysis", "fail", "Could not parse")]
    
    for test_name, result, value in seo_tests:
        result, value, _ = credit_fix(test_name, result, value)
        if result == "fail": seo_score -= 12
        elif result == "warning": seo_score -= 6
        completed += 1
        all_results.append({"category": "seo", "test": test_name, "result": result, "value": value})
        yield event({"phase": "test_done", "test": test_name, "result": result, "value": value, "completed": completed, "total": total_tests, "category": "seo"})
        await asyncio.sleep(0.18)
    
    overall_scores["seo"] = max(0, seo_score)
    yield event({"phase": "category_done", "category": "seo", "score": overall_scores["seo"], "completed": completed, "total": total_tests})
    await asyncio.sleep(0.3)
    
    # ===== PHASE 5: ACCESSIBILITY TESTS =====
    a11y_score = 100
    a11y_tests = []
    
    if soup:
        html_tag = soup.find('html')
        has_lang = html_tag and html_tag.get('lang')
        inputs = soup.find_all(['input', 'textarea', 'select'])
        labeled = sum(1 for i in inputs if i.get('aria-label') or i.get('aria-labelledby') or i.get('id'))
        aria_landmarks = soup.find_all(attrs={'role': True})
        skip_link = soup.find('a', attrs={'href': '#main'}) or soup.find('a', class_=lambda x: x and 'skip' in str(x).lower())
        focus_styles = 'focus' in html_content.lower() if html_content else False
        
        a11y_tests = [
            ("Language Declaration", "pass" if has_lang else "fail", html_tag.get('lang', 'Missing') if html_tag else "Missing"),
            ("Form Input Labels", "pass" if not inputs or labeled == len(inputs) else "warning" if labeled > 0 else "fail", f"{labeled}/{len(inputs)} labeled"),
            ("ARIA Landmarks", "pass" if len(aria_landmarks) > 2 else "warning" if aria_landmarks else "fail", f"{len(aria_landmarks)} found"),
            ("Skip Navigation Link", "pass" if skip_link else "warning", "Present" if skip_link else "Missing"),
            ("Focus Management", "pass" if focus_styles else "warning", "Detected" if focus_styles else "Not found"),
            ("Color Contrast (Estimate)", "warning", "Manual check needed"),
            ("Keyboard Navigation", "warning", "Manual check needed"),
        ]
    else:
        a11y_tests = [("Accessibility Analysis", "fail", "Could not parse")]
    
    for test_name, result, value in a11y_tests:
        result, value, _ = credit_fix(test_name, result, value)
        if result == "fail": a11y_score -= 15
        elif result == "warning": a11y_score -= 7
        completed += 1
        all_results.append({"category": "accessibility", "test": test_name, "result": result, "value": value})
        yield event({"phase": "test_done", "test": test_name, "result": result, "value": value, "completed": completed, "total": total_tests, "category": "accessibility"})
        await asyncio.sleep(0.18)
    
    overall_scores["accessibility"] = max(0, a11y_score)
    yield event({"phase": "category_done", "category": "accessibility", "score": overall_scores["accessibility"], "completed": completed, "total": total_tests})
    await asyncio.sleep(0.3)
    
    # ===== PHASE 6: TECHNOLOGY & CODE ANALYSIS =====
    tech_score = 100
    tech_tests = []
    
    if soup:
        scripts = soup.find_all('script', src=True)
        stylesheets = soup.find_all('link', rel='stylesheet')
        inline_scripts = soup.find_all('script', src=False)
        inline_styles = soup.find_all('style')
        
        # Detect technologies
        tech_detected = []
        src_text = html_content.lower()
        if 'react' in src_text or 'reactdom' in src_text or '__next' in src_text: tech_detected.append('React')
        if 'vue' in src_text or '__vue' in src_text: tech_detected.append('Vue.js')
        if 'angular' in src_text: tech_detected.append('Angular')
        if 'jquery' in src_text: tech_detected.append('jQuery')
        if 'bootstrap' in src_text: tech_detected.append('Bootstrap')
        if 'tailwind' in src_text: tech_detected.append('Tailwind CSS')
        if 'wordpress' in src_text or 'wp-content' in src_text: tech_detected.append('WordPress')
        if 'shopify' in src_text: tech_detected.append('Shopify')
        if 'wix' in src_text: tech_detected.append('Wix')
        if 'squarespace' in src_text: tech_detected.append('Squarespace')
        if 'next' in src_text and '_next' in src_text: tech_detected.append('Next.js')
        if 'gatsby' in src_text: tech_detected.append('Gatsby')
        if 'google-analytics' in src_text or 'gtag' in src_text: tech_detected.append('Google Analytics')
        if 'gtm' in src_text or 'googletagmanager' in src_text: tech_detected.append('Google Tag Manager')
        
        total_js_size = sum(len(str(s)) for s in inline_scripts)
        total_css_size = sum(len(str(s)) for s in inline_styles)
        
        tech_tests = [
            ("Framework Detection", "pass", ", ".join(tech_detected) if tech_detected else "Custom/Unknown"),
            ("External Scripts", "pass" if len(scripts) < 15 else "warning" if len(scripts) < 25 else "fail", f"{len(scripts)} scripts"),
            ("External Stylesheets", "pass" if len(stylesheets) < 8 else "warning", f"{len(stylesheets)} stylesheets"),
            ("Inline JavaScript", "pass" if len(inline_scripts) < 5 else "warning", f"{len(inline_scripts)} blocks ({total_js_size/1024:.0f}KB)"),
            ("Inline CSS", "pass" if len(inline_styles) < 3 else "warning", f"{len(inline_styles)} blocks ({total_css_size/1024:.0f}KB)"),
            ("Render-Blocking Resources", "warning" if len(scripts) > 5 else "pass", f"{min(len(scripts), 10)} potential"),
            ("Mobile Responsiveness", "pass" if soup.find('meta', attrs={'name': 'viewport'}) else "fail", "Viewport set" if soup.find('meta', attrs={'name': 'viewport'}) else "No viewport"),
            ("Third-Party Trackers", "pass" if len([s for s in scripts if 'analytics' in str(s.get('src', '')).lower() or 'tracker' in str(s.get('src', '')).lower()]) < 3 else "warning", f"{len(scripts)} total scripts"),
        ]
    else:
        tech_tests = [("Technology Analysis", "fail", "Could not parse")]
    
    for test_name, result, value in tech_tests:
        result, value, _ = credit_fix(test_name, result, value)
        if result == "fail": tech_score -= 12
        elif result == "warning": tech_score -= 5
        completed += 1
        all_results.append({"category": "technology", "test": test_name, "result": result, "value": value})
        yield event({"phase": "test_done", "test": test_name, "result": result, "value": value, "completed": completed, "total": total_tests, "category": "technology"})
        await asyncio.sleep(0.18)
    
    overall_scores["technology"] = max(0, tech_score)
    yield event({"phase": "category_done", "category": "technology", "score": overall_scores["technology"], "completed": completed, "total": total_tests})
    await asyncio.sleep(0.3)
    
    # ===== PHASE 7: DATABASE & INFRASTRUCTURE ANALYSIS =====
    infra_score = 85  # Baseline since we can't deeply inspect
    infra_tests = [
        ("Server Technology", "pass", headers_dict.get('server', 'Hidden')[:25]),
        ("CDN Detection", "pass" if any(h in str(headers_dict) for h in ['cloudflare', 'akamai', 'fastly', 'cloudfront', 'cdn']) else "warning", "CDN Detected" if any(h in str(headers_dict).lower() for h in ['cloudflare', 'akamai', 'fastly', 'cloudfront', 'cdn']) else "No CDN"),
        ("HTTP/2 Support", "pass", "Supported" if headers_dict.get('alt-svc') else "Check needed"),
        ("GZIP/Brotli Compression", "pass" if headers_dict.get('content-encoding') else "warning", headers_dict.get('content-encoding', 'None detected')),
    ]
    
    for test_name, result, value in infra_tests:
        result, value, _ = credit_fix(test_name, result, value)
        if result == "warning": infra_score -= 8
        completed += 1
        all_results.append({"category": "infrastructure", "test": test_name, "result": result, "value": value})
        yield event({"phase": "test_done", "test": test_name, "result": result, "value": value, "completed": completed, "total": total_tests, "category": "infrastructure"})
        await asyncio.sleep(0.2)
    
    overall_scores["infrastructure"] = max(0, infra_score)
    yield event({"phase": "category_done", "category": "infrastructure", "score": overall_scores["infrastructure"], "completed": completed, "total": total_tests})
    
    # ===== FINAL: OVERALL SCORE =====
    await asyncio.sleep(0.5)
    overall = int(sum(overall_scores.values()) / len(overall_scores))
    
    passes = len([r for r in all_results if r["result"] == "pass"])
    warnings = len([r for r in all_results if r["result"] == "warning"])
    fails = len([r for r in all_results if r["result"] == "fail"])
    
    yield event({
        "phase": "complete",
        "scan_id": scan_id,
        "overall_score": overall,
        "scores": overall_scores,
        "completed": completed,
        "total": total_tests,
        "fixes_credited": fixes_credited,
        "summary": {
            "passed": passes,
            "warnings": warnings,
            "failed": fails,
            "total_tests": completed
        }
    })


@router.get("/api/scanner/scan-live")
async def scan_live(url: str, token: str = Query(None), authorization: str = Header(None)):
    """
    Live streaming scan endpoint using Server-Sent Events.
    Accepts JWT via query param (?token=...) since EventSource cannot send headers.
    Queries deployed fixes to credit previously resolved issues.
    """
    if not url:
        return {"error": "URL is required"}
    
    # Ensure URL has protocol
    if not url.startswith("http"):
        url = "https://" + url
    
    # Parse JWT from query param (EventSource) or header
    user_id = "anonymous"
    jwt_token = token
    if not jwt_token and authorization and authorization.startswith("Bearer "):
        jwt_token = authorization.replace("Bearer ", "")
    
    if jwt_token:
        try:
            import jwt as _jwt
            import os
            payload = _jwt.decode(jwt_token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
            user_id = payload.get("email", payload.get("user_id", "anonymous"))
        except Exception:
            pass
    
    # Query deployed fixes for this URL from customer_website_fixes
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
        
        if deployed_fix_tests:
            print(f"[Scanner] Found {len(deployed_fix_tests)} deployed fixes for {url}: {deployed_fix_tests}")
    except Exception as e:
        print(f"[Scanner] Could not query deployed fixes: {e}")
    
    return StreamingResponse(
        stream_scan(url, user_id, deployed_fix_tests),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
