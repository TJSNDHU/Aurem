"""
AUREM System Pulse QA Bot
──────────────────────────────────────────────────────────────
Proactive endpoint pulse checks — runs every 10 minutes, logs pass/fail to DB,
alerts admin via Resend on 2+ consecutive failures for any endpoint.

Logs to:
  • db.qa_bot_runs         — one doc per scheduler run (summary)
  • db.qa_bot_endpoint_log — one doc per endpoint per run (for history/uptime)
  • db.qa_bot_alerts       — alert audit trail
"""
import os
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _base_url() -> str:
    """Internal URL — always hit local supervisor-managed backend."""
    return os.environ.get("QA_BOT_BASE_URL") or "http://localhost:8001"


# ══════════════════════════════════════════════════════════════
# Critical endpoint catalog — what the pulse bot verifies
# ══════════════════════════════════════════════════════════════
# Each entry: method, path, expected_status (list), timeout_ms, category, label
CRITICAL_ENDPOINTS: List[Dict[str, Any]] = [
    # Health / Core
    {"id": "health",           "method": "GET",  "path": "/api/health",                       "expect": [200],      "category": "core",      "label": "Health Check"},
    {"id": "system_overview",  "method": "GET",  "path": "/api/system/overview/public",       "expect": [200, 404], "category": "core",      "label": "System Overview (public)"},
    {"id": "admin_pulse_snap", "method": "GET",  "path": "/api/admin/pulse/snapshot",         "expect": [401, 403], "category": "admin",     "label": "Admin Pulse (auth-gated)"},

    # Auth
    {"id": "auth_register_gate", "method": "POST", "path": "/api/auth/register", "body": {"email": "qa-bot-invalid"}, "expect": [400, 422, 409], "category": "auth", "label": "Register validation"},
    {"id": "auth_login_gate",    "method": "POST", "path": "/api/auth/login",    "body": {"email": "qa-bot@example.com", "password": "nope"}, "expect": [400, 401, 403, 422], "category": "auth", "label": "Login validation"},

    # SEO / Audit
    {"id": "seo_audit_scan",    "method": "POST", "path": "/api/seo-audit/scan", "body": {"url": "https://aurem.live", "email": "qa-bot@example.com"}, "expect": [200, 202, 429], "timeout": 35.0, "category": "seo", "label": "SEO Audit Scan"},
    {"id": "robots_txt",        "method": "GET",  "path": "/robots.txt",                       "expect": [200, 404], "category": "seo",      "label": "robots.txt"},
    {"id": "sitemap_xml",       "method": "GET",  "path": "/sitemap.xml",                      "expect": [200, 404], "category": "seo",      "label": "sitemap.xml"},
    {"id": "llms_txt",          "method": "GET",  "path": "/llms.txt",                         "expect": [200, 404], "category": "seo",      "label": "llms.txt"},

    # Stripe / Billing (gate-level check — no live charge)
    {"id": "billing_plans",     "method": "GET",  "path": "/api/aurem-billing/plans",          "expect": [200, 404], "category": "billing",  "label": "Billing Plans"},
    {"id": "catalog_public",    "method": "GET",  "path": "/api/catalog/services",             "expect": [200, 404], "category": "billing", "label": "Public Catalog"},

    # Voice / Retell (gate)
    {"id": "voice_agent_ping",  "method": "GET",  "path": "/api/voice-agent/health",           "expect": [200, 404], "category": "voice",    "label": "Voice Agent Health"},

    # Static downloads
    {"id": "wp_plugin_zip",     "method": "GET",  "path": "/api/static/plugins/aurem-pixel.zip", "expect": [200, 404], "category": "assets", "label": "WP Plugin Zip"},

    # Catalog / Services
    {"id": "service_catalog",   "method": "GET",  "path": "/api/service-catalog",              "expect": [200, 404], "category": "catalog",  "label": "Service Catalog"},
    {"id": "service_catalog_v2","method": "GET",  "path": "/api/services/catalog",             "expect": [200, 404], "category": "catalog",  "label": "Services Catalog v2"},

    # Leads / CRM
    {"id": "leads_ping",        "method": "GET",  "path": "/api/leads/health",                 "expect": [200, 401, 403, 404], "category": "crm", "label": "Leads"},

    # ORA / AI
    {"id": "ora_health",        "method": "GET",  "path": "/api/ora/health",                   "expect": [200, 404], "category": "ai",       "label": "ORA AI"},
    {"id": "platform_dashboard","method": "GET",  "path": "/api/platform/health",              "expect": [200, 404], "category": "platform", "label": "Platform Dashboard"},

    # Public frontend shell (via ingress → 3000)
    {"id": "frontend_shell",    "method": "GET",  "path": "/",                                 "expect": [200, 404], "category": "frontend", "label": "Frontend Shell", "external": True},
    {"id": "index_llms_full",   "method": "GET",  "path": "/llms-full.txt",                    "expect": [200, 404], "category": "seo",      "label": "llms-full.txt"},
]


