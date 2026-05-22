"""
test_iter326p_scout_safety_net.py — Regression for iter 326p.
══════════════════════════════════════════════════════════════════════════════
Founder ask (verbatim): "Build an auto-refill safety net — so anytime the
queue drops below 5 real leads, the scout automatically wakes up and fills
it. You never have to think about it again."

CONTEXT
───────
`services/scout_replenish_cron.py` already existed (since iter 322g) but
shipped with a fixed 120-minute interval. Two problems:
  1. On a slow night (most cells return 0 leads) the founder could wait
     6+ hours before the cursor hit a productive (city, industry) cell.
  2. After a productive tick lands fresh leads, the next blast cycle
     fires within minutes — but the next refill was still 2 hours away,
     so the queue could go right back to empty.

THE iter 326p CHANGES
─────────────────────
  • Default `AUREM_SCOUT_CRON_INTERVAL_MIN` lowered 120 → 15.
  • Every `replenish_tick` now returns `next_run_in_minutes`:
        skipped (queue healthy)  → max(60, configured)   "coast"
        leads_written > 0        → 20                    "warm"
        ran but 0 leads          → 5                     "hunt"
  • Scheduler hook wraps `replenish_tick` and reschedules the job
    AFTER each run using the hint. Adaptive cadence — slow when full,
    fast when starving.
  • When a tick lands ≥1 lead, send a single Telegram ping to the
    founder so they know the queue is being topped up.

WHAT THIS TEST FILE GUARANTEES
──────────────────────────────
The next_run_in_minutes hint values are part of the contract — if a
future agent reverts them to a fixed cadence the founder loses sleep.
We also test that the Telegram notifier is wired through and that
adaptive scheduling code path lives inside `install_scheduler`.

Run:  cd /app/backend && python3 -m pytest tests/test_iter326p_scout_safety_net.py -v
"""
from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1) Default interval lowered + adaptive hints present in the code
# ─────────────────────────────────────────────────────────────────────────────
def test_default_interval_lowered_to_fifteen_minutes():
    """Override-via-env must still work, but the BAKED-IN default
    becomes 15 minutes (was 120). This is the single biggest reason
    the founder's queue used to dry out overnight."""
    from services import scout_replenish_cron as cron
    import os

    # Make sure no env override is leaking from the dev shell.
    prior = os.environ.pop("AUREM_SCOUT_CRON_INTERVAL_MIN", None)
    try:
        assert cron._interval_min() == 15, (
            f"baseline cron interval is {cron._interval_min()} — should be 15"
        )
    finally:
        if prior is not None:
            os.environ["AUREM_SCOUT_CRON_INTERVAL_MIN"] = prior


def test_env_override_still_respected():
    """A founder who wants a different cadence (e.g. 30 min) can still
    set `AUREM_SCOUT_CRON_INTERVAL_MIN=30` — the default-lowering must
    not have hard-coded 15."""
    from services import scout_replenish_cron as cron
    import os

    prior = os.environ.get("AUREM_SCOUT_CRON_INTERVAL_MIN")
    try:
        os.environ["AUREM_SCOUT_CRON_INTERVAL_MIN"] = "30"
        assert cron._interval_min() == 30
    finally:
        if prior is None:
            os.environ.pop("AUREM_SCOUT_CRON_INTERVAL_MIN", None)
        else:
            os.environ["AUREM_SCOUT_CRON_INTERVAL_MIN"] = prior


# ─────────────────────────────────────────────────────────────────────────────
# 2) Adaptive scheduler hint — three branches encoded in replenish_tick
# ─────────────────────────────────────────────────────────────────────────────
def test_tick_source_carries_three_adaptive_branches():
    """We test the SOURCE rather than running a full tick because
    `replenish_tick` reaches into the live DB + OSM/Apollo. The three
    branches are part of the contract — if any branch literal is
    removed in a future edit, the safety-net cadence regresses."""
    from services import scout_replenish_cron as cron

    src = inspect.getsource(cron.replenish_tick)
    # Coast: skipped path
    assert "next_run_in_minutes\"] = max(60" in src, (
        "coast branch (queue healthy → 60+ min) missing"
    )
    # Warm: lead landed
    assert "next_run_in_minutes\"] = 20" in src, (
        "warm branch (leads_written > 0 → 20 min) missing"
    )
    # Hunt: zero-lead cell
    assert "next_run_in_minutes\"] = 5" in src, (
        "hunt branch (dud cell → 5 min) missing"
    )


