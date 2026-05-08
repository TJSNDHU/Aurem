"""Tests for the Council Rotation Worker (iter 322l Day 2.2)."""
from unittest.mock import patch, AsyncMock

import pytest

from services import council_rotation as cr
from services import sovereign_memory as smg

from test_sovereign_memory import FakeDB


@pytest.mark.asyncio
async def test_rotate_once_no_pending_items_is_noop():
    db = FakeDB()
    summary = await cr.rotate_once(db)
    assert summary["reviews"] == 0
    assert summary["promoted"] == 0


@pytest.mark.asyncio
async def test_agent_decide_parses_approve():
    fake_council = AsyncMock(return_value={
        "ok": True,
        "final_response": "APPROVE — evidence aligns with logs",
        "winner": "dev",
    })
    with patch("services.ora_council.convene_council", side_effect=fake_council):
        out = await cr._agent_decide(
            agent_role="dev",
            candidate={"id": "x", "kind": "k", "submitted_by": "watchdog",
                       "payload": {}, "evidence": {"e": 1}},
            db=FakeDB(),
        )
    assert out["vote"] == "approve"


@pytest.mark.asyncio
async def test_agent_decide_parses_reject():
    fake_council = AsyncMock(return_value={
        "ok": True,
        "final_response": "REJECT — evidence is thin",
    })
    with patch("services.ora_council.convene_council", side_effect=fake_council):
        out = await cr._agent_decide(
            agent_role="qa",
            candidate={"id": "x", "kind": "k", "submitted_by": "watchdog",
                       "payload": {}, "evidence": {}},
            db=FakeDB(),
        )
    assert out["vote"] == "reject"


@pytest.mark.asyncio
async def test_agent_decide_defaults_reject_on_llm_error():
    async def boom(*_a, **_k):
        raise RuntimeError("llm-down")
    with patch("services.ora_council.convene_council", side_effect=boom):
        out = await cr._agent_decide(
            agent_role="security",
            candidate={"id": "x", "kind": "k", "submitted_by": "watchdog",
                       "payload": {}, "evidence": {"e": 1}},
            db=FakeDB(),
        )
    assert out["vote"] == "reject"
    assert "llm_unavailable" in out["notes"]


@pytest.mark.asyncio
async def test_rotate_once_full_path_promotes_after_two_distinct_stamps():
    """E2E: a watchdog candidate gets one stamp from a rotation tick,
    then a second stamp on the next tick → promoted."""
    db = FakeDB()
    await smg.submit_learning(
        db, agent_role="watchdog", kind="redis_fix",
        payload={}, evidence={"src": "log"},
    )

    fake_council = AsyncMock(return_value={
        "ok": True, "final_response": "APPROVE — looks safe",
    })
    # Force the random.shuffle to be deterministic so we can predict which
    # role votes first.
    seq = ["dev", "qa", "security", "pricing", "casl", "seo"]
    with patch.object(cr.random, "shuffle", lambda lst: lst.sort(
        key=lambda x: seq.index(x))):
        with patch("services.ora_council.convene_council",
                   side_effect=fake_council):
            # Limit to one review per tick to test idempotency cleanly.
            with patch.object(cr, "RUN_LIMIT", 1):
                t1 = await cr.rotate_once(db)
                t2 = await cr.rotate_once(db)

    assert t1["reviews"] == 1
    assert t1["promoted"] == 0
    assert t2["reviews"] == 1
    assert t2["promoted"] == 1
    # Live collection now has the row
    assert await db[smg.LIVE].count_documents({}) == 1


@pytest.mark.asyncio
async def test_rotate_once_skips_when_only_submitter_role_could_review():
    """If watchdog submitted the only candidate and the rotation roles
    happen to all have already stamped, rotate_once does nothing."""
    db = FakeDB()
    lid = await smg.submit_learning(
        db, agent_role="watchdog", kind="x",
        payload={}, evidence={"e": 1},
    )
    # Pre-stamp every rotation role.
    for r in cr.ROTATION_ROLES:
        await smg.review_learning(
            db, learning_id=lid, reviewer_role=r, vote="approve",
        )
    # The first 2 stamps already promoted it. Now try rotate — there's
    # no pending row left, so 0 reviews.
    summary = await cr.rotate_once(db)
    assert summary["reviews"] == 0
