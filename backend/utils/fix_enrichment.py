"""
Fix-aware scan enrichment utility.
Cross-references scan issues against deployed fixes in customer_website_fixes
and repair_fixes to set is_fixed flag before persisting scan results.
"""
import re
from typing import Dict, List, Set, Optional


def generate_issue_key(issue: dict) -> str:
    """
    Generate a stable, deterministic key for a scan issue.
    Uses category + normalized issue text.
    Examples:
        "security:missing_clickjacking_protection"
        "seo:missing_meta_description"
        "performance:no_caching_configured"
    """
    category = (issue.get("category") or "general").lower().strip()
    issue_text = (issue.get("issue") or "").lower().strip()
    key = re.sub(r'[^a-z0-9\s]', '', issue_text)
    key = re.sub(r'\s+', '_', key).strip('_')
    return f"{category}:{key}" if key else f"{category}:unknown"


def generate_fix_key(fix: dict) -> str:
    """
    Generate a matching key from a fix record.
    Works with both customer_website_fixes (test field) and repair_fixes (label/fix_type fields).
    """
    category = (fix.get("category") or "general").lower().strip()
    text = fix.get("test") or fix.get("label") or fix.get("fix_type") or ""
    text = text.lower().strip()
    key = re.sub(r'[^a-z0-9\s]', '', text)
    key = re.sub(r'\s+', '_', key).strip('_')
    return f"{category}:{key}" if key else ""


def _build_fix_key_set(fixes: list) -> Set[str]:
    """Build a set of normalized fix keys from a list of fix records."""
    keys = set()
    for fix in fixes:
        k = generate_fix_key(fix)
        if k:
            keys.add(k)
    return keys


def _fuzzy_match(issue_key: str, fix_keys: Set[str]) -> bool:
    """
    Check if an issue_key matches any fix key.
    Tries exact match first, then substring containment both ways.
    """
    if issue_key in fix_keys:
        return True

    issue_parts = issue_key.split(":", 1)
    if len(issue_parts) < 2:
        return False
    issue_cat, issue_name = issue_parts

    for fk in fix_keys:
        fix_parts = fk.split(":", 1)
        if len(fix_parts) < 2:
            continue
        fix_cat, fix_name = fix_parts

        if issue_cat != fix_cat:
            continue

        if issue_name in fix_name or fix_name in issue_name:
            return True

        issue_tokens = set(issue_name.split('_'))
        fix_tokens = set(fix_name.split('_'))
        if issue_tokens and fix_tokens:
            overlap = issue_tokens & fix_tokens
            min_len = min(len(issue_tokens), len(fix_tokens))
            if min_len > 0 and len(overlap) / min_len >= 0.5:
                return True

    return False


async def _fetch_deployed_fixes(db, website_url: str, user_id: Optional[str] = None) -> list:
    """
    Fetch deployed fixes from both collections.
    If user_id is provided, scopes customer_website_fixes to that user (tenant mode).
    If user_id is None, fetches all fixes for the URL (admin mode).
    repair_fixes are always global per URL (admin-deployed).
    """
    base = website_url.rstrip("/")
    url_variants = list({base, base + "/", base.lower(), base.lower() + "/"})

    # customer_website_fixes — scoped by user_id for tenants
    cwf_query = {"website_url": {"$in": url_variants}, "status": "deployed"}
    if user_id:
        cwf_query["user_id"] = user_id

    cwf_fixes = await db.customer_website_fixes.find(
        cwf_query,
        {"_id": 0, "test": 1, "category": 1}
    ).to_list(length=500)

    # repair_fixes — always global per URL (admin/system fixes)
    rf_fixes = await db.repair_fixes.find(
        {"$or": [
            {"scan_url": {"$in": url_variants}},
            {"website_url": {"$in": url_variants}},
        ], "status": "deployed"},
        {"_id": 0, "fix_type": 1, "label": 1, "category": 1}
    ).to_list(length=500)

    return cwf_fixes + rf_fixes


