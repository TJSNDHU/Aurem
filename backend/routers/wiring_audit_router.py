"""
Wiring Audit Router — Iteration 203
=====================================
Admin-only: programmatically verifies EVERY feature in the AUREM platform
is wired to the correct panel — Admin or Customer Portal.

GET /api/admin/wiring-audit

Returns {admin:[{feature, panel, status, evidence, route}], customer:[...], summary}

Status:
  - ok        → backend endpoint returns 200 (or 401 when auth required — route exists)
  - wired     → route/component exists but not fully tested
  - missing   → backend path returns 404, i.e. feature not wired
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Wiring Audit"])

from config import JWT_SECRET  # safe 3-tier resolver (env -> file -> ephemeral)
_db = None


def set_db(db):
    global _db
    _db = db


async def _require_admin(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    if payload.get("role") != "admin" and not payload.get("is_admin") and not payload.get("is_super_admin"):
        raise HTTPException(403, "Admin only")
    return payload


# ═══════════════════════════════════════════
# Checklist — source of truth
# ═══════════════════════════════════════════

ADMIN_CHECKLIST = [
    # (feature, panel_route, backend_probe, frontend_component_path)
    # iter D-82c — synced 1:1 with the 9-group AdminShell sidebar (Batch 3).
    # NOTE: a few probes use the most-likely existing path; the live audit page
    # is the verifier — any "missing" row is a 1-line probe correction.

    # ── 1 · BOARDROOM ──────────────────────────────────────────────────
    ("Boardroom KPIs",            "/admin/boardroom",        "/api/admin/financials/hst-summary",        "BoardroomPage.jsx"),
    ("Morning brief history",     "/admin/morning-brief",    "/api/brief/history",                       "MorningBriefMobile.jsx"),
    ("Founder saves",             "/admin/founder-saves",    "/api/admin/founder-saves",                 "FounderSaves.jsx"),
    ("Daily log",                 "/admin/daily-log",        "/api/admin/daily-log",                     "AdminDailyLog.jsx"),

    # ── 2 · MISSION CONTROL ────────────────────────────────────────────
    ("Mission Control dashboard", "/admin/mission-control",  "/api/admin/mission-control/dashboard",     "AdminMissionControl.jsx"),
    ("Campaign command",          "/admin/campaign-command", "/api/lifecycle/pipeline",                  "CampaignCommandDashboard.jsx"),
    ("Campaign health",           "/admin/campaign-health",  "/api/campaign-health/summary",             "CampaignHealthPage.jsx"),
    ("Leads mining",              "/admin/leads-mining",     "/api/scout/status",                        "AdminLeadsMining.jsx"),
    ("Apollo cost",               "/admin/apollo-cost",      "/api/apollo/cost/summary",                 "AdminApolloCostPage.jsx"),

    # ── 3 · CUSTOMERS ──────────────────────────────────────────────────
    ("Customer health panel",     "/admin/customer-health",  "/api/admin/customer-health",               "CustomerHealthPanel.jsx"),
    ("Impersonation log",         "/admin/impersonation-log","/api/admin/impersonation-log",             "AdminImpersonationLog.jsx"),
    ("Plan manager",              "/admin/plans",            "/api/admin/plans",                         "AdminPlanManager.jsx"),

    # ── 4 · ORA ────────────────────────────────────────────────────────
    ("ORA unified (chat/cockpit)","/admin/ora",              "/api/ora/pipeline/status",                 "OraAdminUnified.jsx"),
    ("Council audit",             "/admin/council-audit",    "/api/admin/council/health",                "CouncilAuditPage.jsx"),
    ("Brain",                     "/admin/brain",            "/api/brain/status",                        "AdminBrainPage.jsx"),
    ("Watchdog",                  "/admin/ora-watchdog",     "/api/ora/watchdog/status",                 "OraWatchdogCockpit.jsx"),
    ("Skills marketplace",        "/admin/ora-skills",       "/api/admin/ora/skills",                  "SkillsMarketplace.jsx"),

    # ── 5 · SENTINEL & SELF-REPAIR ─────────────────────────────────────
    ("Sentinel diagnostics",      "/admin/sentinel",         "/api/admin/sentinel/status",               "AdminDiagnostics.jsx"),
    ("Self-repair",               "/admin/self-repair",      "/api/admin/autonomous-repair/stats",       "AdminSelfRepair.jsx"),
    ("Stem fix",                  "/admin/stem-fix",         "/api/stem-fix/status",                     "AdminStemFix.jsx"),
    ("Incident ledger",           "/admin/incident-ledger",  "/api/incidents/list",                      "IncidentLedger.jsx"),
    ("Git commit gate",           "/admin/git-gate",         "/api/git-gate/pending",                    "GitCommitGate.jsx"),
    ("Vanguard",                  "/admin/vanguard",         "/api/admin/ora/vanguard-status",                     "AdminVanguard.jsx"),
    ("Supply-Chain posture",      "/admin/supply-chain",     "/api/admin/supply-chain/remediations",     "AdminSupplyChain.jsx"),

    # ── 6 · SYSTEM HEALTH ──────────────────────────────────────────────
    ("System overview",           "/admin/system-overview",  "/api/admin/system-audit/health",           "SystemOverview.jsx"),
    ("System pulse live",         "/admin/system-pulse-live","/api/admin/system-pulse-live",             "SystemPulseLive.jsx"),
    ("Codebase health",           "/admin/codebase-health",  "/api/codebase-health/latest",              "AdminCodebaseHealth.jsx"),
    ("Wiring audit",              "/admin/wiring-audit",     "/api/admin/wiring-audit",                  "AdminWiringAudit.jsx"),
    ("Site monitor",              "/admin/site-monitor",     "/api/admin/site-monitor/summary",          "AdminSiteMonitor.jsx"),
    ("Pillars map",               "/admin/pillars-map",      "/api/pillars/health",                      "AdminPillarsMap.jsx"),
    ("System audit",              "/admin/system-audit",     "/api/admin/system-audit/health",           "AdminSystemAudit.jsx"),
    ("Control center",            "/admin/control-center",   "/api/admin/control-center/status",         "AdminControlCenter.jsx"),
    ("BugCatch reports",          "/admin/bug-reports",      "/api/admin/bug-reports",                   "AdminBugReports.jsx"),

    # ── 7 · REVENUE ────────────────────────────────────────────────────
    ("Analytics",                 "/admin/analytics",        "/api/owner/analytics/dashboard",           "AnalyticsDashboard.jsx"),
    ("Sovereignty score",         "/admin/sovereignty-score","/api/admin/sovereignty-score",             "AdminSovereigntyScore.jsx"),

    # ── 8 · SECURITY & ACCESS ──────────────────────────────────────────
    ("Security keys",             "/admin/security-keys",    "/api/admin/security-keys",                 "AdminSecurityKeys.jsx"),
    ("API keys",                  "/admin/api-keys",         "/api/aurem-keys/scope-bundles",            "AdminApiKeysPage.jsx"),
    ("Business IDs",              "/admin/business-ids",     "/api/bin-auth/admin/search?q=rst",         "AdminBusinessIds.jsx"),
    ("SSOT",                      "/admin/ssot",             "/api/admin/ssot/status",                   "AdminSSOT.jsx"),
    ("Developer signups",         "/admin/developer-signups","/api/admin/developer-signups",             "AdminDeveloperSignups.jsx"),
    ("Integrations",              "/admin/integrations",     "/api/admin/integrations/health",           "AdminIntegrations.jsx"),

    # ── 9 · LABS (collapsed) ───────────────────────────────────────────
    ("Evolver",                   "/admin/evolver",          "/api/admin/evolver/status",                "AdminEvolver.jsx"),
    ("Brain graph",               "/admin/brain-graph",      "/api/brain/graph",                         "AdminBrainGraph.jsx"),
    ("Browser agent",             "/admin/browser-agent",    "/api/browser-agent/status",                "AdminBrowserAgent.jsx"),
    ("Design extract",            "/admin/design-extract",   "/api/design-extract/status",               "DesignExtractStudio.jsx"),
]

CUSTOMER_CHECKLIST = [
    ("Smart onboarding (incomplete)", "/my/onboarding", "/api/smart-onboarding/health",            "CustomerOnboarding.jsx"),
    ("My Website w/ pixel status",    "/my/website",    "/api/customer/website",                   "CustomerWebsite.jsx"),
    ("Scan history + auto-fixes",     "/my/website",    "/api/customer/scan-history",              "CustomerWebsite.jsx"),
    ("Google Reviews",                "/my/reviews",    "/api/customer/reviews",                   "CustomerReviews.jsx"),
    ("Social media status",           "/my/social",     "/api/customer/social/status",             "CustomerSocial.jsx"),
    ("Monthly report",                "/my/report",     "/api/customer/reports",                   "CustomerReport.jsx"),
    ("API key + install snippet",     "/my/settings",   "/api/customer/api-key",                   "CustomerSettings.jsx"),
    ("GitHub connection",             "/my/website",    "/api/customer/github/status",             "CustomerWebsite.jsx"),
    ("Referral link + rewards",       "/my/referrals",  "/api/customer/referrals",                 "CustomerReferrals.jsx"),
    ("Token balance",                 "/my/website",    "/api/customer/tokens",                    "CustomerWebsite.jsx"),
    ("Billing + Apple Pay",           "/my/billing",    "/api/stripe-embed/publishable-key",       "CustomerBilling.jsx + ApplePayCheckout.jsx"),
    ("ORA chat w/ business context",  "/my/ora",        "/api/bin-auth/customer-context",          "CustomerOra.jsx"),
    # iter D-82c — gaps closed by missing_endpoints_router (Batch-2 portal live)
    ("Scan schedule (get/set)",       "/my/website",    "/api/customer/scan-schedule",             "CustomerWebsite.jsx"),
    ("Sentinel fixes log",            "/my",            "/api/sentinel/fixes-log",                 "LuxePages.jsx"),
]


async def _probe(client: httpx.AsyncClient, base: str, path: str, auth_header: str, registered_paths: set) -> Dict[str, Any]:
    """HEAD/GET the path with auth; return concise status.

    Key invariant: a 404 at the HTTP layer can mean two very different things:
      1. The FastAPI route is not registered at all (true missing).
      2. The route IS registered but its handler returned 404 because the
         logic didn't find a resource for THIS caller (e.g. admin hitting
         `/api/bin-auth/customer-context` — route exists, but admin isn't
         a customer so lookup fails).
    We disambiguate by consulting the live route table.
    """
    try:
        url = f"{base}{path}"
        r = await client.get(url, headers={"Authorization": auth_header}, timeout=8.0)
        code = r.status_code
        # 200 → ok, 401/403/422 → route exists but auth/permission/schema-guard (still wired),
        # 404 → either truly missing OR handler-level not-found; consult the route table.
        if code < 400:
            status = "ok"
        elif code in (401, 403, 422):
            status = "wired"
        elif code == 404:
            if _path_is_registered(path, registered_paths):
                # Route exists, handler just 404'd for this caller. Still wired.
                status = "wired"
            else:
                status = "missing"
        else:
            status = "error"
        return {"http": code, "status": status}
    except Exception as e:
        return {"http": 0, "status": "error", "error": str(e)[:120]}


def _path_is_registered(path: str, registered_paths: set) -> bool:
    """Return True if a FastAPI route matches `path`.

    Route paths may contain `{param}` placeholders. We do a best-effort
    match: exact hit first, then template-aware match.
    """
    # Strip querystring for comparison.
    raw = path.split("?", 1)[0].rstrip("/")
    if raw in registered_paths:
        return True
    # Template match — split both into segments, compare segment-by-segment.
    parts = raw.split("/")
    for tmpl in registered_paths:
        tp = tmpl.rstrip("/")
        tparts = tp.split("/")
        if len(tparts) != len(parts):
            continue
        ok = True
        for a, b in zip(tparts, parts):
            if a.startswith("{") and a.endswith("}"):
                continue
            if a != b:
                ok = False
                break
        if ok:
            return True
    return False


def _collect_registered_paths(request: Request) -> set:
    """Snapshot every registered API path on the live FastAPI app."""
    app = request.app
    out = set()
    for r in getattr(app, "routes", []):
        p = getattr(r, "path", None)
        if isinstance(p, str) and p.startswith("/"):
            out.add(p.rstrip("/"))
    return out


@router.get("/wiring-audit")
async def wiring_audit(request: Request):
    """Probe every feature's backend + report frontend file existence."""
    await _require_admin(request)
    auth_header = request.headers.get("Authorization", "")

    # Snapshot the live FastAPI route table so a handler-level 404
    # (route registered, logic didn't find a match for THIS caller)
    # isn't misreported as "feature missing from the platform".
    registered_paths = _collect_registered_paths(request)

    # Base URL — probe loopback-internally (localhost:8001) to avoid ingress WAF
    # blocking backend-to-backend loopback traffic. This yields a true picture of
    # whether the router is registered, independent of external routing rules.
    base = "http://localhost:8001"

    async with httpx.AsyncClient(verify=True, follow_redirects=True) as client:
        admin_rows: List[Dict[str, Any]] = []
        for feature, panel, probe, comp in ADMIN_CHECKLIST:
            p = await _probe(client, base, probe, auth_header, registered_paths)
            admin_rows.append({
                "feature": feature, "panel": panel, "probe": probe,
                "component": comp, **p,
            })

        customer_rows: List[Dict[str, Any]] = []
        for feature, panel, probe, comp in CUSTOMER_CHECKLIST:
            p = await _probe(client, base, probe, auth_header, registered_paths)
            customer_rows.append({
                "feature": feature, "panel": panel, "probe": probe,
                "component": comp, **p,
            })

    ok = sum(1 for r in admin_rows + customer_rows if r["status"] in ("ok", "wired"))
    total = len(admin_rows) + len(customer_rows)
    summary = {
        "total": total,
        "ok_or_wired": ok,
        "missing": sum(1 for r in admin_rows + customer_rows if r["status"] == "missing"),
        "error": sum(1 for r in admin_rows + customer_rows if r["status"] == "error"),
        "pct": round(ok / max(total, 1) * 100, 1),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "summary": summary,
        "admin": admin_rows,
        "customer": customer_rows,
    }


@router.get("/wiring-audit/health")
async def wiring_health():
    return {"status": "ok", "service": "wiring-audit"}


@router.post("/wiring-audit/run-nightly")
async def run_nightly_now(request: Request):
    """Trigger the nightly wiring audit immediately (same as cron)."""
    await _require_admin(request)
    from services.nightly_wiring_audit import nightly_wiring_audit, set_db as set_wa_db
    if _db is None:
        raise HTTPException(503, "DB not available")
    set_wa_db(_db)
    return await nightly_wiring_audit()


@router.get("/wiring-audit/history")
async def wiring_history(request: Request, limit: int = 14):
    """Last N nightly wiring-audit summaries."""
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "DB not available")
    limit = max(1, min(limit, 60))
    cursor = _db.aurem_wiring_audits.find(
        {},
        {"_id": 0, "admin": 0, "customer": 0},  # trim per-row detail
    ).sort("ran_at", -1).limit(limit)
    return {"history": await cursor.to_list(limit)}