def test_telegram_alert_fires_when_leads_land():
    """When leads_written > 0 the tick must call into
    autopilot_brief_notifier._send_telegram. The source must reference
    it so the contract is locked in."""
    from services import scout_replenish_cron as cron

    src = inspect.getsource(cron.replenish_tick)
    assert "_send_telegram" in src, (
        "Telegram notification call site missing — founder won't get pings"
    )
    assert "leads_written" in src
    # Must contain the human-readable copy so the ping isn't a debug dump.
    assert "AUREM auto-refill" in src


# ─────────────────────────────────────────────────────────────────────────────
# 3) Adaptive rescheduling — `install_scheduler` must wrap, not pass
#    `replenish_tick` directly.
# ─────────────────────────────────────────────────────────────────────────────
def test_install_scheduler_wraps_with_adaptive_callback():
    """The job's callable must NOT be `replenish_tick` directly any
    more — it has to be a wrapper that calls `reschedule_job` after
    each tick. Otherwise the next_run_in_minutes hint is computed and
    thrown away."""
    from services import scout_replenish_cron as cron

    src = inspect.getsource(cron.install_scheduler)
    # The wrapper exists
    assert "_adaptive_tick" in src, (
        "install_scheduler must define an _adaptive_tick wrapper that "
        "calls replenish_tick THEN reschedules the job"
    )
    # The wrapper calls reschedule_job
    assert "reschedule_job" in src
    # And uses the hint
    assert "next_run_in_minutes" in src


# ─────────────────────────────────────────────────────────────────────────────
# 4) End-to-end smoke — running a tick on a real DB returns the hint shape
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_replenish_tick_returns_hint_on_skip_path():
    """When the DB queue is already past the target, the tick must
    return `skipped=True` AND a `next_run_in_minutes` ≥ 60. Validates
    the coast-branch wiring end-to-end on a real (test) DB."""
    import os
    from motor.motor_asyncio import AsyncIOMotorClient
    from services import scout_replenish_cron as cron

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client["aurem_test_iter326p"]
    try:
        # Seed the queue with more leads than the target so the tick
        # takes the skip path (no OSM call needed → fast and offline-safe).
        target = cron._queue_target()
        seed_count = target + 5
        await db.campaign_leads.delete_many({})
        await db.campaign_leads.insert_many([
            {
                "id": f"seed-{i}",
                "status": "queued",
                "noise_flag": False,
                "email": f"owner{i}@example.com",
            } for i in range(seed_count)
        ])

        cron.set_db(db)
        result = await cron.replenish_tick()

        assert result["ok"] is True
        assert result["skipped"] is True
        assert result["queue_depth"] >= target
        # Coast hint — the founder's queue is healthy, so chill for a while.
        assert result["next_run_in_minutes"] >= 60, (
            f"skip path returned {result['next_run_in_minutes']} — "
            f"should be ≥60 to avoid hammering OSM when not needed"
        )
    finally:
        await client.drop_database("aurem_test_iter326p")
        client.close()


# ─────────────────────────────────────────────────────────────────────────────
# 5) Module sanity — file still parseable and exports unchanged
# ─────────────────────────────────────────────────────────────────────────────
def test_public_api_surface_unchanged():
    """Existing callers (server.py, registry.py, admin routers) import
    `set_db`, `replenish_tick`, `install_scheduler`. None must vanish."""
    from services import scout_replenish_cron as cron

    for name in ("set_db", "replenish_tick", "install_scheduler"):
        assert hasattr(cron, name), f"{name} disappeared from public API"


def test_module_size_within_reasonable_bound():
    """Sanity floor — if a future edit accidentally truncates the
    module to a stub, this catches it."""
    path = Path("/app/backend/services/scout_replenish_cron.py")
    assert path.exists()
    lines = path.read_text().splitlines()
    # The refactor adds ~70 lines on top of the original ~290 → expect ≥300.
    assert len(lines) > 300, f"module shrank to {len(lines)} lines"
