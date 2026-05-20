"""
AUREM Self-Detect & Repair Loop
=================================
AUREM monitors itself (and connected client sites) on a schedule.
Runs ORA Scanner → generates fixes → pushes to system_auto_repairs collection.
ClawChief integrates for deadlock/corruption detection.
"""
import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

_db = None
SCAN_INTERVAL_HOURS = 6
ADMIN_PHONE = os.environ.get("ADMIN_WHATSAPP", "12265017777")

# Default baseline sites — always scanned even if workspaces collection is empty.
# Additional sites are auto-discovered from `aurem_workspaces` collection on
# every scan cycle, so NEW customers get repaired automatically without any
# code change after they onboard.
BASELINE_SCAN_SITES = [
    {"url": "https://aurem.live", "tenant_id": "aurem_self", "label": "AUREM Platform"},
    {"url": "https://aurem.live", "tenant_id": "reroots_aesthetics", "label": "AUREM Aesthetics"},
]

# Backward-compat alias (older code imports this name)
AUTO_SCAN_SITES = BASELINE_SCAN_SITES


async def _discover_scan_targets() -> List[Dict]:
    """
    Merge BASELINE_SCAN_SITES with every active workspace from
    `aurem_workspaces`. Any workspace with a `website` URL is scanned.
    This means the moment a new customer is onboarded, they're covered
    by the self-repair loop — no code deploy required.
    """
    targets: Dict[str, Dict] = {}

    if _db is not None:
        try:
            cursor = _db["aurem_workspaces"].find(
                {
                    "website": {"$nin": [None, ""], "$exists": True},
                    # Skip workspaces that have explicitly opted out of scanning
                    "auto_repair_disabled": {"$ne": True},
                },
                {"_id": 0, "business_id": 1, "business_name": 1, "website": 1, "tenant_id": 1},
            )
            async for ws in cursor:
                url = (ws.get("website") or "").strip()
                if not url.startswith(("http://", "https://")):
                    continue
                # Prefer a per-workspace tenant_id; fall back to business_id
                tid = ws.get("tenant_id") or ws.get("business_id") or "unknown"
                label = ws.get("business_name") or url
                targets[url] = {"url": url, "tenant_id": tid, "label": label}
        except Exception as e:
            logger.warning(f"[SelfRepair] workspace discovery failed: {e}")

    # Baseline sites ALWAYS override workspace data (canonical labels + tenant IDs).
    # This ensures our core products (AUREM, AUREM) are always labeled correctly
    # in WhatsApp alerts even if the workspace document has stale metadata.
    for site in BASELINE_SCAN_SITES:
        targets[site["url"]] = dict(site)

    return list(targets.values())


def set_db(database):
    global _db
    _db = database


async def _queue_unfixable(
    repairs: List[Dict],
    tenant_id: str,
    label: str,
    site_url: str,
    scan_time,
) -> int:
    """
    For every repair that the patch_deployer could NOT auto-fix
    (no template matched), create/upsert an entry in
    `unfixable_issues_queue` so the admin can bridge it to AUREM Builder.

    Dedupe key = (tenant_id, category, issue-text-fingerprint).
    Returns the count of queue entries touched this run.
    """
    if _db is None or not repairs:
        return 0

    try:
        from services.patch_deployer import (
            generate_css_fix, generate_meta_fix, generate_schema_fix, generate_js_fix,
        )
    except Exception:
        return 0

    generators = [generate_css_fix, generate_meta_fix, generate_schema_fix, generate_js_fix]
    touched = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for repair in repairs:
        fixable = any(gen(repair) for gen in generators)
        if fixable:
            continue
        issue_text = (repair.get("issue") or "").strip()
        category = repair.get("category") or "general"
        severity = repair.get("severity") or "warning"
        if not issue_text:
            continue
        # Stable fingerprint so repeat scans update the same queue row
        fingerprint = f"{tenant_id}::{category}::{issue_text.lower()[:160]}"
        update = {
            "$setOnInsert": {
                "fingerprint": fingerprint,
                "tenant_id": tenant_id,
                "label": label,
                "site_url": site_url,
                "category": category,
                "issue": issue_text,
                "first_seen": now_iso,
                "status": "queued",  # queued | sent_to_builder | resolved | dismissed
                "builder_build_id": None,
                "builder_status": None,
            },
            "$set": {
                "last_seen": now_iso,
                "severity": severity,
                "details": repair.get("details", ""),
                "aurem_solution": repair.get("aurem_solution", ""),
            },
            "$inc": {"occurrences": 1},
        }
        try:
            await _db["unfixable_issues_queue"].update_one(
                {"fingerprint": fingerprint}, update, upsert=True,
            )
            touched += 1
        except Exception as e:
            logger.warning(f"[SelfRepair] unfixable queue upsert failed: {e}")

    if touched:
        logger.info(f"[SelfRepair] Queued {touched} unfixable issue(s) for {label} → Builder bridge")
    return touched