async def enrich_issues_with_fix_status(
    db, all_issues: list, website_url: str, user_id: Optional[str] = None
):
    """
    Cross-reference scan issues against deployed fixes.
    Mutates each issue in-place: adds issue_key, is_fixed, fixed_note.

    Args:
        db: MongoDB database reference
        all_issues: list of issue dicts from scanner
        website_url: the scanned URL
        user_id: if provided, scopes customer_website_fixes to this user (tenant mode).
                 If None, fetches all fixes for the URL (admin mode).
    """
    if not all_issues or not website_url:
        return

    all_fixes = await _fetch_deployed_fixes(db, website_url, user_id)
    fix_keys = _build_fix_key_set(all_fixes)

    if not fix_keys:
        for issue in all_issues:
            issue["issue_key"] = generate_issue_key(issue)
            issue["is_fixed"] = False
        return

    # Build set of detected issue keys for confirmed-resolved detection
    detected_issue_keys = set()

    for issue in all_issues:
        issue_key = generate_issue_key(issue)
        issue["issue_key"] = issue_key
        detected_issue_keys.add(issue_key)

        if _fuzzy_match(issue_key, fix_keys):
            # Fix deployed but issue still detected on live site
            issue["is_fixed"] = True
            issue["fixed_note"] = "Fix deployed \u2014 pending live site propagation"
        else:
            issue["is_fixed"] = False

    return detected_issue_keys, fix_keys


def build_confirmed_resolved(detected_keys: set, fix_keys: set) -> list:
    """
    Detect fixes that worked: fix exists but issue is no longer detected on live site.
    Returns a list of confirmed-resolved entries to include in scan results.
    """
    resolved = []
    for fk in fix_keys:
        # Check if any detected issue matches this fix key
        matched = _fuzzy_match_reverse(fk, detected_keys)
        if not matched:
            # Fix exists but issue is gone from live site = confirmed resolved
            parts = fk.split(":", 1)
            category = parts[0] if len(parts) > 1 else "general"
            name = parts[1].replace("_", " ").title() if len(parts) > 1 else fk
            resolved.append({
                "issue_key": fk,
                "category": category,
                "issue": name,
                "is_fixed": True,
                "fix_status": "confirmed_resolved",
                "fixed_note": "Confirmed resolved \u2014 no longer detected on live site",
                "severity": "resolved",
            })
    return resolved


def _fuzzy_match_reverse(fix_key: str, detected_keys: Set[str]) -> bool:
    """Check if a fix_key matches any detected issue key (reverse of _fuzzy_match)."""
    if fix_key in detected_keys:
        return True

    fix_parts = fix_key.split(":", 1)
    if len(fix_parts) < 2:
        return False
    fix_cat, fix_name = fix_parts

    for dk in detected_keys:
        det_parts = dk.split(":", 1)
        if len(det_parts) < 2:
            continue
        det_cat, det_name = det_parts

        if fix_cat != det_cat:
            continue

        if fix_name in det_name or det_name in fix_name:
            return True

        fix_tokens = set(fix_name.split('_'))
        det_tokens = set(det_name.split('_'))
        if fix_tokens and det_tokens:
            overlap = fix_tokens & det_tokens
            min_len = min(len(fix_tokens), len(det_tokens))
            if min_len > 0 and len(overlap) / min_len >= 0.5:
                return True

    return False


def enrich_scan_result_issues(scan_result: dict, all_issues: list, confirmed_resolved: list = None):
    """
    After enrichment, update the scan_result's category sub-objects
    with the enriched issue data (is_fixed, issue_key).
    Also adds top-level counts and confirmed_resolved entries.
    """
    fixed_count = sum(1 for i in all_issues if i.get("is_fixed"))
    open_count = len(all_issues) - fixed_count
    resolved_count = len(confirmed_resolved) if confirmed_resolved else 0

    scan_result["fixed_issues"] = fixed_count
    scan_result["open_issues"] = open_count
    scan_result["confirmed_resolved"] = resolved_count
    if confirmed_resolved:
        scan_result["resolved_details"] = confirmed_resolved

    # Update recommendations to mark fixed ones
    for rec in scan_result.get("recommendations", []):
        rec_key = generate_issue_key({
            "category": rec.get("category", "general"),
            "issue": rec.get("title", "")
        })
        rec["issue_key"] = rec_key
        rec["is_fixed"] = any(
            i.get("is_fixed") and i.get("issue_key") == rec_key
            for i in all_issues
        )
