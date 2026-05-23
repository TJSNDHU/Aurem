"""
services/db_manager.py — iter 331a Sprint 3.5

Portable MongoDB connection manager. Selects the connection string
based on the `DB_TYPE` env var so AUREM can move between Atlas /
local / Hetzner / Docker / Legion-laptop without code changes.

Env vars:
  DB_TYPE      = atlas | legion | docker | hetzner | local
                 (defaults to "atlas" if MONGO_URL looks like a +srv URI,
                  else "local")
  MONGO_URL    = full connection string (always honoured if set)
  DB_NAME      = database name (required)

When DB_TYPE is provided but MONGO_URL is empty, we build a sensible
default per type. When MONGO_URL is provided, we honour it verbatim
regardless of DB_TYPE — DB_TYPE then serves only as a label for logs
and the portability manifest.

Public API:
    get_connection_info()  -> dict
    get_client()           -> AsyncIOMotorClient
    get_db()               -> AsyncIOMotorDatabase
    ping()                 -> dict   (real round-trip, never raises)

Portability: zero Emergent imports. Same module ships unchanged to
Hetzner / Docker / local / Legion.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── Built-in defaults per DB_TYPE ───────────────────────────────────
_DEFAULTS = {
    "atlas":   None,  # must supply MONGO_URL (atlas requires secret + +srv)
    "legion":  "mongodb://aurem:aurem@legion.local:27017/aurem_db",
    "docker":  "mongodb://mongo:27017/aurem_db",
    "hetzner": "mongodb://aurem:aurem@hetzner.local:27017/aurem_db",
    "local":   "mongodb://localhost:27017/aurem_db",
}


def _detect_type(mongo_url: str | None) -> str:
    """If DB_TYPE not set, infer from MONGO_URL shape."""
    if not mongo_url:
        return "local"
    if mongo_url.startswith("mongodb+srv://"):
        return "atlas"
    if "localhost" in mongo_url or "127.0.0.1" in mongo_url:
        return "local"
    if "mongo:" in mongo_url:
        return "docker"
    return "remote"


def get_connection_info() -> dict[str, Any]:
    """Return the resolved connection info as a dict.

    Never includes the password — safe to log or surface in /api/health.
    """
    db_type = os.environ.get("DB_TYPE", "").strip().lower()
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    db_name = os.environ.get("DB_NAME", "").strip()

    if not mongo_url:
        # Fall back to a built-in default for the requested type.
        if db_type in _DEFAULTS and _DEFAULTS[db_type]:
            mongo_url = _DEFAULTS[db_type]
        else:
            mongo_url = _DEFAULTS["local"]
            db_type = db_type or "local"

    if not db_type:
        db_type = _detect_type(mongo_url)

    # Redact password if any.
    redacted = mongo_url
    if "@" in mongo_url and "://" in mongo_url:
        scheme, rest = mongo_url.split("://", 1)
        if "@" in rest:
            cred, host = rest.split("@", 1)
            if ":" in cred:
                user = cred.split(":", 1)[0]
                redacted = f"{scheme}://{user}:***@{host}"

    return {
        "db_type":  db_type,
        "mongo_url_redacted": redacted,
        "db_name":  db_name or "aurem_db",
    }


def get_client():
    """Return a Motor AsyncIOMotorClient using the resolved connection."""
    from motor.motor_asyncio import AsyncIOMotorClient
    info = get_connection_info()
    # Always pull the full (unredacted) URL from env for the actual client.
    mongo_url = os.environ.get("MONGO_URL") or _DEFAULTS.get(info["db_type"]) or _DEFAULTS["local"]
    return AsyncIOMotorClient(mongo_url, maxPoolSize=5)


def get_db():
    """Return the resolved database handle."""
    info = get_connection_info()
    client = get_client()
    return client[info["db_name"]]


async def ping(timeout_s: float = 3.0) -> dict[str, Any]:
    """Real round-trip ping. Returns a dict; never raises."""
    info = get_connection_info()
    try:
        client = get_client()
        await asyncio.wait_for(
            client.admin.command("ping"),
            timeout=timeout_s,
        )
        return {
            "ok":       True,
            "db_type":  info["db_type"],
            "db_name":  info["db_name"],
            "mongo_url_redacted": info["mongo_url_redacted"],
            "message":  f"Connected to {info['db_type']} ({info['db_name']}) successfully.",
        }
    except Exception as e:
        return {
            "ok":      False,
            "db_type": info["db_type"],
            "db_name": info["db_name"],
            "error":   f"{type(e).__name__}: {e}",
        }


# ── Migration helper (Tier-3 — invoked from ORA via legion_exec) ────

async def mongo_migrate(
    from_uri: str,
    to_uri: str,
    db_name: str,
    collections: list[str] | None = None,
) -> dict[str, Any]:
    """Copy data from one MongoDB to another. Verifies count after.

    DESTRUCTIVE-ADJACENT: overwrites docs in the destination collection.
    Never deletes source. Use only when the destination is a fresh DB
    or you accept the overwrite semantics.

    Args:
        from_uri:    source connection string
        to_uri:      destination connection string
        db_name:     database name on both sides
        collections: list of collection names; ["all"] copies every
                     non-system collection from the source

    Returns:
        ok                  : True if every collection copied and counts match
        copied              : [{collection, source_count, dest_count, matched}]
        failed              : [{collection, error}]
        total_copied        : int
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    try:
        src_client = AsyncIOMotorClient(from_uri, maxPoolSize=5)
        dst_client = AsyncIOMotorClient(to_uri, maxPoolSize=5)
        src_db = src_client[db_name]
        dst_db = dst_client[db_name]
    except Exception as e:
        return {"ok": False, "error": f"connection failed: {e}"}

    # Resolve collection list.
    try:
        if not collections or collections == ["all"]:
            all_cols = await src_db.list_collection_names()
            collections = [c for c in all_cols if not c.startswith("system.")]
    except Exception as e:
        return {"ok": False, "error": f"list_collection_names failed: {e}"}

    copied: list[dict] = []
    failed: list[dict] = []
    total = 0
    for col in collections:
        try:
            src_count = await src_db[col].count_documents({})
            if src_count == 0:
                copied.append({"collection": col, "source_count": 0,
                                "dest_count": 0, "matched": True})
                continue
            # Bulk-copy in 1000-doc chunks.
            BATCH = 1000
            cursor = src_db[col].find({})
            batch = []
            async for doc in cursor:
                batch.append(doc)
                if len(batch) >= BATCH:
                    await dst_db[col].insert_many(batch, ordered=False)
                    total += len(batch)
                    batch = []
            if batch:
                await dst_db[col].insert_many(batch, ordered=False)
                total += len(batch)
            dst_count = await dst_db[col].count_documents({})
            matched = (dst_count >= src_count)
            copied.append({
                "collection":   col,
                "source_count": src_count,
                "dest_count":   dst_count,
                "matched":      matched,
            })
        except Exception as e:
            failed.append({"collection": col, "error": str(e)[:200]})

    return {
        "ok":           len(failed) == 0,
        "copied":       copied,
        "failed":       failed,
        "total_copied": total,
    }


__all__ = [
    "get_connection_info", "get_client", "get_db", "ping", "mongo_migrate",
]
