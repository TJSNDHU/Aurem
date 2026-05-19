"""
Auth-critical MongoDB indexes — iter 324f
─────────────────────────────────────────
Run at startup. Idempotent — `create_index` is a no-op if the index
already exists with the same spec.

Without these indexes, every login does a full collection scan on
`users.find_one({"email": ...})` and friends. As collections grow,
login latency degrades linearly with collection size.

With these indexes:
  • users.email                 → B-tree, <5ms per lookup
  • platform_users.email        → B-tree, <5ms
  • team_members.email          → B-tree, <5ms
  • failed_login_attempts (TTL) → auto-expire after 30 min
  • campaign_leads (composite)  → speeds up the auto-blast engine's
                                   `_eligible_leads` scan
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def ensure_auth_indexes(db) -> Dict[str, Any]:
    """Create login-critical indexes. Returns {"ok": N, "errors": N, "detail": {...}}.

    Safe to call multiple times — `create_index` is idempotent when the
    target spec already exists. Logs each index creation at INFO level.
    """
    results: Dict[str, str] = {}

    # (collection, key_spec, kwargs)
    specs = [
        # ── Login lookups ────────────────────────────────────────────
        ("users",          [("email",   1)], {"unique": True,  "sparse": True, "name": "email_unique"}),
        ("users",          [("phone",   1)], {"sparse": True,                  "name": "phone_idx"}),
        ("users",          [("user_id", 1)], {"unique": True,  "sparse": True, "name": "user_id_unique"}),
        ("platform_users", [("email",   1)], {"unique": True,  "sparse": True, "name": "email_unique"}),
        ("team_members",   [("email",   1)], {"sparse": True,                  "name": "email_idx"}),
        ("team_members",   [("role_id", 1)], {"sparse": True,                  "name": "role_id_idx"}),
        ("roles",          [("id",      1)], {"unique": True,  "sparse": True, "name": "id_unique"}),
        # ── Login-lockout TTL (30 min auto-cleanup) ──────────────────
        ("failed_login_attempts", [("created_at", 1)],
            {"expireAfterSeconds": 1800, "sparse": True, "name": "ttl_cleanup"}),
        ("failed_login_attempts", [("identifier", 1)],
            {"sparse": True, "name": "identifier_idx"}),
        # ── Campaign blast engine perf ───────────────────────────────
        ("campaign_leads", [("status", 1), ("noise_flag", 1)],
            {"name": "status_noise_idx"}),
        ("campaign_leads", [("last_blast_at", 1)],
            {"sparse": True, "name": "blast_at_idx"}),
    ]

    for coll_name, keys, kwargs in specs:
        try:
            await db[coll_name].create_index(keys, **kwargs)
            label = f"{coll_name}.{kwargs.get('name', keys)}"
            results[label] = "ok"
            logger.info(f"[auth-indexes] ✓ {coll_name} {keys}")
        except Exception as e:
            err = str(e)
            label = f"{coll_name}.{kwargs.get('name', keys)}"
            if "already exists" in err.lower() or "IndexOptionsConflict" in err:
                results[label] = "already_exists"
            else:
                results[label] = f"error: {err[:90]}"
                logger.warning(f"[auth-indexes] ✗ {coll_name} {keys}: {err[:120]}")

    ok = sum(1 for v in results.values() if v in ("ok", "already_exists"))
    errs = len(results) - ok
    logger.info(f"[auth-indexes] complete — {ok} ok, {errs} errors")
    return {"ok": ok, "errors": errs, "detail": results}
