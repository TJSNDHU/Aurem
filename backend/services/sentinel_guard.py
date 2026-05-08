"""
AUREM Sentinel Guard
====================
Non-blocking parallel monitoring layer — "Shadow Guard" mode.

Sits on top of the existing crash_log + self_repair_alerts + system_auto_repairs
collections. Adds three things they don't have:

  1. ERROR FINGERPRINTING + PATTERN RECOGNITION
     Groups similar tracebacks into `error_patterns`. When one pattern fires
     > THRESHOLD times within WINDOW seconds, auto-triggers root_cause_analysis
     which checks: Redis reachable? Mongo reachable? Emergent LLM key valid?

  2. PER-SIDEBAR-ITEM HEARTBEAT
     Aggregates per-item health ("healthy" | "degraded" | "error") from
     self_repair_alerts + error_patterns + recent crash_log entries.

  3. PROACTIVE WHATSAPP ALERT
     When a new P0 pattern emerges, fires one WhatsApp ping to admin with
     the root-cause payload. Rate-limited to prevent spam.

All ops are fire-and-forget — this module NEVER blocks the request path.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_db = None

# Fingerprint-to-last-alert timestamp, prevents WhatsApp spam
_last_alert_at: Dict[str, float] = {}

# Config (kept modest — this is a BG guard, not a stress tester)
PATTERN_THRESHOLD = int(os.environ.get("SENTINEL_PATTERN_THRESHOLD", "3"))
PATTERN_WINDOW_SECONDS = int(os.environ.get("SENTINEL_PATTERN_WINDOW", "900"))  # 15 min
ALERT_COOLDOWN_SECONDS = int(os.environ.get("SENTINEL_ALERT_COOLDOWN", "3600"))  # 1 hr
ADMIN_WHATSAPP = os.environ.get("ADMIN_WHATSAPP", "12265017777")


def set_db(database) -> None:
    global _db
    _db = database


# ─────────────────────────────────────────────────────────────────────
# STEP 1 — Error fingerprinting + pattern recognition
# ─────────────────────────────────────────────────────────────────────

# Strip request IDs, UUIDs, timestamps etc so "same error" groups together.
_NORMALIZE_RX = [
    (re.compile(r"0x[0-9a-fA-F]+"), "0xHEX"),
    (re.compile(r"\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b"), "UUID"),
    (re.compile(r"\d{10,}"), "N"),
    (re.compile(r"/tmp/[^\s:]+"), "/tmp/PATH"),
    (re.compile(r"at 0x[0-9a-fA-F]+"), "at 0xHEX"),
]


def fingerprint(error_type: str, error_msg: str, url: str = "") -> str:
    """Stable short hash for grouping similar errors."""
    norm = f"{error_type}|{url.split('?', 1)[0]}|{error_msg or ''}"
    for rx, sub in _NORMALIZE_RX:
        norm = rx.sub(sub, norm)
    return hashlib.sha256(norm.encode("utf-8", errors="ignore")).hexdigest()[:12]


async def record_error(
    url: str,
    error: Exception,
    error_type: str,
    sidebar_item: Optional[str] = None,
) -> None:
    """
    Fire-and-forget: record an error occurrence, bump pattern count.
    If pattern has fired > THRESHOLD times within WINDOW, schedule a
    root_cause_analysis + WhatsApp alert (still non-blocking).

    NEVER raises — Sentinel must not be able to crash the caller.
    """
    if _db is None:
        return
    try:
        fp = fingerprint(error_type, str(error), url)
        now = datetime.now(timezone.utc)
        window_start = (now - timedelta(seconds=PATTERN_WINDOW_SECONDS)).isoformat()

        doc = await _db["error_patterns"].find_one_and_update(
            {"fingerprint": fp},
            {
                "$setOnInsert": {
                    "fingerprint": fp,
                    "first_seen": now.isoformat(),
                    "error_type": error_type,
                    "sample_message": str(error)[:500],
                    "sample_url": url[:500],
                },
                "$set": {"last_seen": now.isoformat(), "sidebar_item": sidebar_item},
                "$inc": {"total_count": 1},
                "$push": {
                    # Keep a ring-buffer of recent timestamps capped at 200
                    "recent_hits": {
                        "$each": [now.isoformat()],
                        "$slice": -200,
                    },
                },
            },
            upsert=True,
            return_document=True,
        ) or {}

        # Count hits inside the window
        recent = doc.get("recent_hits") or []
        window_hits = sum(1 for ts in recent if ts >= window_start)

        if window_hits >= PATTERN_THRESHOLD:
            # Check cooldown
            last = _last_alert_at.get(fp, 0.0)
            if time.time() - last >= ALERT_COOLDOWN_SECONDS:
                _last_alert_at[fp] = time.time()
                # Schedule RCA + alert as a background task
                asyncio.create_task(_escalate_pattern(fp, window_hits, doc))
    except Exception as e:
        logger.debug(f"[Sentinel] record_error swallowed: {e}")


async def _escalate_pattern(fp: str, hits: int, pattern_doc: Dict) -> None:
    """Run root-cause analysis, fire WhatsApp alert, optionally bridge to Builder."""
    if _db is None:
        return
    try:
        rca = await root_cause_analysis()
        await _db["error_patterns"].update_one(
            {"fingerprint": fp},
            {"$set": {
                "last_rca": rca,
                "last_escalated_at": datetime.now(timezone.utc).isoformat(),
                "last_escalation_hits": hits,
            }},
        )

        # ── Auto-ACK via Builder Bridge ───────────────────────────────────
        # If SENTINEL_AUTO_FIX=1, escalated patterns automatically file a
        # Builder request. Default OFF because we don't want every transient
        # 502 to kick the LLM. Admin opts in by setting the env flag.
        auto_fix = os.environ.get("SENTINEL_AUTO_FIX", "0") == "1"
        if auto_fix:
            try:
                build_info = await _auto_bridge_to_builder(fp, pattern_doc, rca, hits)
                if build_info:
                    await _db["error_patterns"].update_one(
                        {"fingerprint": fp},
                        {"$set": {
                            "auto_fix_build_id": build_info.get("build_id"),
                            "auto_fix_bridged_at": datetime.now(timezone.utc).isoformat(),
                        }},
                    )
            except Exception as bridge_err:
                logger.warning(f"[Sentinel] auto-bridge failed for {fp}: {bridge_err}")

        # ── WhatsApp alert (always sent, cooldown already enforced) ───────
        try:
            from routers.whatsapp_alerts import send_whatsapp
            svc_summary = ", ".join(f"{k}={v}" for k, v in rca.get("services", {}).items())
            bridge_note = " · Builder bridge fired" if auto_fix else ""
            msg = (
                f"SENTINEL: {hits}× {pattern_doc.get('error_type','Error')} in "
                f"{PATTERN_WINDOW_SECONDS//60}min · "
                f"url={pattern_doc.get('sample_url','')[:80]} · "
                f"services={svc_summary}{bridge_note} · fp={fp}"
            )
            await send_whatsapp(ADMIN_WHATSAPP, msg)
        except Exception as alert_err:
            logger.debug(f"[Sentinel] whatsapp alert failed: {alert_err}")
    except Exception as e:
        logger.debug(f"[Sentinel] escalate swallowed: {e}")


async def _auto_bridge_to_builder(fp: str, pattern_doc: Dict, rca: Dict, hits: int) -> Optional[Dict]:
    """
    Convert an escalated error-pattern into an unfixable_issues_queue entry
    AND immediately call the Self-Repair → AUREM Builder bridge.

    Dedupe: if the SAME fingerprint already bridged in the last 6h, skip.
    """
    if _db is None:
        return None

    # 6-hour dedupe — don't refire Builder for the same pattern repeatedly
    existing = await _db["unfixable_issues_queue"].find_one(
        {"fingerprint": fp}, {"_id": 0, "status": 1, "bridged_at": 1}
    )
    if existing and existing.get("status") == "sent_to_builder":
        bridged_at = existing.get("bridged_at")
        if bridged_at:
            try:
                ts = datetime.fromisoformat(bridged_at.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - ts).total_seconds() < 6 * 3600:
                    logger.info(f"[Sentinel] {fp} already bridged <6h ago, skipping")
                    return None
            except Exception:
                pass

    # Upsert into unfixable_issues_queue so the bridge has a document to work on
    now_iso = datetime.now(timezone.utc).isoformat()
    error_type = pattern_doc.get("error_type", "Error")
    sample_url = pattern_doc.get("sample_url") or ""
    sample_msg = pattern_doc.get("sample_message", "")[:300]
    services_str = ", ".join(f"{k}={v}" for k, v in rca.get("services", {}).items())
    sidebar_item = pattern_doc.get("sidebar_item") or "platform"

    issue_doc = {
        "tenant_id": "aurem_self",
        "label": "AUREM Platform (Sentinel)",
        "site_url": sample_url,
        "category": "runtime",
        "severity": "critical" if hits >= PATTERN_THRESHOLD * 2 else "warning",
        "issue": f"Recurring {error_type} on {sidebar_item} ({hits}× in {PATTERN_WINDOW_SECONDS//60}min)",
        "details": f"Sample: {sample_msg} · URL: {sample_url} · RCA services: {services_str}",
        "aurem_solution": (
            f"Inspect the handler serving `{sample_url}` and patch the root cause "
            f"of `{error_type}`. Live RCA shows: {services_str}."
        ),
        "last_seen": now_iso,
        "status": "queued",
        "occurrences": hits,
        "source": "sentinel_auto",
    }

    await _db["unfixable_issues_queue"].update_one(
        {"fingerprint": fp},
        {
            "$set": issue_doc,
            "$setOnInsert": {"fingerprint": fp, "first_seen": now_iso},
        },
        upsert=True,
    )

    # Call the bridge helper (no HTTP hop, no auth needed — same-process)
    from routers.self_repair_router import bridge_issue_to_builder
    full_issue = await _db["unfixable_issues_queue"].find_one({"fingerprint": fp}, {"_id": 0})
    return await bridge_issue_to_builder(
        _db, full_issue, actor_email="sentinel-auto", source="sentinel_guard",
    )


# ─────────────────────────────────────────────────────────────────────
# STEP 2 — Root-cause analysis (service health probe)
# ─────────────────────────────────────────────────────────────────────

async def root_cause_analysis() -> Dict[str, Any]:
    """
    Non-blocking (all probes capped at 0.5s). Returns the live state of the
    dependencies a recurring error most commonly correlates with.
    """
    checks: Dict[str, Any] = {}

    # MongoDB
    try:
        if _db is not None:
            await asyncio.wait_for(_db.command("ping"), timeout=0.5)
            checks["mongodb"] = "ok"
        else:
            checks["mongodb"] = "no_db_handle"
    except Exception:
        checks["mongodb"] = "unreachable"

    # Redis
    try:
        from utils.redis_pool import get_async_redis
        r = await asyncio.wait_for(get_async_redis(), timeout=0.5)
        if r is None:
            checks["redis"] = "fallback_memory"
        else:
            await asyncio.wait_for(r.ping(), timeout=0.3)
            checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unreachable"

    # Emergent LLM key presence (we don't burn a call here — just presence)
    checks["emergent_llm_key"] = "set" if os.environ.get("EMERGENT_LLM_KEY") else "missing"

    # Disk check (non-blocking)
    try:
        import shutil
        total, used, free = shutil.disk_usage("/app")
        pct_free = (free / total) * 100 if total else 0
        checks["disk_free_pct"] = round(pct_free, 1)
        checks["disk_status"] = "ok" if pct_free > 15 else "low"
    except Exception:
        checks["disk_status"] = "unknown"

    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "services": checks,
    }


# ─────────────────────────────────────────────────────────────────────
# STEP 3 — Per-sidebar-item heartbeat
# ─────────────────────────────────────────────────────────────────────

async def sidebar_heartbeat() -> Dict[str, str]:
    """
    Roll up health for each sidebar item:
      - "error":     open P0 pattern or recent crash on this item
      - "degraded":  self-repair alert active OR pattern below threshold
      - "healthy":   no noise in the last window

    Returns {item_id: status}. Items not present means "healthy" by default.
    """
    if _db is None:
        return {}

    since = (datetime.now(timezone.utc) - timedelta(seconds=PATTERN_WINDOW_SECONDS)).isoformat()
    status: Dict[str, str] = {}

    try:
        # Open error patterns touching a sidebar item
        cursor = _db["error_patterns"].find(
            {"last_seen": {"$gte": since}, "sidebar_item": {"$ne": None}},
            {"_id": 0, "sidebar_item": 1, "total_count": 1, "last_escalated_at": 1},
        )
        async for ep in cursor:
            item = ep.get("sidebar_item")
            if not item:
                continue
            is_p0 = bool(ep.get("last_escalated_at"))
            lvl = "error" if is_p0 else "degraded"
            # Worst status wins
            prev = status.get(item)
            if prev is None or (prev == "degraded" and lvl == "error"):
                status[item] = lvl

        # Self-repair alerts keyed by "label" — not per-item, but we expose
        # the platform flag under a pseudo-id "self_repair_alerts" so the
        # UI can paint a global dot if any label is alerting.
        recent_alert = await _db["self_repair_alerts"].find_one(
            {"sent_at": {"$gte": since}},
            {"_id": 0, "sent_at": 1},
            sort=[("sent_at", -1)],
        )
        if recent_alert:
            status.setdefault("self-repair-global", "degraded")
    except Exception as e:
        logger.debug(f"[Sentinel] heartbeat roll-up error: {e}")

    return status


async def get_top_patterns(limit: int = 10) -> List[Dict]:
    """Return the top recurring error patterns (dashboard view)."""
    if _db is None:
        return []
    cursor = _db["error_patterns"].find(
        {}, {"_id": 0, "recent_hits": 0}
    ).sort("last_seen", -1).limit(max(1, min(limit, 50)))
    return await cursor.to_list(limit)


print("[STARTUP] Sentinel Guard loaded — error patterns + per-item heartbeat", flush=True)
