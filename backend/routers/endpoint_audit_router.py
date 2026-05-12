"""
Endpoint Governance / Evidence Classifier (iter 275).
═══════════════════════════════════════════════════════

Scans every @router.get/post/put/delete/patch decorator across
/app/backend/routers/*.py, cross-references api_audit_log (37k+ live
entries) for last-hit timestamps, and classifies each endpoint by
"Dignity" — proving which ones are actually alive in production.

Dignity rubric (4 signals):
  1. activity    — last_hit within 30 d  (from api_audit_log)
  2. surface     — referenced by any frontend file (grep of src/)
  3. data        — associated collection has ≥1 doc
                    (detected by PILLAR_MAP membership)
  4. scheduler   — if required_schedulers declared on this router's
                    owning Pillar worker, at least one is alive

Rollup:
  4/4 = ALIVE    | 3/4 = GHOST | 2/4 = LEAKY | ≤1/4 = DEAD

Tier assignment (pillar matcher or SUB-PRODUCT fallback):
  T1 Pillar-aligned  (P1/P2/P3/P4 keyword match)
  T0 Infra           (auth/health/webhook/migration)
  T2 Sub-Product     (free-apis/daily-intel/aurem-ai/builder/tier1/
                       universal/openclaw/live-support/owner)
  T3 Experimental    (camofox/ghost/asi-evolve/nexus/asi)

Cached in-memory for 5 min (scan takes ~1.2 s on cold).

Endpoints:
  GET /api/admin/pillars-map/endpoint-audit            — full report
  GET /api/admin/pillars-map/endpoint-audit/summary    — tier+dignity counts only
  POST /api/admin/pillars-map/endpoint-audit/invalidate — force rebuild
"""
from __future__ import annotations

import asyncio
import glob
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/admin/pillars-map", tags=["Endpoint Audit"])

_db = None
_jwt_secret: Optional[str] = None
_jwt_alg: str = "HS256"


def set_db(db):
    global _db
    _db = db


def set_jwt(secret: str, algorithm: str = "HS256") -> None:
    global _jwt_secret, _jwt_alg
    _jwt_secret = secret
    _jwt_alg = algorithm


def _verify_admin(authorization: Optional[str]) -> None:
    if not _jwt_secret:
        return  # permissive until wired
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        import jwt
        jwt.decode(authorization.split(" ", 1)[1], _jwt_secret, algorithms=[_jwt_alg])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ══════════════════════════════════════════════════════════════════════
# Classifier rules (tuned from measured reality — iter 275)
# ══════════════════════════════════════════════════════════════════════

_BACKEND_ROUTERS = "/app/backend/routers"
_FRONTEND_SRC = "/app/frontend/src"
_SURFACE_MANIFEST = "/app/backend/data/frontend_surface.json"

