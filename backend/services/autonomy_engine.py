"""
AUREM Autonomous Operations — Self-Audit + A2A Problem Resolver
================================================================
5 agents scan customer databases simultaneously.
Problems broadcast via A2A → agents bid → best wins → auto-fix.

Agents:
  Scout    — data freshness, stale records, API health
  Shannon  — security issues, weak points, PII exposure
  Architect — data patterns, inefficiencies, schema gaps
  Hermes   — memory gaps, missing customer data, unlinked records
  Repair   — broken records, failed operations, sync issues

Survival Tiers (Stripe-based):
  Abundant   — active subscription → full agents + GLM-5.1
  Economical — trial → free models only
  Survival   — payment failed → minimal responses
  Death      — cancelled → stop all operations
"""
import os
import logging
import secrets
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

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
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


# ═══════════════════════════════════════════════════════════════
# SURVIVAL TIERS
# ═══════════════════════════════════════════════════════════════

SURVIVAL_TIERS = {
    "abundant": {"label": "Abundant", "agents": "all", "models": "glm-5.1 + cloud", "auto_fixes": -1},
    "economical": {"label": "Economical", "agents": "all", "models": "free only", "auto_fixes": 50},
    "survival": {"label": "Survival", "agents": "repair only", "models": "minimal", "auto_fixes": 10},
    "death": {"label": "Death", "agents": "none", "models": "none", "auto_fixes": 0},
}

# Plan-based fix limits (monthly)
PLAN_FIX_LIMITS = {
    "starter": 50,
    "growth": 500,
    "enterprise": -1,  # Unlimited
}


async def get_monthly_fix_usage(tenant_id: str) -> Dict:
    """Get current month's auto-fix usage for a tenant."""
    db = _get_db()
    if db is None:
        return {"used": 0, "limit": 50, "plan": "starter"}
    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")

    usage = await db.aurem_tenant_usage.find_one(
        {"tenant_id": tenant_id, "month": month_key}, {"_id": 0}
    )
    used = (usage or {}).get("auto_fixes_count", 0)

    # Get plan
    ws = await db.workspaces.find_one({"tenant_id": tenant_id}, {"_id": 0, "tier": 1, "plan": 1})
    plan = (ws or {}).get("tier") or (ws or {}).get("plan") or "starter"
    limit = PLAN_FIX_LIMITS.get(plan, 50)

    return {"used": used, "limit": limit, "plan": plan, "month": month_key,
            "remaining": max(0, limit - used) if limit != -1 else -1,
            "over_limit": limit != -1 and used >= limit}


