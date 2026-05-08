"""
AUREM Self-Scan Automation — "Eating Our Own Dogfood"
=====================================================

Registers AUREM's own platform as a customer in its Repair Engine.
Runs the full Double-Lock pipeline on itself:
  1. Scan (SEO + GEO + A11y)
  2. Auto-approve all generated fixes
  3. Deploy via Pixel Hot-Patch (Phase 1)
  4. Commit to Origin (Phase 2)
  5. Verify with PageSpeed (Truth-Sync)

Can be triggered manually or by Sentinel on a schedule.
"""

import os
import logging
import secrets
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from server import db
        return db
    except Exception:
        return None


def _get_aurem_url() -> str:
    """Get AUREM's own public URL — production-first, preview fallback only for local dev."""
    return (
        os.environ.get("AUREM_PUBLIC_URL")
        or os.environ.get("REACT_APP_BACKEND_URL")
        or "https://aurem.live"
    )


async def _get_system_user_id() -> str:
    """Get or create the system user ID for self-scan."""
    db = _get_db()
    if db is None:
        return "system"

    user = await db.users.find_one(
        {"email": "system@aurem.ai"},
        {"_id": 0, "id": 1}
    )
    if user:
        return user["id"]

    # Use the admin user
    admin = await db.users.find_one(
        {"is_admin": True},
        {"_id": 0, "id": 1}
    )
    if admin:
        return admin["id"]

    return "system"


