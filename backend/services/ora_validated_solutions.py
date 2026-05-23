"""
services/ora_validated_solutions.py — iter 332a-1 (Parts 3 + 4)

Self-learning memory for ORA's fork_context specialist calls.

The pattern:
  1. ORA hits a task. Before doing real work, hash the (task_type, error,
     file_type) signature and look it up in `ora_validated_solutions`.
  2. If we have a cached solution AND it's been used < 10 times,
     return it directly. Cost = $0. Increment use_count.
  3. If no cache hit, run the specialist (LLM call), then SAVE the
     answer under that signature so the next identical problem is free.
  4. Every call — cache hit or miss — logs a row in
     `ora_specialist_calls` so the cockpit can show real cost rollups.

Public API:
  - compute_signature(task_type, error_message, file_type) → str
  - async lookup_solution(signature)                       → dict | None
  - async save_solution(...)                               → dict
  - async log_specialist_call(...)                         → dict
  - async cost_rollup_7d()                                 → dict
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ── Knobs ────────────────────────────────────────────────────────────
MAX_USES_BEFORE_REVALIDATE = int(os.environ.get("ORA_VS_MAX_USES", "10"))

# Rough $-per-call estimates so the cockpit tile shows something honest
# until we wire in real provider-level usage telemetry. These are upper
# bounds based on OpenRouter pricing observed in 2026Q1.
_ORA_USD_PER_CALL = 0.001  # local LLM via openrouter / deepseek
_EMERGENT_USD_PER_CALL = 0.05  # E1 platform specialist (heavier model)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Signature hashing ────────────────────────────────────────────────

_TRACEBACK_LINE = re.compile(r'File "[^"]+",\s*line\s+\d+,?\s*in\s+\S+')
_HEX_ID         = re.compile(r"\b0x[0-9a-fA-F]{6,}\b")
_NUMERIC_ID     = re.compile(r"\b\d{6,}\b")
_QUOTED_STR     = re.compile(r"'[^']{1,80}'")


def _normalise_error(text: str) -> str:
    """Strip line numbers, memory addresses, request ids etc so two
    different occurrences of the SAME bug hash to the same signature.
    Cap at 2000 chars to keep hashes stable."""
    if not text:
        return ""
    out = text.strip()
    out = _TRACEBACK_LINE.sub("File X, line N, in F", out)
    out = _HEX_ID.sub("0xMEM", out)
    out = _NUMERIC_ID.sub("NUM", out)
    out = _QUOTED_STR.sub("'STR'", out)
    out = re.sub(r"\s+", " ", out)
    return out[:2000]


def compute_signature(task_type: str, error_message: str,
                       file_type: str = "") -> str:
    """SHA256 of the normalised (task_type, error, file_type) triple.

    `file_type` is the file extension or "n/a" — used so a Python null-
    deref doesn't collide with a JS undefined-deref of the same shape.
    """
    norm = _normalise_error(error_message)
    payload = f"{task_type.strip().lower()}\n{file_type.strip().lower()}\n{norm}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Cache lookup + save ──────────────────────────────────────────────

async def lookup_solution(signature: str) -> dict[str, Any] | None:
    """Return the cached solution row (no _id) if one exists AND its
    use_count is below the revalidate threshold. Atomically increments
    use_count + stamps last_used_at on hit."""
    if _db is None or not signature:
        return None
    row = await _db.ora_validated_solutions.find_one_and_update(
        {"signature": signature,
         "use_count": {"$lt": MAX_USES_BEFORE_REVALIDATE}},
        {"$inc": {"use_count": 1},
         "$set": {"last_used_at": _now_iso()}},
        projection={"_id": 0},
        return_document=True,
    )
    if row:
        logger.info(
            f"[validated-solutions] cache HIT sig={signature[:12]}… "
            f"use_count={row.get('use_count')}"
        )
        return row
    return None


async def save_solution(
    *,
    signature: str,
    task_type: str,
    fix_suggestion: str,
    findings: list[str] | None = None,
    files_involved: list[str] | None = None,
    specialist: str = "ora",
    cost_usd: float = 0.0,
) -> dict[str, Any]:
    """Persist a successful specialist answer. Idempotent on
    `signature` — re-saving the same signature only refreshes timestamps."""
    if _db is None or not signature:
        return {"ok": False, "error": "db_or_signature_missing"}
    now = _now_iso()
    update = {
        "$setOnInsert": {
            "signature":      signature,
            "task_type":      task_type,
            "specialist":     specialist,
            "cost_usd":       float(cost_usd),
            "created_at":     now,
            "use_count":      0,
        },
        "$set": {
            "fix_suggestion": (fix_suggestion or "")[:4000],
            "findings":       list(findings or [])[:20],
            "files_involved": list(files_involved or [])[:20],
            "last_updated_at": now,
        },
    }
    r = await _db.ora_validated_solutions.update_one(
        {"signature": signature},
        update,
        upsert=True,
    )
    return {
        "ok":     True,
        "saved":  bool(r.upserted_id) or r.modified_count > 0,
        "is_new": bool(r.upserted_id),
        "signature": signature,
    }


# ── Cost logging ─────────────────────────────────────────────────────

async def log_specialist_call(
    *,
    session_id: str,
    mode: str,
    task_type: str,
    specialist_name: str,
    verdict: str,
    used_validated_solution: bool,
    tokens_used: int = 0,
    cost_usd: float | None = None,
    elapsed_ms: int = 0,
) -> dict[str, Any]:
    """Append a row to ora_specialist_calls. Used by the cockpit tile."""
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    if cost_usd is None:
        if used_validated_solution:
            cost_usd = 0.0
        elif mode == "emergent":
            cost_usd = _EMERGENT_USD_PER_CALL
        else:
            cost_usd = _ORA_USD_PER_CALL
    row = {
        "session_id":              session_id or "",
        "mode":                    mode,
        "task_type":               task_type,
        "specialist_name":         specialist_name or mode,
        "verdict":                 verdict,
        "used_validated_solution": bool(used_validated_solution),
        "tokens_used":             int(tokens_used or 0),
        "cost_usd":                float(cost_usd),
        "elapsed_ms":              int(elapsed_ms or 0),
        "created_at":              _now_iso(),
    }
    await _db.ora_specialist_calls.insert_one(row)
    return {"ok": True, **{k: v for k, v in row.items() if k != "_id"}}


# ── 7-day cost rollup (cockpit tile feed) ───────────────────────────

async def cost_rollup_7d() -> dict[str, Any]:
    """Returns the 7-day Specialist Cost Breakdown for the ORA Cockpit.
    Walks ora_specialist_calls grouped by mode + cache-hit, sums calls
    and USD, and computes 'saved vs naive looping' = the count of
    validated-solution hits × the emergent cost. Doesn't pretend to
    know real Stripe / Emergent invoices — just an honest local roll-up.
    """
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": {"mode": "$mode", "cache": "$used_validated_solution"},
            "calls": {"$sum": 1},
            "usd":   {"$sum": "$cost_usd"},
            "tokens": {"$sum": "$tokens_used"},
        }},
    ]
    buckets = {
        "ora":       {"calls": 0, "usd": 0.0, "tokens": 0},
        "emergent":  {"calls": 0, "usd": 0.0, "tokens": 0},
        "validated": {"calls": 0, "usd_saved": 0.0},
    }
    async for row in _db.ora_specialist_calls.aggregate(pipeline):
        mode  = (row["_id"] or {}).get("mode")  or "ora"
        cache = bool((row["_id"] or {}).get("cache"))
        calls = int(row.get("calls") or 0)
        usd   = float(row.get("usd")   or 0.0)
        toks  = int(row.get("tokens") or 0)
        if cache:
            buckets["validated"]["calls"]     += calls
            # Every cache hit saved ONE emergent-grade call
            buckets["validated"]["usd_saved"] += calls * _EMERGENT_USD_PER_CALL
        elif mode == "emergent":
            buckets["emergent"]["calls"]  += calls
            buckets["emergent"]["usd"]    += usd
            buckets["emergent"]["tokens"] += toks
        else:
            buckets["ora"]["calls"]  += calls
            buckets["ora"]["usd"]    += usd
            buckets["ora"]["tokens"] += toks
    total_spent = round(buckets["ora"]["usd"] + buckets["emergent"]["usd"], 4)
    total_saved = round(buckets["validated"]["usd_saved"], 4)
    return {
        "ok":          True,
        "window_days": 7,
        "ora":         {**buckets["ora"], "usd": round(buckets["ora"]["usd"], 4)},
        "emergent":    {**buckets["emergent"], "usd": round(buckets["emergent"]["usd"], 4)},
        "validated":   {"calls": buckets["validated"]["calls"],
                         "usd_saved": total_saved},
        "total_spent_usd": total_spent,
        "total_saved_usd": total_saved,
        "generated_at": _now_iso(),
    }


__all__ = [
    "set_db",
    "MAX_USES_BEFORE_REVALIDATE",
    "compute_signature",
    "lookup_solution",
    "save_solution",
    "log_specialist_call",
    "cost_rollup_7d",
]