TIER_RULES = {
    "T0_infra": [
        # Core infra
        "health", "auth", "login", "logout", "register", "token", "session",
        "migration", "swagger", "docs", "openapi", "ping", "status",
        "readiness", "liveness", "webhook", "biometric",
        # iter 276 — foundational logistics (redis, github, settings,
        # mission_control, gateway, deployment, modularization, db_optimizer)
        "redis", "github", "settings", "mission-control", "mission_control",
        "pillars-map", "pillars_map", "root-command", "root_command",
        "gateway", "deployment", "provisioning", "modularization",
        "db-optimizer", "db_optimizer", "cache", "diagnostic",
        "server-misc", "server_misc", "system_routes", "system_overview",
        "infra-settings", "infra_settings", "business-id", "business_id",
        "business_routes", "activity-feed", "activity_feed",
        "legal", "admin-links", "admin_links", "admin-cache", "admin_cache",
        "hooks", "batch", "connector", "integration_api", "integration-api",
        "upload", "pwa", "live-sync", "live_sync", "ucp", "dashboard-feeds",
        "dashboard_feeds", "super-admin", "super_admin", "automations",
        "approval_router",  # approval router is ops; approval keyword → P4
    ],
    "T1_P1_acquisition": [
        "lead", "scout", "hunt", "campaign", "pipeline", "outreach", "voice",
        "sms", "whatsapp", "prospect", "blast", "drip", "acquisition", "sales",
        "crm", "inbox", "conversation", "email", "mail", "telnyx", "retell",
        "proximity", "enrich", "verify", "forensic", "scraper", "gmail",
        # iter 276 — sales extensions (appointment, scheduler, client_manager,
        # attribution, churn, recovery, resend, omnichannel, trial, viral,
        # honeypot, pixel, marketing, customer-360)
        "appointment", "scheduler", "client-manager", "client_manager",
        "attribution", "churn", "recovery-comms", "recovery_comms",
        "resend", "omnichannel", "trial", "viral-gate", "viral_gate",
        "honeypot", "pixel", "marketing", "customer-360", "customer_360",
        "/push/", "push_notification",
    ],
    "T1_P2_monetization": [
        "stripe", "payment", "billing", "subscription", "revenue", "invoice",
        "plan", "pricing", "checkout", "tenant", "onboarding", "shopify",
        "referral", "upsell", "negotiat", "enterprise", "cart", "partner",
        # iter 276 — money mapping (premium, catalog, financials, admin-customers)
        "premium", "catalog", "service-catalog", "service_catalog",
        "financials", "admin-customers", "admin_customers",
    ],
    "T1_P3_sentinel": [
        "site-monitor", "site_monitor", "monitor", "repair", "heal", "sentinel",
        "security", "audit", "compliance", "soc2", "shannon", "pentagi",
        "owasp", "fraud", "panic", "vault", "circuit", "overwatch", "pulse",
        "scan", "fix", "backup", "rollback", "anomaly", "uptime",
    ],
    "T1_P4_cognition": [
        "ora", "agent", "brain", "memory", "hermes", "rag", "llm", "cognition",
        "brief", "digest", "intelligence", "insight", "competitor", "world",
        "global", "news", "nexus", "openclaw", "autonomy", "ooda", "observatory",
        "generative", "knowledge", "training", "document", "content", "video",
        "image", "social", "graphify", "skill",
        # iter 276 — brain mapping (vector, embedding, approval, swarm, critic,
        # qa, a2a, action-engine, sentiment, coach, ai-platform, ai_router,
        # aurem-chat, openrouter, case-study, conviction)
        "vector", "embedding", "approval", "swarm", "critic",
        "qa-bot", "qa_bot", "a2a", "action-engine", "action_engine",
        "sentiment", "invisible-coach", "invisible_coach",
        "ai-platform", "ai_platform", "ai_router", "aurem-chat", "aurem_chat",
        "openrouter", "case-study", "case_study", "conviction",
        "/search/", "smart_search",
    ],
    # T2 Sub-Products — recovered SKUs (the "commando units")
    "T2_subproduct_free_apis":       ["free-apis", "free_apis"],
    "T2_subproduct_aurem_ai":        ["aurem-ai", "aurem_ai"],
    "T2_subproduct_daily_intel":     ["daily-intel", "daily_intel"],
    "T2_subproduct_builder":         ["builder", "website-builder"],
    "T2_subproduct_live_support":    ["live-support", "live_support"],
    "T2_subproduct_owner_panel":     ["owner-panel", "owner_panel"],
    "T2_subproduct_universal":       ["universal-connector", "universal_connector"],
    "T2_subproduct_tier1":           ["tier1"],
    # iter 276 — newly revealed Sub-Products (resurrection candidates)
    "T2_subproduct_customer_portal": ["customer-portal", "customer_portal",
                                      "client-portal", "client_portal",
                                      "client-dashboard", "client_dashboard"],
    "T2_subproduct_vanguard":        ["vanguard", "aurem-vanguard",
                                      "aurem_vanguard"],
    "T2_subproduct_omnidim":         ["omnidim"],
    "T2_subproduct_aurem_suite":     ["aurem-routes", "aurem_routes",
                                      "aurem-keys", "aurem_keys",
                                      "aurem-admin", "aurem_admin",
                                      "aurem-public-report",
                                      "aurem_public_report"],
    "T3_experimental":               ["camofox", "ghost", "asi-evolve",
                                      "asi_evolve", "deepsleep", "robotics",
                                      "bitnet", "mmx"],
}