async def _increment_fix_usage(tenant_id: str, count: int = 1):
    """Increment monthly auto-fix counter for a tenant."""
    db = _get_db()
    if db is None:
        return
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    await db.aurem_tenant_usage.update_one(
        {"tenant_id": tenant_id, "month": month_key},
        {"$inc": {"auto_fixes_count": count}, "$set": {"last_fix_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


async def _send_upgrade_prompt(tenant_id: str, usage: Dict):
    """Send WhatsApp upgrade prompt when fix limit reached."""
    try:
        from services.whapi_service import send_whatsapp_message
        plan = usage.get("plan", "starter")
        used = usage.get("used", 0)
        limit = usage.get("limit", 50)
        next_plan = "Growth" if plan == "starter" else "Enterprise"
        msg = (
            f"AUREM Auto-Fix Limit Reached\n\n"
            f"Plan: {plan.capitalize()} ({used}/{limit} fixes used this month)\n"
            f"Upgrade to {next_plan} for {'500' if plan == 'starter' else 'unlimited'} auto-fixes.\n\n"
            f"Upgrade at: aurem.live/billing"
        )
        await send_whatsapp_message(ADMIN_PHONE, msg)
    except Exception:
        pass


async def get_survival_tier(tenant_id: str) -> Dict:
    """Determine tenant's survival tier based on subscription status."""
    db = _get_db()
    if db is None:
        return {"tier": "economical", **SURVIVAL_TIERS["economical"]}
    ws = await db.workspaces.find_one({"tenant_id": tenant_id}, {"_id": 0, "tier": 1, "plan": 1, "subscription_status": 1, "trial": 1})
    if not ws:
        return {"tier": "economical", **SURVIVAL_TIERS["economical"]}

    sub_status = ws.get("subscription_status", "")
    plan = ws.get("tier") or ws.get("plan") or "starter"

    if sub_status == "cancelled":
        return {"tier": "death", **SURVIVAL_TIERS["death"]}
    if sub_status == "payment_failed":
        return {"tier": "survival", **SURVIVAL_TIERS["survival"]}
    if ws.get("trial") or plan == "starter":
        return {"tier": "economical", **SURVIVAL_TIERS["economical"]}
    return {"tier": "abundant", **SURVIVAL_TIERS["abundant"]}


# ═══════════════════════════════════════════════════════════════
# AGENT SCANNERS — Each agent scans its domain
# ═══════════════════════════════════════════════════════════════

async def _scout_scan(tenant_id: str) -> Dict:
    """Scout: data freshness, stale records, API connectivity."""
    db = _get_db()
    issues = []
    if db is None:
        return {"agent": "scout", "issues_found": [], "scan_time_ms": 0}

    t0 = asyncio.get_event_loop().time()

    # Check stale customer data (no update in 30 days)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    stale_count = await db.customers.count_documents(
        {"tenant_id": tenant_id, "updated_at": {"$lt": cutoff}}
    )
    if stale_count > 0:
        issues.append({
            "type": "stale_data", "severity": "P2",
            "description": f"{stale_count} customers not updated in 30+ days",
            "affected_records": stale_count, "fix_available": True, "fix_confidence": 0.80,
            "fix_action": "refresh_stale_records",
        })

    # Check for customers with no email
    no_email = await db.customers.count_documents(
        {"tenant_id": tenant_id, "$or": [{"email": ""}, {"email": None}, {"email": {"$exists": False}}]}
    )
    if no_email > 0:
        issues.append({
            "type": "missing_email", "severity": "P1",
            "description": f"{no_email} customers have no email address",
            "affected_records": no_email, "fix_available": True, "fix_confidence": 0.70,
            "fix_action": "find_missing_emails",
        })

    # Check for customers with no phone
    no_phone = await db.customers.count_documents(
        {"tenant_id": tenant_id, "$or": [{"phone": ""}, {"phone": None}, {"phone": {"$exists": False}}]}
    )
    if no_phone > 0:
        issues.append({
            "type": "missing_phone", "severity": "P2",
            "description": f"{no_phone} customers have no phone number",
            "affected_records": no_phone, "fix_available": True, "fix_confidence": 0.60,
            "fix_action": "find_missing_phones",
        })

    elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)
    return {"agent": "scout", "issues_found": issues, "scan_time_ms": elapsed,
            "suggestions": ["Schedule weekly data freshness check", "Add email validation on customer creation"] if issues else []}


async def _shannon_scan(tenant_id: str) -> Dict:
    """Shannon: security issues, PII exposure, weak points."""
    db = _get_db()
    issues = []
    if db is None:
        return {"agent": "shannon", "issues_found": [], "scan_time_ms": 0}

    t0 = asyncio.get_event_loop().time()

    # Check for plaintext passwords in customer records
    plaintext = await db.customers.count_documents(
        {"tenant_id": tenant_id, "password": {"$exists": True, "$ne": None}}
    )
    if plaintext > 0:
        issues.append({
            "type": "plaintext_password", "severity": "P0",
            "description": f"{plaintext} records have plaintext password fields",
            "affected_records": plaintext, "fix_available": True, "fix_confidence": 0.99,
            "fix_action": "remove_plaintext_passwords",
        })

    # Check for unencrypted PII
    pii_exposed = await db.customers.count_documents(
        {"tenant_id": tenant_id, "ssn": {"$exists": True}}
    )
    if pii_exposed > 0:
        issues.append({
            "type": "pii_exposure", "severity": "P0",
            "description": f"{pii_exposed} records have exposed PII (SSN field)",
            "affected_records": pii_exposed, "fix_available": True, "fix_confidence": 0.95,
            "fix_action": "encrypt_pii_fields",
        })

    elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)
    return {"agent": "shannon", "issues_found": issues, "scan_time_ms": elapsed,
            "suggestions": ["Enable field-level encryption for PII"] if issues else []}


async def _architect_scan(tenant_id: str) -> Dict:
    """Architect: data patterns, duplicates, schema gaps."""
    db = _get_db()
    issues = []
    if db is None:
        return {"agent": "architect", "issues_found": [], "scan_time_ms": 0}

    t0 = asyncio.get_event_loop().time()

    # Check for duplicate emails
    pipeline = [
        {"$match": {"tenant_id": tenant_id, "email": {"$exists": True, "$ne": "", "$ne": None}}},
        {"$group": {"_id": "$email", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$count": "duplicates"},
    ]
    dup_result = await db.customers.aggregate(pipeline).to_list(1)
    dup_count = dup_result[0]["duplicates"] if dup_result else 0
    if dup_count > 0:
        issues.append({
            "type": "duplicate_customers", "severity": "P1",
            "description": f"{dup_count} duplicate email addresses found",
            "affected_records": dup_count, "fix_available": True, "fix_confidence": 0.92,
            "fix_action": "merge_duplicate_records",
        })

    # Check for records missing required fields
    incomplete = await db.customers.count_documents(
        {"tenant_id": tenant_id, "$or": [
            {"name": {"$in": ["", None]}},
            {"email": {"$in": ["", None]}},
        ]}
    )
    if incomplete > 0:
        issues.append({
            "type": "incomplete_records", "severity": "P2",
            "description": f"{incomplete} records missing name or email",
            "affected_records": incomplete, "fix_available": True, "fix_confidence": 0.75,
            "fix_action": "enrich_incomplete_records",
        })

    elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)
    return {"agent": "architect", "issues_found": issues, "scan_time_ms": elapsed,
            "suggestions": ["Add unique constraint on email field", "Implement dedup on customer creation"] if issues else []}


async def _hermes_scan(tenant_id: str) -> Dict:
    """Hermes: memory gaps, unlinked records, interaction gaps."""
    db = _get_db()
    issues = []
    if db is None:
        return {"agent": "hermes", "issues_found": [], "scan_time_ms": 0}

    t0 = asyncio.get_event_loop().time()

    # Customers with zero interactions (never contacted)
    total_customers = await db.customers.count_documents({"tenant_id": tenant_id})
    interacted = await db.hermes_interactions.distinct("tenant_id", {"tenant_id": tenant_id})
    orphan_count = max(0, total_customers - len(interacted)) if total_customers > 0 else 0
    # Simplified: check outreach queue for uncontacted
    never_contacted = await db.customers.count_documents(
        {"tenant_id": tenant_id, "last_contacted": {"$exists": False}}
    )
    if never_contacted > 0:
        issues.append({
            "type": "never_contacted", "severity": "P2",
            "description": f"{never_contacted} customers never contacted",
            "affected_records": never_contacted, "fix_available": True, "fix_confidence": 0.85,
            "fix_action": "queue_initial_outreach",
        })

    # Check for failed outreach in queue
    failed_outreach = await db.forensic_miner_outreach_queue.count_documents(
        {"tenant_id": tenant_id, "status": "failed"}
    )
    if failed_outreach > 0:
        issues.append({
            "type": "failed_outreach", "severity": "P1",
            "description": f"{failed_outreach} outreach messages failed delivery",
            "affected_records": failed_outreach, "fix_available": True, "fix_confidence": 0.90,
            "fix_action": "retry_failed_outreach",
        })

    elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)
    return {"agent": "hermes", "issues_found": issues, "scan_time_ms": elapsed,
            "suggestions": ["Set up auto-welcome sequence for new customers"] if issues else []}


