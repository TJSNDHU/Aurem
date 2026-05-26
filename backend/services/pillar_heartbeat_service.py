"""
Pillar Heartbeat Service — P4 background worker (iter 269).
═════════════════════════════════════════════════════════════

Every 20 s it:
  1. Gathers a full pillars-map snapshot (4 pillars × ~12-19 collections each).
  2. Writes it into the in-memory cache (serves /heartbeat endpoint instantly).
  3. Also persists a tiny summary doc into db.pillar_heartbeats for history/alerting.

This is the "State Persistence" layer requested — ensures the admin UI loads
in < 50 ms without hammering Mongo on every poll.

Scheduler name: p4:pillar_heartbeat  (matches P4 prefix → shows up in workers
list of the same router it powers).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 300  # iter 301: trimmed from 20s — was constant DB noise (~4320 writes/day)
HISTORY_COLLECTION = "pillar_heartbeats"
HISTORY_RETENTION_DOCS = 2880  # ~16 hours at 20 s cadence


async def pillar_heartbeat_scheduler(db) -> None:
    """Run forever, refresh cache every 20 s. Safe: all errors logged, never raises."""
    # Import here to avoid circular (router imports us not the other way round)
    from routers.pillars_map_router import (
        PILLAR_MAP,
        _gather_pillar,
        _gather_wires,
        _gather_flows,
        set_cached_snapshot,
        _fetch_sentinel_overlay,
        _merge_sentinel_into_pillar,
    )

    logger.info("[pillar-heartbeat] scheduler started — interval=%ss", INTERVAL_SECONDS)

    # iter 282 — status-change tracker for A2A emit (no spam, only on change)
    last_pillar_status: dict = {}
    last_overall: str | None = None
    # iter 283 — persistent-red detector: track when each pillar first went red
    red_since: dict = {}
    PERSISTENT_RED_THRESHOLD_SEC = 900  # 15 min
    PERSISTENT_RED_RECORD_COOLDOWN_SEC = 1800  # re-log every 30 min
    last_persistent_record: dict = {}

    while True:
        try:
            pillars, wires, flows = await asyncio.gather(
                asyncio.gather(
                    *[_gather_pillar(k, s) for k, s in PILLAR_MAP.items()],
                    return_exceptions=True,
                ),
                _gather_wires(),
                _gather_flows(),
            )
            # drop any exceptions, keep only dict results
            clean = [p for p in pillars if isinstance(p, dict)]

            # iter 280.3 — Sentinel overlay escalates p3_monitor on error surge
            try:
                sentinel_overlay = await _fetch_sentinel_overlay()
                _merge_sentinel_into_pillar(clean, sentinel_overlay)
            except Exception as _so:
                logger.debug("[pillar-heartbeat] sentinel overlay failed: %s", _so)
                sentinel_overlay = None

            worst = "green"
            for p in clean:
                if p.get("status") == "red":
                    worst = "red"; break
                if p.get("status") == "yellow":
                    worst = "yellow"

            from routers.pillars_map_router import _pick_worst as _pw
            # iter 332b D-30 — exclude non_blocking flows from verdict escalation.
            # Advisory flows (e.g. opt-in Ollama Sovereign Node) stay visible
            # red in the UI but do NOT flip the global "Broken" badge.
            wires_red_blocking = sum(
                1 for w in wires
                if w["status"] == "red" and not w.get("non_blocking")
            )
            wires_red_advisory = sum(
                1 for w in wires
                if w["status"] == "red" and w.get("non_blocking")
            )
            wires_red = wires_red_blocking + wires_red_advisory
            wires_yellow = sum(
                1 for w in wires
                if w["status"] == "yellow" and not w.get("non_blocking")
            )
            wires_idle = sum(1 for w in wires if w["status"] == "idle")
            flows_red_blocking = sum(
                1 for f in flows
                if f["status"] == "red" and not f.get("non_blocking")
            )
            flows_red_advisory = sum(
                1 for f in flows
                if f["status"] == "red" and f.get("non_blocking")
            )
            flows_red = flows_red_blocking + flows_red_advisory
            flows_yellow_blocking = sum(
                1 for f in flows
                if f["status"] == "yellow" and not f.get("non_blocking")
            )
            flows_yellow = sum(1 for f in flows if f["status"] == "yellow")
            if wires_red_blocking > 0 or flows_red_blocking > 0:
                worst = "red"
            elif (wires_yellow > 0 or flows_yellow_blocking > 0) and worst == "green":
                worst = "yellow"

            # admin/customer surface verdicts — only BLOCKING flows count.
            admin_flows = [f for f in flows if f.get("surface") == "admin"]
            customer_flows = [f for f in flows if f.get("surface") == "customer"]
            admin_blocking = [f for f in admin_flows if not f.get("non_blocking")]
            customer_blocking = [f for f in customer_flows if not f.get("non_blocking")]
            admin_worst = _pw(*[f["status"] for f in admin_blocking]) if admin_blocking else "green"
            customer_worst = _pw(*[f["status"] for f in customer_blocking]) if customer_blocking else "green"
            interface_desync = (
                admin_worst == "green" and customer_worst in ("red", "yellow")
            ) or (
                customer_worst == "green" and admin_worst in ("red", "yellow")
            )

            snapshot = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "overall_status": worst,
                "pillars": clean,
                "wires": wires,
                "flows": flows,
                "admin_worst": admin_worst,
                "customer_worst": customer_worst,
                "interface_desync": interface_desync,
                "totals": {
                    "collections":         sum(p["collections"]["total"] for p in clean),
                    "silent_failures":     sum(p["collections"].get("silent_failures", 0) for p in clean),
                    "unreachable":         sum(p["collections"]["unreachable"] for p in clean),
                    "backend_red":         sum(p["collections"].get("backend_red", 0) for p in clean),
                    "wires_total":         len(wires),
                    "wires_red":           wires_red,
                    "wires_red_blocking":  wires_red_blocking,
                    "wires_red_advisory":  wires_red_advisory,
                    "wires_yellow":        wires_yellow,
                    "wires_idle":          wires_idle,
                    "flows_total":         len(flows),
                    "flows_red":           flows_red,
                    "flows_red_blocking":  flows_red_blocking,
                    "flows_red_advisory":  flows_red_advisory,
                    "flows_yellow":        flows_yellow,
                },
                "sentinel_overlay": sentinel_overlay,
                "silent_failure_threshold_minutes": 15,
            }
            set_cached_snapshot(snapshot)

            # iter 282 — A2A bus emit on pillar status CHANGE only.
            # Prevents spam; downstream Learning Bus consumes these events
            # to build agent-health awareness.
            try:
                from services.a2a_bus import bus as _a2a_bus
                for p in clean:
                    key = p.get("key")
                    cur = p.get("status")
                    prev = last_pillar_status.get(key)
                    if prev is not None and prev != cur and cur in ("red", "yellow", "green"):
                        await _a2a_bus.emit(
                            from_agent="pillar_monitor",
                            event="health_event",
                            payload={
                                "pillar_key": key,
                                "status": cur,
                                "prev_status": prev,
                                "silent_failures": p.get("collections", {}).get("silent_failures", 0),
                                "backend_red": p.get("collections", {}).get("backend_red", 0),
                                "overall": worst,
                                "ts_iso": snapshot["generated_at"],
                            },
                        )
                    last_pillar_status[key] = cur

                    # iter 283 — persistent_red truth ledger entry
                    import time as _t
                    if cur == "red":
                        red_since.setdefault(key, _t.monotonic())
                        stuck_for = _t.monotonic() - red_since[key]
                        last_rec = last_persistent_record.get(key, 0)
                        if (stuck_for >= PERSISTENT_RED_THRESHOLD_SEC
                                and (_t.monotonic() - last_rec) >= PERSISTENT_RED_RECORD_COOLDOWN_SEC):
                            try:
                                from services import truth_ledger
                                await truth_ledger.record_persistent_red(
                                    actor="pillar_heartbeat",
                                    description=f"{key} stuck red for {int(stuck_for/60)} min",
                                    evidence={"pillar_key": key,
                                              "stuck_seconds": int(stuck_for),
                                              "silent_failures": p.get("collections", {}).get("silent_failures", 0)},
                                    outcome="escalated",
                                )
                                last_persistent_record[key] = _t.monotonic()
                            except Exception:
                                pass
                    else:
                        red_since.pop(key, None)
                        last_persistent_record.pop(key, None)
                if last_overall is not None and last_overall != worst:
                    await _a2a_bus.emit(
                        from_agent="pillar_monitor",
                        event="overall_change",
                        payload={
                            "prev": last_overall,
                            "now": worst,
                            "ts_iso": snapshot["generated_at"],
                        },
                    )
                last_overall = worst
            except Exception as _e:
                logger.debug("[pillar-heartbeat] A2A emit failed: %s", _e)

            # Persist tiny summary (not the full pillar payload)
            try:
                await db[HISTORY_COLLECTION].insert_one({
                    "generated_at": datetime.now(timezone.utc),
                    "overall_status": worst,
                    "totals": snapshot["totals"],
                    "per_pillar": {p["key"]: p["status"] for p in clean},
                })
                # Trim old docs (keep last N)
                total = await db[HISTORY_COLLECTION].count_documents({})
                if total > HISTORY_RETENTION_DOCS:
                    over = total - HISTORY_RETENTION_DOCS
                    cursor = db[HISTORY_COLLECTION].find(
                        {}, projection={"_id": 1}
                    ).sort("generated_at", 1).limit(over)
                    to_delete = [d["_id"] async for d in cursor]
                    if to_delete:
                        await db[HISTORY_COLLECTION].delete_many({"_id": {"$in": to_delete}})
            except Exception as e:
                logger.debug("[pillar-heartbeat] persist failed: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[pillar-heartbeat] tick failed: %s", e)

        await asyncio.sleep(INTERVAL_SECONDS)