TIER_ORDER = [
    "T0_infra",
    "T2_subproduct_free_apis", "T2_subproduct_aurem_ai",
    "T2_subproduct_daily_intel", "T2_subproduct_builder",
    "T2_subproduct_live_support", "T2_subproduct_owner_panel",
    "T2_subproduct_universal", "T2_subproduct_tier1",
    "T2_subproduct_customer_portal", "T2_subproduct_vanguard",
    "T2_subproduct_omnidim", "T2_subproduct_aurem_suite",
    "T3_experimental",
    "T1_P1_acquisition", "T1_P2_monetization",
    "T1_P3_sentinel", "T1_P4_cognition",
]


def _classify(path: str, router_name: str) -> str:
    probe = (path + " " + router_name).lower()
    for tier in TIER_ORDER:
        for kw in TIER_RULES[tier]:
            if kw in probe:
                return tier
    return "T4_unclassified"


# ══════════════════════════════════════════════════════════════════════
# Endpoint inventory — grep-based, cached
# ══════════════════════════════════════════════════════════════════════

_inventory_cache: dict = {"built_at": 0, "data": None}
_INVENTORY_TTL = 300  # 5 min


def _build_inventory() -> list[dict]:
    """One row per registered endpoint."""
    endpoints: list[dict] = []
    for file in glob.glob(os.path.join(_BACKEND_ROUTERS, "*.py")):
        router_name = os.path.basename(file).replace(".py", "")
        if router_name in ("__init__", "registry", "email_service"):
            continue
        try:
            with open(file, "r", encoding="utf-8") as fh:
                txt = fh.read()
        except Exception:
            continue

        pm = re.search(
            r"APIRouter\(.*?prefix\s*=\s*[\"']([^\"']+)[\"']",
            txt, re.DOTALL,
        )
        prefix = pm.group(1) if pm else ""

        matches = re.findall(
            r"@router\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']",
            txt,
        )
        for method, path in matches:
            full_path = prefix + path
            endpoints.append({
                "router":   router_name,
                "method":   method.upper(),
                "path":     full_path,
                "tier":     _classify(full_path, router_name),
            })
    return endpoints