async def run_self_scan(site_url: str, tenant_id: str, label: str) -> Dict:
    """Run a full scan on a site and save results + auto-repairs to DB."""
    if _db is None:
        return {"success": False, "error": "no_db"}

    logger.info(f"[SelfRepair] Scanning {label} ({site_url})...")
    scan_start = datetime.now(timezone.utc)
    results = {"url": site_url, "tenant_id": tenant_id, "label": label}

    try:
        from routers.customer_scanner import scan_performance, scan_security, scan_seo, scan_accessibility
        import httpx

        # Run all scan categories
        # NOTE: 30s timeout cut to 8s — if a target is slow we skip it rather
        # than blocking the event loop. In a fresh deploy the target may be
        # self-referential (aurem.live == this pod) and still warming up.
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                resp = await client.get(site_url)
                html = resp.text
            except Exception as e:
                html = ""
                # Target site slow/down — expected, not a bug. Log at INFO not WARNING.
                logger.info(f"[SelfRepair] Could not fetch {site_url}: {e}")

        scans = {}
        scan_funcs = [
            ("performance", scan_performance),
            ("security", scan_security),
            ("seo", scan_seo),
            ("accessibility", scan_accessibility),
        ]

        for category, func in scan_funcs:
            try:
                if category == "performance":
                    scans[category] = await func(site_url)
                elif category in ("security", "seo"):
                    scans[category] = await func(site_url, html)
                elif category == "accessibility":
                    scans[category] = await func(html)
            except Exception as e:
                scans[category] = {"score": 0, "issues": [], "error": str(e)}

        # Calculate overall score
        scores = {k: v.get("score", 0) for k, v in scans.items()}
        overall = round(sum(scores.values()) / max(len(scores), 1))

        # Collect all issues
        all_issues = []
        for cat, data in scans.items():
            for issue in data.get("issues", []):
                issue["category"] = cat
                all_issues.append(issue)

        critical_count = sum(1 for i in all_issues if i.get("severity") == "critical")
        warning_count = sum(1 for i in all_issues if i.get("severity") == "warning")

        # Generate auto-repair entries
        repairs = []
        for issue in all_issues:
            if issue.get("severity") in ("critical", "warning"):
                repairs.append({
                    "issue": issue.get("issue", ""),
                    "category": issue.get("category", ""),
                    "severity": issue.get("severity", ""),
                    "details": issue.get("details", ""),
                    "aurem_solution": issue.get("aurem_solution", ""),
                    "status": "auto_detected",
                    "detected_at": scan_start.isoformat(),
                })

        # Save to system_auto_repairs
        scan_doc = {
            "site_url": site_url,
            "tenant_id": tenant_id,
            "label": label,
            "overall_score": overall,
            "scores": scores,
            "issues_total": len(all_issues),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "repairs": repairs,
            "scanned_at": scan_start.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        await _db["system_auto_repairs"].insert_one(scan_doc)

        # ─── LIVE-PATCH DEPLOYMENT ─────────────────────────────
        # Convert detected repairs into deployable patches and push
        # through the pixel bridge. Patches are applied in real-time
        # on the client's next page load (no restart needed).
        deployed_info = {"deployed": 0}
        unfixable_count = 0
        if repairs:
            try:
                from services.patch_deployer import generate_patches_from_repairs, deploy_patches
                # Track which repairs actually produced a patch so we can
                # queue everything else for AUREM Builder (LLM-powered fixes).
                unfixable_count = await _queue_unfixable(
                    repairs=repairs,
                    tenant_id=tenant_id,
                    label=label,
                    site_url=site_url,
                    scan_time=scan_start,
                )

                # Load workspace for business context (schema placeholders etc.)
                workspace = await _db["aurem_workspaces"].find_one(
                    {"website": site_url}, {"_id": 0}
                )
                if not workspace:
                    # Try matching by tenant_id pattern
                    workspace = await _db["aurem_workspaces"].find_one(
                        {"business_id": {"$regex": tenant_id.split("_")[0] if "_" in tenant_id else tenant_id, "$options": "i"}},
                        {"_id": 0}
                    )

                patches = generate_patches_from_repairs(repairs, workspace)

                if patches and workspace:
                    business_id = workspace.get("business_id", tenant_id)
                    deployed_info = await deploy_patches(
                        business_id=business_id,
                        patches=patches,
                        rollout_pct=10,  # Start at 10% canary
                        scan_id=scan_doc.get("tenant_id", "") + "_" + scan_start.strftime("%Y%m%d%H%M"),
                    )
                    logger.info(f"[SelfRepair] Deployed {deployed_info.get('deployed', 0)} live patches for {label} (canary 10%)")

                    # Route through DeploymentRouter for platform-specific push
                    if deployed_info.get("deployed", 0) > 0:
                        try:
                            from services.deployment_router import route_and_deploy
                            deploy_result = await route_and_deploy(
                                tenant_id=tenant_id,
                                business_id=business_id,
                                patches=patches,
                                batch_id=deployed_info.get("batch_id", ""),
                            )
                            deployed_info["deploy_result"] = deploy_result
                            logger.info(f"[SelfRepair] DeploymentRouter: {label} → {deploy_result.get('platform','?')} ({deploy_result.get('method','?')})")
                        except Exception as dr_err:
                            logger.warning(f"[SelfRepair] DeploymentRouter failed for {label}: {dr_err}")

                elif patches:
                    # No workspace found but we have patches — deploy with tenant_id
                    deployed_info = await deploy_patches(
                        business_id=tenant_id,
                        patches=patches,
                        rollout_pct=10,
                        scan_id=tenant_id + "_" + scan_start.strftime("%Y%m%d%H%M"),
                    )
                    logger.info(f"[SelfRepair] Deployed {deployed_info.get('deployed', 0)} patches for {label} (no workspace, using tenant_id)")

                    # Route through DeploymentRouter
                    if deployed_info.get("deployed", 0) > 0:
                        try:
                            from services.deployment_router import route_and_deploy
                            deploy_result = await route_and_deploy(
                                tenant_id=tenant_id,
                                business_id=tenant_id,
                                patches=patches,
                                batch_id=deployed_info.get("batch_id", ""),
                            )
                            deployed_info["deploy_result"] = deploy_result
                        except Exception as dr_err:
                            logger.warning(f"[SelfRepair] DeploymentRouter failed for {label}: {dr_err}")
            except Exception as e:
                logger.warning(f"[SelfRepair] Patch deployment failed for {label}: {e}")

        # WhatsApp alert — ONLY when something actually regresses or stays red.
        # Previous logic alerted every 6h with the same stale "X queued" count,
        # which created notification fatigue (score stayed 59-72 for weeks).
        try:
            # Fetch the PREVIOUS scan for this site to compare
            prev_scan = await _db["system_auto_repairs"].find_one(
                {"label": label, "scanned_at": {"$lt": scan_start.isoformat()}},
                {"_id": 0, "overall_score": 1, "critical_count": 1, "repairs": 1},
                sort=[("scanned_at", -1)],
            )
            should_alert = False
            alert_reason = ""

            if critical_count > 0 and (not prev_scan or prev_scan.get("critical_count", 0) == 0):
                # NEW critical issue appeared
                should_alert = True
                alert_reason = "new critical issue"
            elif overall < 60 and prev_scan and prev_scan.get("overall_score", 100) >= 60:
                # Score dropped below 60 for the first time
                should_alert = True
                alert_reason = "score dropped below 60"
            elif overall < 60:
                # Still below 60 but only alert once per 24h to avoid spam
                last_alert = await _db["self_repair_alerts"].find_one(
                    {"label": label}, {"_id": 0, "sent_at": 1}, sort=[("sent_at", -1)],
                )
                if last_alert:
                    from datetime import timedelta
                    last_ts = datetime.fromisoformat(last_alert["sent_at"].replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - last_ts > timedelta(hours=24):
                        should_alert = True
                        alert_reason = "still degraded (24h reminder)"
                else:
                    should_alert = True
                    alert_reason = "first-ever alert for this site"

            if should_alert:
                from routers.whatsapp_alerts import send_whatsapp
                delta = ""
                if prev_scan and prev_scan.get("overall_score") is not None:
                    diff = overall - prev_scan["overall_score"]
                    if diff != 0:
                        delta = f" ({'+' if diff > 0 else ''}{diff} vs last)"
                patches_info = f" · {deployed_info.get('deployed', 0)} patches deployed" if deployed_info.get("deployed", 0) else ""
                msg = (
                    f"AUREM SELF-REPAIR: {label} scored {overall}/100{delta}. "
                    f"{critical_count} critical · {len(repairs)} issues · {alert_reason}.{patches_info}"
                )
                await send_whatsapp(ADMIN_PHONE, msg)
                # Record alert so 24h dedupe works
                await _db["self_repair_alerts"].insert_one({
                    "label": label,
                    "score": overall,
                    "critical_count": critical_count,
                    "reason": alert_reason,
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as alert_err:
            logger.warning(f"[SelfRepair] Alert logic failed: {alert_err}")

        # Log to security_events if score dropped below threshold
        if overall < 60:
            await _db["security_events"].insert_one({
                "event_type": "self_scan_degraded",
                "severity": "high",
                "tenant_id": tenant_id,
                "details": {"score": overall, "critical": critical_count, "url": site_url},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        results.update({
            "success": True,
            "overall_score": overall,
            "scores": scores,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "repairs_queued": len(repairs),
            "patches_deployed": deployed_info.get("deployed", 0),
            "patch_batch_id": deployed_info.get("batch_id"),
            "unfixable_queued": unfixable_count,
        })
        logger.info(f"[SelfRepair] {label}: score={overall}, critical={critical_count}, repairs={len(repairs)}")

    except Exception as e:
        logger.error(f"[SelfRepair] Scan failed for {label}: {e}")
        results.update({"success": False, "error": str(e)})

    return results


async def run_all_scans() -> List[Dict]:
    """Run self-scan on every registered site + every active workspace."""
    results = []
    sites = await _discover_scan_targets()
    logger.info(f"[SelfRepair] Running scan cycle across {len(sites)} site(s)")
    for site in sites:
        try:
            result = await run_self_scan(site["url"], site["tenant_id"], site["label"])
            results.append(result)
        except Exception as e:
            logger.warning(f"[SelfRepair] {site.get('label')} scan errored: {e}")
            results.append({"success": False, "url": site["url"], "error": str(e)[:200]})
    return results


async def get_repair_history(tenant_id: str = None, limit: int = 20) -> List[Dict]:
    """Get auto-repair history from DB."""
    if _db is None:
        return []
    query = {"tenant_id": tenant_id} if tenant_id else {}
    cursor = _db["system_auto_repairs"].find(query, {"_id": 0}).sort("scanned_at", -1).limit(limit)
    return await cursor.to_list(limit)


async def self_repair_loop():
    """Background loop: scan all sites every 6 hours.

    Initial delay is intentionally long (30 min) so the K8s pod has time
    to settle (warm caches, finish APScheduler bootstrap, open Mongo
    connections). Scanning external URLs (https://aurem.live,
    https://aurem.live) immediately at boot — while the same pod is also
    serving the request that just deployed it — pegs the event loop and
    causes nginx upstream timeouts on /health.

    Set `AUREM_SELF_REPAIR_DISABLED=1` to skip entirely (e.g. during
    deploy/canary windows).
    """
    if os.environ.get("AUREM_SELF_REPAIR_DISABLED", "").strip() in ("1", "true", "yes"):
        logger.info("[SelfRepair] Loop disabled via AUREM_SELF_REPAIR_DISABLED env var")
        return

    # Wait 30 minutes after startup — let all services stabilize and let
    # K8s liveness probes settle into a steady state before issuing
    # outbound HTTP scans on the same event loop.
    await asyncio.sleep(1800)
    try:
        await run_all_scans()
    except Exception as e:
        logger.error(f"[SelfRepair] Initial scan failed: {e}")

    while True:
        try:
            await asyncio.sleep(SCAN_INTERVAL_HOURS * 3600)
            await run_all_scans()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[SelfRepair] Loop error: {e}")
            await asyncio.sleep(300)


print("[STARTUP] Self-Repair Loop loaded — auto-discovers sites from aurem_workspaces every 6h", flush=True)
