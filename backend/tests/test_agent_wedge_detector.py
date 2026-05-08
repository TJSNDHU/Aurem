"""Tests for the Agent Wedge Detector + auto-heal cascade (iter 322o)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest

from services import agent_wedge_detector as awd


# ─── Fakes ─────────────────────────────────────────────────────────────
class _FakeColl:
    def __init__(self, docs: List[Dict[str, Any]] | None = None):
        self.docs: List[Dict[str, Any]] = list(docs or [])
        self.inserts: List[Dict[str, Any]] = []

    async def find_one(self, q, proj=None, sort=None):
        # Support direct {k: v}, {k: {"$gte": v}} and {"$or": [...]}.
        def _matches(doc, query):
            if "$or" in query:
                return any(_matches(doc, sub) for sub in query["$or"])
            for k, v in query.items():
                if k == "$or":
                    continue
                if isinstance(v, dict) and "$gte" in v:
                    if doc.get(k, "") < v["$gte"]:
                        return False
                elif doc.get(k) != v:
                    return False
            return True

        candidates = [d for d in self.docs if _matches(d, q)]
        if not candidates:
            return None
        if sort:
            (key, direction) = sort[0]
            candidates.sort(key=lambda x: x.get(key, ""), reverse=(direction == -1))
        return candidates[0]

    async def insert_one(self, doc):
        self.inserts.append(doc)
        self.docs.append(doc)
        return type("R", (), {"inserted_id": "id-fake"})()

    async def count_documents(self, q, limit=None):
        n = 0
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if isinstance(v, dict) and "$gte" in v:
                    if d.get(k, "") < v["$gte"]:
                        ok = False
                        break
                elif d.get(k) != v:
                    ok = False
                    break
            if ok:
                n += 1
                if limit and n >= limit:
                    return n
        return n

    def aggregate(self, pipeline):
        # Only support $group + $limit used by detector's discovery scan.
        ids = sorted({d.get("agent_id") for d in self.docs if d.get("agent_id")})
        results = [{"_id": i} for i in ids]

        class _Cursor:
            def __init__(self, items):
                self._iter = iter(items)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration

        return _Cursor(results)

    def find(self, q, proj=None):
        # Used by stats avg-aggregation.
        items = []
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if isinstance(v, dict) and "$gte" in v:
                    if d.get(k, "") < v["$gte"]:
                        ok = False
                        break
                elif d.get(k) != v:
                    ok = False
                    break
            if ok:
                items.append(d)

        class _Cursor:
            def __init__(self, items):
                self._items = items
                self._n_limit = None

            def limit(self, n):
                self._n_limit = n
                return self

            def __aiter__(self):
                self._iter = iter(
                    self._items[: self._n_limit] if self._n_limit else self._items
                )
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration

        return _Cursor(items)


class _FakeDB:
    def __init__(self):
        self.agent_ledger_entries = _FakeColl()
        self.agent_a2a_signals = _FakeColl()
        self.system_pulse_actions = _FakeColl()
        self.council_sessions = _FakeColl()
        self.learnings_pending_review = _FakeColl()


def _ago_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


# ─── Detection ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_detect_returns_empty_when_no_db():
    out = await awd.detect_wedged_agents(db=None)
    assert out == []


@pytest.mark.asyncio
async def test_dormant_agent_is_not_wedged():
    """Agent with zero rows ever — dormant, not wedged."""
    db = _FakeDB()
    out = await awd.detect_wedged_agents(db, threshold_s=60, active_days=7)
    # KNOWN_AGENTS exist as candidates but none have ledger rows → not wedged
    assert out == []


@pytest.mark.asyncio
async def test_recently_active_agent_is_not_wedged():
    db = _FakeDB()
    db.agent_ledger_entries.docs.append({
        "agent_id": "scout_ora", "kind": "cost",
        "timestamp": _ago_iso(30),  # 30 seconds ago
    })
    out = await awd.detect_wedged_agents(db, threshold_s=60, active_days=7)
    assert out == []


@pytest.mark.asyncio
async def test_stale_active_agent_is_wedged():
    db = _FakeDB()
    db.agent_ledger_entries.docs.append({
        "agent_id": "scout_ora", "kind": "cost",
        "timestamp": _ago_iso(3600),  # 1 hour ago
    })
    out = await awd.detect_wedged_agents(db, threshold_s=60, active_days=7)
    assert len(out) == 1
    assert out[0]["agent_id"] == "scout_ora"
    assert out[0]["tier"] == "T1_customer"
    assert out[0]["age_seconds"] >= 3600
    assert out[0]["reason"] == "stale_heartbeat"


@pytest.mark.asyncio
async def test_long_dormant_agent_is_not_wedged():
    """Agent that was active 60 days ago but not recently — dormant."""
    db = _FakeDB()
    db.agent_ledger_entries.docs.append({
        "agent_id": "scout_ora", "kind": "cost",
        "timestamp": _ago_iso(86400 * 60),  # 60 days ago
    })
    out = await awd.detect_wedged_agents(db, threshold_s=60, active_days=7)
    assert out == []


# ─── Heal cascade ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_auto_heal_writes_three_artifacts():
    """One heal must produce: 1 ledger row, 1 A2A signal, 1 pulse log."""
    db = _FakeDB()
    out = await awd.auto_heal_agent(db, "scout_ora", age_seconds=3600)
    assert out["healed"] is True
    assert out["agent_id"] == "scout_ora"
    assert out["age_seconds_before_heal"] == 3600
    assert isinstance(out["heal_total_us"], int) and out["heal_total_us"] > 0

    # Ledger heartbeat ping
    pings = [d for d in db.agent_ledger_entries.inserts
             if d.get("kind") == "boot_unwedge"]
    assert len(pings) == 1
    assert pings[0]["agent_id"] == "scout_ora"
    assert pings[0]["meta"]["healed_by"] == "wedge_detector"

    # A2A signal
    assert len(db.agent_a2a_signals.inserts) == 1
    sig = db.agent_a2a_signals.inserts[0]
    assert sig["kind"] == "wedge_recovered"
    assert sig["from"] == "wedge_detector"
    assert sig["to"] == "scout_ora"
    assert sig["payload"]["age_seconds"] == 3600

    # Pulse log
    assert len(db.system_pulse_actions.inserts) == 1
    pulse = db.system_pulse_actions.inserts[0]
    assert pulse["action_taken"] == "recovered_after_wedge_heal"
    assert pulse["agent_id"] == "scout_ora"
    assert pulse["age_seconds_before_heal"] == 3600


@pytest.mark.asyncio
async def test_auto_heal_respects_cooldown():
    """Second heal within cooldown window must be skipped."""
    db = _FakeDB()
    # Pre-seed an A2A signal so the cooldown guard fires
    db.agent_a2a_signals.docs.append({
        "kind": "wedge_recovered",
        "to": "scout_ora",
        "ts": _ago_iso(5),  # 5 seconds ago
    })
    out = await awd.auto_heal_agent(db, "scout_ora", age_seconds=3600)
    assert out["healed"] is False
    assert out["reason"] == "in_cooldown"
    # No new artifacts written
    assert db.agent_ledger_entries.inserts == []
    assert db.system_pulse_actions.inserts == []


@pytest.mark.asyncio
async def test_auto_heal_force_overrides_cooldown():
    db = _FakeDB()
    db.agent_a2a_signals.docs.append({
        "kind": "wedge_recovered",
        "to": "scout_ora",
        "ts": _ago_iso(5),
    })
    out = await awd.auto_heal_agent(
        db, "scout_ora", age_seconds=3600, force=True,
    )
    assert out["healed"] is True


@pytest.mark.asyncio
async def test_auto_heal_rejects_blank_agent_id():
    out = await awd.auto_heal_agent(db=None, agent_id="")
    assert out["healed"] is False
    assert out["reason"] == "no_agent_id"


# ─── Microsecond budget ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_heal_completes_under_200ms():
    """Sovereign claim: detection → 3-step cascade in micro-to-millisec.
    With fakes there's no I/O latency; this enforces the cascade's own
    overhead stays tiny so production budget remains believable."""
    db = _FakeDB()
    out = await awd.auto_heal_agent(db, "scout_ora", age_seconds=3600)
    # Each step also reports its own us-budget
    for s in out["steps"]:
        assert s.get("ok") is True
        assert s.get("elapsed_us", 0) >= 0  # might be 0 on very fast hosts
    # Total cascade < 200_000 us = 200 ms
    assert out["heal_total_us"] < 200_000


# ─── Scheduler entry-point ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_run_wedge_scan_finds_and_heals(monkeypatch):
    db = _FakeDB()
    db.agent_ledger_entries.docs.append({
        "agent_id": "scout_ora", "kind": "cost",
        "timestamp": _ago_iso(3600),
    })
    monkeypatch.setattr(awd, "WEDGE_THRESHOLD_S", 60)
    out = await awd.run_wedge_scan(db)
    assert out["wedged_detected"] == 1
    assert len(out["healed"]) == 1
    assert out["healed"][0]["agent_id"] == "scout_ora"
    assert out["skipped"] == []
    assert out["elapsed_ms"] >= 0


@pytest.mark.asyncio
async def test_run_wedge_scan_clean_when_no_wedge():
    db = _FakeDB()
    out = await awd.run_wedge_scan(db)
    assert out["wedged_detected"] == 0
    assert out["healed"] == []
    assert out["skipped"] == []


# ─── Stats ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_wedge_stats_counts_recoveries():
    db = _FakeDB()
    # Seed 3 historical heals
    for i in range(3):
        db.system_pulse_actions.docs.append({
            "action_taken": "recovered_after_wedge_heal",
            "agent_id": f"agent_{i}",
            "heal_total_us": 1500 + i * 100,
            "ts": _ago_iso(60 * (i + 1)),
        })
    out = await awd.get_wedge_stats(db, hours=24)
    assert out["auto_healed_24h"] == 3
    assert out["wedges_now"] == 0
    assert out["avg_heal_us"] > 0


# ─── A2A multi-tier (T2 council + T3 sovereign) ────────────────────────
@pytest.mark.asyncio
async def test_council_role_silent_is_wedged():
    db = _FakeDB()
    db.council_sessions.docs.append({
        "role": "scout", "winner": "scout",
        "ts": _ago_iso(7200),  # 2 hours ago
    })
    out = await awd.detect_wedged_council(db, threshold_s=3600)
    # Only 'scout' has any heartbeat — others have None → dormant, skipped
    assert len(out) == 1
    assert out[0]["agent_id"] == "council:scout"
    assert out[0]["tier"] == "T2_council"
    assert out[0]["reason"] == "stale_council_heartbeat"


@pytest.mark.asyncio
async def test_council_role_recent_is_not_wedged():
    db = _FakeDB()
    db.council_sessions.docs.append({
        "role": "scout", "ts": _ago_iso(60),
    })
    out = await awd.detect_wedged_council(db, threshold_s=3600)
    assert out == []


@pytest.mark.asyncio
async def test_sovereign_worker_silent_is_wedged():
    db = _FakeDB()
    db.system_pulse_actions.docs.append({
        "source": "sovereign_watchdog",
        "action_taken": "scan_summary",
        "ts": _ago_iso(3600),
    })
    out = await awd.detect_wedged_sovereign_workers(db, threshold_s=60)
    assert len(out) == 1
    assert out[0]["agent_id"] == "worker:sovereign_watchdog"
    assert out[0]["tier"] == "T3_sovereign"


@pytest.mark.asyncio
async def test_detect_all_wedges_aggregates_three_tiers():
    db = _FakeDB()
    # T1 customer ORA — 1 hour stale
    db.agent_ledger_entries.docs.append({
        "agent_id": "scout_ora", "kind": "cost",
        "timestamp": _ago_iso(3600),
    })
    # T2 council role — 2 hours stale
    db.council_sessions.docs.append({
        "role": "envoy", "winner": "envoy",
        "ts": _ago_iso(7200),
    })
    # T3 sovereign worker — 30 min stale
    db.system_pulse_actions.docs.append({
        "source": "council_rotation", "action_taken": "tick",
        "ts": _ago_iso(2400),
    })

    # Use a low threshold so all three trigger
    import services.agent_wedge_detector as m
    saved = m.WEDGE_THRESHOLD_S
    try:
        m.WEDGE_THRESHOLD_S = 60
        out = await awd.detect_all_wedges(db)
    finally:
        m.WEDGE_THRESHOLD_S = saved

    tiers = {row["tier"] for row in out}
    assert "T1_customer" in tiers
    assert "T2_council" in tiers
    assert "T3_sovereign" in tiers


# ─── Learning loop (Memory Guard 2-stamp queue) ────────────────────────
@pytest.mark.asyncio
async def test_run_wedge_scan_records_learning_observation(monkeypatch):
    db = _FakeDB()
    db.agent_ledger_entries.docs.append({
        "agent_id": "scout_ora", "kind": "cost",
        "timestamp": _ago_iso(3600),
    })
    monkeypatch.setattr(awd, "WEDGE_THRESHOLD_S", 60)
    out = await awd.run_wedge_scan(db)
    assert out["wedged_detected"] >= 1
    # At least one learning observation must be queued for the
    # Memory Guard 2-stamp gate.
    learnings = [
        d for d in db.learnings_pending_review.inserts
        if d.get("kind") == "agent_wedge_observation"
        and d.get("subject") == "scout_ora"
    ]
    assert len(learnings) >= 1
    L = learnings[0]
    assert L["status"] == "pending"
    assert L["tier"] == "T1_customer"
    assert L["payload"]["auto_healed"] is True
    # Exactly one stamp from the wedge_detector — Council Rotation
    # adds the second stamp asynchronously.
    assert len(L["stamps"]) == 1
    assert L["stamps"][0]["role"] == "wedge_detector"


@pytest.mark.asyncio
async def test_run_wedge_scan_breaks_down_by_tier(monkeypatch):
    db = _FakeDB()
    db.agent_ledger_entries.docs.append({
        "agent_id": "envoy_ora", "kind": "cost",
        "timestamp": _ago_iso(3600),
    })
    db.council_sessions.docs.append({
        "role": "casl", "winner": "casl",
        "ts": _ago_iso(7200),
    })
    monkeypatch.setattr(awd, "WEDGE_THRESHOLD_S", 60)
    out = await awd.run_wedge_scan(db)
    assert "wedged_by_tier" in out
    assert out["wedged_by_tier"]["T1_customer"] >= 1
    assert out["wedged_by_tier"]["T2_council"] >= 1


@pytest.mark.asyncio
async def test_get_wedge_stats_safe_when_no_db():
    out = await awd.get_wedge_stats(db=None)
    assert out["wedges_now"] == 0
    assert out["auto_healed_24h"] == 0
    assert out["avg_heal_us"] == 0