async def _repair_scan(tenant_id: str) -> Dict:
    """Repair: broken records, failed operations, sync issues."""
    db = _get_db()
    issues = []
    if db is None:
        return {"agent": "repair", "issues_found": [], "scan_time_ms": 0}

    t0 = asyncio.get_event_loop().time()

    # Failed video generation jobs
    failed_videos = await db.video_queue.count_documents(
        {"tenant_id": tenant_id, "status": "failed"}
    )
    if failed_videos > 0:
        issues.append({
            "type": "failed_video_jobs", "severity": "P3",
            "description": f"{failed_videos} video generation jobs failed",
            "affected_records": failed_videos, "fix_available": True, "fix_confidence": 0.70,
            "fix_action": "requeue_failed_videos",
        })

    # Stuck rendering jobs (started > 1 hour ago)
    stuck_cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    stuck = await db.video_queue.count_documents(
        {"tenant_id": tenant_id, "status": "rendering", "started_at": {"$lt": stuck_cutoff}}
    )
    if stuck > 0:
        issues.append({
            "type": "stuck_jobs", "severity": "P2",
            "description": f"{stuck} jobs stuck in rendering for 1+ hours",
            "affected_records": stuck, "fix_available": True, "fix_confidence": 0.95,
            "fix_action": "reset_stuck_jobs",
        })

    elapsed = round((asyncio.get_event_loop().time() - t0) * 1000)
    return {"agent": "repair", "issues_found": issues, "scan_time_ms": elapsed,
            "suggestions": ["Add job timeout watchdog"] if issues else []}


# ═══════════════════════════════════════════════════════════════
# A2A BIDDING + EXECUTION
# ═══════════════════════════════════════════════════════════════

AGENT_CAPABILITIES = {
    "scout": ["stale_data", "missing_email", "missing_phone", "find_missing_emails", "find_missing_phones"],
    "shannon": ["plaintext_password", "pii_exposure", "remove_plaintext_passwords", "encrypt_pii_fields"],
    "architect": ["duplicate_customers", "incomplete_records", "merge_duplicate_records", "enrich_incomplete_records"],
    "hermes": ["never_contacted", "failed_outreach", "queue_initial_outreach", "retry_failed_outreach"],
    "repair": ["failed_video_jobs", "stuck_jobs", "requeue_failed_videos", "reset_stuck_jobs",
               "refresh_stale_records", "merge_duplicate_records"],
}


def _agent_bid(agent: str, issue: Dict) -> Dict:
    """Agent bids on a problem with a confidence score."""
    issue_type = issue.get("type", "")
    fix_action = issue.get("fix_action", "")

    # Base confidence from issue's own fix_confidence
    base = issue.get("fix_confidence", 0.5)

    # Boost if agent specializes in this issue type
    caps = AGENT_CAPABILITIES.get(agent, [])
    if issue_type in caps or fix_action in caps:
        confidence = min(1.0, base + 0.10)
    else:
        confidence = max(0.0, base - 0.30)

    # Repair agent gets bonus for execution tasks
    if agent == "repair" and "fix" in fix_action:
        confidence = min(1.0, confidence + 0.05)

    return {"agent": agent, "confidence": round(confidence, 3), "can_fix": confidence > 0.4}


