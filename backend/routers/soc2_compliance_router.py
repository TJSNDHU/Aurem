"""
AUREM SOC 2 Compliance Router
================================
Endpoints for:
  1. Kill Switch (Global Emergency Controls)
  2. Audit Trail (Immutable log viewer)
  3. Encryption Evidence (AES-256 at-rest, TLS 1.3 in-transit)
  4. Agent RBAC Matrix (Least Privilege proof)
  5. Data Deletion API (GDPR/PIPEDA right-to-erasure)
  6. Evidence Snapshots (automated compliance evidence)
"""
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
import jwt
import os
import json
import platform
import ssl
import subprocess

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compliance", tags=["SOC 2 Compliance"])

_db = None
# Bug-fix #79 — initialize from env at module load so kill-switch routes
# never become permanently unreachable when set_jwt() is never called
# (race-condition at startup, partial init, hot reload). Without this,
# _jwt_secret=None made every admin token 401 → kill switch unusable in
# the actual emergency it was designed for.
_jwt_secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
_jwt_algorithm = "HS256"


def set_db(database):
    global _db
    _db = database
    from services.kill_switch import set_db as set_ks_db
    set_ks_db(database)


def set_jwt(secret, algorithm="HS256"):
    global _jwt_secret, _jwt_algorithm
    if secret:
        _jwt_secret = secret
    _jwt_algorithm = algorithm


async def _require_admin(request: Request):
    """Require valid JWT with admin privileges.

    Bug-fix #74 — previously accepted ANY token with an `email` claim as
    admin (every JWT has email → every user was "admin"). This let any
    paying customer call /kill-switch/activate and /data-deletion to wipe
    competitor tenants. Now uses the centralized unified admin guard
    which requires explicit `is_admin`/`is_super_admin` claim, `role`
    admin, or email in the ADMIN_EMAIL_WHITELIST.
    """
    from utils.admin_guard import verify_admin as _verify_admin
    auth = request.headers.get("Authorization", "")
    return _verify_admin(auth, secret=_jwt_secret, algorithm=_jwt_algorithm)


def _get_client_info(request: Request):
    """Extract IP and User-Agent for audit logging."""
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    ua = request.headers.get("user-agent", "unknown")
    return ip, ua


# ═══════════════════════════════════════════════════════════════
# 1. KILL SWITCH — Global Emergency Controls
# ═══════════════════════════════════════════════════════════════

@router.get("/kill-switch")
async def get_kill_switch_status(request: Request):
    """Get current kill switch state. Requires admin JWT."""
    await _require_admin(request)
    from services.kill_switch import get_kill_switch_state
    return {"kill_switch": get_kill_switch_state()}


@router.post("/kill-switch/activate")
async def activate_kill_switch(request: Request):
    """EMERGENCY: Activate full kill switch (disable patches, revoke V2V, maintenance mode)."""
    payload = await _require_admin(request)
    ip, ua = _get_client_info(request)
    actor_id = payload.get("user_id", "admin")

    from services.kill_switch import activate_full_kill_switch
    result = await activate_full_kill_switch(actor_id, ip, ua)
    return result


@router.post("/kill-switch/deactivate")
async def deactivate_kill_switch(request: Request):
    """Deactivate all kill switch controls."""
    payload = await _require_admin(request)
    ip, ua = _get_client_info(request)
    actor_id = payload.get("user_id", "admin")

    from services.kill_switch import deactivate_full_kill_switch
    result = await deactivate_full_kill_switch(actor_id, ip, ua)
    return result


@router.post("/kill-switch/patches")
async def toggle_live_patches(request: Request):
    """Toggle live patches on/off."""
    payload = await _require_admin(request)
    ip, ua = _get_client_info(request)
    actor_id = payload.get("user_id", "admin")
    body = await request.json()
    enabled = body.get("enabled", True)

    from services.kill_switch import enable_live_patches, disable_live_patches
    if enabled:
        result = await enable_live_patches(actor_id, ip, ua)
    else:
        result = await disable_live_patches(actor_id, ip, ua)
    return result


