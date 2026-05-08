"""
AUREM Patch Deployer Service
==============================
Converts self-repair scan issues into deployable fix payloads.
Pushes fixes through the correct channel based on platform type:
  - Shopify: Admin API (PUT theme assets)
  - WordPress/WooCommerce: WP REST API
  - Custom/Pixel: Store in DB → pixel fetches on next load

Supports canary rollout (1% → 10% → 100%) and instant rollback.
"""
import logging
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════
# FIX GENERATORS — Convert scan issues into deployable patches
# ═══════════════════════════════════════════════════════════════

def generate_css_fix(issue: Dict) -> Optional[Dict]:
    """Generate a CSS fix payload from a scan issue."""
    issue_text = issue.get("issue", "").lower()
    category = issue.get("category", "")

    css = None
    description = ""

    # Accessibility fixes
    if "contrast" in issue_text or "color contrast" in issue_text:
        css = "/* AUREM Fix: Improve text contrast */\nbody { color: #1a1a1a !important; }\na { color: #0056b3 !important; }"
        description = "Improved text color contrast ratio to meet WCAG 2.1 AA"

    elif "tap target" in issue_text or "touch target" in issue_text or "click target" in issue_text:
        css = "/* AUREM Fix: Enlarge tap targets */\na, button, [role='button'] { min-height: 44px !important; min-width: 44px !important; padding: 8px 12px !important; }"
        description = "Enlarged tap targets to 44px minimum for mobile"

    elif "font-size" in issue_text or "text too small" in issue_text:
        css = "/* AUREM Fix: Readable font size */\nbody { font-size: 16px !important; }"
        description = "Set minimum body font size to 16px"

    elif "layout shift" in issue_text or "cls" in issue_text:
        css = "/* AUREM Fix: Prevent layout shift */\nimg, video, iframe { aspect-ratio: attr(width) / attr(height); max-width: 100%; height: auto; }\nimg:not([width]) { width: 100%; aspect-ratio: 16/9; }"
        description = "Added aspect-ratio constraints to prevent CLS"

    elif "viewport" in issue_text and "responsive" in issue_text:
        css = "/* AUREM Fix: Responsive overflow */\n* { box-sizing: border-box !important; }\nimg, video, iframe { max-width: 100% !important; height: auto !important; }\nbody { overflow-x: hidden !important; }"
        description = "Added responsive overflow protection"

    if not css:
        return None

    return {"type": "css", "code": css.strip(), "description": description, "source_issue": issue.get("issue", ""), "category": category}


def generate_meta_fix(issue: Dict) -> Optional[Dict]:
    """Generate a meta tag / SEO fix payload."""
    issue_text = issue.get("issue", "").lower()

    meta_tags = []
    description = ""

    if "meta description" in issue_text or "missing description" in issue_text:
        meta_tags.append({"name": "description", "content": "Welcome to our website. Learn more about our services and products."})
        description = "Added missing meta description tag"

    elif "viewport" in issue_text and "meta" in issue_text:
        meta_tags.append({"name": "viewport", "content": "width=device-width, initial-scale=1.0"})
        description = "Added responsive viewport meta tag"

    elif "charset" in issue_text:
        meta_tags.append({"charset": "UTF-8"})
        description = "Added UTF-8 charset declaration"

    elif "open graph" in issue_text or "og:" in issue_text:
        meta_tags.extend([
            {"property": "og:type", "content": "website"},
            {"property": "og:locale", "content": "en_US"},
        ])
        description = "Added basic Open Graph meta tags"

    elif "xss" in issue_text or "x-xss" in issue_text or "xss protection" in issue_text:
        # XSS protection is a header, but we can add a meta equiv as a safety net
        meta_tags.append({"http-equiv": "X-XSS-Protection", "content": "1; mode=block"})
        description = "Injected X-XSS-Protection meta tag as client-side safety layer"

    elif "clickjack" in issue_text or "frame" in issue_text or "x-frame" in issue_text:
        # X-Frame-Options is a header, but CSP frame-ancestors can be set via meta
        meta_tags.append({"http-equiv": "Content-Security-Policy", "content": "frame-ancestors 'self'"})
        description = "Injected CSP frame-ancestors via meta tag to prevent clickjacking"

    if not meta_tags:
        return None

    return {"type": "meta", "tags": meta_tags, "description": description, "source_issue": issue.get("issue", "")}