async def _execute_fix(tenant_id: str, issue: Dict, assigned_agent: str) -> Dict:
    """Execute an auto-fix for a detected issue. Always backs up before changing."""
    db = _get_db()
    if db is None:
        return {"fixed": False, "reason": "no_db"}

    fix_action = issue.get("fix_action", "")
    records_fixed = 0
    backup_id = f"bkp_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc)

    try:
        # ═══ SAFETY: Backup affected records before ANY change ═══
        backup_doc = {
            "backup_id": backup_id,
            "tenant_id": tenant_id,
            "fix_action": fix_action,
            "issue_type": issue.get("type", ""),
            "agent": assigned_agent,
            "confidence": issue.get("fix_confidence", 0),
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
            "rolled_back": False,
            "records": [],
        }

        if fix_action == "reset_stuck_jobs":
            # Backup stuck jobs before reset
            stuck_filter = {"tenant_id": tenant_id, "status": "rendering",
                            "started_at": {"$lt": (now - timedelta(hours=1)).isoformat()}}
            backup_doc["records"] = await db.video_queue.find(stuck_filter, {"_id": 0}).to_list(100)
            backup_doc["collection"] = "video_queue"
            backup_doc["restore_field"] = "status"
            result = await db.video_queue.update_many(stuck_filter,
                {"$set": {"status": "queued", "worker_id": None, "started_at": None}})
            records_fixed = result.modified_count

        elif fix_action == "requeue_failed_videos":
            failed_filter = {"tenant_id": tenant_id, "status": "failed"}
            backup_doc["records"] = await db.video_queue.find(failed_filter, {"_id": 0}).to_list(100)
            backup_doc["collection"] = "video_queue"
            backup_doc["restore_field"] = "status"
            result = await db.video_queue.update_many(failed_filter,
                {"$set": {"status": "queued", "error": None, "worker_id": None}})
            records_fixed = result.modified_count

        elif fix_action == "retry_failed_outreach":
            failed_filter = {"tenant_id": tenant_id, "status": "failed"}
            backup_doc["records"] = await db.forensic_miner_outreach_queue.find(failed_filter, {"_id": 0}).to_list(100)
            backup_doc["collection"] = "forensic_miner_outreach_queue"
            backup_doc["restore_field"] = "status"
            result = await db.forensic_miner_outreach_queue.update_many(failed_filter,
                {"$set": {"status": "queued", "retry_count": 1}})
            records_fixed = result.modified_count

        elif fix_action == "remove_plaintext_passwords":
            pw_filter = {"tenant_id": tenant_id, "password": {"$exists": True}}
            backup_doc["records"] = await db.customers.find(pw_filter, {"_id": 0}).to_list(100)
            backup_doc["collection"] = "customers"
            backup_doc["restore_field"] = "password"
            result = await db.customers.update_many(pw_filter, {"$unset": {"password": ""}})
            records_fixed = result.modified_count

        elif fix_action == "refresh_stale_records":
            stale_filter = {"tenant_id": tenant_id,
                            "updated_at": {"$lt": (now - timedelta(days=30)).isoformat()}}
            backup_doc["records"] = await db.customers.find(stale_filter, {"_id": 0}).to_list(100)
            backup_doc["collection"] = "customers"
            backup_doc["restore_field"] = "updated_at"
            result = await db.customers.update_many(stale_filter,
                {"$set": {"updated_at": now.isoformat(), "needs_refresh": True}})
            records_fixed = result.modified_count

        else:
            return {"fixed": False, "reason": "needs_human_review", "fix_action": fix_action}

        # Save backup (only if records were actually changed)
        if records_fixed > 0:
            backup_doc["records_count"] = records_fixed
            await db.audit_backups.insert_one(backup_doc)

        return {"fixed": True, "records_fixed": records_fixed, "fix_action": fix_action,
                "agent": assigned_agent, "backup_id": backup_id}

    except Exception as e:
        logger.warning(f"[AUTONOMY] Fix failed: {fix_action} — {e}")
        return {"fixed": False, "reason": str(e), "fix_action": fix_action}


# ═══════════════════════════════════════════════════════════════
# FULL AUDIT ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

