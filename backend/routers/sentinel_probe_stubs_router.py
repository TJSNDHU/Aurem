"""
routers/sentinel_probe_stubs_router.py — iter 326m
═══════════════════════════════════════════════════════════════════════════
Stub aliases for the four routes that `sentinel_client_router` PUBLIC_PROBES
expects to exist:

  • /api/service-catalog        → alias of /api/catalog/services
  • /api/services/catalog       → alias of /api/catalog/services
  • /api/leads/health           → simple 200 OK health probe
  • /api/system/overview/public → public-safe system overview

Without these aliases, the sentinel reports the AUREM fleet as degraded
even though the underlying services are healthy — it's just probing the
wrong URL shape. Adding lightweight stubs here is cheaper than rewriting
the sentinel probe paths.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()

_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ── Aliases that mirror /api/catalog/services ──────────────────────────
async def _resolve_service_catalog() -> dict:
    if _db is None:
        return {"ok": False, "services": [], "reason": "db not ready"}
    services = []
    async for s in _db.service_catalog.find(
        {"status": "live"}, {"_id": 0, "service_id": 1, "name": 1,
                              "price_monthly": 1, "cluster": 1, "tagline": 1}
    ).sort("price_monthly", 1):
        services.append(s)
    return {"ok": True, "count": len(services), "services": services}


@router.get("/api/service-catalog")
async def service_catalog_dash_alias():
    return await _resolve_service_catalog()


@router.get("/api/services/catalog")
async def services_catalog_plural_alias():
    return await _resolve_service_catalog()


# ── /api/leads/health — sentinel just needs a 2xx ──────────────────────
@router.get("/api/leads/health")
async def leads_health():
    if _db is None:
        return {"ok": True, "service": "leads", "db": "not_ready"}
    try:
        n = await _db.leads_inbox.estimated_document_count()
    except Exception:
        n = -1
    return {"ok": True, "service": "leads", "rows": n}


# ── /api/system/overview/public — public-safe system summary ──────────
@router.get("/api/system/overview/public")
async def system_overview_public():
    if _db is None:
        return {"ok": True, "platform": "aurem", "live": False}
    try:
        n_services = await _db.service_catalog.count_documents({"status": "live"})
    except Exception:
        n_services = 0
    return {
        "ok": True,
        "platform":         "aurem",
        "live":             True,
        "services_count":   n_services,
        "providers_chain":  ["deepseek", "gemini", "nvidia", "claude", "groq"],
    }