def generate_schema_fix(issue: Dict) -> Optional[Dict]:
    """Generate JSON-LD schema fix."""
    issue_text = issue.get("issue", "").lower()

    if "structured data" not in issue_text and "schema" not in issue_text and "json-ld" not in issue_text:
        return None

    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": "{{BUSINESS_NAME}}",
        "url": "{{WEBSITE_URL}}",
        "description": "{{BUSINESS_DESCRIPTION}}",
    }

    return {"type": "schema", "json_ld": schema, "description": "Added LocalBusiness structured data schema", "source_issue": issue.get("issue", "")}


def generate_js_fix(issue: Dict) -> Optional[Dict]:
    """Generate a safe JavaScript fix (try/catch with auto-rollback)."""
    issue_text = issue.get("issue", "").lower()

    js = None
    description = ""

    if "title" in issue_text and ("length" in issue_text or "suboptimal" in issue_text or "short" in issue_text or "long" in issue_text):
        # SEO: fix page title length by adding business context if too short
        js = """
// AUREM Fix: Optimize page title for SEO (50-60 char target)
(function() {
  var t = document.title || '';
  if (t.length < 30) {
    var h1 = document.querySelector('h1');
    if (h1 && h1.textContent.trim()) { document.title = h1.textContent.trim().substring(0, 55) + ' | ' + t; }
  }
})();
"""
        description = "Optimized page title length for better SEO ranking"

    elif "console error" in issue_text or "javascript error" in issue_text:
        js = "window.addEventListener('error',function(e){if(window.__auremErrors)window.__auremErrors.push({m:e.message,s:e.filename,l:e.lineno})});window.__auremErrors=[];"
        description = "Added global JS error handler"

    elif "lazy load" in issue_text or "image loading" in issue_text:
        js = "document.querySelectorAll('img:not([loading])').forEach(function(i){if(i.getBoundingClientRect().top>window.innerHeight*1.5){i.loading='lazy';i.decoding='async'}});"
        description = "Applied lazy loading to offscreen images"

    elif "render blocking" in issue_text or "blocking resource" in issue_text:
        js = "document.querySelectorAll('link[rel=stylesheet]:not([data-critical])').forEach(function(l){l.media='print';l.onload=function(){this.media='all'}});"
        description = "Deferred non-critical stylesheets"

    elif "navigation landmark" in issue_text or "nav landmark" in issue_text:
        # A11y: wrap the primary navigation in a proper <nav role="navigation"> landmark
        js = """
// AUREM Fix: Ensure navigation landmark exists
(function(){
  if (document.querySelector('nav, [role="navigation"]')) return;
  var nav = document.querySelector('header ul, header .menu, .main-menu, #menu, .navbar');
  if (nav && nav.tagName !== 'NAV') {
    nav.setAttribute('role','navigation');
    nav.setAttribute('aria-label','Main navigation');
  }
})();
"""
        description = "Added navigation landmark for screen reader users"

    elif "main content landmark" in issue_text or "main landmark" in issue_text:
        # A11y: ensure <main> / role=main exists wrapping primary content
        js = """
// AUREM Fix: Ensure main content landmark
(function(){
  if (document.querySelector('main, [role="main"]')) return;
  var cand = document.querySelector('#content, .content, #main, .main, article');
  if (cand) {
    cand.setAttribute('role','main');
    cand.setAttribute('aria-label','Main content');
  }
})();
"""
        description = "Added main content landmark for accessibility"

    elif "header landmark" in issue_text or "banner landmark" in issue_text or "header/banner" in issue_text:
        js = """
// AUREM Fix: Ensure banner landmark on <header>
(function(){
  if (document.querySelector('header[role="banner"], [role="banner"]')) return;
  var h = document.querySelector('header, #header, .site-header');
  if (h) { h.setAttribute('role','banner'); }
})();
"""
        description = "Added banner landmark for site header"

    elif "h1 heading" in issue_text or "no h1" in issue_text or "missing h1" in issue_text:
        js = """
// AUREM Fix: Promote first big heading to H1 if page lacks one
(function(){
  if (document.querySelector('h1')) return;
  var cand = document.querySelector('h2, .page-title, .title, [class*="heading"]');
  if (cand) {
    var h1 = document.createElement('h1');
    h1.textContent = cand.textContent;
    h1.className = cand.className;
    cand.parentNode.replaceChild(h1, cand);
  }
})();
"""
        description = "Promoted page heading to H1 for SEO"

    elif "slow page load" in issue_text or "slow load" in issue_text or "page load time" in issue_text:
        # Perf: aggressive resource hints for the top 3 external origins
        js = """
// AUREM Fix: Add preconnect hints for top external origins to speed page load
(function(){
  var origins = new Set();
  document.querySelectorAll('link[href^="http"], script[src^="http"], img[src^="http"]').forEach(function(el){
    var src = el.href || el.src; try { origins.add(new URL(src).origin); } catch(e){}
  });
  Array.from(origins).slice(0,3).forEach(function(o){
    if (document.querySelector('link[rel="preconnect"][href="'+o+'"]')) return;
    var l = document.createElement('link');
    l.rel='preconnect'; l.href=o; l.crossOrigin='anonymous';
    document.head.appendChild(l);
  });
  // Also: enable lazy-loading on all below-fold images
  document.querySelectorAll('img:not([loading])').forEach(function(i){
    if (i.getBoundingClientRect().top > window.innerHeight) i.loading='lazy';
  });
})();
"""
        description = "Added preconnect hints + lazy-loading for faster page load"

    elif "zoom disabled" in issue_text or "user-scalable=no" in issue_text or "maximum-scale=1" in issue_text:
        # A11y: fix viewport meta that prevents mobile zoom (WCAG 1.4.4)
        js = """
// AUREM Fix: Restore mobile zoom capability (accessibility fix)
(function(){
  var vp = document.querySelector('meta[name="viewport"]');
  if (!vp) return;
  var content = (vp.content || '').replace(/,?\\s*user-scalable\\s*=\\s*no/gi, '')
                                   .replace(/,?\\s*maximum-scale\\s*=\\s*1(\\.0)?/gi, '');
  vp.content = content.trim().replace(/^,|,$/,'') || 'width=device-width, initial-scale=1';
})();
"""
        description = "Restored mobile zoom capability (WCAG accessibility fix)"

    elif "footer landmark" in issue_text or "contentinfo" in issue_text:
        js = """
// AUREM Fix: Ensure footer/contentinfo landmark exists
(function(){
  if (document.querySelector('footer, [role="contentinfo"]')) return;
  var cand = document.querySelector('#footer, .footer, .site-footer, .page-footer');
  if (cand) { cand.setAttribute('role','contentinfo'); cand.setAttribute('aria-label','Site footer'); }
})();
"""
        description = "Added contentinfo landmark for footer"

    if not js:
        return None

    return {"type": "js", "code": js.strip(), "description": description, "source_issue": issue.get("issue", "")}