# ══════════════════════════════════════════════════════════════
# Core pulse execution
# ══════════════════════════════════════════════════════════════
async def _check_one(client: httpx.AsyncClient, ep: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single endpoint check. Returns result dict."""
    url = (_base_url().rstrip("/") + ep["path"])
    t0 = time.time()
    result = {
        "id": ep["id"],
        "label": ep["label"],
        "category": ep["category"],
        "method": ep["method"],
        "path": ep["path"],
        "expected": ep["expect"],
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    # Per-endpoint timeout override — some checks (e.g. SEO Audit Scan
    # invoking Lighthouse) legitimately take >25 s. Default 25 s honours
    # the AsyncClient's outer timeout if no override is set.
    per_call_timeout = ep.get("timeout")
    try:
        if ep["method"] == "GET":
            r = await client.get(url, timeout=per_call_timeout) if per_call_timeout else await client.get(url)
        elif ep["method"] == "POST":
            if per_call_timeout:
                r = await client.post(url, json=ep.get("body", {}), timeout=per_call_timeout)
            else:
                r = await client.post(url, json=ep.get("body", {}))
        else:
            r = await client.request(ep["method"], url, json=ep.get("body", {}), timeout=per_call_timeout) if per_call_timeout else await client.request(ep["method"], url, json=ep.get("body", {}))
        latency = round((time.time() - t0) * 1000, 1)
        passed = r.status_code in ep["expect"]
        result.update({
            "status_code": r.status_code,
            "latency_ms": latency,
            "passed": passed,
            "error": None,
        })
    except Exception as e:
        latency = round((time.time() - t0) * 1000, 1)
        result.update({
            "status_code": 0,
            "latency_ms": latency,
            "passed": False,
            "error": str(e)[:200],
        })
    return result


async def run_pulse_once() -> Dict[str, Any]:
    """Run one pulse sweep across all critical endpoints."""
    if _db is None:
        return {"error": "db_unavailable", "checks": []}

    started = datetime.now(timezone.utc)
    checks: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        # Run checks concurrently for speed
        results = await asyncio.gather(
            *[_check_one(client, ep) for ep in CRITICAL_ENDPOINTS],
            return_exceptions=True,
        )

    for r in results:
        if isinstance(r, Exception):
            checks.append({
                "id": "unknown", "label": "Task crashed",
                "passed": False, "status_code": 0, "latency_ms": 0,
                "error": str(r)[:200], "category": "unknown",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        else:
            checks.append(r)

    passed = sum(1 for c in checks if c.get("passed"))
    failed = len(checks) - passed

    # Latency stats — compute BOTH the raw mean AND an internal-only mean
    # so the founder dashboard can show the production-relevant number
    # (target <400ms) without being dragged by deliberate external
    # probes like `/api/seo-audit/scan` which hits aurem.live from the
    # pod and can take 1.5–3 s round-trip through Cloudflare.
    INTERNAL_FAST_CATEGORIES = {"core", "auth", "billing", "admin"}
    raw_latencies = [c.get("latency_ms", 0) for c in checks if c.get("passed")]
    internal_latencies = [
        c.get("latency_ms", 0) for c in checks
        if c.get("passed") and c.get("category") in INTERNAL_FAST_CATEGORIES
    ]

    avg_latency = round(
        sum(raw_latencies) / max(len(raw_latencies), 1), 1
    ) if raw_latencies else 0.0
    internal_avg_latency = round(
        sum(internal_latencies) / max(len(internal_latencies), 1), 1
    ) if internal_latencies else 0.0

    # P95 over passing checks (drops one slow outlier — e.g. SEO scan
    # going through the public proxy)
    if raw_latencies:
        sorted_lat = sorted(raw_latencies)
        p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)
        p95_latency = round(sorted_lat[p95_idx], 1)
    else:
        p95_latency = 0.0

    run_doc = {
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "total": len(checks),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / max(len(checks), 1) * 100, 1),
        "avg_latency_ms": internal_avg_latency,           # ← founder-facing (internal-only)
        "avg_latency_raw_ms": avg_latency,                # ← all probes, including external
        "p95_latency_ms": p95_latency,                    # ← drops outliers
        "failures": [c for c in checks if not c.get("passed")],
    }

    try:
        await _db.qa_bot_runs.insert_one({**run_doc})
        run_doc.pop("_id", None)

        # Per-endpoint log for historical uptime
        batch = [
            {
                "endpoint_id": c["id"],
                "label": c["label"],
                "category": c["category"],
                "passed": c.get("passed"),
                "status_code": c.get("status_code"),
                "latency_ms": c.get("latency_ms"),
                "error": c.get("error"),
                "ts": c["ts"],
                "run_started_at": started.isoformat(),
            } for c in checks
        ]
        if batch:
            await _db.qa_bot_endpoint_log.insert_many(batch)
    except Exception as e:
        logger.warning(f"[QA_BOT] DB write failed: {e}")

    # Alert check — any endpoint failed now + in previous run?
    await _maybe_alert(checks)

    # Latency Guardian — auto-heal slow-but-passing endpoints (iter 322f).
    # Pass `checks` directly so the guardian doesn't need to re-query.
    try:
        from services.latency_guardian import run_guardian_after_sweep
        await run_guardian_after_sweep(_db, {**run_doc, "checks": checks})
    except Exception as e:
        logger.warning(f"[QA_BOT] guardian hook failed: {e}")

    return run_doc


async def _maybe_alert(current_checks: List[Dict[str, Any]]):
    """Send admin alert if any endpoint failed this run AND previous run."""
    if _db is None:
        return
    current_fails = {c["id"] for c in current_checks if not c.get("passed")}
    if not current_fails:
        return

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    # Previously failing endpoints (in last 30 min, excluding this run)
    try:
        prior_fail_ids = set()
        async for doc in _db.qa_bot_endpoint_log.find(
            {"ts": {"$gte": cutoff}, "passed": False},
            {"_id": 0, "endpoint_id": 1},
        ).limit(500):
            prior_fail_ids.add(doc.get("endpoint_id"))
    except Exception:
        prior_fail_ids = set()

    recurring = current_fails & prior_fail_ids
    if not recurring:
        return

    # Throttle — only alert once per endpoint per 2 hours
    throttle_cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    to_alert = []
    for ep_id in recurring:
        try:
            existing = await _db.qa_bot_alerts.find_one({
                "endpoint_id": ep_id, "ts": {"$gte": throttle_cutoff}
            }, {"_id": 0})
            if not existing:
                to_alert.append(ep_id)
        except Exception:
            to_alert.append(ep_id)

    if not to_alert:
        return

    # ────────────────────────────────────────────────────────────────
    # Iter 286.0 — Alert Suppression / Digest Mode
    # Default: DIGEST_ONLY=true → queue the alert instead of sending
    # an instant email. Morning + Evening digest dispatchers drain this
    # queue. Override with ALERTS_DIGEST_ONLY=false to restore instant
    # emails. P0 critical (>= 80% endpoints failing simultaneously)
    # always bypasses the mute.
    # ────────────────────────────────────────────────────────────────
    digest_only = (os.environ.get("ALERTS_DIGEST_ONLY", "true").lower()
                   not in ("0", "false", "no", "off"))
    total_checks = len(current_checks) or 1
    fail_ratio = len(current_fails) / total_checks
    is_p0 = fail_ratio >= 0.8  # ≥80% of endpoints down → genuine system crisis

    if digest_only and not is_p0:
        # Queue — do NOT send instant email
        try:
            await _db.alerts_digest_queue.insert_many([{
                "source": "qa_bot",
                "endpoint_id": ep_id,
                "severity": "warn",
                "ts_iso": datetime.now(timezone.utc).isoformat(),
                "delivered": False,  # False = still pending digest dispatch
                "fail_ratio": round(fail_ratio, 3),
                "total_checks": total_checks,
            } for ep_id in to_alert])
            # Record in qa_bot_alerts table so throttle still works (2h dedupe)
            await _db.qa_bot_alerts.insert_many([{
                "ts": datetime.now(timezone.utc).isoformat(),
                "endpoint_id": ep_id,
                "delivered": False,
                "queued_for_digest": True,
                "provider_info": {"mode": "digest_only"},
            } for ep_id in to_alert])
            logger.info(f"[QA_BOT] {len(to_alert)} alert(s) queued for digest (digest-only mode)")
        except Exception as e:
            logger.error(f"[QA_BOT] Digest queue failed: {e}")
        return

    # Build + send email
    admin_email = os.environ.get("QA_BOT_ALERT_EMAIL") or os.environ.get("ADMIN_EMAIL") or "ora@aurem.live"
    failed_rows = "".join(
        f"<tr><td style='padding:8px;border:1px solid #333'>{c['label']}</td>"
        f"<td style='padding:8px;border:1px solid #333;color:#ff6b6b'>{c.get('status_code', 'ERR')}</td>"
        f"<td style='padding:8px;border:1px solid #333'>{c.get('error') or 'status mismatch'}</td></tr>"
        for c in current_checks if not c.get("passed") and c["id"] in to_alert
    )
    html = f"""
    <div style='font-family:system-ui;background:#050505;color:#eee;padding:24px;border-radius:12px'>
      <h2 style='color:#D4AF37;margin:0 0 8px 0'>AUREM System Pulse — Alert</h2>
      <p style='color:#aaa;margin:0 0 16px 0'>Recurring endpoint failure detected by QA Bot.</p>
      <table style='width:100%;border-collapse:collapse;color:#eee'>
        <tr style='background:#1a1a1a'><th style='padding:8px;text-align:left;border:1px solid #333'>Endpoint</th><th style='padding:8px;text-align:left;border:1px solid #333'>Code</th><th style='padding:8px;text-align:left;border:1px solid #333'>Error</th></tr>
        {failed_rows}
      </table>
      <p style='color:#666;margin-top:16px;font-size:12px'>Triggered at {datetime.now(timezone.utc).isoformat()} • Throttled 2h per endpoint</p>
    </div>
    """
    try:
        from services.email_service_resend import send_email
        ok, info = await send_email(
            to=admin_email,
            subject=f"[AUREM] System Pulse Alert — {len(to_alert)} endpoint(s) failing",
            html=html,
        )
        await _db.qa_bot_alerts.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint_ids": list(to_alert),
            "email_to": admin_email,
            "delivered": ok,
            "provider_info": info,
        })
        logger.info(f"[QA_BOT] Alert sent for {len(to_alert)} endpoints → {admin_email} ({ok})")
    except Exception as e:
        logger.error(f"[QA_BOT] Alert send failed: {e}")


# ══════════════════════════════════════════════════════════════
# Scheduler loop — every 10 minutes
# ══════════════════════════════════════════════════════════════
async def qa_bot_pulse_scheduler():
    """Run pulse sweep every 10 minutes, with a 90s warmup delay on boot."""
    await asyncio.sleep(90)
    logger.info("[QA_BOT] Pulse scheduler started — every 10 minutes")
    while True:
        try:
            result = await run_pulse_once()
            logger.info(
                f"[QA_BOT] Pulse: {result.get('passed')}/{result.get('total')} passed "
                f"({result.get('pass_rate')}%) • avg {result.get('avg_latency_ms')}ms"
            )
        except Exception as e:
            logger.error(f"[QA_BOT] Pulse error: {e}")
        await asyncio.sleep(600)  # 10 min


# ══════════════════════════════════════════════════════════════
# Reporting helpers (used by router)
# ══════════════════════════════════════════════════════════════
async def get_latest_run() -> Optional[Dict[str, Any]]:
    if _db is None:
        return None
    doc = await _db.qa_bot_runs.find_one({}, {"_id": 0}, sort=[("started_at", -1)])
    return doc


async def get_run_history(limit: int = 100) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    out = []
    async for d in _db.qa_bot_runs.find({}, {"_id": 0, "failures": 0}).sort("started_at", -1).limit(limit):
        out.append(d)
    return out


async def get_endpoint_stats(window_hours: int = 24) -> List[Dict[str, Any]]:
    """Compute per-endpoint uptime, avg latency, failure count for the window."""
    if _db is None:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    pipeline = [
        {"$match": {"ts": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$endpoint_id",
            "label": {"$last": "$label"},
            "category": {"$last": "$category"},
            "total": {"$sum": 1},
            "passed": {"$sum": {"$cond": [{"$eq": ["$passed", True]}, 1, 0]}},
            "avg_latency_ms": {"$avg": "$latency_ms"},
            "last_status": {"$last": "$status_code"},
            "last_passed": {"$last": "$passed"},
            "last_error": {"$last": "$error"},
            "last_ts": {"$last": "$ts"},
        }},
        {"$project": {
            "_id": 0,
            "endpoint_id": "$_id",
            "label": 1,
            "category": 1,
            "total": 1,
            "passed": 1,
            "failed": {"$subtract": ["$total", "$passed"]},
            "uptime_pct": {"$multiply": [{"$divide": ["$passed", "$total"]}, 100]},
            "avg_latency_ms": {"$round": ["$avg_latency_ms", 1]},
            "last_status": 1,
            "last_passed": 1,
            "last_error": 1,
            "last_ts": 1,
        }},
        {"$sort": {"label": 1}},
    ]
    try:
        out = [d async for d in _db.qa_bot_endpoint_log.aggregate(pipeline)]
    except Exception as e:
        logger.warning(f"[QA_BOT] stats aggregate failed: {e}")
        return []
    # Round uptime to 1 decimal
    for d in out:
        d["uptime_pct"] = round(d.get("uptime_pct", 0), 1)
    return out
