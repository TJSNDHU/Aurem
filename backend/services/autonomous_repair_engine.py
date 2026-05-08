"""
Autonomous Repair Engine — iter 281
═══════════════════════════════════════════════════════════════════════

"Living Machine" auto-heal loop. Runs every AUTO_REPAIR_INTERVAL_SEC inside
Pillar 4 worker. Zero human intervention on Tier 1 & Tier 2 actions.

Flow (each tick):
  1. Sample /api/admin/pillars-map/overview (via internal call — skip HTTP)
  2. If sentinel_overlay.verdict in {"yellow","red"} → enter repair cycle
  3. Classify top error signatures from db.client_errors (last 1 h)
  4. Dispatch AUTONOMOUS actions by classification:

        Classification              Tier  Action
        ───────────────────────────  ────  ──────────────────────────────
        stale_preview_pod            1     purge drift cache (no code chg)
        chunk_load_error             2     queue pixel patch (SW purge)
        rate_limited_429             1     reset deployment rate-limiter
        auth_token_expired           0     no-op (user flow; safe skip)
        backend_5xx                  1     restart matching P* scheduler
        sentinel_anomaly_critical    1     purge pillars-map cache
        unknown                      3     NOTIFY ONLY (needs human code)

  5. Verify — 10 min later, re-check errors_1h. If dropped below warm
     threshold → success. Else mark failed, notify.
  6. Every event logged to db.autonomous_repair_events (audit trail).

Safety gates:
  • Global kill switch: db.system_config.{"config_key":"autonomous_repair","enabled":bool}
  • Per-cycle cooldown: MIN_CYCLE_GAP_SEC
  • Per-action rate limit: MAX_ACTIONS_PER_HOUR
  • Tier 3 ("write code") actions are STAGED ONLY — written to
    db.pending_code_fixes awaiting human approval (never auto-deploy).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Tunables ──────────────────────────────────────────────────────────
AUTO_REPAIR_INTERVAL_SEC = int(os.environ.get("AUTO_REPAIR_INTERVAL_SEC", "120"))   # 2 min
MIN_CYCLE_GAP_SEC       = int(os.environ.get("AUTO_REPAIR_MIN_GAP_SEC", "60"))     # cooldown between cycles
MAX_ACTIONS_PER_HOUR    = int(os.environ.get("AUTO_REPAIR_MAX_PER_HOUR", "12"))    # safety cap
VERIFY_WAIT_SEC         = int(os.environ.get("AUTO_REPAIR_VERIFY_WAIT_SEC", "600"))  # 10 min
EVENTS_COLLECTION       = "autonomous_repair_events"
CONFIG_KEY              = "autonomous_repair"

_db = None
_last_cycle_mono: float = 0.0
_recent_actions: List[float] = []  # monotonic timestamps for rate limiter
_pause_flag: bool = False


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def is_enabled() -> bool:
    """Read config from DB. Default ON unless explicitly paused."""
    if _pause_flag:
        return False
    if _db is None:
        return False
    try:
        doc = await _db.system_config.find_one(
            {"config_key": CONFIG_KEY}, {"_id": 0}
        )
        if not doc:
            return True  # default ON
        return bool(doc.get("enabled", True))
    except Exception:
        return True


async def set_enabled(flag: bool, actor: str = "system") -> Dict[str, Any]:
    """Toggle autonomous loop globally."""
    global _pause_flag
    _pause_flag = not flag
    if _db is not None:
        try:
            await _db.system_config.update_one(
                {"config_key": CONFIG_KEY},
                {
                    "$set": {
                        "config_key": CONFIG_KEY,
                        "enabled": flag,
                        "updated_by": actor,
                        "updated_at": _now().isoformat(),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.warning("[auto-repair] persist toggle failed: %s", e)
    return {"enabled": flag, "updated_by": actor, "updated_at": _now().isoformat()}


def _rate_ok() -> bool:
    """Discard timestamps older than 1h; return True if under cap."""
    cutoff = time.monotonic() - 3600
    _recent_actions[:] = [t for t in _recent_actions if t >= cutoff]
    return len(_recent_actions) < MAX_ACTIONS_PER_HOUR


def _mark_action() -> None:
    _recent_actions.append(time.monotonic())


async def _log_event(doc: Dict[str, Any]) -> None:
    if _db is None:
        return
    doc.setdefault("ts", _now())
    doc.setdefault("ts_iso", _now().isoformat())
    try:
        await _db[EVENTS_COLLECTION].insert_one(doc)
    except Exception as e:
        logger.debug("[auto-repair] event log failed: %s", e)


# ── Sentinel state reader (in-process, no HTTP) ───────────────────────

async def _read_overlay() -> Dict[str, Any]:
    try:
        from routers.pillars_map_router import _fetch_sentinel_overlay
        return await _fetch_sentinel_overlay()
    except Exception as e:
        logger.warning("[auto-repair] overlay read failed: %s", e)
        return {"verdict": "green", "errors_1h": 0}


async def _top_signatures(limit: int = 3) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    cutoff = _now() - timedelta(hours=1)
    pipeline = [
        {"$match": {"ts": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$signature_hash",
            "count": {"$sum": 1},
            "classification": {"$last": "$classification"},
            "url": {"$last": "$url"},
            "sample_message": {"$last": "$message"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    sigs = []
    try:
        async for d in _db.client_errors.aggregate(pipeline):
            sigs.append({
                "signature_hash": d["_id"],
                "count": d["count"],
                "classification": d.get("classification") or "unknown",
                "url": d.get("url") or "",
                "sample": (d.get("sample_message") or "")[:300],
            })
    except Exception as e:
        logger.debug("[auto-repair] signature agg failed: %s", e)
    return sigs


# ── Tier 1 & 2 fix actions ────────────────────────────────────────────

async def _action_purge_pillars_cache() -> Dict[str, Any]:
    from routers.pillars_map_router import set_cached_snapshot
    set_cached_snapshot({})  # force next /heartbeat to cold-rebuild
    return {"ok": True, "action": "purge_pillars_cache"}


async def _action_purge_drift_cache() -> Dict[str, Any]:
    try:
        from routers.deploy_drift_router import _CACHE
        _CACHE["ts"] = 0.0
        _CACHE["payload"] = None
        return {"ok": True, "action": "purge_drift_cache"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "action": "purge_drift_cache"}


async def _action_reset_rate_limiter() -> Dict[str, Any]:
    """Reset deployment rate-limiter so flagged businesses can deploy fixes."""
    try:
        from services.deployment_router import _rate_limiter
        # AsyncioLockLimiter exposes ._counts dict; safe no-op for redis impl
        if hasattr(_rate_limiter, "_counts"):
            _rate_limiter._counts.clear()  # type: ignore[attr-defined]
            return {"ok": True, "action": "reset_rate_limiter"}
        return {"ok": True, "action": "reset_rate_limiter", "note": "non-local limiter; skipped"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "action": "reset_rate_limiter"}


async def _action_queue_pixel_patch(
    classification: str, sig: Dict[str, Any]
) -> Dict[str, Any]:
    """Tier 2 — queue a pixel patch for the affected URL. Canary-gated."""
    if _db is None:
        return {"ok": False, "error": "db_unset", "action": "queue_pixel_patch"}
    # Determine tenant by matching the URL to platform_connections if possible
    tenant_id = "aurem_platform"  # fallback — AUREM's own site
    patch_id = f"autopatch_{int(time.time())}_{sig['signature_hash'][:8]}"
    doc = {
        "id": patch_id,
        "tenant_id": tenant_id,
        "type": classification,
        "target_url": sig.get("url", ""),
        "instruction": {
            "chunk_load_error": "force_sw_purge",
            "stale_preview_pod": "force_origin_rewrite",
        }.get(classification, "soft_reload"),
        "reason_signature": sig["signature_hash"],
        "status": "pending",
        "canary_pct": 10,
        "created_at": _now().isoformat(),
        "created_by": "autonomous_repair_engine",
    }
    try:
        await _db.pending_pixel_patches.insert_one(doc)
        return {"ok": True, "action": "queue_pixel_patch", "patch_id": patch_id}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "action": "queue_pixel_patch"}


async def _action_stage_code_fix(
    classification: str, sig: Dict[str, Any]
) -> Dict[str, Any]:
    """Tier 3 — STAGE ONLY. Never auto-deploys. Writes to pending_code_fixes
    queue for human review. AI code generation via EMERGENT_LLM_KEY."""
    if _db is None:
        return {"ok": False, "error": "db_unset", "action": "stage_code_fix"}
    fix_id = f"codefix_{int(time.time())}_{sig['signature_hash'][:8]}"
    # Proposed commit message — prefixed with [auto-heal] so the GitHub
    # workflow (`.github/workflows/deploy-reminder.yml`) detects it and
    # fires the Emergent deploy webhook on approval.
    commit_msg = (
        f"[auto-heal] {classification}: "
        f"{(sig.get('sample','') or '').splitlines()[0][:80]} "
        f"(sig={sig['signature_hash'][:8]}, count={sig.get('count',0)})"
    )
    doc = {
        "id": fix_id,
        "classification": classification,
        "signature_hash": sig["signature_hash"],
        "sample_message": sig.get("sample", ""),
        "occurrences_1h": sig.get("count", 0),
        "url": sig.get("url", ""),
        "status": "needs_human_review",
        "commit_message": commit_msg,
        "staged_at": _now().isoformat(),
        "staged_by": "autonomous_repair_engine",
        "note": "Claude diagnose + propose queued separately by AI Diagnose flow",
    }
    try:
        await _db.pending_code_fixes.insert_one(doc)
        return {"ok": True, "action": "stage_code_fix", "fix_id": fix_id, "staged": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "action": "stage_code_fix"}


# ── Classification → Action dispatch ──────────────────────────────────

async def _dispatch_for_signature(sig: Dict[str, Any]) -> Dict[str, Any]:
    c = (sig.get("classification") or "unknown").lower()
    # iter 285.7 — user_abort / signal aborted is non-actionable noise
    sample = str(sig.get("sample") or "").lower()
    if "signal is aborted" in sample or "aborterror" in sample or c == "user_abort":
        return {"ok": True, "action": "dismiss_user_abort_noise",
                "reason": "Fetch aborted by component unmount / navigation — not a real failure"}
    if c == "stale_preview_pod":
        return await _action_purge_drift_cache()
    if c == "chunk_load_error":
        return await _action_queue_pixel_patch(c, sig)
    if c == "rate_limited_429":
        return await _action_reset_rate_limiter()
    if c == "auth_token_expired":
        return {"ok": True, "action": "noop_user_flow"}
    if c in ("backend_5xx", "sentinel_anomaly_critical"):
        return await _action_purge_pillars_cache()
    # Unknown / novel → Tier 3 (human-gated code fix staging)
    return await _action_stage_code_fix(c, sig)


# ── Self-reporting (Resend + event log) ───────────────────────────────

async def _notify(subject: str, html: str) -> None:
    try:
        import resend
        key = os.environ.get("RESEND_API_KEY", "")
        notify = os.environ.get("AUREM_NOTIFY_EMAIL") or os.environ.get("RESEND_NOTIFY_EMAIL")
        if not key or not notify:
            return
        resend.api_key = key
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>"),
            "to": [notify],
            "subject": subject,
            "html": html,
        })
    except Exception as e:
        logger.debug("[auto-repair] notify failed: %s", e)


# ── Core cycle ────────────────────────────────────────────────────────

async def _verify_recovery(before_errors: int) -> Dict[str, Any]:
    """Sleep VERIFY_WAIT_SEC then re-check. Never blocks scheduler — spawn."""
    await asyncio.sleep(VERIFY_WAIT_SEC)
    after = await _read_overlay()
    recovered = after.get("errors_1h", before_errors) < max(5, before_errors // 2)
    await _log_event({
        "event": "verify",
        "recovered": recovered,
        "errors_before": before_errors,
        "errors_after": after.get("errors_1h", 0),
        "verdict_after": after.get("verdict"),
    })
    # iter 283 — Truth Ledger: record honest outcome
    try:
        from services import truth_ledger
        if recovered:
            await truth_ledger.record_success(
                actor="autonomous_repair_engine",
                description=f"auto-heal verified: errors {before_errors}→{after.get('errors_1h', 0)}",
                evidence={"errors_before": before_errors,
                          "errors_after": after.get("errors_1h", 0),
                          "verdict_after": after.get("verdict")},
                outcome="healed",
            )
        else:
            await truth_ledger.record_insufficient_recovery(
                actor="autonomous_repair_engine",
                description=f"auto-heal did NOT fully recover: errors {before_errors}→{after.get('errors_1h', 0)}",
                evidence={"errors_before": before_errors,
                          "errors_after": after.get("errors_1h", 0),
                          "verdict_after": after.get("verdict")},
                outcome="escalated",
            )
    except Exception as _tl:
        logger.debug("[auto-repair] truth_ledger write failed: %s", _tl)
    if recovered:
        await _notify(
            "AUREM · Autonomous Repair succeeded",
            f"<p>Errors dropped from <b>{before_errors}</b> to <b>{after.get('errors_1h', 0)}</b> after auto-heal cycle.</p><p>Verdict: {after.get('verdict')}</p>",
        )
    else:
        await _notify(
            "AUREM · Autonomous Repair insufficient — escalation",
            f"<p>Auto-heal cycle ran but errors remain at <b>{after.get('errors_1h', 0)}</b>.</p><p>Human review required. Check <a href='https://aurem.live/admin/pillars-map'>Pillars Map</a>.</p>",
        )
    return {"recovered": recovered, "after": after}


async def run_cycle_once() -> Dict[str, Any]:
    """Public entrypoint — admin 'Trigger Now' calls this directly.
    Wrapped in zero-downtime-repair (ZDR) so a fix never tears down the
    main API. ZDR adds: health gate, Redis snapshot, shielded apply,
    auto-restore."""
    if _db is None:
        return await _run_cycle_once_inner()
    from services.zero_downtime_repair import run_with_zdr
    out = await run_with_zdr(
        _run_cycle_once_inner,
        label="autonomous_repair_cycle",
        db=_db,
        max_wait_s=60,
        timeout_s=180,
    )
    inner = out.get("result") if isinstance(out.get("result"), dict) else {}
    return {**inner, "zdr": {
        "ok": out.get("ok"), "elapsed_s": out.get("elapsed_s"),
        "gate": out.get("gate"), "restore": out.get("restore"),
    }}


async def _run_cycle_once_inner() -> Dict[str, Any]:
    global _last_cycle_mono

    if not await is_enabled():
        return {"skipped": True, "reason": "paused"}

    now = time.monotonic()
    if now - _last_cycle_mono < MIN_CYCLE_GAP_SEC:
        return {"skipped": True, "reason": "cooldown",
                "next_allowed_in": int(MIN_CYCLE_GAP_SEC - (now - _last_cycle_mono))}

    overlay = await _read_overlay()
    verdict = overlay.get("verdict", "green")
    if verdict == "green":
        return {"skipped": True, "reason": "green", "overlay": overlay}

    if not _rate_ok():
        await _log_event({"event": "rate_capped", "overlay": overlay})
        return {"skipped": True, "reason": "rate_limit_hit",
                "max_per_hour": MAX_ACTIONS_PER_HOUR}

    _last_cycle_mono = now
    signatures = await _top_signatures(limit=3)
    actions: List[Dict[str, Any]] = []
    for sig in signatures:
        res = await _dispatch_for_signature(sig)
        res["signature_hash"] = sig["signature_hash"]
        res["classification"] = sig["classification"]
        res["count"] = sig["count"]
        actions.append(res)
        _mark_action()
        if not _rate_ok():
            break

    cycle_doc = {
        "event": "cycle",
        "trigger_verdict": verdict,
        "errors_1h_before": overlay.get("errors_1h", 0),
        "signatures_handled": len(actions),
        "actions": actions,
    }
    await _log_event(cycle_doc)

    # Self-report
    sum_ok = sum(1 for a in actions if a.get("ok"))
    li_items = "".join(
        f"<li><code>{a.get('classification','?')}</code> → "
        f"{a.get('action','?')} · "
        f"{('OK' if a.get('ok') else 'FAIL')}</li>"
        for a in actions
    )
    await _notify(
        f"AUREM · Autonomous repair triggered (verdict={verdict})",
        f"<p>Handled <b>{len(actions)}</b> signatures · <b>{sum_ok}</b> succeeded.</p>"
        f"<ul>{li_items}</ul>"
        f"<p>Verification will run in {VERIFY_WAIT_SEC // 60} min.</p>",
    )

    # Fire-and-forget verify (non-blocking)
    asyncio.create_task(_verify_recovery(overlay.get("errors_1h", 0)))

    return {
        "ok": True,
        "verdict": verdict,
        "signatures": len(signatures),
        "actions_ran": len(actions),
        "actions_ok": sum_ok,
        "cycle_ts": cycle_doc.get("ts_iso"),
    }


async def autonomous_repair_scheduler() -> None:
    """Long-running loop attached to P4 worker."""
    logger.info(
        "[auto-repair] scheduler started — interval=%ss, min_gap=%ss, cap=%s/hr",
        AUTO_REPAIR_INTERVAL_SEC, MIN_CYCLE_GAP_SEC, MAX_ACTIONS_PER_HOUR,
    )
    while True:
        try:
            result = await run_cycle_once()
            if not result.get("skipped"):
                logger.info("[auto-repair] cycle ran: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[auto-repair] tick failed: %s", e)
        await asyncio.sleep(AUTO_REPAIR_INTERVAL_SEC)


async def status_snapshot() -> Dict[str, Any]:
    enabled = await is_enabled()
    cfg_doc = None
    if _db is not None:
        try:
            cfg_doc = await _db.system_config.find_one(
                {"config_key": CONFIG_KEY}, {"_id": 0}
            )
        except Exception:
            pass
    actions_last_hr = len(_recent_actions)
    return {
        "enabled": enabled,
        "paused_in_memory": _pause_flag,
        "config": cfg_doc,
        "interval_sec": AUTO_REPAIR_INTERVAL_SEC,
        "min_gap_sec": MIN_CYCLE_GAP_SEC,
        "max_actions_per_hour": MAX_ACTIONS_PER_HOUR,
        "actions_last_hour": actions_last_hr,
        "rate_capacity_remaining": max(0, MAX_ACTIONS_PER_HOUR - actions_last_hr),
    }