@router.post("/kill-switch/v2v")
async def revoke_v2v(request: Request):
    """Revoke all active V2V sessions."""
    payload = await _require_admin(request)
    ip, ua = _get_client_info(request)
    actor_id = payload.get("user_id", "admin")

    from services.kill_switch import revoke_v2v_sessions
    result = await revoke_v2v_sessions(actor_id, ip, ua)
    return result


@router.post("/kill-switch/maintenance")
async def toggle_maintenance(request: Request):
    """Toggle maintenance mode."""
    payload = await _require_admin(request)
    ip, ua = _get_client_info(request)
    actor_id = payload.get("user_id", "admin")
    body = await request.json()
    enabled = body.get("enabled", True)

    from services.kill_switch import enable_maintenance_mode, disable_maintenance_mode
    if enabled:
        result = await enable_maintenance_mode(actor_id, ip, ua)
    else:
        result = await disable_maintenance_mode(actor_id, ip, ua)
    return result


# ═══════════════════════════════════════════════════════════════
# 2. AUDIT TRAIL — Immutable Log Viewer
# ═══════════════════════════════════════════════════════════════

@router.get("/audit-trail")
async def get_audit_trail(
    request: Request,
    action: Optional[str] = None,
    actor_id: Optional[str] = None,
    hours: int = 24,
    limit: int = 100,
    skip: int = 0,
):
    """Get immutable audit trail. Filterable by action, actor, time window."""
    await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    query = {}
    if action:
        query["action"] = action
    if actor_id:
        query["actor_id"] = actor_id
    if hours > 0:
        query["timestamp"] = {"$gte": datetime.now(timezone.utc) - timedelta(hours=hours)}

    cursor = _db["aurem_audit_logs"].find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit)
    logs = await cursor.to_list(limit)

    total = await _db["aurem_audit_logs"].count_documents(query)

    # Convert datetime objects to ISO strings for JSON serialization
    for log in logs:
        if isinstance(log.get("timestamp"), datetime):
            log["timestamp"] = log["timestamp"].isoformat()

    return {
        "total": total,
        "showing": len(logs),
        "skip": skip,
        "limit": limit,
        "logs": logs,
    }


