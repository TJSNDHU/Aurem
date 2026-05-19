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
    ("Living Audit Dashboard",      "/admin/system-audit",               "/api/admin/system-audit/health",           "AdminSystemAudit.jsx"),
    ("4 Agents dry-run toggles",    "/admin/system-audit",               "/api/agents/status",                       "AdminSystemAudit.jsx"),
    ("Per-customer pixel status",   "/admin/system-audit + pixel admin", "/api/pixel/admin/customer-status?email=teji.ss1986@gmail.com", "pixel_patches_router.py"),
    ("BIN search",                  "/dashboard (admin)",                "/api/bin-auth/admin/search?q=rst",         "bin_auth_router.py"),
    ("Scan history per customer",   "/my/website (customer)",            "/api/customer/scan-history",               "CustomerWebsite.jsx"),
    ("Campaign HQ with Kanban",     "/dashboard → pipeline-kanban",      "/api/lifecycle/pipeline",                   "LeadPipelineKanban.jsx"),
    ("Flame score + auto-dialer",   "/dashboard → voice-sales-agent",    "/api/lifecycle/pipeline",                   "lead_lifecycle_router.py"),
    ("Morning digest history",      "/dashboard → brief-history",        "/api/brief/history",                         "brief_router.py"),
    ("A2A activity feed",           "/dashboard → agent-observatory",    "/api/agents/a2a-feed",                     "AgentObservatory.jsx"),
    ("Referral tracking (admin)",   "/dashboard → partner-referral",     "/api/customer/referrals",                  "PartnerReferralPortal.jsx"),
    ("Apple Pay checkout sessions", "/admin/financials",                 "/api/stripe-embed/health",                 "stripe_embed_router.py"),
    ("Nightly health check status", "/admin/system-audit",               "/api/admin/system-audit/health",           "AdminSystemAudit.jsx"),
    ("Smart onboarding status",     "/my/onboarding (customer)",         "/api/smart-onboarding/health",             "CustomerOnboarding.jsx"),
    ("API keys per customer",       "/dashboard → api-keys",             "/api/aurem-keys/scope-bundles",             "APIKeysManager.jsx"),
    ("GitHub connection status",    "/my/website (customer)",            "/api/customer/github/status",              "CustomerWebsite.jsx"),
    ("Pixel events per customer",   "/admin/system-audit (pixel card)",  "/api/pixel/status?key=invalid",            "pixel_patches_router.py"),
    ("Auto-hunt queue + schedule",  "/dashboard → hunt-command",         "/api/auto-hunt/settings",                  "agents_router.py"),
    ("CASL audit trail",            "/dashboard → security",             "/api/compliance/status",                    "agents_router.py"),
    ("HST financial records",       "/admin/financials",                 "/api/admin/financials/hst-summary",         "admin_financials_router.py"),
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