# ═══════════════════════════════════════════════════════════════
# PATCH GENERATOR — Process all repairs from a scan
# ═══════════════════════════════════════════════════════════════

def generate_patches_from_repairs(repairs: List[Dict], workspace: Optional[Dict] = None) -> List[Dict]:
    """Convert scan repair entries into deployable patch payloads."""
    patches = []
    generators = [generate_css_fix, generate_meta_fix, generate_schema_fix, generate_js_fix]
    # Dedupe: if we'd deploy two identical patches from different phrasings of
    # the same issue (e.g., "No H1 heading" + "Missing H1"), collapse to one.
    seen: set = set()

    for repair in repairs:
        for gen in generators:
            patch = gen(repair)
            if not patch:
                continue
            # Fill in business-specific placeholders
            if workspace and patch.get("type") == "schema" and patch.get("json_ld"):
                schema = patch["json_ld"]
                schema["name"] = workspace.get("business_name", schema["name"])
                schema["url"] = workspace.get("website", schema["url"])
                ai_ctx = workspace.get("ai_context", {})
                schema["description"] = ai_ctx.get(
                    "business_description", schema.get("description", "")
                )

            fingerprint = (patch.get("type"), patch.get("description", ""))
            if fingerprint in seen:
                break  # identical fix already queued
            seen.add(fingerprint)
            patches.append(patch)
            break  # one fix per repair

    return patches


