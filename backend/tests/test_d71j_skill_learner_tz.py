"""
D-71j — Skill Learner tz-aware datetime fix.

User reported BE-side broken on /admin/pillars-map →
/api/admin/skills/learning-health. The endpoint returned 200 JSON but
with {ok:false, status:"red", detail:"health probe crashed: can't
subtract offset-naive and offset-aware datetimes"}.

Root cause: legacy skill_learnings rows were written via
`datetime.utcnow()` (naive). The health probe did
`datetime.now(timezone.utc) - ts` which raises TypeError when `ts` is
naive. Now we normalise naive datetimes to UTC before diffing.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest


def test_skill_learner_normalises_naive_datetime():
    src = Path("/app/backend/services/skill_learner.py").read_text()
    # The fix is a tzinfo check + replace with UTC.
    assert "ts.tzinfo is None" in src, (
        "Must check tzinfo before subtracting"
    )
    assert "ts.replace(tzinfo=timezone.utc)" in src, (
        "Naive timestamps must be upgraded to UTC, not silently broken"
    )


@pytest.mark.asyncio
async def test_learning_engine_health_does_not_crash_on_naive_ts():
    """Simulate a legacy row with naive `datetime.utcnow()` value and
    confirm the health probe returns green/yellow instead of crashing."""
    from services.skill_learner import learning_engine_health

    naive_recent = datetime.utcnow()  # legacy style — naive
    naive_old    = datetime.utcnow() - timedelta(days=7)

    class FakeColl:
        def __init__(self, ts):
            self._ts = ts
        async def find_one(self, *a, **k):
            return {"ts": self._ts, "insights_count": 12}

    class FakeDB:
        def __init__(self, ts):
            self.skill_learnings = FakeColl(ts)

    # Naive recent → green
    res1 = await learning_engine_health(FakeDB(naive_recent))
    assert res1["ok"] is True
    assert res1["status"] in ("green", "yellow"), f"unexpected: {res1}"
    assert res1["insights_count"] == 12

    # Naive old (>48h) → yellow
    res2 = await learning_engine_health(FakeDB(naive_old))
    assert res2["ok"] is True
    assert res2["status"] == "yellow"


@pytest.mark.asyncio
async def test_learning_engine_health_with_aware_ts_still_works():
    """tz-aware datetimes (new ssot pattern) must keep working."""
    from services.skill_learner import learning_engine_health

    aware = datetime.now(timezone.utc)
    class FakeColl:
        async def find_one(self, *a, **k):
            return {"ts": aware, "insights_count": 5}
    class FakeDB:
        skill_learnings = FakeColl()

    res = await learning_engine_health(FakeDB())
    assert res["ok"] is True
    assert res["status"] == "green"
    assert res["insights_count"] == 5
