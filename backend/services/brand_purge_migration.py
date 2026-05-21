"""
brand_purge_migration.py — iter 325m
============================================================
Idempotent startup migration that rewrites lingering ReRoots
brand strings → AUREM across user/tenant collections.

Why this exists
---------------
The 142-file source-code rebrand (iter 325g) renamed every literal
"ReRoots" → "AUREM" in the codebase. But **persisted strings in Mongo**
(e.g. ``users.company_name = "REROOTS"`` set during the legacy onboarding
flow) were never touched. That's why customers on aurem.live still see
"REROOTS · AURE-ADMIN" in the sidebar avatar — the frontend reads the
user record verbatim.

Strategy
--------
Run on every backend boot (cheap — single regex scan over a handful of
small collections). Updates are case-insensitive whole-token replacements
so things like "ReRoots Plus" → "AUREM Plus" stay coherent. Safe for
green-field DBs (zero matches = zero writes). Logs counts.

Fields scanned per collection:
  users / platform_users / admin_users / aurem_users
      company_name, business_name, full_name, name, display_name
  bins / tenants
      tenant_name, business_name, name, display_name
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Case-insensitive whole-token replacement so "ReRoots", "REROOTS",
# "Reroots", "reroots" all collapse to "AUREM" but words like
# "RerootsCompany" (no boundary) are left alone — those would be flagged
# manually since they're more likely product names than stale brand.
_BRAND_RE = re.compile(r"\b(?:ReRoots|REROOTS|Reroots|reroots|RerootS)\b")

_USER_COLLECTIONS = ("users", "platform_users", "admin_users", "aurem_users")
_USER_FIELDS = ("company_name", "business_name", "full_name",
                "name", "display_name")

_TENANT_COLLECTIONS = ("bins", "tenants")
_TENANT_FIELDS = ("tenant_name", "business_name", "name", "display_name")


def _rewrite(value: Any) -> Tuple[Any, bool]:
    """Return (new_value, changed?). Non-string passthrough."""
    if not isinstance(value, str) or not value:
        return value, False
    new = _BRAND_RE.sub("AUREM", value)
    return new, (new != value)


async def _sweep_collection(db, coll_name: str,
                            fields: Tuple[str, ...]) -> int:
    """Update every doc in ``coll_name`` where any of ``fields`` contains
    a ReRoots-brand token. Returns the number of docs updated."""
    if coll_name not in await db.list_collection_names():
        return 0

    or_clauses = [
        {f: {"$regex": _BRAND_RE.pattern, "$options": ""}}
        for f in fields
    ]
    updates = 0
    cursor = db[coll_name].find({"$or": or_clauses}, {f: 1 for f in fields})
    async for doc in cursor:
        patch: Dict[str, str] = {}
        for f in fields:
            new_val, changed = _rewrite(doc.get(f))
            if changed:
                patch[f] = new_val
        if patch:
            await db[coll_name].update_one({"_id": doc["_id"]},
                                           {"$set": patch})
            updates += 1
            logger.info(
                f"[brand-purge] {coll_name}/{doc['_id']} → "
                + ", ".join(f"{k}={v!r}" for k, v in patch.items())
            )
    return updates


async def run_brand_purge(db) -> Dict[str, int]:
    """Idempotent. Safe to call on every boot. Returns per-collection
    update counts so the caller can log a one-liner summary."""
    if db is None:
        return {}

    counts: Dict[str, int] = {}
    for coll in _USER_COLLECTIONS:
        counts[coll] = await _sweep_collection(db, coll, _USER_FIELDS)
    for coll in _TENANT_COLLECTIONS:
        counts[coll] = await _sweep_collection(db, coll, _TENANT_FIELDS)

    total = sum(counts.values())
    if total:
        logger.info(
            f"[brand-purge] iter 325m — rewrote ReRoots → AUREM in "
            f"{total} doc(s): "
            + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        )
    return counts
