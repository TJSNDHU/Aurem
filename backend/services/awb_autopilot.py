"""
AWB Auto-Pilot (iter 299)
=========================
30-min cron loop: pick top N queue leads → build_site_for_lead each.

Public API:
  ap = autopilot
  ap.start()                 — start background task (idempotent)
  ap.stop()
  ap.set_enabled(bool)       — toggle persistence flag
  ap.get_state(db) -> dict   — {enabled, running, interval_minutes, batch_size,
                                last_run_at, last_run_summary, next_run_at}

Persistence:
  Collection `awb_autopilot_state` doc {_id: 'singleton', ...}
  Collection `awb_autopilot_runs`  history rows (status, built, skipped, ts)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_MIN = 30
DEFAULT_BATCH_SIZE = 5


class AutoPilot:
    def __init__(self):
        self._db = None
        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()

    def set_db(self, db):
        self._db = db

    # ─── persistence ────────────────────────────────────────────────────────
    async def _load_state(self) -> Dict[str, Any]:
        if self._db is None:
            return {"enabled": False, "interval_minutes": DEFAULT_INTERVAL_MIN,
                    "batch_size": DEFAULT_BATCH_SIZE}
        row = await self._db.awb_autopilot_state.find_one({"_id": "singleton"}, {"_id": 0})
        if not row:
            row = {"enabled": False, "interval_minutes": DEFAULT_INTERVAL_MIN,
                   "batch_size": DEFAULT_BATCH_SIZE}
            await self._db.awb_autopilot_state.update_one(
                {"_id": "singleton"}, {"$set": row}, upsert=True,
            )
        return row

    async def _save_state(self, **patch) -> None:
        if self._db is None:
            return
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._db.awb_autopilot_state.update_one(
            {"_id": "singleton"}, {"$set": patch}, upsert=True,
        )

    # ─── public ─────────────────────────────────────────────────────────────
    async def get_state(self) -> Dict[str, Any]:
        st = await self._load_state()
        st["running"] = bool(self._task and not self._task.done())
        st.setdefault("interval_minutes", DEFAULT_INTERVAL_MIN)
        st.setdefault("batch_size", DEFAULT_BATCH_SIZE)
        if st.get("last_run_at"):
            try:
                last = datetime.fromisoformat(st["last_run_at"].replace("Z", "+00:00"))
                st["next_run_at"] = (last + timedelta(minutes=int(st["interval_minutes"]))).isoformat()
            except Exception:
                st["next_run_at"] = None
        else:
            st["next_run_at"] = None
        return st

    async def set_enabled(self, enabled: bool, batch_size: Optional[int] = None,
                          interval_minutes: Optional[int] = None) -> Dict[str, Any]:
        patch: Dict[str, Any] = {"enabled": bool(enabled)}
        if batch_size is not None:
            patch["batch_size"] = max(1, min(20, int(batch_size)))
        if interval_minutes is not None:
            patch["interval_minutes"] = max(5, min(360, int(interval_minutes)))
        await self._save_state(**patch)
        if enabled:
            self.start()
        else:
            self.stop()
        return await self.get_state()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("[autopilot] started")

    def stop(self) -> None:
        self._stopping.set()
        logger.info("[autopilot] stop signaled")

    # ─── loop ───────────────────────────────────────────────────────────────
    async def _loop(self) -> None:
        try:
            while not self._stopping.is_set():
                state = await self._load_state()
                if not state.get("enabled"):
                    return
                interval = max(5, int(state.get("interval_minutes") or DEFAULT_INTERVAL_MIN))
                batch = max(1, int(state.get("batch_size") or DEFAULT_BATCH_SIZE))
                try:
                    await self._run_once(batch)
                except Exception as e:
                    logger.error(f"[autopilot] run failed: {e}")
                # sleep with cancellation
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=interval * 60)
                except asyncio.TimeoutError:
                    pass
        finally:
            logger.info("[autopilot] loop exited")

    async def _run_once(self, batch_size: int) -> Dict[str, Any]:
        if self._db is None:
            return {"ok": False, "error": "no db"}
        from services.auto_website_builder import build_batch
        started = datetime.now(timezone.utc).isoformat()
        result = await build_batch(self._db, limit=batch_size)
        finished = datetime.now(timezone.utc).isoformat()

        # iter 282al-18 · Part 5 — also audit has-website leads via dispatcher
        audit_ct = 0
        try:
            from services.scout_dispatcher import dispatch_lead_sync
            # Pick a small batch of newly-verified leads that still have a
            # website but haven't been routed yet
            q = {
                "website":         {"$exists": True, "$nin": [None, ""]},
                "dispatch_route":  {"$exists": False},
                "audited_at":      {"$exists": False},
            }
            has_web = await self._db.campaign_leads.find(
                q, {"_id": 1, "lead_id": 1, "business_name": 1,
                    "website": 1, "email": 1, "phone": 1, "city": 1},
            ).limit(batch_size).to_list(length=batch_size)
            for _lead in has_web:
                try:
                    await dispatch_lead_sync(self._db, _lead)
                    audit_ct += 1
                except Exception as _e:
                    logger.debug(f"[autopilot] dispatch failed: {_e}")
        except Exception as _dx:
            logger.debug(f"[autopilot] has-website dispatch skipped: {_dx}")

        summary = {
            "started_at": started, "finished_at": finished,
            "selected": result.get("selected", 0),
            "built_n": len(result.get("built") or []),
            "skipped_n": len(result.get("skipped") or []),
            "audited_n": audit_ct,
        }
        await self._save_state(last_run_at=finished, last_run_summary=summary)
        try:
            await self._db.awb_autopilot_runs.insert_one(summary | {
                "built_ids": [b.get("site_id") for b in (result.get("built") or [])][:20],
                "skipped_reasons": [s.get("error") or s.get("reason") for s in (result.get("skipped") or [])][:20],
            })
        except Exception:
            pass
        logger.info(f"[autopilot] run done: built={summary['built_n']} skipped={summary['skipped_n']}")
        return summary

    async def trigger_now(self, batch_size: Optional[int] = None) -> Dict[str, Any]:
        st = await self._load_state()
        n = batch_size or st.get("batch_size") or DEFAULT_BATCH_SIZE
        return await self._run_once(int(n))

    async def history(self, limit: int = 20):
        if self._db is None:
            return []
        return await self._db.awb_autopilot_runs.find(
            {}, {"_id": 0},
        ).sort("finished_at", -1).limit(int(limit)).to_list(int(limit))


autopilot = AutoPilot()


def set_db(db):
    autopilot.set_db(db)
    # Auto-resume on startup if enabled
    try:
        async def _resume():
            st = await autopilot._load_state()
            if st.get("enabled"):
                autopilot.start()
        asyncio.create_task(_resume())
    except Exception:
        pass
