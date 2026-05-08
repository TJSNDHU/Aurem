"""
AUREM Self-Scan: Daily automated scan of aurem.live (dogfooding).
Runs at 3:00 AM EST via APScheduler. Skips if previous scan still in progress.
"""
import logging
import secrets
from datetime import datetime, timezone

logger = logging.getLogger("aurem.self_scan")

SELF_CLIENT_URL = "https://aurem.live"
SELF_CLIENT_TENANT = "aurem_internal"
SELF_CLIENT_PROFILE_ID = "aurem_self"


async def run_self_scan():
    """Daily self-scan of aurem.live. Called by APScheduler."""
    scan_id = None
    try:
        from server import db
        if db is None:
            logger.warning("[SELF-SCAN] Database not initialized — skipping")
            return

        # Guard: skip if previous scan is in progress
        in_progress = await db.system_scans.find_one({
            "tenant_id": SELF_CLIENT_TENANT,
            "status": "in_progress",
        })
        if in_progress:
            logger.info("[SELF-SCAN] Skipped — previous scan still in progress")
            return

        # Mark scan as in progress
        scan_id = f"scan_{secrets.token_urlsafe(16)}"
        await db.system_scans.insert_one({
            "_id": scan_id,
            "tenant_id": SELF_CLIENT_TENANT,
            "website_url": SELF_CLIENT_URL,
            "status": "in_progress",
            "scan_date": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"[SELF-SCAN] Starting daily scan of {SELF_CLIENT_URL} (scan_id={scan_id})")

        # Import scanner functions
        from routers.customer_scanner import (
            scan_performance, scan_security, scan_seo, scan_accessibility,
        )
        from utils.fix_enrichment import (
            enrich_issues_with_fix_status, enrich_scan_result_issues,
            build_confirmed_resolved,
        )
        import httpx

        # Fetch the live site
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(SELF_CLIENT_URL)
            html_content = response.text
            headers_dict = dict(response.headers)

        # Run all scanners
        import asyncio
        perf_result, sec_result, seo_result, acc_result = await asyncio.gather(
            scan_performance(SELF_CLIENT_URL),
            scan_security(SELF_CLIENT_URL),
            scan_seo(html_content),
            scan_accessibility(html_content),
        )

        # Aggregate issues
        all_issues = []
        for cat_name, result in [("performance", perf_result), ("security", sec_result), ("seo", seo_result), ("accessibility", acc_result)]:
            for issue in result.get("issues", []):
                issue["_cat"] = cat_name
                all_issues.append(issue)

        overall_score = round(sum([
            perf_result.get("score", 0),
            sec_result.get("score", 0),
            seo_result.get("score", 0),
            acc_result.get("score", 0)
        ]) / 4)

        critical_count = sum(1 for i in all_issues if i.get("severity") == "critical")

        scan_result = {
            "scan_id": scan_id,
            "website_url": SELF_CLIENT_URL,
            "tenant_id": SELF_CLIENT_TENANT,
            "scan_date": datetime.now(timezone.utc).isoformat(),
            "overall_score": overall_score,
            "issues_found": len(all_issues),
            "critical_issues": critical_count,
            "performance": perf_result,
            "security": sec_result,
            "seo": seo_result,
            "accessibility": acc_result,
            "triggered_from": "daily_cron",
            "status": "completed",
        }

        # Enrich with fix status
        result = await enrich_issues_with_fix_status(db, all_issues, SELF_CLIENT_URL)
        confirmed_resolved = []
        if result:
            detected_keys, fix_keys = result
            confirmed_resolved = build_confirmed_resolved(detected_keys, fix_keys)
        enrich_scan_result_issues(scan_result, all_issues, confirmed_resolved)

        # Update the in-progress record with full results
        await db.system_scans.update_one(
            {"_id": scan_id},
            {"$set": scan_result}
        )

        logger.info(
            f"[SELF-SCAN] Completed: score={overall_score}, "
            f"open={scan_result.get('open_issues', 0)}, "
            f"fixed={scan_result.get('fixed_issues', 0)}, "
            f"resolved={scan_result.get('confirmed_resolved', 0)}"
        )

    except Exception as e:
        logger.error(f"[SELF-SCAN] Failed: {e}")
        # Clean up in-progress marker
        try:
            from server import db
            await db.system_scans.update_one(
                {"_id": scan_id, "status": "in_progress"},
                {"$set": {"status": "failed", "error": str(e)}}
            )
        except Exception:
            pass


async def run_daily_client_scans():
    """Scan all active client websites. Called by APScheduler after self-scan."""
    try:
        from server import db
        if db is None:
            logger.warning("[CLIENT-SCAN] Database not initialized — skipping")
            return

        from services.client_scanner_service import ClientScannerService
        from services.auto_fix_engine import run_auto_fixes

        scanner = ClientScannerService(db)

        tenants = await db.users.find(
            {"website_url": {"$exists": True, "$ne": ""}, "active": {"$ne": False}},
            {"_id": 0, "tenant_id": 1, "id": 1, "website_url": 1, "business_name": 1},
        ).to_list(length=100)

        logger.info(f"[CLIENT-SCAN] Starting daily scan for {len(tenants)} clients")

        for tenant in tenants:
            tid = tenant.get("tenant_id") or tenant.get("id", "unknown")
            url = tenant.get("website_url", "")
            if not url:
                continue
            try:
                result = await scanner.run_full_scan(tid, url, triggered_by="daily_cron")
                fixes = await run_auto_fixes(db, tid, result.get("issues", []))
                fixed_count = len([f for f in fixes if f.get("fixed")])

                # Check for score drops
                prev = await db.client_scan_results.find_one(
                    {"tenant_id": tid, "status": "completed", "scanned_at": {"$lt": result["scanned_at"]}},
                    {"_id": 0, "overall_score": 1},
                    sort=[("scanned_at", -1)],
                )
                if prev:
                    drop = prev.get("overall_score", 0) - result.get("overall_score", 0)
                    if drop >= 10:
                        logger.warning(f"[CLIENT-SCAN] ALERT: {tenant.get('business_name', tid)} score dropped {drop} pts!")

                logger.info(f"[CLIENT-SCAN] {tenant.get('business_name', tid)}: {result.get('overall_score', 0)}/100, {fixed_count} auto-fixed")
            except Exception as e:
                logger.error(f"[CLIENT-SCAN] Failed for {tenant.get('business_name', tid)}: {e}")

        logger.info(f"[CLIENT-SCAN] Daily scan complete for {len(tenants)} clients")
    except Exception as e:
        logger.error(f"[CLIENT-SCAN] Daily scan failed: {e}")
