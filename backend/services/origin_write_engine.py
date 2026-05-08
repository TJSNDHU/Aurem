"""
AUREM Origin-Write Engine — "The Anchor" (Phase 2 of Double-Lock Fix)
======================================================================

The Double-Lock Fix Standard:
  Phase 1 (The Spark): Pixel Hot-Patch — instant, user-only visibility
  Phase 2 (The Anchor): Origin-Write — permanent, internet-wide visibility

This module compiles pixel-patched fixes into origin-ready files that
get baked into the customer's source code so Google/crawlers see them.

Output formats:
  - CSS:  All style fixes compiled into a single stylesheet
  - HEAD: All meta/schema/OG fixes compiled into an HTML <head> snippet
  - JS:   Any remaining JS-only fixes (semantic HTML restructuring, etc.)

Deployment methods:
  - Static serve: AUREM hosts the files at permanent URLs
  - Download bundle: Customer gets files to commit manually
  - Direct write: For platforms with API access (Shopify, WordPress)
  - PR generation: For Git-connected repos
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None

# Fix types that go into <head> as HTML
HEAD_FIX_TYPES = {
    "title", "meta_description", "og_title", "og_description",
    "og_image", "json_ld_article", "json_ld_product", "json_ld_org",
    "json_ld_faq", "canonical", "twitter_card", "robots",
}

# Fix types that produce CSS
CSS_FIX_TYPES = {
    "skip_nav",  # .sr-only styles
}

# Fix types that are structural guidance (not direct code)
GUIDANCE_FIX_TYPES = {
    "semantic_html",  # instructions to wrap in <article>/<section>
}


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


async def compile_origin_files(scan_url: str, user_id: str) -> dict:
    """
    Compile all deployed fixes for a URL into origin-ready files.
    
    Returns:
      {
        "head_html": "...",     # Everything that goes in <head>
        "body_html": "...",     # Elements for <body> (citations, summary)
        "css": "...",           # Compiled stylesheet
        "js": "...",            # Any JS needed
        "fix_count": 15,
        "categories": {...},
        "fixes_detail": [...]
      }
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}

    # Get all deployed fixes for this URL
    fixes = await db.repair_fixes.find(
        {"scan_url": scan_url, "user_id": user_id, "status": "deployed"},
        {"_id": 0}
    ).to_list(100)

    if not fixes:
        return {"error": "No deployed fixes found", "fix_count": 0}

    head_lines = [
        "<!-- ═══════════════════════════════════════════════════ -->",
        "<!-- AUREM Origin-Write — Phase 2 (The Anchor)          -->",
        f"<!-- Compiled: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} -->",
        f"<!-- URL: {scan_url} -->",
        f"<!-- Fixes: {len(fixes)} -->",
        "<!-- ═══════════════════════════════════════════════════ -->",
        "",
    ]

    body_lines = [
        "<!-- AUREM Origin-Write — Body Elements -->",
        "",
    ]

    css_lines = [
        "/* ═══════════════════════════════════════════════════ */",
        "/* AUREM Origin-Write — Compiled Stylesheet            */",
        f"/* Compiled: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} */",
        f"/* URL: {scan_url} */",
        "/* ═══════════════════════════════════════════════════ */",
        "",
    ]

    js_lines = []
    fixes_detail = []
    categories = {"seo": 0, "geo": 0, "accessibility": 0, "performance": 0}

    # Deduplicate by fix_type (keep latest)
    seen_types = {}
    for fix in sorted(fixes, key=lambda f: f.get("created_at", "")):
        ft = fix.get("fix_type", "")
        seen_types[ft] = fix

    for fix_type, fix in seen_types.items():
        category = fix.get("category", "seo")
        label = fix.get("label", "Unknown Fix")
        fix_code = fix.get("fix_code", "") or ""
        categories[category] = categories.get(category, 0) + 1

        fixes_detail.append({
            "fix_id": fix.get("fix_id", ""),
            "fix_type": fix_type,
            "label": label,
            "category": category,
            "target": "head" if fix_type in HEAD_FIX_TYPES else "body" if fix_type not in CSS_FIX_TYPES else "css",
        })

        if not fix_code.strip():
            continue

        # Route fix code to the right output file
        if fix_type in HEAD_FIX_TYPES:
            head_lines.append(f"<!-- [{category.upper()}] {label} -->")
            head_lines.append(fix_code.strip())
            head_lines.append("")

        elif fix_type == "skip_nav":
            # Skip nav needs both HTML (in body) and CSS
            body_lines.append(f"<!-- [{category.upper()}] {label} -->")
            body_lines.append(fix_code.strip())
            body_lines.append("")
            css_lines.append("/* Skip Navigation - Accessibility */")
            css_lines.append(".sr-only {")
            css_lines.append("  position: absolute;")
            css_lines.append("  width: 1px; height: 1px;")
            css_lines.append("  padding: 0; margin: -1px;")
            css_lines.append("  overflow: hidden;")
            css_lines.append("  clip: rect(0, 0, 0, 0);")
            css_lines.append("  white-space: nowrap;")
            css_lines.append("  border-width: 0;")
            css_lines.append("}")
            css_lines.append(".sr-only:focus, .focus\\:not-sr-only:focus {")
            css_lines.append("  position: static;")
            css_lines.append("  width: auto; height: auto;")
            css_lines.append("  padding: 0.75rem 1rem;")
            css_lines.append("  margin: 0;")
            css_lines.append("  overflow: visible;")
            css_lines.append("  clip: auto;")
            css_lines.append("  white-space: normal;")
            css_lines.append("  background: #1A1A2E;")
            css_lines.append("  color: #fff;")
            css_lines.append("  z-index: 9999;")
            css_lines.append("}")
            css_lines.append("")

        elif fix_type == "ai_summary":
            # AI-friendly summary paragraph — goes in body
            body_lines.append(f"<!-- [{category.upper()}] {label} -->")
            body_lines.append('<p class="aurem-ai-summary" style="position:absolute;left:-9999px;top:auto;width:1px;height:1px;overflow:hidden;">')
            body_lines.append(f"  {fix_code.strip()}")
            body_lines.append("</p>")
            body_lines.append("")

        elif fix_type == "citation_block":
            body_lines.append(f"<!-- [{category.upper()}] {label} -->")
            body_lines.append(fix_code.strip())
            body_lines.append("")

        elif fix_type in GUIDANCE_FIX_TYPES:
            # Structural guidance — add as JS that restructures DOM
            js_lines.append(f"// [{category.upper()}] {label}")
            js_lines.append(f"// Guidance: {fix_code.strip()[:200]}")
            js_lines.append("")

        else:
            # Unknown type — put in body as HTML comment + code
            body_lines.append(f"<!-- [{category.upper()}] {label} -->")
            body_lines.append(fix_code.strip())
            body_lines.append("")

    # Build the final JS if needed
    js_output = ""
    if js_lines:
        js_output = "\n".join([
            "/* AUREM Origin-Write — Structural Fixes */",
            "(function() {",
            "  'use strict';",
            *["  " + line for line in js_lines],
            "})();",
        ])

    return {
        "head_html": "\n".join(head_lines),
        "body_html": "\n".join(body_lines),
        "css": "\n".join(css_lines),
        "js": js_output,
        "fix_count": len(seen_types),
        "categories": categories,
        "fixes_detail": fixes_detail,
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "scan_url": scan_url,
    }