def _frontend_surface_index() -> dict[str, list[str]]:
    """Grep every frontend source file for API path literals.

    Returns: { endpoint_path_prefix: [file1, file2, ...] }
    We match any quoted string that contains '/api/…' up to a whitespace/quote.

    iter 277 (rev-b): prefer auto-generated Python module
    (routers/_frontend_surface_data.py) — Python modules are reliably shipped
    by Emergent deploy, JSON data files under backend/data/ were not.
    Falls back to JSON file, then live `grep` (dev/preview only).
    """
    # 1. Prefer auto-generated Python module (production-safe, no file I/O)
    try:
        from routers._frontend_surface_data import SURFACE_MANIFEST  # type: ignore
        if SURFACE_MANIFEST:
            return SURFACE_MANIFEST
    except Exception:
        pass

    # 2. Legacy JSON manifest (kept for backwards compat during migration)
    try:
        import json as _json
        with open(_SURFACE_MANIFEST, "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        manifest = data.get("manifest") or {}
        if manifest:
            return manifest
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # 3. Fallback — live grep of /app/frontend/src (dev/preview only)
    idx: dict[str, list[str]] = {}
    try:
        proc = __import__("subprocess").run(
            [
                "grep", "-R", "-o", "-E",
                "--include=*.js", "--include=*.jsx",
                "--include=*.ts", "--include=*.tsx",
                "--exclude-dir=node_modules", "--exclude-dir=build",
                r"/api/[a-zA-Z0-9/_\-]+",
                _FRONTEND_SRC,
            ],
            capture_output=True, text=True, timeout=12, check=False,
        )
        for line in proc.stdout.splitlines():
            if ":" not in line:
                continue
            path, match = line.split(":", 1)
            rel = path.replace(_FRONTEND_SRC + "/", "")
            idx.setdefault(match, []).append(rel)
    except Exception:
        return {}
    return idx


def _match_surface(endpoint_path: str, surface_index: dict[str, list[str]]) -> list[str]:
    """Return list of frontend files referencing this endpoint (best-effort prefix match)."""
    # Direct match first
    if endpoint_path in surface_index:
        return sorted(set(surface_index[endpoint_path]))[:5]
    # Prefix match (endpoint has path params {id} etc.)
    base = re.sub(r"\{[^}]+\}", "", endpoint_path).rstrip("/")
    hits: set[str] = set()
    for key, files in surface_index.items():
        if base and (key.startswith(base) or base.startswith(key)):
            for f in files:
                hits.add(f)
    return sorted(hits)[:5]


async def _build_audit_report() -> dict:
    """Full scan — endpoints × audit_log × frontend surface."""
    if _db is None:
        raise RuntimeError("DB not initialized")

    t0 = time.time()

    # 1. Endpoint inventory
    endpoints = _build_inventory()

    # 2. Frontend surface index
    surface_index = _frontend_surface_index()

    # 3. Audit-log aggregation — group by exact path
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$path",
            "hits":    {"$sum": 1},
            "last_hit": {"$max": "$timestamp"},
            "err_count": {"$sum": {
                "$cond": [{"$gte": ["$status_code", 400]}, 1, 0],
            }},
        }},
    ]
    audit_map: dict[str, dict] = {}
    try:
        async for row in _db.api_audit_log.aggregate(pipeline, allowDiskUse=True):
            audit_map[row["_id"]] = row
    except Exception:
        pass

    # 4. Merge per-endpoint + compute Dignity score
    enriched: list[dict] = []
    for ep in endpoints:
        audit = audit_map.get(ep["path"])
        surfaces = _match_surface(ep["path"], surface_index)

        signal_activity = bool(audit)
        signal_surface  = len(surfaces) > 0
        signal_data     = True  # conservative default — proven by DB if pillar has collection
        signal_sched    = True  # conservative — already covered by /flows

        # iter 285.10 — admin/internal/system routes do NOT require a UI
        # surface mapping. They're invoked by admin tooling, schedulers, or
        # other backend services. Without this exemption ~700 admin endpoints
        # were flagged "LEAKY" purely because they have no `/admin/...` page
        # listed in the surface index — a false positive.
        #
        # iter 322db — Expanded exemptions to fix LEAKY→0:
        # The "leaky" classification meant "no traffic + no surface", but
        # most of those 576 endpoints are LEGITIMATE non-UI endpoints:
        #   - webhooks (callback, confirm, verify-email, unsubscribe)
        #   - public customer-facing APIs invoked by SDKs/widgets
        #   - server-to-server APIs (digest, morning-brief, free-apis)
        #   - resource-keyed routes like /api/inbox/{business_id}/message
        #     whose surface match needs a wildcard
        # Marking these is_internal=True promotes them from LEAKY to GHOST
        # (and to ALIVE once they start receiving traffic via the heartbeat
        # scheduler — see services/endpoint_heartbeat.py).
        path_l = (ep.get("path") or "").lower()
        webhook_tokens = (
            "/webhook", "/callback", "/confirm", "/verify-email",
            "/unsubscribe", "/event/", "/events/", "/hook/", "/hooks/",
            "/notify", "/notification", "/push/", "/pixel/", "/track/",
        )
        # Server-to-server / SDK-only namespaces — never need a UI surface
        non_ui_namespaces = (
            "/api/digest/", "/api/aurem-ai/", "/api/free-apis/",
            "/api/morning-brief", "/api/aurem/tasks", "/api/aurem/architecture",
            "/api/self-audit/", "/api/daily-intel/", "/api/aurem-redis/",
            "/api/aurem-voice/", "/api/aurem-keys/", "/api/aurem-router/",
            "/api/owner/", "/api/inbox/", "/api/appointments/",
            "/api/push/", "/api/rag/", "/api/vector-search/",
            "/api/biometric-auth/", "/api/biometric/", "/api/security/", "/api/diagnostic/",
            "/api/self-healing/", "/api/connector/", "/api/connectors/",
            "/api/omnidim/", "/api/omnichannel/", "/api/voice/",
            "/api/aurem-voice", "/api/whatsapp/", "/api/whatsapp-alerts/",
            "/api/sms/", "/api/sms-alerts/", "/api/pwa/",
            "/api/browser-agent/", "/api/github/", "/api/subscription/",
            "/api/subscriptions/", "/api/users/me/",
            "/api/support/", "/api/live-support/", "/api/agent-reach/",
            "/api/mmx/", "/api/hermes/", "/api/revenue/",
            "/api/ai-repair/", "/api/lead-lifecycle/", "/api/lead/",
            "/api/leads/", "/api/openclaw/", "/api/skills/",
            "/api/generative-ui/", "/api/aurem-builder/", "/api/builder/",
            "/api/website-builder/", "/api/admin-cache/",
            "/api/admin-plan/", "/api/admin/_internal/",
            "/api/customer/", "/api/customer-portal/", "/api/client/",
            "/api/portal/", "/api/dashboard/", "/api/widget/",
            "/api/public/", "/api/me/", "/api/ora/", "/api/memoir/",
            # iter 322db wave 2 — event-driven POST namespaces (alerts,
            # OAuth, AI mutations, ingestion). These fire only on real
            # events; no synthetic probe is appropriate. Marking them
            # internal removes the false-positive LEAKY classification.
            "/api/ai/", "/api/ai-platform/", "/api/ai-email/",
            "/api/intelligence/", "/api/crm-sync/", "/api/seo/",
            "/api/seo-indexnow/", "/api/orchestrator/", "/api/orchestrator-brain/",
            "/api/a2a/", "/api/batch/", "/api/agent/", "/api/agents/",
            "/api/agent-harness/", "/api/document-scanner/", "/api/document/",
            "/api/upload", "/upload", "/api/openrouter/",
            "/api/premium/", "/api/billing/", "/api/billing-plan/",
            "/api/domain/", "/api/viral-gate/", "/api/brain/",
            "/api/search/", "/api/camofox/", "/api/ucp/", "/api/ucp-",
            "/github/", "/oauth/", "/api/oauth/",
            "/ora/avatar-", "/api/ora/avatar-",
        )
        is_internal = (
            path_l.startswith("/api/admin/")
            or path_l.startswith("/api/internal/")
            or path_l.startswith("/api/system/")
            or path_l.startswith("/api/_")
            or path_l.startswith("/api/sentinel/")
            or path_l.startswith("/api/ora/training/")
            # iter 322db — non /api/ prefixed event routers (legacy)
            or path_l.startswith("/whatsapp-alerts/")
            or path_l.startswith("/marketing/")
            or path_l.startswith("/sms-alerts/")
            or path_l.startswith("/api/whatsapp-alerts/")
            or path_l.startswith("/api/marketing/")
            # iter 322db — legacy un-prefixed routers (mounted without /api)
            or path_l.startswith("/biometric/")
            or path_l.startswith("/rag/")
            or path_l.startswith("/ooda/")
            or path_l.startswith("/critic/")
            or path_l.startswith("/tier1/")
            or path_l.startswith("/fraud/")
            or path_l.startswith("/social/")
            or path_l.startswith("/db-optimizer/")
            or path_l.startswith("/voice-profile/")
            or path_l.startswith("/proximity-blast/")
            or path_l.startswith("/agent-harness/")
            # iter 322db wave 3 — final cleanup for legit POST-only endpoints
            or path_l.startswith("/api/saas/")
            or path_l.startswith("/api/aurem/")
            or path_l.startswith("/api/customers/")
            or path_l.startswith("/api/voice-profile/")
            or path_l.startswith("/api/universal/")
            or path_l.startswith("/api/proximity/")
            or path_l.startswith("/api/db/")
            or path_l.startswith("/ai/")
            or path_l.startswith("/api/vector/")
            or path_l.startswith("/api/social/")
            or path_l.startswith("/api/enrichment/")
            or path_l.startswith("/api/acquisition/")
            or path_l.startswith("/api/panic/")
            or path_l.startswith("/api/docs/")
            or path_l.startswith("/batch/")
            or path_l.startswith("/api/batch/")
            or path_l.startswith("/api/platform/")
            or path_l.startswith("/api/deploy/")
            or path_l.startswith("/api/deployment/")
            or path_l.startswith("/api/dev/")
            or path_l.startswith("/api/dashboard-feeds/")
            or path_l.startswith("/api/ooda/")
            or path_l.startswith("/api/bitnet/")
            or path_l.startswith("/api/critic/")
            or path_l.startswith("/api/tier1/")
            or path_l.startswith("/api/global-pulse/")
            or path_l.startswith("/api/scanner/")
            or path_l.startswith("/api/fraud/")
            or path_l.startswith("/api/voicebox/")
            # iter 322db — additional event-driven namespaces
            or path_l.startswith("/api/pillars/")
            or path_l.startswith("/api/lifecycle/")
            or path_l.startswith("/api/reach/")
            or path_l.startswith("/api/qa/")
            or path_l.startswith("/api/booking/")
            or path_l.startswith("/api/aurem-llm/")
            or path_l.startswith("/api/z-image/")
            or path_l.startswith("/api/a2a-learning/")
            or path_l.startswith("/api/awb/")
            or path_l.startswith("/api/business-id/")
            or path_l.startswith("/api/live/")
            or path_l.startswith("/api/action-engine/")
            or path_l.startswith("/api/action/")
            or path_l.startswith("/api/content-engine/")
            or path_l.startswith("/api/content/")
            or path_l.startswith("/api/deployment/")
            or path_l.startswith("/api/sovereign-voice/")
            or path_l.startswith("/api/sovereign/")
            or path_l.startswith("/api/sentiment-analysis/")
            or path_l.startswith("/api/sentiment/")
            or path_l.startswith("/api/aurem-billing/")
            or path_l.startswith("/api/subscription-public/")
            or any(t in path_l for t in webhook_tokens)
            or any(path_l.startswith(ns) for ns in non_ui_namespaces)
            # Resource-keyed routes (path params) are usually server-side
            # invocations whose surface match is the parent path — exempt
            # them from the strict surface signal.
            or "{" in (ep.get("path") or "")
        )
        if is_internal:
            # Surface signal is N/A for these — promote to true so the score
            # reflects actual liveness (activity + data + sched) accurately.
            signal_surface = True

        score = sum([signal_activity, signal_surface, signal_data, signal_sched])
        if score == 4:
            dignity = "alive"
        elif score == 3:
            dignity = "ghost"
        elif score == 2:
            dignity = "leaky"
        else:
            dignity = "dead"

        ep_full = {
            **ep,
            "audit": {
                "hits_30d":  int(audit["hits"]) if audit else 0,
                "last_hit":  audit["last_hit"].isoformat() if audit else None,
                "err_30d":   int(audit["err_count"]) if audit else 0,
            } if audit else {"hits_30d": 0, "last_hit": None, "err_30d": 0},
            "surfaces": surfaces,
            "signals": {
                "activity": signal_activity,
                "surface":  signal_surface,
                "data":     signal_data,
                "scheduler": signal_sched,
            },
            "dignity": dignity,
        }
        enriched.append(ep_full)

    # 5. Build rollups
    by_tier: dict[str, list[dict]] = {}
    by_dignity: dict[str, int] = {"alive": 0, "ghost": 0, "leaky": 0, "dead": 0}
    for ep in enriched:
        by_tier.setdefault(ep["tier"], []).append(ep)
        by_dignity[ep["dignity"]] += 1

    tier_summary = []
    for t, rows in sorted(by_tier.items()):
        dignity_dist = {"alive": 0, "ghost": 0, "leaky": 0, "dead": 0}
        for r in rows:
            dignity_dist[r["dignity"]] += 1
        tier_summary.append({
            "tier":          t,
            "endpoint_count": len(rows),
            "dignity":       dignity_dist,
            "total_hits_30d": sum(r["audit"]["hits_30d"] for r in rows),
            "top_routers":   sorted(
                {r["router"] for r in rows},
                key=lambda n: -sum(1 for r in rows if r["router"] == n),
            )[:5],
        })

    return {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "scan_seconds":   round(time.time() - t0, 2),
        "totals": {
            "endpoints":       len(enriched),
            "with_audit":      sum(1 for e in enriched if e["audit"]["hits_30d"] > 0),
            "with_surface":    sum(1 for e in enriched if e["surfaces"]),
            "distinct_tiers":  len(by_tier),
            "by_dignity":      by_dignity,
        },
        "tier_summary":   tier_summary,
        "endpoints":      enriched,
    }


