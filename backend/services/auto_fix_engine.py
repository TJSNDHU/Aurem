"""
AUREM — Auto-Fix Engine.
Generates AI-powered fix suggestions for scannable issues.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger("aurem.auto_fix")


async def run_auto_fixes(db, tenant_id: str, issues: list) -> list:
    """Attempt to auto-fix all fixable issues. Returns list of fix results."""
    results = []
    for issue in issues:
        if not issue.get("fixable"):
            continue
        fix_type = issue.get("auto_fix", "")
        try:
            fix_result = await _apply_fix(db, tenant_id, issue, fix_type)
            results.append(fix_result)
        except Exception as e:
            logger.error(f"[AUTO-FIX] Failed for {fix_type}: {e}")
            results.append({"fixed": False, "fix_type": fix_type, "error": str(e)})
    return results


async def _apply_fix(db, tenant_id: str, issue: dict, fix_type: str) -> dict:
    """Apply a specific auto-fix and return the result with instructions."""
    business = await db.users.find_one({"tenant_id": tenant_id}, {"_id": 0, "business_name": 1, "industry": 1, "website_url": 1})
    bname = (business or {}).get("business_name", "your business")
    industry = (business or {}).get("industry", "services")

    if fix_type == "add_meta_description":
        desc = f"{bname} — Expert {industry} solutions. Get started today with a free consultation."
        return {
            "fixed": True,
            "fix_type": fix_type,
            "title": issue.get("title", ""),
            "fix_value": desc,
            "instruction": f'Add to your homepage <head>:\n<meta name="description" content="{desc}">',
        }

    elif fix_type == "add_page_title":
        title = f"{bname} | Professional {industry.title()}"
        return {
            "fixed": True,
            "fix_type": fix_type,
            "title": issue.get("title", ""),
            "fix_value": title,
            "instruction": f"Update your homepage <title>:\n<title>{title}</title>",
        }

    elif fix_type == "add_alt_tags":
        return {
            "fixed": True,
            "fix_type": fix_type,
            "title": issue.get("title", ""),
            "fix_value": "Generated alt text suggestions",
            "instruction": f"Add descriptive alt attributes to all <img> tags. Example:\n<img src='hero.jpg' alt='{bname} — {industry} services'>",
        }

    elif fix_type == "generate_robots_txt":
        robots = f"User-agent: *\nAllow: /\nSitemap: https://{(business or {}).get('website_url', 'example.com').replace('https://', '').replace('http://', '')}/sitemap.xml"
        return {
            "fixed": True,
            "fix_type": fix_type,
            "title": issue.get("title", ""),
            "fix_value": robots,
            "instruction": f"Create a robots.txt file at your website root:\n{robots}",
        }

    elif fix_type == "add_viewport":
        return {
            "fixed": True,
            "fix_type": fix_type,
            "title": issue.get("title", ""),
            "fix_value": '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "instruction": 'Add to <head>:\n<meta name="viewport" content="width=device-width, initial-scale=1">',
        }

    return {"fixed": False, "fix_type": fix_type, "reason": "Unknown fix type"}