async def run_full_audit(tenant_id: str, auto_fix: bool = True) -> Dict:
    """
    Run all 5 agents simultaneously → consolidate → bid → fix.
    Returns full audit report with actions taken.
    """
    db = _get_db()
    audit_id = f"audit_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc)

    # Check survival tier
    tier = await get_survival_tier(tenant_id)
    if tier["tier"] == "death":
        return {"audit_id": audit_id, "status": "blocked", "reason": "Subscription cancelled (Death tier)", "tier": tier}

    # Phase 1: All agents scan in parallel
    scan_results = await asyncio.gather(
        _scout_scan(tenant_id),
        _shannon_scan(tenant_id),
        _architect_scan(tenant_id),
        _hermes_scan(tenant_id),
        _repair_scan(tenant_id),
        return_exceptions=True,
    )

    # Consolidate findings
    all_issues = []
    all_suggestions = []
    agent_reports = []
    for result in scan_results:
        if isinstance(result, Exception):
            agent_reports.append({"agent": "unknown", "error": str(result), "issues_found": []})
            continue
        agent_reports.append(result)
        all_issues.extend(result.get("issues_found", []))
        all_suggestions.extend(result.get("suggestions", []))

    # Phase 2: A2A Bidding — each issue gets bids from all agents
    assignments = []
    for issue in all_issues:
        bids = []
        for agent_name in ["scout", "shannon", "architect", "hermes", "repair"]:
            bid = _agent_bid(agent_name, issue)
            if bid["can_fix"]:
                bids.append(bid)
        bids.sort(key=lambda b: b["confidence"], reverse=True)
        winner = bids[0] if bids else None
        assignments.append({
            "issue": issue,
            "bids": bids[:3],
            "assigned_to": winner["agent"] if winner else None,
            "confidence": winner["confidence"] if winner else 0,
        })

    # Phase 3: Execute fixes (if auto_fix enabled and survival tier allows)
    fixes_applied = []
    fixes_skipped = []
    needs_review = []
    fix_count = 0

    # Get plan-based fix limit
    usage = await get_monthly_fix_usage(tenant_id)
    plan_limit = usage.get("limit", 50)
    already_used = usage.get("used", 0)
    over_limit = usage.get("over_limit", False)

    if auto_fix and tier["tier"] != "survival" and not over_limit:
        for assignment in assignments:
            if not assignment["assigned_to"]:
                needs_review.append(assignment["issue"])
                continue
            # Check plan limit (per-month)
            if plan_limit != -1 and (already_used + fix_count) >= plan_limit:
                fixes_skipped.append({"issue": assignment["issue"], "reason": "monthly_fix_limit_reached"})
                continue
            if assignment["confidence"] < 0.5:
                needs_review.append(assignment["issue"])
                continue

            fix_result = await _execute_fix(tenant_id, assignment["issue"], assignment["assigned_to"])
            if fix_result.get("fixed"):
                fixes_applied.append({**fix_result, "issue_type": assignment["issue"]["type"],
                                       "severity": assignment["issue"]["severity"]})
                fix_count += 1
            elif fix_result.get("reason") == "needs_human_review":
                needs_review.append(assignment["issue"])
            else:
                fixes_skipped.append({"issue": assignment["issue"], "reason": fix_result.get("reason", "unknown")})

        # Track usage
        if fix_count > 0:
            await _increment_fix_usage(tenant_id, fix_count)

        # Check if now over limit → send upgrade prompt
        if plan_limit != -1 and (already_used + fix_count) >= plan_limit:
            new_usage = await get_monthly_fix_usage(tenant_id)
            await _send_upgrade_prompt(tenant_id, new_usage)
    elif over_limit:
        needs_review = [a["issue"] for a in assignments]
        fixes_skipped.append({"reason": f"Monthly fix limit reached ({already_used}/{plan_limit}). Upgrade plan for more."})
    else:
        needs_review = [a["issue"] for a in assignments]

    # Phase 4: Build report
    total_scan_ms = sum(r.get("scan_time_ms", 0) for r in agent_reports if isinstance(r, dict))
    report = {
        "audit_id": audit_id,
        "tenant_id": tenant_id,
        "status": "completed",
        "tier": tier,
        "usage": {"plan": usage.get("plan"), "fixes_used": already_used + fix_count,
                  "fix_limit": plan_limit, "remaining": max(0, plan_limit - already_used - fix_count) if plan_limit != -1 else -1},
        "timestamp": now.isoformat(),
        "scan_duration_ms": total_scan_ms,
        "agents_scanned": len(agent_reports),
        "total_issues": len(all_issues),
        "auto_fixed": len(fixes_applied),
        "needs_review": len(needs_review),
        "skipped": len(fixes_skipped),
        "agent_reports": agent_reports,
        "fixes_applied": fixes_applied,
        "needs_human_review": [{"type": i["type"], "severity": i["severity"], "description": i["description"],
                                "fix_action": i.get("fix_action", ""), "affected_records": i.get("affected_records", 0)} for i in needs_review],
        "suggestions": list(set(all_suggestions)),
        "assignments": [{"issue_type": a["issue"]["type"], "assigned_to": a["assigned_to"],
                          "confidence": a["confidence"]} for a in assignments],
    }

    # Save to DB
    if db is not None:
        await db.autonomy_audits.insert_one({k: v for k, v in report.items()})
        # Update agent performance stats
        for fix in fixes_applied:
            await db.autonomy_agent_stats.update_one(
                {"agent": fix["agent"], "tenant_id": tenant_id},
                {"$inc": {"problems_solved": 1, "records_fixed": fix.get("records_fixed", 0)},
                 "$set": {"last_active": now.isoformat()}},
                upsert=True,
            )

    return report


