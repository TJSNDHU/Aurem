"""
Hunter ORA 🔍 — Finds new businesses daily.
Wraps the existing hunt_live pipeline (Scout → Verify → Website → Blast)
and adds province/state-aware daily distribution + weekly rotation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from services.agents import AuremAgent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Daily distribution — 200 businesses/day once fully ramped.
# Scaled down by current daily_limit ramp (wk1=50, wk2=100, wk3=200).
# ─────────────────────────────────────────────────────────────
TERRITORY_DISTRIBUTION = [
    # Canada — 120/day at full ramp (60%)
    {"territory": "Ontario",     "country": "CA", "timezone": "America/Toronto",   "share": 30},
    {"territory": "BC",          "country": "CA", "timezone": "America/Vancouver", "share": 20},
    {"territory": "Alberta",     "country": "CA", "timezone": "America/Edmonton",  "share": 20},
    {"territory": "Quebec",      "country": "CA", "timezone": "America/Toronto",   "share": 20},
    {"territory": "Manitoba",    "country": "CA", "timezone": "America/Winnipeg",  "share": 10},
    {"territory": "Atlantic",    "country": "CA", "timezone": "America/Halifax",   "share": 10},
    {"territory": "Other_CA",    "country": "CA", "timezone": "America/Toronto",   "share": 10},
    # USA — 80/day at full ramp (40%)
    {"territory": "Eastern",     "country": "US", "timezone": "America/New_York",   "share": 25},
    {"territory": "Central",     "country": "US", "timezone": "America/Chicago",    "share": 20},
    {"territory": "Mountain",    "country": "US", "timezone": "America/Denver",     "share": 15},
    {"territory": "Pacific",     "country": "US", "timezone": "America/Los_Angeles","share": 20},
]

# Weekly rotation — day-of-week → (territory, industry)
WEEKLY_ROTATION = {
    0: [("Ontario", "auto shops"), ("BC", "salons")],          # Mon
    1: [("Alberta", "restaurants"), ("Eastern", "dental")],    # Tue
    2: [("Pacific", "gyms"), ("Quebec", "real estate")],       # Wed
    3: [("Manitoba", "hvac"), ("Central", "lawyers")],         # Thu
    4: [("Atlantic", "accountants"), ("Mountain", "gyms")],    # Fri
    5: [("Ontario", "restaurants"), ("BC", "auto shops")],     # Sat
    6: [("Eastern", "salons"), ("Pacific", "dental")],         # Sun
}


class HunterORA(AuremAgent):
    AGENT_ID = "hunter_ora"
    AGENT_NAME = "Hunter ORA"
    AGENT_EMOJI = "🔍"
    AGENT_JOB = "Find new businesses daily"

    async def get_daily_limit(self) -> int:
        """Return current daily limit based on auto-ramp schedule + selected ramp mode."""
        if self.db is None:
            return 20
        settings = await self.db.auto_hunt_settings.find_one({"_id": "singleton"}, {"_id": 0}) or {}
        if not settings.get("enabled", False):
            return 0
        override = settings.get("daily_limit_override")
        if override:
            return int(override)
        activated_at = settings.get("activated_at")
        if not activated_at:
            return self._ramp_for_week(settings.get("ramp_mode", "safe"), 1)
        try:
            started = datetime.fromisoformat(activated_at.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - started).days
        except Exception:
            days = 0
        week = min(4, (days // 7) + 1)
        return self._ramp_for_week(settings.get("ramp_mode", "safe"), week)

    @staticmethod
    def _ramp_for_week(mode: str, week: int) -> int:
        """Safe: 20→50→100→200 | Aggressive: 50→100→200→200"""
        safe = {1: 20, 2: 50, 3: 100, 4: 200}
        aggressive = {1: 50, 2: 100, 3: 200, 4: 200}
        table = aggressive if (mode or "").lower() == "aggressive" else safe
        return table.get(max(1, min(4, week)), 200)

    def _pick_today_targets(self) -> List[Dict[str, Any]]:
        """Return today's list of (territory, industry, count) tuples."""
        dow = datetime.now(timezone.utc).weekday()
        return WEEKLY_ROTATION.get(dow, WEEKLY_ROTATION[0])

    async def run_cycle(self) -> Dict[str, Any]:
        """Run the hunter for one day's slice. Called by the scheduler."""
        if self._paused:
            return {"skipped": "paused"}

        daily_limit = await self.get_daily_limit()
        if daily_limit == 0:
            return {"skipped": "auto_hunt_disabled"}

        # LIVE MODE — Hunter always respects daily_cap.
        daily_limit = min(daily_limit, self.daily_cap)

        targets = self._pick_today_targets()
        # Preserve any stats already accumulated today (cap accounting).
        stats: Dict[str, int] = dict(self._today_stats or {})
        stats.setdefault("scouted", 0)
        stats.setdefault("hunts_started", 0)

        from services.hunt_live import start_hunt
        # Lazy heartbeat/log_action — mirror Closer's pattern.
        try:
            from services.agent_registry import heartbeat, log_action
            await heartbeat("hunter_ora")
        except Exception:
            log_action = None

        for (territory, industry) in targets:
            # Remaining room under the cap for real outbound work.
            remaining = max(0, daily_limit - stats["scouted"])
            if remaining == 0:
                logger.info("[HunterORA] daily cap reached — stopping cycle early")
                break

            # Even split across remaining targets, clamped to what's left.
            per_target = max(1, daily_limit // max(1, len(targets)))
            count = min(per_target, remaining)

            # Enforce can_send() daily-cap guard.
            if not self.can_send():
                logger.info("[HunterORA] can_send() blocked — cap reached")
                break

            # ── Council gate (CASL required, advisory: qa) ─────────────
            # Hunter discovers + queues outbound — CASL must approve the
            # territory/industry combo before we burn discovery API calls
            # AND before any subsequent blast goes out. REJECTED skips this
            # target only; the cycle continues to the next.
            council_payload = {
                "territory": territory,
                "industry": industry,
                "count": count,
                "daily_limit": daily_limit,
                "country": next(
                    (t["country"] for t in TERRITORY_DISTRIBUTION
                     if t["territory"] == territory), "CA",
                ),
            }
            try:
                from services.council_deliberate import deliberate
                verdict = await deliberate(
                    "hunter_outbound_hunt", "hunter_ora", council_payload,
                    required=["casl"], advisory=["qa"],
                )
            except Exception as e:
                verdict = {"verdict": "APPROVED", "votes": {},
                           "confidence": 0.5, "_council_error": str(e)}
            if verdict.get("verdict") == "REJECTED":
                stats["council_rejected"] = stats.get("council_rejected", 0) + 1
                if log_action:
                    await log_action(
                        "hunter_ora", "REJECTED_BY_COUNCIL",
                        f"{territory}/{industry}: {verdict.get('votes')}",
                        success=False,
                        metadata={"territory": territory, "industry": industry,
                                  "votes": verdict.get("votes")},
                    )
                logger.info(
                    f"[HunterORA] Council REJECTED {territory}/{industry} — "
                    f"votes={verdict.get('votes')}"
                )
                continue

            self.mark_task(f"Hunting {territory} {industry} ({count})")

            try:
                hunt_id = await start_hunt(
                    self.db,
                    city=territory,
                    industry=industry,
                    count=count,
                )
                stats["hunts_started"] += 1
                stats["scouted"] += count
                # Update live counter so can_send() reflects current cycle.
                self._today_stats = stats

                # Notify Follow-up to pick up these leads tomorrow
                await self.notify(
                    "followup_ora",
                    "new_leads_batch",
                    {"hunt_id": hunt_id, "territory": territory, "industry": industry, "count": count},
                )
            except Exception as e:
                logger.warning(f"[HunterORA] hunt failed for {territory}/{industry}: {e}")
                continue

        self._today_stats = stats
        await self.broadcast("daily_complete", {"agent": self.AGENT_ID, "stats": stats})
        return stats
