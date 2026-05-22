"""
ora_campaign_watchdog.py — Campaign uptime sentinel (iter 322g).
══════════════════════════════════════════════════════════════════
The user mandate: "compaing kabhi rukni nahi chahiye, ORA always
ping karta rahe, jo bhi ruke microsec me fix kare."

This service runs forever in the Pillar-1 worker loop. Every 60s it
checks three campaign health signals:

  1. auto_blast_config.last_run_at  — engine heartbeat
  2. auto_blast_config.last_run_sent — actual send count last cycle
  3. council_decisions veto-rate    — 100% vetoes = silent kill

If any guard trips, it emits to `incident_bus` (category=`campaign_stalled`)
so the existing triage_brain + ORA auto-recovery pipeline takes over.

It also surfaces a live snapshot at `db.ora_campaign_health` so the
admin UI / ORA chat can read current status without grepping logs.

NOT a fix engine itself — it's a sentinel. Fixes are owned by
incident_playbooks + ORA's tool-use loop (3-proof rule applies).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("ora_campaign_watchdog")

_db = None
HEALTH_COLL = "ora_campaign_health"

# Thresholds (tuned for production realism — not test-friendly)
SILENT_RUN_SENT_ZERO_CYCLES = 3      # 3 cycles in a row of sent=0 → P1 incident
STALE_HEARTBEAT_MINUTES     = 20     # last_run_at older than 20m → P0 incident
VETO_RATE_WINDOW_HOURS      = 1      # look at council vetoes in last 1h
VETO_RATE_TRIP              = 0.90   # ≥90% veto-rate → P1 incident
POLL_INTERVAL_SECONDS       = 60


def set_db(database) -> None:
    global _db
    _db = database


async def _emit(category: str, signature: str, severity: str,
                title: str, detail: str, metadata: dict) -> None:
    """Wrapper so incident_bus stays an optional dep."""
    try:
        from services import incident_bus
        await incident_bus.report(
            category=category, signature=signature, severity=severity,
            source="campaign_watchdog", title=title, detail=detail,
            metadata=metadata,
        )
    except Exception as e:
        logger.warning(f"[watchdog] incident emit failed: {e}")


async def _check_once() -> dict:
    """Run one health check. Returns the snapshot it persists."""
    db = _db
    if db is None:
        return {"ok": False, "error": "db not wired"}

    now = datetime.now(timezone.utc)
    snapshot: dict = {
        "checked_at": now.isoformat(),
        "tripped": [],
    }

    # ── Guard 1: engine heartbeat (last_run_at fresh?) ──────────────
    cfg = await db.auto_blast_config.find_one({"tenant_id": "global"}, {"_id": 0})
    last_run = (cfg or {}).get("last_run_at")
    last_sent = int((cfg or {}).get("last_run_sent") or 0)
    enabled = bool((cfg or {}).get("enabled"))
    snapshot["enabled"] = enabled
    snapshot["last_run_at"] = last_run
    snapshot["last_run_sent"] = last_sent

    if enabled and last_run:
        try:
            lr = datetime.fromisoformat(str(last_run).replace("Z", "+00:00"))
            if lr.tzinfo is None:
                lr = lr.replace(tzinfo=timezone.utc)
            age_min = (now - lr).total_seconds() / 60
            snapshot["heartbeat_age_min"] = round(age_min, 1)
            if age_min > STALE_HEARTBEAT_MINUTES:
                snapshot["tripped"].append("stale_heartbeat")
                await _emit(
                    category="unknown",  # 'campaign_stalled' isn't in CATEGORIES; map to unknown w/ signature
                    signature=f"campaign_stalled:heartbeat:{int(age_min)}m",
                    severity="P0",
                    title=f"Auto-Blast heartbeat stale ({int(age_min)}m)",
                    detail=f"last_run_at={last_run}; expected <{STALE_HEARTBEAT_MINUTES}m. "
                           f"Scheduler likely crashed or worker not attached.",
                    metadata={"age_min": age_min, "last_run_at": last_run, "enabled": enabled},
                )
        except Exception as e:
            logger.warning(f"[watchdog] heartbeat parse error: {e}")

    # ── Guard 2: 3 consecutive cycles with sent=0 ───────────────────
    # Use a tiny rolling buffer stored in ora_campaign_health doc.
    health = await db[HEALTH_COLL].find_one({"_id": "global"}, {"_id": 0}) or {}
    zero_streak = int(health.get("zero_sent_streak") or 0)
    # iter 326m — distinguish "silent failure" from "empty queue".
    # Previously every `last_sent == 0` incremented the streak — including
    # cycles where the engine processed 0 leads because the queue was
    # legitimately empty (last_run_note=="no-eligible-leads"). That turned
    # the watchdog into a false-alarm machine (streak=203 with NO actual
    # delivery problem). True silent failure = engine PROCESSED leads but
    # NONE got sent. Empty queue = needs scout, not a campaign-watchdog
    # trip.
    last_processed = int((cfg or {}).get("last_run_processed") or 0)
    last_note = str((cfg or {}).get("last_run_note") or "")
    is_empty_queue_cycle = (last_processed == 0) or (last_note == "no-eligible-leads")
    snapshot["last_run_processed"] = last_processed
    snapshot["last_run_note"] = last_note
    snapshot["empty_queue"] = is_empty_queue_cycle
    if enabled and last_run:
        if last_sent == 0 and not is_empty_queue_cycle:
            zero_streak += 1
        elif last_sent > 0:
            zero_streak = 0
        # else: empty queue → hold streak steady (neither punish nor reset)
    snapshot["zero_sent_streak"] = zero_streak

    if zero_streak >= SILENT_RUN_SENT_ZERO_CYCLES and not is_empty_queue_cycle:
        snapshot["tripped"].append("zero_sent_streak")
        # iter 325u — incident noise fix. Old code emitted to incident_bus on
        # every 60s cycle while tripped (streak=232 = 232 dup incidents). Now
        # only emit on the *transition* (streak crosses threshold) and every
        # 30x escalation thereafter (3, 30, 60, …) — matches the Telegram
        # cadence philosophy and stops log/incident spam.
        prev_streak = int(health.get("zero_sent_streak") or 0)
        should_emit_incident = (
            prev_streak < SILENT_RUN_SENT_ZERO_CYCLES   # entering trip state
            or (zero_streak % 30 == 0)                  # every 30-cycle escalation
        )
        if should_emit_incident:
            await _emit(
                category="unknown",
                signature=f"campaign_stalled:zero_sent_streak:{zero_streak}",
                severity="P1",
                title=f"Auto-Blast silent: sent=0 for {zero_streak} cycles",
                detail="Engine cycles complete but no leads are being sent. "
                       "Check Council veto reasons + channel_gating fallback.",
                metadata={"zero_streak": zero_streak, "last_run_at": last_run},
            )
        # iter 325d — ping founder Telegram on every 10x streak escalation
        # (10, 20, 30, …) so a stuck pipeline can't go unnoticed for hours.
        # Fingerprint uses the bucket so each escalation is one ping.
        try:
            if zero_streak % 10 == 0:
                from services.telegram_bot_service import send_telegram_alert
                await send_telegram_alert(
                    message=(
                        f"Auto-blast engine has sent ZERO leads for "
                        f"{zero_streak} consecutive cycles.\n"
                        f"Last run: {last_run or 'unknown'}\n\n"
                        f"Check Council vetoes + channel_gating in:\n"
                        f"/admin/pillars-map → campaign_health"
                    ),
                    alert_type="campaign_zero",
                    fingerprint=f"streak_{zero_streak}",
                )
        except Exception as e:
            logger.debug(f"[watchdog] telegram campaign_zero alert skipped: {e}")

    # ── Guard 3: Council veto-rate ──────────────────────────────────
    try:
        window_start = now - timedelta(hours=VETO_RATE_WINDOW_HOURS)
        # Use find + python aggregation (Mongo aggregate had retry issues
        # in this env). Keep window tight (1h) so this stays fast.
        total = 0; vetoed = 0
        async for d in db.council_decisions.find(
            {"action_kind": "outreach_blast",
             "$or": [
                 {"ts":         {"$gte": window_start.isoformat()}},
                 {"created_at": {"$gte": window_start.isoformat()}},
             ]},
            {"_id": 0, "decision": 1},
        ).limit(2000):
            total += 1
            if (d.get("decision") or "").lower() == "veto":
                vetoed += 1
        veto_rate = (vetoed / total) if total else 0.0
        snapshot["veto_rate_1h"] = round(veto_rate, 3)
        snapshot["veto_decisions_1h"] = total
        if total >= 10 and veto_rate >= VETO_RATE_TRIP:
            snapshot["tripped"].append("high_veto_rate")
            await _emit(
                category="unknown",
                signature=f"campaign_stalled:veto_rate:{int(veto_rate*100)}",
                severity="P1",
                title=f"Council vetoing {int(veto_rate*100)}% of blasts (last 1h)",
                detail=f"{vetoed}/{total} blasts vetoed in the past hour. "
                       "Check verification.channel_gating + scout timeouts.",
                metadata={"veto_rate": veto_rate, "vetoed": vetoed, "total": total},
            )
    except Exception as e:
        logger.warning(f"[watchdog] veto-rate check failed: {e}")

    # ── Persist snapshot for UI / ORA tool reads ────────────────────
    snapshot["zero_sent_streak"] = zero_streak
    await db[HEALTH_COLL].update_one(
        {"_id": "global"},
        {"$set": snapshot},
        upsert=True,
    )

    if snapshot["tripped"]:
        logger.warning(f"[watchdog] TRIPPED: {snapshot['tripped']}")
    return snapshot


async def watchdog_loop() -> None:
    """Pillar-1 worker entrypoint. Polls forever."""
    print("[watchdog] campaign watchdog alive — 15s grace then 60s polling", flush=True)
    await asyncio.sleep(15)
    while True:
        try:
            snap = await _check_once()
            if snap.get("tripped"):
                # iter 325u — only print on transition + every 30x cycle so
                # a long-running stalled campaign doesn't flood stdout.
                streak = int(snap.get("zero_sent_streak") or 0)
                if streak <= SILENT_RUN_SENT_ZERO_CYCLES or streak % 30 == 0:
                    print(f"[watchdog] tripped guards: {snap['tripped']}  "
                          f"last_sent={snap.get('last_run_sent')}  "
                          f"streak={streak}  "
                          f"veto_rate={snap.get('veto_rate_1h')}", flush=True)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[watchdog] loop error: {e}", exc_info=True)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