async def get_audit_history(tenant_id: str = None, limit: int = 10) -> List[Dict]:
    db = _get_db()
    if db is None:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    cursor = db.autonomy_audits.find(q, {"_id": 0, "agent_reports": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(limit)


async def get_agent_stats(tenant_id: str = None) -> List[Dict]:
    db = _get_db()
    if db is None:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    cursor = db.autonomy_agent_stats.find(q, {"_id": 0})
    return await cursor.to_list(20)


async def get_problem_queue(tenant_id: str = None) -> List[Dict]:
    """Get unresolved problems needing human review."""
    db = _get_db()
    if db is None:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    latest = await db.autonomy_audits.find_one(q, {"_id": 0, "needs_human_review": 1}, sort=[("timestamp", -1)])
    return latest.get("needs_human_review", []) if latest else []


# ═══════════════════════════════════════════════════════════════
# ITEM 1: NIGHTLY 2 AM AUTO-AUDIT CRON + MONITORING
# ═══════════════════════════════════════════════════════════════

_audit_schedule = {"enabled": True, "frequency": "daily", "hour": 2, "minute": 0}
_cron_state = {"status": "idle", "started_at": None, "next_run": None, "pid": None}


def _calc_next_run(now: datetime = None) -> datetime:
    """Calculate the next scheduled run time."""
    now = now or datetime.now(timezone.utc)
    target_hour = _audit_schedule.get("hour", 2)
    target_min = _audit_schedule.get("minute", 0)
    next_run = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    if _audit_schedule.get("frequency") == "weekly":
        days_ahead = 7 - (next_run.weekday() - 0) % 7
        if days_ahead == 0 and next_run <= now:
            days_ahead = 7
        next_run = now.replace(hour=target_hour, minute=target_min, second=0) + timedelta(days=days_ahead)
    return next_run


async def _persist_cron_state(db, state_update: Dict):
    """Write cron state to MongoDB for monitoring."""
    if db is None:
        return
    try:
        await db.aurem_cron_state.update_one(
            {"cron_id": "autonomy_nightly"},
            {"$set": {**state_update, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[AUTONOMY] Cron state persist failed: {e}")


async def _log_cron_execution(db, run_record: Dict):
    """Append a cron execution record for history tracking."""
    if db is None:
        return
    try:
        await db.aurem_cron_runs.insert_one({**run_record})
    except Exception as e:
        logger.debug(f"[AUTONOMY] Cron run log failed: {e}")


async def autonomy_cron_scheduler():
    """Background scheduler: runs self-audit at configured time (default 2 AM UTC)."""
    global _cron_state
    logger.info("[AUTONOMY] Nightly audit scheduler started")
    _cron_state["started_at"] = datetime.now(timezone.utc).isoformat()
    _cron_state["status"] = "waiting"

    db = _get_db()
    await _persist_cron_state(db, {
        "status": "waiting", "started_at": _cron_state["started_at"],
        "schedule": _audit_schedule,
    })

    while True:
        try:
            now = datetime.now(timezone.utc)
            next_run = _calc_next_run(now)
            _cron_state["next_run"] = next_run.isoformat()
            _cron_state["status"] = "waiting"
            wait_seconds = (next_run - now).total_seconds()

            db = _get_db()
            await _persist_cron_state(db, {
                "status": "waiting", "next_run": next_run.isoformat(),
                "schedule": _audit_schedule,
            })

            logger.info(f"[AUTONOMY] Next audit in {wait_seconds/3600:.1f}h at {next_run.isoformat()}")
            await asyncio.sleep(wait_seconds)

            if not _audit_schedule.get("enabled", True):
                _cron_state["status"] = "disabled"
                await _persist_cron_state(db, {"status": "disabled"})
                continue

            # ── Execute audit ──
            _cron_state["status"] = "running"
            run_start = datetime.now(timezone.utc)
            db = _get_db()
            await _persist_cron_state(db, {"status": "running", "last_run_started": run_start.isoformat()})

            tenants_audited = 0
            total_issues = 0
            total_fixed = 0
            errors = []

            if db is not None:
                tenants = await db.workspaces.distinct("tenant_id")
                for tid in (tenants or ["aurem_platform"]):
                    try:
                        report = await run_full_audit(tid, auto_fix=True)
                        tenants_audited += 1
                        total_issues += report.get("total_issues", 0)
                        total_fixed += report.get("auto_fixed", 0)
                        logger.info(f"[AUTONOMY] Nightly audit {tid}: {report.get('total_issues',0)} issues, {report.get('auto_fixed',0)} fixed")
                        if report.get("needs_review", 0) > 0:
                            await _send_audit_notification(tid, report)
                    except Exception as e:
                        errors.append({"tenant": tid, "error": str(e)})
                        logger.warning(f"[AUTONOMY] Nightly audit failed for {tid}: {e}")

            run_end = datetime.now(timezone.utc)
            duration_ms = int((run_end - run_start).total_seconds() * 1000)

            run_record = {
                "cron_id": "autonomy_nightly",
                "status": "error" if errors and not tenants_audited else "success",
                "started_at": run_start.isoformat(),
                "finished_at": run_end.isoformat(),
                "duration_ms": duration_ms,
                "tenants_audited": tenants_audited,
                "total_issues": total_issues,
                "total_fixed": total_fixed,
                "errors": errors,
            }
            await _log_cron_execution(db, run_record)
            await _persist_cron_state(db, {
                "status": "waiting",
                "last_run": run_record,
                "next_run": _calc_next_run(run_end).isoformat(),
            })
            _cron_state["status"] = "waiting"

        except asyncio.CancelledError:
            _cron_state["status"] = "stopped"
            break
        except Exception as e:
            logger.warning(f"[AUTONOMY] Scheduler error: {e}")
            _cron_state["status"] = "error"
            db = _get_db()
            await _persist_cron_state(db, {"status": "error", "last_error": str(e), "last_error_at": datetime.now(timezone.utc).isoformat()})
            await asyncio.sleep(3600)


async def get_cron_status() -> Dict:
    """Get full cron monitoring status (in-memory + persistent)."""
    db = _get_db()
    result = {
        "schedule": _audit_schedule,
        "in_memory": {**_cron_state},
    }
    if db is not None:
        state = await db.aurem_cron_state.find_one({"cron_id": "autonomy_nightly"}, {"_id": 0})
        result["persistent"] = state or {}
        # Last 5 runs
        runs = await db.aurem_cron_runs.find(
            {"cron_id": "autonomy_nightly"}, {"_id": 0}
        ).sort("started_at", -1).limit(5).to_list(5)
        result["recent_runs"] = runs
    else:
        result["persistent"] = {}
        result["recent_runs"] = []
    return result


def set_audit_schedule(frequency: str = "daily", hour: int = 2, minute: int = 0, enabled: bool = True) -> Dict:
    """Update the auto-audit schedule."""
    global _audit_schedule
    if frequency not in ("daily", "weekly", "disabled"):
        return {"error": "frequency must be daily, weekly, or disabled"}
    _audit_schedule = {"enabled": enabled and frequency != "disabled", "frequency": frequency, "hour": hour, "minute": minute}
    return {"schedule": _audit_schedule, "updated": True}


def get_audit_schedule() -> Dict:
    return {"schedule": _audit_schedule}


# ═══════════════════════════════════════════════════════════════
# ITEM 2: WHATSAPP NOTIFICATION FOR NEEDS_REVIEW
# ═══════════════════════════════════════════════════════════════

ADMIN_PHONE = "+16134000000"


async def _send_audit_notification(tenant_id: str, report: Dict):
    """Send WhatsApp notification when audit finds items needing human review."""
    try:
        from services.whapi_service import send_whatsapp_message
        fixed = report.get("auto_fixed", 0)
        review = report.get("needs_review", 0)
        total = report.get("total_issues", 0)
        msg = (
            f"AUREM Autonomous Audit Complete\n\n"
            f"Issues found: {total}\n"
            f"Auto-fixed: {fixed}\n"
            f"Needs your approval: {review}\n\n"
            f"Review at: aurem.live/autonomy\n"
            f"Audit ID: {report.get('audit_id', '?')}"
        )
        await send_whatsapp_message(ADMIN_PHONE, msg)
        logger.info(f"[AUTONOMY] WhatsApp notification sent to {ADMIN_PHONE}")
    except Exception as e:
        logger.debug(f"[AUTONOMY] WhatsApp notification failed (non-blocking): {e}")


# ═══════════════════════════════════════════════════════════════
# ITEM 3: APPROVE / REJECT SUGGESTED FIX
# ═══════════════════════════════════════════════════════════════

async def approve_fix(audit_id: str, issue_type: str, action: str = "approve", tenant_id: str = None) -> Dict:
    """Approve or reject a suggested fix from the needs_review queue."""
    db = _get_db()
    if db is None:
        return {"approved": False, "reason": "no_db"}

    audit = await db.autonomy_audits.find_one({"audit_id": audit_id})
    if not audit:
        return {"approved": False, "reason": "audit_not_found"}
    audit.pop("_id", None)

    # Find the issue in needs_human_review
    target = None
    for item in audit.get("needs_human_review", []):
        if item.get("type") == issue_type:
            target = item
            break
    if not target:
        return {"approved": False, "reason": f"issue_type '{issue_type}' not found in review queue"}

    if action == "reject":
        await db.autonomy_audits.update_one(
            {"audit_id": audit_id},
            {"$pull": {"needs_human_review": {"type": issue_type}},
             "$push": {"rejected_fixes": {"type": issue_type, "rejected_at": datetime.now(timezone.utc).isoformat()}}},
        )
        return {"approved": False, "action": "rejected", "issue_type": issue_type}

    # Execute the fix
    fix_result = await _execute_fix(tenant_id or audit.get("tenant_id", "aurem_platform"), target, "repair")

    # Update audit record
    await db.autonomy_audits.update_one(
        {"audit_id": audit_id},
        {"$pull": {"needs_human_review": {"type": issue_type}},
         "$push": {"fixes_applied": {**fix_result, "issue_type": issue_type, "approved_by": "admin", "approved_at": datetime.now(timezone.utc).isoformat()}},
         "$inc": {"auto_fixed": 1, "needs_review": -1}},
    )
    return {"approved": True, "fix_result": fix_result, "issue_type": issue_type}


# ═══════════════════════════════════════════════════════════════
# ITEM 5: DATA REPLACEMENT VIA FREE APIs
# ═══════════════════════════════════════════════════════════════

async def verify_and_replace_data(tenant_id: str, record_id: str, field: str, current_value: str) -> Dict:
    """
    Verify data against trusted free APIs. Replace only if confidence > 0.85.
    Always logs old value before replacing.
    """
    db = _get_db()
    if db is None:
        return {"replaced": False, "reason": "no_db"}

    result = {"field": field, "old_value": current_value, "replaced": False}

    try:
        if field == "email":
            from services.free_api_arsenal import verify_email_tomba
            verification = await verify_email_tomba(current_value)
            if verification.get("error"):
                result["reason"] = f"tomba: {verification['error']}"
                return result
            status = verification.get("status", "")
            confidence = 0.95 if status == "valid" else 0.50 if status == "accept_all" else 0.20
            result["verification"] = {"source": "tomba", "status": status, "confidence": confidence}
            if status == "invalid" and confidence > 0.85:
                # Email is confirmed invalid — flag it
                await db.customers.update_one(
                    {"_id": record_id, "tenant_id": tenant_id},
                    {"$set": {"email_status": "invalid", "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                result["action"] = "flagged_invalid"

        elif field == "phone":
            from services.free_api_arsenal import validate_phone
            verification = await validate_phone(current_value)
            if verification.get("error"):
                result["reason"] = f"numverify: {verification['error']}"
                return result
            is_valid = verification.get("valid", False)
            confidence = 0.90 if is_valid else 0.10
            result["verification"] = {
                "source": "numverify", "valid": is_valid, "confidence": confidence,
                "carrier": verification.get("carrier", ""), "line_type": verification.get("line_type", ""),
            }
            if not is_valid:
                await db.customers.update_one(
                    {"_id": record_id, "tenant_id": tenant_id},
                    {"$set": {"phone_status": "invalid", "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                result["action"] = "flagged_invalid"

        elif field == "location":
            from services.free_api_arsenal import geolocate_ip
            ip = current_value
            geo = await geolocate_ip(ip)
            if geo.get("error"):
                result["reason"] = f"ipstack: {geo['error']}"
                return result
            new_location = {
                "country": geo.get("country", ""),
                "region": geo.get("region", ""),
                "city": geo.get("city", ""),
                "latitude": geo.get("latitude"),
                "longitude": geo.get("longitude"),
            }
            confidence = 0.90 if new_location["city"] else 0.60
            result["verification"] = {"source": "ipstack", "confidence": confidence, "location": new_location}
            if confidence > 0.85:
                await db.customers.update_one(
                    {"_id": record_id, "tenant_id": tenant_id},
                    {"$set": {"geo_location": new_location, "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                result["replaced"] = True
                result["new_value"] = new_location
        else:
            result["reason"] = f"unsupported field: {field}"
            return result

        # Log the verification attempt
        if db is not None:
            await db.autonomy_data_replacements.insert_one({
                "tenant_id": tenant_id, "record_id": str(record_id), "field": field,
                "old_value": current_value, "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    except Exception as e:
        result["reason"] = str(e)
        logger.warning(f"[AUTONOMY] Data replacement failed: {field}={current_value}: {e}")

    return result


# ═══════════════════════════════════════════════════════════════
# SAFETY LAYER: ROLLBACK + BACKUP MANAGEMENT
# ═══════════════════════════════════════════════════════════════

async def rollback_fix(backup_id: str, tenant_id: str = None) -> Dict:
    """
    Rollback an auto-fix using its backup.
    Restores original record state from audit_backups collection.
    Available for 7 days after fix.
    """
    db = _get_db()
    if db is None:
        return {"rolled_back": False, "reason": "no_db"}

    backup = await db.audit_backups.find_one({"backup_id": backup_id})
    if not backup:
        return {"rolled_back": False, "reason": "backup_not_found"}
    backup.pop("_id", None)

    if backup.get("rolled_back"):
        return {"rolled_back": False, "reason": "already_rolled_back"}

    # Check 7-day window
    expires = backup.get("expires_at", "")
    if expires:
        try:
            exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_dt:
                return {"rolled_back": False, "reason": "rollback_expired", "expired_at": expires}
        except Exception:
            pass

    collection_name = backup.get("collection", "")
    records = backup.get("records", [])
    if not collection_name or not records:
        return {"rolled_back": False, "reason": "no_records_to_restore"}

    collection = db[collection_name]
    restored = 0

    for record in records:
        # Find the record by its unique identifier
        match_key = "job_id" if "job_id" in record else "domain" if "domain" in record else "email"
        match_val = record.get(match_key)
        if not match_val:
            continue

        # Restore original values
        restore_fields = {}
        restore_field = backup.get("restore_field", "")
        if restore_field and restore_field in record:
            restore_fields[restore_field] = record[restore_field]
        else:
            # Restore all non-system fields
            for k, v in record.items():
                if k not in ("_id", "tenant_id"):
                    restore_fields[k] = v

        if restore_fields:
            await collection.update_one({match_key: match_val, "tenant_id": backup.get("tenant_id")},
                                         {"$set": restore_fields})
            restored += 1

    # Mark backup as rolled back
    await db.audit_backups.update_one(
        {"backup_id": backup_id},
        {"$set": {"rolled_back": True, "rolled_back_at": datetime.now(timezone.utc).isoformat(),
                  "records_restored": restored}},
    )

    logger.info(f"[AUTONOMY] Rollback {backup_id}: restored {restored}/{len(records)} records in {collection_name}")
    return {"rolled_back": True, "backup_id": backup_id, "records_restored": restored,
            "collection": collection_name, "fix_action": backup.get("fix_action", "")}


async def get_backups(tenant_id: str = None, limit: int = 20) -> List[Dict]:
    """List available backups (undoable fixes) for a tenant."""
    db = _get_db()
    if db is None:
        return []
    q = {}
    if tenant_id:
        q["tenant_id"] = tenant_id
    cursor = db.audit_backups.find(q, {"_id": 0, "records": 0}).sort("created_at", -1).limit(limit)
    backups = await cursor.to_list(limit)
    now = datetime.now(timezone.utc)
    for b in backups:
        expires = b.get("expires_at", "")
        if expires:
            try:
                exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                b["can_undo"] = not b.get("rolled_back", False) and now < exp_dt
                b["days_remaining"] = max(0, (exp_dt - now).days)
            except Exception:
                b["can_undo"] = False
        else:
            b["can_undo"] = False
    return backups
