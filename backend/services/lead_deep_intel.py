"""
AUREM Lead Deep-Intel — on-demand Dark Scout enrichment (iter 322n)
====================================================================

Wraps `services.dark_scout_service.run_investigation()` so it can be
fired against ONE specific lead from the admin dashboard. Stores the
result in the ``lead_deep_intel`` collection so the dashboard can
display "Last threat scan: 14h ago — risk_level: LOW" without
re-running the LLM cascade.

Why on-demand and NOT auto-fire?
--------------------------------
Dark Scout is a 30-60 second + 2 LLM-call pipeline (~$0.05/lead). At
production lead volume (50-200 leads/day per active query) that's
$2.50-$10/day per query — fast burn for a "nice to have" intel layer.

The Sovereign architecture: discovery is autonomous + free; **deep
threat intel is opt-in**. Admin clicks the button on a Sovereign-Gold
lead → enriched. No accidental budget drain.

Public API
----------
- ``enrich_lead(db, *, lead_id, lead, preset, tenant_id) -> dict``
- ``get_deep_intel(db, lead_id) -> dict | None``
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


_VALID_PRESETS = {"brand_monitor", "competitor_intel", "breach_detection", "threat_landscape"}


def _build_query(lead: Dict[str, Any]) -> str:
    """Compose the OSINT query string for a lead.

    Prefer the business name; fall back to the website host. We also
    pin the city when present so the surface-web search lands on the
    right local listings (instead of unrelated brands sharing a name).
    """
    name = (lead.get("business_name") or "").strip()
    city = (lead.get("city") or lead.get("address") or "").strip()
    website = (lead.get("website") or "").strip()
    parts = []
    if name:
        parts.append(f'"{name}"')
    if city:
        parts.append(city.split(",")[0].strip())
    if website and not name:
        parts.append(website)
    return " ".join(parts).strip() or "unknown business"


async def enrich_lead(
    db,
    *,
    lead_id: str,
    lead: Dict[str, Any],
    preset: str = "brand_monitor",
    tenant_id: str = "system",
) -> Dict[str, Any]:
    """Fire Dark Scout on a single lead and persist the verdict.

    Returns the persisted intel doc shape:
        {
          lead_id, query, preset, tenant_id, ts,
          risk_level, analysis, source_count, status,
        }
    Never raises — failures roll up into ``status: "failed"`` so the
    admin UI can show the error inline without 500-ing the request.
    """
    if not lead_id:
        return {"status": "failed", "error": "lead_id_required"}
    if preset not in _VALID_PRESETS:
        preset = "brand_monitor"

    query = _build_query(lead or {})
    started = datetime.now(timezone.utc)

    intel: Dict[str, Any] = {
        "lead_id": lead_id,
        "query": query,
        "preset": preset,
        "tenant_id": tenant_id,
        "ts": started.isoformat(),
        "risk_level": "UNKNOWN",
        "analysis": "",
        "source_count": 0,
        "status": "running",
    }

    try:
        from services.dark_scout_service import run_investigation
        out = await run_investigation(
            query=query, tenant_id=tenant_id, preset=preset, max_results=10,
        )
        intel.update({
            "status": out.get("status") or "completed",
            "risk_level": out.get("risk_level") or "UNKNOWN",
            "analysis": (out.get("analysis") or "")[:4000],
            "source_count": int(out.get("scraped_pages") or 0),
            "investigation_id": out.get("investigation_id"),
            "elapsed_ms": int(
                (datetime.now(timezone.utc) - started).total_seconds() * 1000,
            ),
        })
    except Exception as e:
        logger.warning(f"[deep-intel] enrichment failed for {lead_id}: {e}")
        intel.update({"status": "failed", "error": str(e)[:200]})

    if db is not None:
        try:
            await db.lead_deep_intel.update_one(
                {"lead_id": lead_id},
                {"$set": intel},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"[deep-intel] persist failed: {e}")

    return intel


async def get_deep_intel(db, lead_id: str) -> Optional[Dict[str, Any]]:
    """Read the latest persisted intel for a lead. Returns None when
    the lead has never been enriched."""
    if db is None or not lead_id:
        return None
    try:
        return await db.lead_deep_intel.find_one(
            {"lead_id": lead_id}, {"_id": 0},
        )
    except Exception:
        return None