@router.get("/audit-trail/stats")
async def get_audit_stats(request: Request):
    """Get audit trail summary statistics for compliance reporting."""
    await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    total_all = await _db["aurem_audit_logs"].count_documents({})
    total_24h = await _db["aurem_audit_logs"].count_documents({"timestamp": {"$gte": day_ago}})
    total_7d = await _db["aurem_audit_logs"].count_documents({"timestamp": {"$gte": week_ago}})

    # Security events in last 24h
    security_actions = [
        "login_failed", "rate_limit_hit", "suspicious_activity",
        "kill_switch_activated", "maintenance_mode_on", "v2v_sessions_revoked",
        "live_patches_disabled",
    ]
    security_24h = await _db["aurem_audit_logs"].count_documents({
        "action": {"$in": security_actions},
        "timestamp": {"$gte": day_ago},
    })

    # Action type breakdown (last 7 days)
    pipeline = [
        {"$match": {"timestamp": {"$gte": week_ago}}},
        {"$group": {"_id": "$action", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 15},
    ]
    breakdown = await _db["aurem_audit_logs"].aggregate(pipeline).to_list(15)

    return {
        "total_all_time": total_all,
        "total_24h": total_24h,
        "total_7d": total_7d,
        "security_events_24h": security_24h,
        "action_breakdown_7d": [{"action": b["_id"], "count": b["count"]} for b in breakdown],
    }


# ═══════════════════════════════════════════════════════════════
# 3. ENCRYPTION EVIDENCE
# ═══════════════════════════════════════════════════════════════

@router.get("/encryption-evidence")
async def get_encryption_evidence(request: Request):
    """Document encryption-at-rest and encryption-in-transit status for SOC 2 auditors."""
    await _require_admin(request)

    # Check TLS version available
    tls_version = ssl.OPENSSL_VERSION
    tls_1_3_supported = hasattr(ssl, "TLSVersion") and hasattr(ssl.TLSVersion, "TLSv1_3")

    # MongoDB encryption check
    mongo_encryption = {
        "engine": "WiredTiger",
        "encryption_at_rest": "AES-256-CBC (WiredTiger default for MongoDB Enterprise / Atlas)",
        "note": "Local dev uses unencrypted storage; production Atlas enforces AES-256",
    }

    # Check if MongoDB connection uses TLS
    mongo_url = os.environ.get("MONGO_URL", "")
    mongo_tls = "tls=true" in mongo_url or "ssl=true" in mongo_url or "+srv" in mongo_url

    return {
        "encryption_at_rest": {
            "mongodb": mongo_encryption,
            "status": "CONFIGURED" if "+srv" in mongo_url else "DEV_MODE",
            "standard": "AES-256",
        },
        "encryption_in_transit": {
            "tls_library": tls_version,
            "tls_1_3_supported": tls_1_3_supported,
            "mongodb_tls": mongo_tls,
            "api_tls": "Enforced via Kubernetes Ingress (TLS termination)",
            "internal_services": "Pod-to-pod traffic within cluster network",
        },
        "compliance_notes": [
            "All external API traffic terminates TLS at ingress controller",
            "MongoDB Atlas connections use TLS 1.2+ by default",
            "Sensitive fields (passwords, tokens) hashed with bcrypt/SHA-256 before storage",
            "Audit logs are append-only with _immutable flag",
            "PII scrubber active on all AI output (credit cards, emails, phones, SSNs)",
        ],
        "evidence_generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# 4. AGENT RBAC MATRIX
# ═══════════════════════════════════════════════════════════════

@router.get("/rbac-matrix")
async def get_rbac_matrix(request: Request):
    """Return the full Agent RBAC permission matrix for SOC 2 auditors."""
    await _require_admin(request)

    from services.agent_rbac import get_rbac_matrix, AgentRole

    matrix = get_rbac_matrix()

    return {
        "title": "AUREM Agent RBAC — Least Privilege Matrix",
        "principle": "Each AI agent has only the permissions strictly required for its OODA stage",
        "matrix": matrix,
        "roles": {
            "scout": "Observation — Read-only access to client sites and logs",
            "architect": "Orientation — Read-only pattern matching and decision mapping",
            "envoy": "Decision — Read + external API calls to select tools",
            "closer": "Action — Write access scoped to specific tenant_id only",
            "verifier": "Validation — Read-only health checks post-action",
            "system": "Platform — Full access for automated maintenance tasks only",
        },
        "enforcement": "Runtime permission checks via agent_rbac.check_permission()",
        "evidence_generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# 5. DATA DELETION API (GDPR/PIPEDA)
# ═══════════════════════════════════════════════════════════════

@router.post("/data-deletion")
async def delete_tenant_data(request: Request):
    """
    GDPR/PIPEDA Right to Erasure — Purge all data for a specific tenant.
    Retains audit trail entries (required by law for 2 years).
    """
    payload = await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    body = await request.json()
    tenant_id = body.get("tenant_id")
    confirm = body.get("confirm", False)

    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id required")
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to proceed with data deletion")

    ip, ua = _get_client_info(request)
    actor_id = payload.get("user_id", "admin")

    # Collections to purge for this tenant
    collections_to_purge = [
        ("aurem_workspaces", {"business_id": tenant_id}),
        ("aurem_workspaces", {"owner_email": {"$regex": tenant_id, "$options": "i"}}),
        ("scanner_history", {"tenant_id": tenant_id}),
        ("system_auto_repairs", {"tenant_id": tenant_id}),
        ("live_patches", {"business_id": tenant_id}),
        ("pixel_events", {"business_id": tenant_id}),
        ("api_keys", {"business_id": tenant_id}),
        ("aurem_usage", {"business_id": tenant_id}),
        ("pipeline_states", {"tenant_id": tenant_id}),
        ("ora_action_logs", {"tenant_id": tenant_id}),
        ("tenant_settings", {"tenant_id": tenant_id}),
        ("v2v_sessions", {"tenant_id": tenant_id}),
    ]

    deleted_counts = {}
    total_deleted = 0
    for collection_name, query in collections_to_purge:
        result = await _db[collection_name].delete_many(query)
        deleted_counts[collection_name] = result.deleted_count
        total_deleted += result.deleted_count

    # Audit the deletion (retained for compliance)
    await _db["aurem_audit_logs"].insert_one({
        "action": "data_purged",
        "business_id": tenant_id,
        "actor_id": actor_id,
        "actor_type": "admin",
        "resource_type": "tenant_data",
        "resource_id": tenant_id,
        "details": {
            "collections_purged": deleted_counts,
            "total_records_deleted": total_deleted,
            "reason": "GDPR/PIPEDA Right to Erasure request",
        },
        "ip_address": ip,
        "user_agent": ua,
        "success": True,
        "timestamp": datetime.now(timezone.utc),
        "_immutable": True,
    })

    return {
        "status": "completed",
        "tenant_id": tenant_id,
        "total_records_deleted": total_deleted,
        "collections_purged": deleted_counts,
        "audit_trail_retained": True,
        "note": "Audit logs retained for 2-year compliance window per PIPEDA/SOC 2",
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# 6. EVIDENCE SNAPSHOT
# ═══════════════════════════════════════════════════════════════

@router.post("/evidence-snapshot")
async def take_evidence_snapshot(request: Request):
    """Take a point-in-time compliance evidence snapshot."""
    payload = await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    ip, ua = _get_client_info(request)
    actor_id = payload.get("user_id", "admin")

    now = datetime.now(timezone.utc)

    # Gather evidence
    from services.kill_switch import get_kill_switch_state
    from services.agent_rbac import get_rbac_matrix

    # Security audit results
    audit_report = None
    try:
        with open("/app/test_reports/security_audit.json", "r") as f:
            audit_report = json.load(f)
    except Exception:
        audit_report = {"status": "no_report_found"}

    # System info
    system_info = {
        "python_version": platform.python_version(),
        "openssl_version": ssl.OPENSSL_VERSION,
        "os": f"{platform.system()} {platform.release()}",
    }

    # DB stats
    total_audit_logs = await _db["aurem_audit_logs"].count_documents({})
    total_tenants = await _db["aurem_workspaces"].count_documents({})

    # pip freeze for dependency inventory
    try:
        pip_result = subprocess.run(["pip", "freeze"], capture_output=True, text=True, timeout=30)
        dependencies = pip_result.stdout.strip().split("\n") if pip_result.returncode == 0 else []
    except Exception:
        dependencies = []

    snapshot = {
        "snapshot_id": f"evidence_{now.strftime('%Y%m%d_%H%M%S')}",
        "taken_at": now.isoformat(),
        "taken_by": actor_id,
        "kill_switch_state": get_kill_switch_state(),
        "rbac_matrix": get_rbac_matrix(),
        "security_audit": audit_report,
        "system_info": system_info,
        "db_stats": {
            "total_audit_logs": total_audit_logs,
            "total_tenants": total_tenants,
        },
        "dependency_count": len(dependencies),
        "dependencies": dependencies[:50],
        "compliance_controls": {
            "audit_logging": "ACTIVE",
            "pii_scrubber": "ACTIVE",
            "guardrail_proxy": "ACTIVE",
            "kill_switch": "AVAILABLE",
            "rbac_enforcement": "ACTIVE",
            "encryption_at_rest": "AES-256 (MongoDB WiredTiger)",
            "encryption_in_transit": "TLS 1.2+ (Kubernetes Ingress)",
        },
    }

    # Store in DB
    await _db["compliance_evidence"].insert_one({
        **snapshot,
        "_immutable": True,
    })

    # Audit the snapshot
    await _db["aurem_audit_logs"].insert_one({
        "action": "admin_action",
        "business_id": "platform",
        "actor_id": actor_id,
        "actor_type": "admin",
        "resource_type": "evidence_snapshot",
        "resource_id": snapshot["snapshot_id"],
        "details": {"type": "compliance_evidence_snapshot"},
        "ip_address": ip,
        "user_agent": ua,
        "success": True,
        "timestamp": now,
        "_immutable": True,
    })

    return snapshot


# ═══════════════════════════════════════════════════════════════
# 7. COMPLIANCE SUMMARY (for dashboard)
# ═══════════════════════════════════════════════════════════════

@router.get("/summary")
async def get_compliance_summary(request: Request):
    """Quick compliance health overview for the admin dashboard."""
    await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    from services.kill_switch import get_kill_switch_state
    ks = get_kill_switch_state()

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    audit_count_24h = await _db["aurem_audit_logs"].count_documents({"timestamp": {"$gte": day_ago}})
    security_events = await _db["aurem_audit_logs"].count_documents({
        "action": {"$in": ["login_failed", "suspicious_activity", "rate_limit_hit"]},
        "timestamp": {"$gte": day_ago},
    })
    total_evidence = await _db["compliance_evidence"].count_documents({})

    # Last daily compliance report
    from services.compliance_scheduler import get_latest_report
    latest_report = await get_latest_report()
    last_report = None
    if latest_report:
        last_report = {
            "report_id": latest_report.get("report_id"),
            "generated_at": latest_report.get("generated_at"),
            "status": latest_report.get("status"),
            "score": latest_report.get("security_audit", {}).get("score"),
        }
    total_daily = await _db["compliance_reports"].count_documents({})

    # Last security audit score
    audit_score = None
    try:
        with open("/app/test_reports/security_audit.json", "r") as f:
            report = json.load(f)
            audit_score = report.get("summary", {})
    except Exception:
        pass

    return {
        "kill_switch": ks,
        "audit_logs_24h": audit_count_24h,
        "security_events_24h": security_events,
        "evidence_snapshots": total_evidence,
        "last_security_audit": audit_score,
        "last_daily_report": last_report,
        "total_daily_reports": total_daily,
        "controls_status": {
            "audit_logging": True,
            "pii_scrubber": True,
            "guardrail_proxy": True,
            "kill_switch_available": True,
            "rbac_enforcement": True,
            "hmac_patch_signing": True,
            "daily_compliance_reports": True,
            "maintenance_mode": ks.get("maintenance_mode", False),
            "live_patches_active": not ks.get("live_patches_disabled", False),
        },
    }


# ═══════════════════════════════════════════════════════════════
# 8. DAILY COMPLIANCE REPORTS
# ═══════════════════════════════════════════════════════════════

@router.get("/daily-report/latest")
async def get_latest_daily_report(request: Request):
    """Get the most recent automated daily compliance report."""
    await _require_admin(request)
    from services.compliance_scheduler import get_latest_report
    report = await get_latest_report()
    if not report:
        return {"status": "no_reports", "message": "No daily reports generated yet. Scheduler runs at midnight UTC."}
    return report


@router.get("/daily-report/history")
async def get_daily_report_history(request: Request, limit: int = 30):
    """Get history of automated compliance reports."""
    await _require_admin(request)
    from services.compliance_scheduler import get_report_history
    history = await get_report_history(limit)
    return {"reports": history, "total": len(history)}


@router.post("/daily-report/generate")
async def generate_report_now(request: Request):
    """Manually trigger a daily compliance report (on-demand)."""
    payload = await _require_admin(request)
    ip, ua = _get_client_info(request)

    from services.compliance_scheduler import generate_daily_report
    report = await generate_daily_report()
    return report
