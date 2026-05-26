"""
services/onboarding_wallet.py — iter D-32

Shared wallet/project helpers used by the dev CTO chat stream so we can
debit tokens + update project progress without circular imports.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Mirror the constants from routers/onboarding_flow_router.py — kept in
# sync via tests/test_onboarding_constants.py (introduced D-32).
COST_CHEAP_MODEL    = 1
COST_FRONTIER_MODEL = 5

# Progress + manifest hints the AUREM CTO model can emit in its reply.
# - "progress: 0.42"    → set project.progress = 0.42
# - "phase: drafting"   → set project.phase
# - "MANIFEST_PATCH:{…json…}" → shallow-merge into project.manifest
_PROGRESS_RE = re.compile(r"^\s*progress\s*[:=]\s*([01](?:\.\d+)?)\s*$",
                          re.IGNORECASE | re.MULTILINE)
_PHASE_RE    = re.compile(r"^\s*phase\s*[:=]\s*([a-z0-9_-]{2,40})\s*$",
                          re.IGNORECASE | re.MULTILINE)
_MANIFEST_PATCH_START_RE = re.compile(r"MANIFEST_PATCH:\s*", re.IGNORECASE)


def _extract_manifest_json(text: str) -> Optional[dict]:
    """Find `MANIFEST_PATCH: {…}` and return the parsed JSON dict.
    Uses balanced-brace counting so embedded `{}` inside sections work."""
    m = _MANIFEST_PATCH_START_RE.search(text)
    if not m:
        return None
    start = text.find("{", m.end() - 1)
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, min(len(text), start + 8000)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    import json as _json
                    return _json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db():
    """Pull the live db handle from the onboarding router (single source)."""
    from routers import onboarding_flow_router as _onb
    return _onb._db


async def debit_for_chat_turn(*, user_id: str, project_id: str,
                               model_tier: str) -> dict[str, Any]:
    """Atomic conditional decrement. Returns {ok, balance, cost} or
    {ok: False, balance, cost} when the wallet is too low."""
    db = _db()
    cost = COST_FRONTIER_MODEL if model_tier == "frontier" else COST_CHEAP_MODEL
    if db is None:
        # No DB → fail open (chat continues) so dev mode without onboarding
        # router wired doesn't break legacy flows.
        return {"ok": True, "balance": -1, "cost": cost, "skipped": "no_db"}

    # Ensure wallet exists with signup grant on first use.
    existing = await db.onboarding_token_wallets.find_one(
        {"user_id": user_id}, {"_id": 0, "balance": 1},
    )
    if not existing:
        await db.onboarding_token_wallets.insert_one({
            "user_id":    user_id,
            "balance":    1000,
            "lifetime_earned": 1000,
            "lifetime_spent":  0,
            "ledger": [{
                "ts":     _now_iso(),
                "delta":  1000,
                "kind":   "grant_signup",
                "note":   "Welcome — 1000 free tokens to get you started.",
            }],
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        })

    res = await db.onboarding_token_wallets.find_one_and_update(
        {"user_id": user_id, "balance": {"$gte": cost}},
        {
            "$inc": {"balance": -cost, "lifetime_spent": cost},
            "$push": {"ledger": {
                "ts":         _now_iso(),
                "delta":      -cost,
                "kind":       f"debit_{model_tier}",
                "project_id": project_id or None,
                "note":       f"chat turn ({model_tier})",
            }},
            "$set": {"updated_at": _now_iso()},
        },
        projection={"_id": 0, "balance": 1},
        return_document=True,
    )
    if res is None:
        cur = await db.onboarding_token_wallets.find_one(
            {"user_id": user_id}, {"_id": 0, "balance": 1},
        )
        return {"ok": False, "balance": (cur or {}).get("balance", 0),
                "cost": cost}
    return {"ok": True, "balance": res.get("balance", 0), "cost": cost}


async def apply_progress_from_reply(*, user_id: str, project_id: str,
                                     reply_text: str) -> Optional[dict]:
    """Parse the AUREM CTO reply for `progress: 0.XX`, `phase: …`,
    `MANIFEST_PATCH:{…}` markers and PATCH the project doc.

    Returns the updated project dict, or None if nothing changed."""
    db = _db()
    if db is None or not reply_text or not project_id:
        return None

    updates: dict[str, Any] = {}

    m = _PROGRESS_RE.search(reply_text)
    if m:
        try:
            val = float(m.group(1))
            if 0.0 <= val <= 1.0:
                updates["progress"] = val
        except Exception:
            pass

    m = _PHASE_RE.search(reply_text)
    if m:
        updates["phase"] = m.group(1).lower()[:40]

    patch = _extract_manifest_json(reply_text)
    if patch is not None and isinstance(patch, dict):
        drop = {"_id", "user_id", "project_id"}
        updates["__manifest_patch__"] = {
            k: v for k, v in patch.items() if k not in drop
        }

    if not updates:
        return None

    # Build the mongo update payload.
    set_doc: dict[str, Any] = {"updated_at": _now_iso()}
    if "progress" in updates: set_doc["progress"] = updates["progress"]
    if "phase"    in updates: set_doc["phase"]    = updates["phase"]
    manifest_patch = updates.get("__manifest_patch__")
    if manifest_patch:
        for k, v in manifest_patch.items():
            set_doc[f"manifest.{k}"] = v

    return await db.onboarding_projects.find_one_and_update(
        {"project_id": project_id, "user_id": user_id},
        {"$set": set_doc},
        projection={"_id": 0},
        return_document=True,
    )