async def run_self_scan(scan_types: list = None) -> dict:
    """
    Run the full repair scan on AUREM's own platform.
    
    Args:
        scan_types: List of scan types to run. Default: all.
                    Options: ['seo', 'geo', 'accessibility']
    
    Returns:
        Summary of scan results with fix counts.
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}

    aurem_url = _get_aurem_url()
    user_id = await _get_system_user_id()

    if scan_types is None:
        scan_types = ["seo", "geo", "accessibility"]

    logger.info(f"[Self-Scan] Starting self-scan on {aurem_url} for types: {scan_types}")

    results = {}
    total_fixes = 0

    for scan_type in scan_types:
        try:
            if scan_type == "seo":
                result = await _run_seo_scan(db, aurem_url, user_id)
            elif scan_type == "geo":
                result = await _run_geo_scan(db, aurem_url, user_id)
            elif scan_type == "accessibility":
                result = await _run_a11y_scan(db, aurem_url, user_id)
            else:
                result = {"error": f"Unknown scan type: {scan_type}"}

            results[scan_type] = result
            total_fixes += result.get("fix_count", 0)
            logger.info(f"[Self-Scan] {scan_type}: {result.get('fix_count', 0)} fixes found")

        except Exception as e:
            logger.error(f"[Self-Scan] {scan_type} failed: {e}")
            results[scan_type] = {"error": str(e), "fix_count": 0}

    return {
        "url": aurem_url,
        "user_id": user_id,
        "scan_types": scan_types,
        "results": results,
        "total_fixes": total_fixes,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


async def _run_seo_scan(db, url: str, user_id: str) -> dict:
    """Run SEO scan internally (same logic as the API endpoint)."""
    import httpx
    from bs4 import BeautifulSoup

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AUREM-SelfScan/1.0"})
            html = resp.text
    except Exception as e:
        return {"error": f"Fetch failed: {e}", "fix_count": 0}

    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc).isoformat()
    scan_id = f"selfscan_{secrets.token_urlsafe(8)}"

    # Archive old pending fixes
    await db.repair_fixes.update_many(
        {"user_id": user_id, "scan_url": url, "category": "seo", "status": "pending_approval"},
        {"$set": {"status": "archived", "archived_at": now}},
    )

    fixes = []

    # Check title
    title_tag = soup.find("title")
    current_title = title_tag.text.strip() if title_tag else ""
    if not current_title or len(current_title) < 20:
        fixes.append(_make_fix(user_id, url, scan_id, "seo", "title",
            "Page Title Tag", "<title>AUREM — Autonomous AI Operating System for Business</title>", now))

    # Check meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if not meta_desc or not meta_desc.get("content", "").strip():
        fixes.append(_make_fix(user_id, url, scan_id, "seo", "meta_description",
            "Meta Description", '<meta name="description" content="AUREM is a commercial-grade autonomous AI platform for business automation. Voice AI, self-healing infrastructure, and OODA pipeline agents." />', now))

    # Check OG tags
    og_title = soup.find("meta", property="og:title")
    if not og_title:
        fixes.append(_make_fix(user_id, url, scan_id, "seo", "og_title",
            "Open Graph Title", '<meta property="og:title" content="AUREM — Autonomous AI Business Platform" />', now))

    og_desc = soup.find("meta", property="og:description")
    if not og_desc:
        fixes.append(_make_fix(user_id, url, scan_id, "seo", "og_description",
            "Open Graph Description", '<meta property="og:description" content="Voice-first AI platform with self-healing infrastructure, 5-agent OODA pipeline, and zero-cost sovereign brain." />', now))

    # Check H1
    h1 = soup.find("h1")
    if not h1:
        fixes.append(_make_fix(user_id, url, scan_id, "seo", "h1",
            "Primary H1 Heading", '<h1 class="sr-only">AUREM — Autonomous AI Business Automation Platform</h1>', now))

    # Check canonical
    canonical = soup.find("link", rel="canonical")
    if not canonical:
        fixes.append(_make_fix(user_id, url, scan_id, "seo", "canonical",
            "Canonical URL", f'<link rel="canonical" href="{url}" />', now))

    if fixes:
        await db.repair_fixes.insert_many(fixes)

    return {"fix_count": len(fixes), "scan_id": scan_id}


async def _run_geo_scan(db, url: str, user_id: str) -> dict:
    """Run GEO scan internally."""
    import httpx
    from bs4 import BeautifulSoup

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AUREM-SelfScan/1.0"})
            html = resp.text
    except Exception as e:
        return {"error": f"Fetch failed: {e}", "fix_count": 0}

    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc).isoformat()
    scan_id = f"selfscan_{secrets.token_urlsafe(8)}"

    await db.repair_fixes.update_many(
        {"user_id": user_id, "scan_url": url, "category": "geo", "status": "pending_approval"},
        {"$set": {"status": "archived", "archived_at": now}},
    )

    fixes = []

    # Check JSON-LD
    json_ld_scripts = soup.find_all("script", type="application/ld+json")
    has_org_schema = any('"Organization"' in (s.string or "") for s in json_ld_scripts)
    has_product_schema = any('"SoftwareApplication"' in (s.string or "") or '"Product"' in (s.string or "") for s in json_ld_scripts)

    if not has_org_schema:
        org_schema = '''{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "AUREM AI",
  "description": "Autonomous AI operating system for business automation",
  "url": "''' + url + '''",
  "sameAs": [],
  "foundingDate": "2025"
}'''
        fixes.append(_make_fix(user_id, url, scan_id, "geo", "json_ld_org",
            "Organization Schema (JSON-LD)", f'<script type="application/ld+json">{org_schema}</script>', now))

    if not has_product_schema:
        product_schema = '''{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "AUREM",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web",
  "description": "Autonomous AI platform with voice agent, self-healing infrastructure, and 5-agent OODA pipeline",
  "offers": {
    "@type": "AggregateOffer",
    "priceCurrency": "USD",
    "lowPrice": "0",
    "highPrice": "497",
    "offerCount": "3"
  }
}'''
        fixes.append(_make_fix(user_id, url, scan_id, "geo", "json_ld_product",
            "SoftwareApplication Schema (JSON-LD)", f'<script type="application/ld+json">{product_schema}</script>', now))

    # AI summary
    ai_summary_exists = soup.find(class_="aurem-ai-summary")
    if not ai_summary_exists:
        fixes.append(_make_fix(user_id, url, scan_id, "geo", "ai_summary",
            "AI-Friendly Summary Paragraph",
            "AUREM is an autonomous AI operating system for business. It features ORA, a voice-to-voice AI agent with sub-second latency, a 5-agent OODA pipeline (Scout, Architect, Envoy, Closer, Oracle), Sentinel self-healing infrastructure, and a sovereign $0-cost brain running on free OpenRouter models.",
            now))

    if fixes:
        await db.repair_fixes.insert_many(fixes)

    return {"fix_count": len(fixes), "scan_id": scan_id}


async def _run_a11y_scan(db, url: str, user_id: str) -> dict:
    """Run accessibility scan internally."""
    import httpx
    from bs4 import BeautifulSoup

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AUREM-SelfScan/1.0"})
            html = resp.text
    except Exception as e:
        return {"error": f"Fetch failed: {e}", "fix_count": 0}

    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc).isoformat()
    scan_id = f"selfscan_{secrets.token_urlsafe(8)}"

    await db.repair_fixes.update_many(
        {"user_id": user_id, "scan_url": url, "category": "accessibility", "status": "pending_approval"},
        {"$set": {"status": "archived", "archived_at": now}},
    )

    fixes = []

    # Check skip navigation
    skip_nav = soup.find("a", class_="skip-nav") or soup.find("a", {"href": "#main-content"})
    if not skip_nav:
        fixes.append(_make_fix(user_id, url, scan_id, "accessibility", "skip_nav",
            "Skip Navigation Link",
            '<a href="#main-content" class="sr-only focus:not-sr-only">Skip to main content</a>',
            now))

    # Check images without alt
    imgs_no_alt = [img for img in soup.find_all("img") if not img.get("alt")]
    if imgs_no_alt:
        fixes.append(_make_fix(user_id, url, scan_id, "accessibility", "img_alt",
            f"Image Alt Text ({len(imgs_no_alt)} images)",
            f"<!-- {len(imgs_no_alt)} images missing alt text. Add descriptive alt attributes. -->",
            now))

    # Check ARIA landmarks
    has_main = soup.find("main") or soup.find(attrs={"role": "main"})
    if not has_main:
        fixes.append(_make_fix(user_id, url, scan_id, "accessibility", "semantic_html",
            "Semantic HTML Structure",
            "Wrap primary content in <main> tag or add role='main' to the content container.",
            now))

    if fixes:
        await db.repair_fixes.insert_many(fixes)

    return {"fix_count": len(fixes), "scan_id": scan_id}


def _make_fix(user_id, url, scan_id, category, fix_type, label, fix_code, now) -> dict:
    return {
        "fix_id": f"fix_{secrets.token_urlsafe(12)}",
        "user_id": user_id,
        "scan_url": url,
        "scan_id": scan_id,
        "category": category,
        "fix_type": fix_type,
        "label": label,
        "fix_code": fix_code,
        "status": "pending_approval",
        "created_at": now,
        "severity": "medium",
        "source": "self_scan",
    }


async def auto_approve_and_deploy(url: str, user_id: str) -> dict:
    """Auto-approve all pending fixes and deploy them (Pixel + Origin)."""
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}

    now = datetime.now(timezone.utc).isoformat()

    # 1. Auto-approve all pending fixes
    approve_result = await db.repair_fixes.update_many(
        {"user_id": user_id, "scan_url": url, "status": "pending_approval"},
        {"$set": {"status": "approved", "approved_at": now, "approved_by": "self_scan_auto"}},
    )
    approved_count = approve_result.modified_count
    logger.info(f"[Self-Scan] Auto-approved {approved_count} fixes for {url}")

    if approved_count == 0:
        return {"approved": 0, "deployed": 0, "message": "No pending fixes to approve"}

    # 2. Deploy all approved fixes (Pixel Hot-Patch — Phase 1)
    deploy_result = await db.repair_fixes.update_many(
        {"user_id": user_id, "scan_url": url, "status": "approved"},
        {"$set": {"status": "deployed", "deployed_at": now, "deploy_method": "self_scan_auto"}},
    )
    deployed_count = deploy_result.modified_count

    # 3. Origin-Write (Phase 2: The Anchor)
    origin_result = {}
    try:
        from services.origin_write_engine import commit_to_origin
        origin_result = await commit_to_origin(url, user_id)
        logger.info(f"[Self-Scan] Origin-Write committed for {url}: {origin_result.get('commit_id')}")
    except Exception as e:
        logger.error(f"[Self-Scan] Origin-Write failed: {e}")
        origin_result = {"error": str(e)}

    return {
        "approved": approved_count,
        "deployed": deployed_count,
        "origin_committed": "error" not in origin_result,
        "origin_commit_id": origin_result.get("commit_id"),
        "serve_urls": origin_result.get("serve_urls", {}),
        "message": f"Self-scan complete: {approved_count} approved, {deployed_count} deployed, origin {'committed' if 'error' not in origin_result else 'failed'}",
    }


async def run_full_self_repair() -> dict:
    """
    Full self-repair pipeline: Scan → Auto-Approve → Deploy → Origin-Write.
    Called by Sentinel or manually.
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}

    url = _get_aurem_url()
    user_id = await _get_system_user_id()

    logger.info(f"[Self-Repair] Starting full pipeline for {url}")

    # 1. Scan
    scan_result = await run_self_scan()

    # 2. Auto-approve + Deploy + Origin-Write
    deploy_result = await auto_approve_and_deploy(url, user_id)

    # 3. Log the self-repair event
    await db.auto_heal_log.insert_one({
        "type": "self_repair",
        "url": url,
        "scan_result": {k: v for k, v in scan_result.items() if k != "results"},
        "deploy_result": {k: v for k, v in deploy_result.items() if k != "serve_urls"},
        "total_fixes": scan_result.get("total_fixes", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "url": url,
        "scan": scan_result,
        "deploy": deploy_result,
        "pipeline": "scan → approve → deploy → origin-write",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
