"""
AUREM Admin Links Hub
======================
Aggregates every internal/admin/shareable URL the operator cares about into a
single payload so the admin UI can render a one-stop Links folder:
  - Admin pages (static list)
  - Active Brain Graph snapshots (public share URLs)
  - Case Study PDFs (admin downloads)
  - System Audit PDFs (admin downloads)
  - Customer workspace websites
  - Public shared scan reports
  - Monthly customer reports
  - Public status pages per tenant

All URLs are built against PUBLIC_BASE_URL env (falls back to aurem.live) for
safe sharing on WhatsApp / LinkedIn / etc. Admin-only.
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from typing import List, Dict, Any

router = APIRouter(tags=["Admin Links Hub"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


async def _admin_only(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        import jwt
        payload = jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = (payload.get("role") or "").lower()
    if not (payload.get("is_admin") or role in ("admin", "super_admin", "owner")):
        raise HTTPException(403, "Admin only")
    return payload


def _public_base() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "https://aurem.live").rstrip("/")


# Static admin pages — single source of truth for the admin interface map.
# Keep this list short & useful; don't dump every internal route.
ADMIN_PAGES: List[Dict[str, str]] = [
    {"title": "Mission Control",     "path": "/admin/mission-control",   "description": "Top-level ops dashboard", "icon": "Target"},
    {"title": "Brain Graph",         "path": "/admin/brain-graph",        "description": "Build & share codebase knowledge graph", "icon": "Brain"},
    {"title": "Case Study Builder",  "path": "/admin/case-study",         "description": "Generate board-ready PDF reports", "icon": "FileText"},
    {"title": "System Audit",        "path": "/admin/system-audit",       "description": "Monthly system heartbeat PDFs", "icon": "Activity"},
    {"title": "Hunter E2E Test",     "path": "/admin/hunter-test",        "description": "Fire Email / SMS / WhatsApp pipeline tests", "icon": "Zap"},
    {"title": "Sentinel (Errors)",   "path": "/admin/sentinel",           "description": "Client error feed + AI diagnosis", "icon": "Shield"},
    {"title": "Site Monitor",        "path": "/admin/site-monitor",       "description": "Multi-tenant uptime + alerts", "icon": "Monitor"},
    {"title": "Self-Repair Loop",    "path": "/admin/self-repair",        "description": "Auto-scan sites + live patches", "icon": "Wrench"},
    {"title": "Control Center",      "path": "/admin/control-center",     "description": "Kill switch, flags, toggles", "icon": "Settings"},
    {"title": "Evolver",             "path": "/admin/evolver",            "description": "AI-driven platform evolution feed", "icon": "Sparkles"},
    {"title": "Plan Manager",        "path": "/admin/plans",              "description": "Pricing tiers + subscriptions", "icon": "Package"},
    {"title": "Analytics",           "path": "/admin/analytics",          "description": "Platform analytics dashboard", "icon": "BarChart3"},
    {"title": "Impersonation Log",   "path": "/admin/impersonation-log",  "description": "Audit trail of admin impersonations", "icon": "Eye"},
    {"title": "Wiring Audit",        "path": "/admin/wiring-audit",       "description": "Router-to-page wiring health", "icon": "Network"},
]


async def _brain_graph_links(base: str) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    now = datetime.now(timezone.utc)
    out = []
    try:
        cursor = _db.graph_snapshots.find(
            {"revoked": {"$ne": True}}, {"_id": 0}
        ).sort("created_at", -1).limit(20)
        async for doc in cursor:
            try:
                exp = datetime.fromisoformat((doc.get("expires_at") or "").replace("Z", "+00:00"))
                if exp < now:
                    continue
            except Exception:
                pass
            sid = doc.get("snapshot_id")
            stats = doc.get("stats") or {}
            out.append({
                "id": sid,
                "title": f"Brain Graph · {stats.get('nodes', '?')} nodes",
                "description": doc.get("note") or f"{stats.get('files_scanned', 0)} files, expires {(doc.get('expires_at') or '')[:10]}",
                "url": f"{base}/graph/share/{sid}",
                "is_public": True,
                "can_share": True,
                "created_at": doc.get("created_at"),
            })
    except Exception as e:
        logger.warning(f"[links-hub] brain graph: {e}")
    return out


async def _case_study_links(base: str) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    out = []
    try:
        cursor = _db.case_study_reports.find({}, {"_id": 0}).sort("issued_at", -1).limit(15)
        async for doc in cursor:
            rid = doc.get("report_id")
            if not rid:
                continue
            out.append({
                "id": rid,
                "title": f"Case Study · {doc.get('customer_name') or doc.get('customer_email') or 'tenant'}",
                "description": f"{doc.get('report_type', 'monthly')} · {(doc.get('period_start') or '')[:10]} → {(doc.get('period_end') or '')[:10]}",
                "url": f"{base}/api/admin/case-study/download/{rid}",
                "is_public": False,
                "can_share": False,
                "created_at": doc.get("issued_at"),
            })
    except Exception as e:
        logger.warning(f"[links-hub] case study: {e}")
    return out


async def _system_audit_links(base: str) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    out = []
    try:
        cursor = _db.system_audit_reports.find({}, {"_id": 0}).sort("issued_at", -1).limit(10)
        async for doc in cursor:
            rid = doc.get("report_id")
            if not rid:
                continue
            summary = doc.get("summary_snapshot") or {}
            out.append({
                "id": rid,
                "title": f"System Heartbeat · {(doc.get('issued_at') or '')[:10]}",
                "description": f"{summary.get('loc', '?')} LOC · {summary.get('endpoints', '?')} endpoints · {summary.get('pdf_size_kb', '?')} KB",
                "url": f"{base}/api/admin/case-study/system-audit/download/{rid}",
                "is_public": False,
                "can_share": False,
                "created_at": doc.get("issued_at"),
            })
    except Exception as e:
        logger.warning(f"[links-hub] system audit: {e}")
    return out


async def _customer_sites(base: str) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    out = []
    try:
        cursor = _db.aurem_workspaces.find(
            {"website": {"$exists": True, "$nin": [None, ""]}},
            {"_id": 0, "business_name": 1, "website": 1, "business_id": 1, "tenant_id": 1, "status": 1, "tier": 1}
        ).limit(50)
        async for doc in cursor:
            out.append({
                "id": doc.get("business_id") or doc.get("tenant_id"),
                "title": doc.get("business_name") or "(tenant)",
                "description": f"{(doc.get('tier') or 'trial').title()} · {(doc.get('status') or 'active')}",
                "url": doc.get("website"),
                "is_public": True,
                "can_share": True,
            })
    except Exception as e:
        logger.warning(f"[links-hub] customer sites: {e}")
    return out


async def _status_pages(base: str) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    out = []
    try:
        # Pull unique bins from site_monitor_endpoints
        seen = set()
        cursor = _db.site_monitor_endpoints.find({}, {"_id": 0, "bin": 1, "tenant_id": 1, "tenant_name": 1}).limit(50)
        async for doc in cursor:
            bin_ = doc.get("bin") or doc.get("tenant_id")
            if not bin_ or bin_ in seen:
                continue
            seen.add(bin_)
            out.append({
                "id": bin_,
                "title": f"Public Status · {doc.get('tenant_name') or bin_}",
                "description": "Share-ready uptime status page",
                "url": f"{base}/status/{bin_}",
                "is_public": True,
                "can_share": True,
            })
    except Exception as e:
        logger.warning(f"[links-hub] status pages: {e}")
    return out


async def _shared_scan_reports(base: str) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    out = []
    try:
        cursor = _db.shared_reports.find({}, {"_id": 0}).sort("created_at", -1).limit(15)
        async for doc in cursor:
            sid = doc.get("share_id")
            if not sid:
                continue
            out.append({
                "id": sid,
                "title": f"Audit Report · {doc.get('website_url', 'site')}",
                "description": f"Score {doc.get('overall_score', '?')}/100 · {(doc.get('created_at') or '')[:10]}",
                "url": f"{base}/report/audit/{sid}",
                "is_public": True,
                "can_share": True,
                "created_at": doc.get("created_at"),
            })
    except Exception as e:
        logger.warning(f"[links-hub] shared reports: {e}")
    return out


async def _customer_monthly(base: str) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    out = []
    try:
        cursor = _db.customer_reports.find(
            {"url": {"$exists": True, "$ne": None}}, {"_id": 0}
        ).sort("generated_at", -1).limit(10)
        async for doc in cursor:
            out.append({
                "id": f"{doc.get('bin', '')}_{doc.get('month', '')}",
                "title": doc.get("title") or f"Monthly report · {doc.get('email', '')}",
                "description": f"{doc.get('month', '')} · {doc.get('status', 'draft')}",
                "url": doc.get("url"),
                "is_public": True,
                "can_share": True,
                "created_at": doc.get("generated_at"),
            })
    except Exception as e:
        logger.warning(f"[links-hub] customer reports: {e}")
    return out


@router.get("/api/admin/links-hub")
async def links_hub(authorization: str = Header(None)):
    """Aggregated admin links — folders for every URL the operator uses."""
    await _admin_only(authorization)
    base = _public_base()

    admin_items = [
        {
            "id": p["path"],
            "title": p["title"],
            "description": p["description"],
            "url": f"{base}{p['path']}",
            "icon": p.get("icon"),
            "is_public": False,
            "can_share": False,
        }
        for p in ADMIN_PAGES
    ]

    brain = await _brain_graph_links(base)
    cases = await _case_study_links(base)
    audits = await _system_audit_links(base)
    sites = await _customer_sites(base)
    statuses = await _status_pages(base)
    scans = await _shared_scan_reports(base)
    monthly = await _customer_monthly(base)

    folders = [
        {"key": "admin",       "label": "Admin Pages",          "icon": "Shield",    "items": admin_items},
        {"key": "brain_graph", "label": "Brain Graph Snapshots","icon": "Brain",     "items": brain},
        {"key": "case_study",  "label": "Case Study PDFs",      "icon": "FileText",  "items": cases},
        {"key": "system_audit","label": "System Heartbeat PDFs","icon": "Activity",  "items": audits},
        {"key": "customer_sites","label": "Customer Websites",  "icon": "Globe",     "items": sites},
        {"key": "status_pages","label": "Public Status Pages",  "icon": "Radio",     "items": statuses},
        {"key": "scan_reports","label": "Shared Scan Reports",  "icon": "Search",    "items": scans},
        {"key": "monthly",     "label": "Customer Monthly Reports","icon": "Calendar","items": monthly},
    ]

    # Filter empty folders except the static admin one (always useful)
    folders = [f for f in folders if f["items"] or f["key"] == "admin"]

    total = sum(len(f["items"]) for f in folders)
    return {
        "ok": True,
        "base_url": base,
        "total": total,
        "folder_count": len(folders),
        "folders": folders,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