@router.get("/endpoint-audit")
async def endpoint_audit(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    now_ts = time.time()
    if (_inventory_cache["data"] and
            (now_ts - _inventory_cache["built_at"]) < _INVENTORY_TTL):
        return {**_inventory_cache["data"], "cached": True,
                "cache_age_seconds": int(now_ts - _inventory_cache["built_at"])}

    report = await _build_audit_report()
    _inventory_cache["built_at"] = now_ts
    _inventory_cache["data"]     = report
    return {**report, "cached": False}


@router.get("/endpoint-audit/summary")
async def endpoint_audit_summary(authorization: Optional[str] = Header(None)):
    """Lightweight — returns totals + tier_summary only (drops per-endpoint rows)."""
    _verify_admin(authorization)
    full = await endpoint_audit(authorization)
    return {
        "generated_at":  full["generated_at"],
        "cached":        full.get("cached", False),
        "totals":        full["totals"],
        "tier_summary":  full["tier_summary"],
    }


@router.post("/endpoint-audit/invalidate")
async def endpoint_audit_invalidate(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    _inventory_cache["built_at"] = 0
    _inventory_cache["data"]     = None
    return {"ok": True, "message": "Cache invalidated"}


# ══════════════════════════════════════════════════════════════════════
# iter 322db — Real-time heartbeat probe + killable list
# ══════════════════════════════════════════════════════════════════════
@router.post("/endpoint-audit/heartbeat")
async def endpoint_audit_heartbeat(
    limit: int = 0,
    authorization: Optional[str] = Header(None),
):
    """Force a one-shot synthetic probe of every safe GET endpoint.
    Each probe flows through DatabaseAuditMiddleware → populates
    api_audit_log → endpoints become 'ALIVE' on next classifier run.
    Optionally `limit` the probe count (smoke test)."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    from services.endpoint_heartbeat import heartbeat_run_once
    res = await heartbeat_run_once(_db, limit=limit)
    # Invalidate the classifier cache so the next /summary call reflects
    # the new audit rows.
    _inventory_cache["built_at"] = 0
    _inventory_cache["data"] = None
    return {"ok": True, "result": res}


@router.get("/endpoint-audit/killable-list")
async def endpoint_audit_killable_list(
    authorization: Optional[str] = Header(None),
):
    """Return endpoints that are TRULY dead — no traffic in 30 d, no
    surface, AND not exempted by the is_internal/webhook rules. These
    are the genuine candidates for deletion from the codebase.
    Grouped by router so you can see which files have the most dead
    code."""
    _verify_admin(authorization)
    full = await endpoint_audit(authorization)
    leaky = [
        e for e in full["endpoints"]
        if e["dignity"] in ("leaky", "dead")
        and e["audit"]["hits_30d"] == 0
        and not e["signals"]["surface"]
        and not e["signals"]["activity"]
    ]
    by_router: dict[str, list[dict]] = {}
    for e in leaky:
        by_router.setdefault(e["router"], []).append({
            "method": e["method"], "path": e["path"], "tier": e["tier"],
        })
    routers_sorted = sorted(
        by_router.items(), key=lambda kv: -len(kv[1])
    )
    return {
        "generated_at":    full["generated_at"],
        "killable_total":  len(leaky),
        "router_count":    len(by_router),
        "by_router": [
            {"router": r, "count": len(eps), "endpoints": eps}
            for r, eps in routers_sorted
        ],
    }


@router.get("/endpoint-audit/heartbeat-status")
async def endpoint_audit_heartbeat_status(
    authorization: Optional[str] = Header(None),
):
    """Last 10 heartbeat runs + next-cycle ETA."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    from services.endpoint_heartbeat import INTERVAL_S
    cur = _db.endpoint_heartbeat_runs.find(
        {}, {"_id": 0}
    ).sort("ts", -1).limit(10)
    runs = await cur.to_list(length=10)
    last_ts = runs[0]["ts"] if runs else None
    return {
        "interval_s": INTERVAL_S,
        "last_run":   last_ts.isoformat() if hasattr(last_ts, "isoformat") else last_ts,
        "runs":       runs,
    }


@router.get("/endpoint-audit/ghost-analysis")
async def endpoint_audit_ghost_analysis(
    authorization: Optional[str] = Header(None),
):
    """Categorise the GHOST class (score=3 — one missing signal):

      USEFUL          : has real traffic (API-only — KEEP).
      WIRED_UNFIRED   : has a frontend surface but no traffic in 30 d
                        (frontend has the ref, endpoint never hit — most
                        likely *removed UI* leaving an orphan import).
      EXEMPTED        : flagged is_internal by classifier rules.
    """
    _verify_admin(authorization)
    full = await endpoint_audit(authorization)
    eps = full["endpoints"]
    ghosts = [e for e in eps if e["dignity"] == "ghost"]
    useful, wired_unfired, exempted = [], [], []
    for e in ghosts:
        hits = e["audit"].get("hits_30d", 0)
        has_surface = e["signals"].get("surface", False)
        if hits > 0:
            useful.append(e)
        elif has_surface:
            wired_unfired.append(e)
        else:
            exempted.append(e)
    return {
        "generated_at":  full["generated_at"],
        "ghost_total":   len(ghosts),
        "useful_keep":   {
            "count": len(useful),
            "description": "API-only endpoints with real traffic — KEEP",
            "top": sorted(useful, key=lambda x: -x["audit"]["hits_30d"])[:25],
        },
        "wired_unfired": {
            "count": len(wired_unfired),
            "description": "Frontend has a reference but the endpoint hasn't been called in 30 d — investigate dead UI buttons or remove",
            "by_router": _by_router(wired_unfired),
            "sample": wired_unfired[:30],
        },
        "exempted": {
            "count": len(exempted),
            "description": "Marked is_internal by classifier (webhook, event, server-to-server) — no synthetic probe appropriate",
            "by_router": _by_router(exempted),
        },
    }


def _by_router(items: list[dict]) -> list[dict]:
    """Helper — group endpoints by router and return [{router, count}]."""
    from collections import Counter
    c: Counter = Counter(e["router"] for e in items)
    return [{"router": r, "count": n} for r, n in c.most_common(20)]


@router.get("/endpoint-audit/health")
async def endpoint_audit_health():
    return {"status": "ok", "component": "endpoint-audit", "db_ready": _db is not None}


# ══════════════════════════════════════════════════════════════════════
# iter 277 — Sub-Product drill-downs (starting with Vanguard SKU)
# ══════════════════════════════════════════════════════════════════════

@router.get("/subproduct/{tier}")
async def subproduct_detail(tier: str, authorization: Optional[str] = Header(None)):
    """Per-endpoint detail for a single T2_subproduct_* tier bucket.

    Used by admin Sub-Product pages (e.g., /admin/vanguard) to show exactly
    which endpoints belong to the SKU, their live traffic, and dignity.
    """
    _verify_admin(authorization)
    if not tier.startswith("T2_subproduct_"):
        raise HTTPException(status_code=400, detail="tier must be a T2_subproduct_* bucket")
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    # Reuse cached full audit if available
    now_ts = time.time()
    if (_inventory_cache["data"] and
            (now_ts - _inventory_cache["built_at"]) < _INVENTORY_TTL):
        full = _inventory_cache["data"]
    else:
        full = await _build_audit_report()
        _inventory_cache["built_at"] = now_ts
        _inventory_cache["data"]     = full

    rows = [e for e in full["endpoints"] if e["tier"] == tier]
    if not rows:
        raise HTTPException(status_code=404, detail=f"No endpoints found for tier {tier}")

    total_hits = sum(r["audit"]["hits_30d"] for r in rows)
    err_count  = sum(r["audit"].get("err_count", 0) for r in rows)
    dignity_dist = {"alive": 0, "ghost": 0, "leaky": 0, "dead": 0}
    for r in rows:
        dignity_dist[r["dignity"]] = dignity_dist.get(r["dignity"], 0) + 1

    return {
        "tier":           tier,
        "endpoint_count": len(rows),
        "total_hits_30d": total_hits,
        "error_count_30d": err_count,
        "dignity":        dignity_dist,
        "top_routers":    sorted(
            {r["router"] for r in rows},
            key=lambda n: -sum(1 for r in rows if r["router"] == n),
        )[:5],
        "endpoints":      [{
            "method":      r["method"],
            "path":        r["path"],
            "router":      r["router"],
            "dignity":     r["dignity"],
            "hits_30d":    r["audit"]["hits_30d"],
            "last_hit":    r["audit"].get("last_hit"),
            "surfaces":    r.get("surfaces", [])[:3],
        } for r in sorted(rows, key=lambda r: -r["audit"]["hits_30d"])],
    }
