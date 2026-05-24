"""
services/data_residency.py — iter 332b Batch C (Step 1)
========================================================

Data residency option: Canadian (default) | US | EU.

For Canadian SMBs especially in healthcare/finance, PIPEDA + provincial
laws (BC PIPA, AB PIPA, Quebec Law 25) require that personal info stay
within Canada or in equivalent jurisdictions. AUREM's MongoDB cluster
already runs in `ca-central-1` by default; this module is the customer-
facing receipt + policy that proves it.

Storage:
  organizations.data_residency = "ca" | "us" | "eu"
  (org owners can request a region change → enterprise_router queues it)

Provides a JSON report we surface in the Enterprise Admin UI + the SOC 2
PDF export. Read-only API; the actual cluster routing lives in the
Mongo connection string + DNS, NOT in code.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


REGION_TABLE = {
    "ca": {
        "name":          "Canada (ca-central-1)",
        "location":      "Montréal, Québec",
        "provider":      "MongoDB Atlas (AWS ca-central-1)",
        "pipeda":        True,
        "law25":         True,
        "hipaa":         True,
        "fedramp":       False,
        "primary":       True,
    },
    "us": {
        "name":          "United States (us-east-1)",
        "location":      "Northern Virginia",
        "provider":      "MongoDB Atlas (AWS us-east-1)",
        "pipeda":        False,
        "law25":         False,
        "hipaa":         True,
        "fedramp":       True,
        "primary":       False,
    },
    "eu": {
        "name":          "European Union (eu-west-1)",
        "location":      "Dublin, Ireland",
        "provider":      "MongoDB Atlas (AWS eu-west-1)",
        "pipeda":        False,
        "law25":         False,
        "hipaa":         False,
        "gdpr":          True,
        "primary":       False,
    },
}


async def get_org_residency(org_id: str) -> Optional[dict]:
    if _db is None:
        return None
    org = await _db.organizations.find_one(
        {"org_id": org_id},
        {"_id": 0, "data_residency": 1, "org_id": 1, "name": 1},
    )
    if not org:
        return None
    region = org.get("data_residency") or "ca"
    info = dict(REGION_TABLE.get(region, REGION_TABLE["ca"]))
    return {
        "org_id":          org["org_id"],
        "org_name":        org.get("name"),
        "region":          region,
        "region_info":     info,
        "effective_since": org.get("residency_set_at") or "2024-01-01T00:00:00+00:00",
    }


async def request_residency_change(
    org_id: str,
    new_region: str,
    requested_by: str,
) -> dict:
    """Customer requests a region move. Logged + queued — actual cluster
    migration is a manual ops step (Atlas snapshot → restore → DNS flip).
    This call does NOT move data immediately."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if new_region not in REGION_TABLE:
        return {"ok": False, "error": "unknown_region"}
    org = await _db.organizations.find_one(
        {"org_id": org_id}, {"_id": 0, "org_id": 1, "data_residency": 1},
    )
    if org is None:
        return {"ok": False, "error": "org_not_found"}
    current = org.get("data_residency") or "ca"
    if current == new_region:
        return {"ok": True, "no_change": True, "region": current}
    # Queue the request — admins handle the actual move.
    await _db.residency_change_requests.insert_one({
        "org_id":       org_id,
        "from_region":  current,
        "to_region":    new_region,
        "requested_by": requested_by,
        "requested_at": _now_iso(),
        "status":       "queued",
    })
    return {"ok": True, "queued": True,
             "from": current, "to": new_region,
             "eta":  "5–10 business days (manual data migration)"}


def system_default_region() -> str:
    """The default region for new orgs. Reads from env so deployments
    in the US/EU can flip the default. Falls back to 'ca'."""
    return (os.environ.get("AUREM_DEFAULT_REGION") or "ca").lower()