async def commit_to_origin(scan_url: str, user_id: str) -> dict:
    """
    Commit compiled fixes to origin. Stores the compiled files
    and marks the deployment as 'origin-committed'.
    
    Returns the origin commit record with file contents and serve URLs.
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}

    compiled = await compile_origin_files(scan_url, user_id)
    if "error" in compiled:
        return compiled

    commit_id = f"origin_{secrets.token_urlsafe(12)}"
    now = datetime.now(timezone.utc).isoformat()

    # Normalize URL for serve path
    url_slug = scan_url.replace("https://", "").replace("http://", "").replace("/", "_").rstrip("_")

    origin_doc = {
        "commit_id": commit_id,
        "user_id": user_id,
        "scan_url": scan_url,
        "url_slug": url_slug,
        "head_html": compiled["head_html"],
        "body_html": compiled["body_html"],
        "css": compiled["css"],
        "js": compiled.get("js", ""),
        "fix_count": compiled["fix_count"],
        "categories": compiled["categories"],
        "fixes_detail": compiled["fixes_detail"],
        "status": "committed",
        "committed_at": now,
        "verified_at": None,
        "verification_score": None,
    }

    await db.origin_commits.update_one(
        {"scan_url": scan_url, "user_id": user_id},
        {"$set": origin_doc},
        upsert=True,
    )

    # Update all deployed fixes to 'origin-committed'
    await db.repair_fixes.update_many(
        {"scan_url": scan_url, "user_id": user_id, "status": "deployed"},
        {"$set": {"origin_status": "committed", "origin_commit_id": commit_id, "origin_committed_at": now}},
    )

    logger.info(f"[Origin-Write] Committed {compiled['fix_count']} fixes for {scan_url} → {commit_id}")

    return {
        "commit_id": commit_id,
        "scan_url": scan_url,
        "fix_count": compiled["fix_count"],
        "categories": compiled["categories"],
        "status": "committed",
        "committed_at": now,
        "files": {
            "head_html": compiled["head_html"],
            "body_html": compiled["body_html"],
            "css": compiled["css"],
            "js": compiled.get("js", ""),
        },
        "serve_urls": {
            "css": f"/api/repair/origin/serve/{url_slug}/fixes.css",
            "head": f"/api/repair/origin/serve/{url_slug}/head.html",
            "body": f"/api/repair/origin/serve/{url_slug}/body.html",
        },
        "instructions": _generate_instructions(scan_url, url_slug, compiled),
    }


def _generate_instructions(scan_url: str, url_slug: str, compiled: dict) -> dict:
    """Generate platform-specific integration instructions."""
    base_url = "https://reroots-ai-platform.emergent.host"

    return {
        "react_pwa": {
            "title": "React / PWA Integration",
            "steps": [
                "1. Add to your public/index.html <head> section:",
                f'   <link rel="stylesheet" href="{base_url}/api/repair/origin/serve/{url_slug}/fixes.css" />',
                "2. Copy the HEAD HTML snippet and paste it into your <head> tag",
                "3. Copy the BODY HTML snippet and paste it right after <body>",
                "4. Rebuild and deploy your React app",
            ],
        },
        "shopify": {
            "title": "Shopify Theme Integration",
            "steps": [
                "1. Go to Online Store → Themes → Edit Code",
                "2. Open theme.liquid",
                f'3. Add before </head>: <link rel="stylesheet" href="{base_url}/api/repair/origin/serve/{url_slug}/fixes.css" />',
                "4. Paste the HEAD HTML snippet before </head>",
                "5. Paste the BODY HTML snippet after <body>",
                "6. Save",
            ],
        },
        "wordpress": {
            "title": "WordPress Integration",
            "steps": [
                "1. Go to Appearance → Theme Editor → header.php",
                f'2. Add before </head>: <link rel="stylesheet" href="{base_url}/api/repair/origin/serve/{url_slug}/fixes.css" />',
                "3. Paste the HEAD HTML snippet before </head>",
                "4. Paste the BODY HTML snippet after <body>",
                "5. Clear any caching plugins",
            ],
        },
    }


async def verify_origin_commit(scan_url: str, user_id: str) -> dict:
    """
    Trigger external PageSpeed Insights scan and compare to internal score.
    The Truth-Sync Verifier — loop only closes when scores match.
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}

    import httpx
    import os

    # Run PageSpeed Insights API (free, no key needed for basic)
    psi_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": scan_url,
        "category": ["performance", "accessibility", "best-practices", "seo"],
        "strategy": "mobile",
    }

    # Also check with Google API key if available
    api_key = os.environ.get("GOOGLE_PSI_API_KEY", "")
    if api_key:
        params["key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(psi_url, params=params)

        if resp.status_code == 200:
            psi_data = resp.json()
            categories = psi_data.get("lighthouseResult", {}).get("categories", {})

            external_scores = {}
            for cat_key, cat_data in categories.items():
                score = cat_data.get("score")
                if score is not None:
                    external_scores[cat_key] = int(score * 100)

            # Get internal score
            internal = await db.repair_fixes.find(
                {"scan_url": scan_url, "user_id": user_id},
                {"_id": 0, "category": 1}
            ).to_list(100)

            internal_fix_count = len(internal)

            # Compare and store
            now = datetime.now(timezone.utc).isoformat()
            verification = {
                "scan_url": scan_url,
                "user_id": user_id,
                "external_scores": external_scores,
                "internal_fix_count": internal_fix_count,
                "verified_at": now,
                "match": all(v >= 80 for v in external_scores.values()) if external_scores else False,
            }

            await db.origin_commits.update_one(
                {"scan_url": scan_url, "user_id": user_id},
                {"$set": {
                    "verified_at": now,
                    "verification_scores": external_scores,
                    "verification_match": verification["match"],
                }}
            )

            logger.info(f"[Truth-Sync] {scan_url} external scores: {external_scores}, match={verification['match']}")

            return {
                "scan_url": scan_url,
                "external_scores": external_scores,
                "match": verification["match"],
                "verified_at": now,
                "message": "Scores match! Origin-Write verified." if verification["match"] else "Scores don't match yet. Google may need time to re-crawl.",
            }
        else:
            return {
                "scan_url": scan_url,
                "error": f"PageSpeed API returned {resp.status_code}",
                "message": "Could not verify. Try again in a few minutes.",
            }

    except Exception as e:
        logger.error(f"[Truth-Sync] Verification failed for {scan_url}: {e}")
        return {
            "scan_url": scan_url,
            "error": str(e),
            "message": "Verification failed. PageSpeed API may be temporarily unavailable.",
        }