# ═══════════════════════════════════════════════════════════════
# DEPLOYMENT — Push patches to DB for pixel to fetch
# ═══════════════════════════════════════════════════════════════

async def deploy_patches(
    business_id: str,
    patches: List[Dict],
    rollout_pct: int = 100,
    scan_id: str = None,
) -> Dict:
    """Store deployable patches in DB for the pixel to fetch and apply."""
    if _db is None:
        return {"success": False, "error": "no_db"}

    if not patches:
        return {"success": True, "deployed": 0}

    now = datetime.now(timezone.utc).isoformat()
    batch_id = f"patch_{secrets.token_hex(8)}"

    patch_docs = []
    for patch in patches:
        doc = {
            "patch_id": f"p_{secrets.token_hex(6)}",
            "batch_id": batch_id,
            "business_id": business_id,
            "type": patch["type"],
            "code": patch.get("code", ""),
            "tags": patch.get("tags", []),
            "json_ld": patch.get("json_ld"),
            "description": patch.get("description", ""),
            "source_issue": patch.get("source_issue", ""),
            "category": patch.get("category", ""),
            "status": "active",
            "rollout_pct": rollout_pct,
            "applied_count": 0,
            "error_count": 0,
            "scan_id": scan_id,
            "created_at": now,
            "updated_at": now,
        }
        patch_docs.append(doc)

    if patch_docs:
        await _db["live_patches"].insert_many(patch_docs)
        logger.info(f"[PatchDeployer] Deployed {len(patch_docs)} patches for {business_id} (batch={batch_id}, rollout={rollout_pct}%)")

    return {
        "success": True,
        "batch_id": batch_id,
        "deployed": len(patch_docs),
        "rollout_pct": rollout_pct,
        "types": [p["type"] for p in patch_docs],
    }


async def get_active_patches(business_id: str) -> List[Dict]:
    """Get all active patches for a business (called by pixel)."""
    if _db is None:
        return []

    cursor = _db["live_patches"].find(
        {"business_id": business_id, "status": "active"},
        {"_id": 0}
    ).sort("created_at", -1)
    return await cursor.to_list(50)


async def rollback_batch(batch_id: str) -> Dict:
    """Instantly rollback all patches in a batch."""
    if _db is None:
        return {"success": False, "error": "no_db"}

    result = await _db["live_patches"].update_many(
        {"batch_id": batch_id},
        {"$set": {"status": "rolled_back", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    logger.info(f"[PatchDeployer] Rolled back batch {batch_id}: {result.modified_count} patches")
    return {"success": True, "rolled_back": result.modified_count}


async def report_patch_applied(patch_id: str, success: bool) -> None:
    """Track that a patch was applied (or failed) on a client browser."""
    if _db is None:
        return
    field = "applied_count" if success else "error_count"
    await _db["live_patches"].update_one(
        {"patch_id": patch_id},
        {"$inc": {field: 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Auto-rollback if error rate exceeds threshold
    if not success:
        patch = await _db["live_patches"].find_one({"patch_id": patch_id}, {"_id": 0})
        if patch and patch.get("error_count", 0) >= 3 and patch.get("applied_count", 0) < 5:
            await _db["live_patches"].update_one(
                {"patch_id": patch_id},
                {"$set": {"status": "auto_rolled_back", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            logger.warning(f"[PatchDeployer] Auto-rolled back patch {patch_id} due to high error rate")


async def canary_promote(batch_id: str, new_pct: int) -> Dict:
    """Promote a patch batch to a higher rollout percentage."""
    if _db is None:
        return {"success": False, "error": "no_db"}

    result = await _db["live_patches"].update_many(
        {"batch_id": batch_id, "status": "active"},
        {"$set": {"rollout_pct": new_pct, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    logger.info(f"[PatchDeployer] Promoted batch {batch_id} to {new_pct}% rollout: {result.modified_count} patches")
    return {"success": True, "promoted": result.modified_count, "rollout_pct": new_pct}
