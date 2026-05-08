"""Tests for /app/backend/services/trial_winback.py — Section 8."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import pytest

sys.path.insert(0, "/app/backend")

# Tight schedule for testing
os.environ["TRIAL_WINBACK_OFFSETS"] = "0,3,8"

from services import trial_winback  # noqa: E402


class _FakeColl:
    def __init__(self) -> None:
        self.docs: List[Dict[str, Any]] = []

    async def find_one(self, q, proj=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                return dict(d)
        return None

    def find(self, q, proj=None):
        results = []
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if isinstance(v, dict):
                    continue  # ignore complex query ops in tests
                if d.get(k) != v:
                    ok = False; break
            if ok: results.append(dict(d))
        class _Cursor:
            def __init__(self, items): self.items = items
            def limit(self, n): return _Cursor(self.items[:n])
            async def to_list(self, n): return self.items[:n]
        return _Cursor(results)

    async def update_one(self, q, upd, upsert=False):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items() if not k.startswith("$")):
                if "$set" in upd:
                    for k, v in upd["$set"].items():
                        d[k] = v
                return type("R", (), {"modified_count": 1})()
        if upsert:
            new = {**{k: v for k, v in q.items() if not k.startswith("$")},
                   **upd.get("$set", {})}
            self.docs.append(new)
            return type("R", (), {"modified_count": 0, "upserted_id": "x"})()
        return type("R", (), {"modified_count": 0})()

    async def insert_one(self, d):
        self.docs.append(dict(d))
        return type("R", (), {"inserted_id": 1})()

    async def count_documents(self, q):
        n = 0
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                n += 1
        return n


class _FakeDB:
    def __init__(self) -> None:
        self.trial_winbacks = _FakeColl()
        self.platform_users = _FakeColl()
        self.customer_subscriptions = _FakeColl()


@pytest.fixture(autouse=True)
def _stub_senders(monkeypatch):
    """Stub email + sms senders so tests stay fast and deterministic."""
    sent = {"emails": [], "sms": []}

    async def _fake_email(to, subject, html):
        sent["emails"].append({"to": to, "subject": subject})

    async def _fake_sms(to, body):
        sent["sms"].append({"to": to, "body": body})

    fake_email_mod = type(sys)("services.resend_email")
    fake_email_mod.send_email = _fake_email  # type: ignore
    sys.modules["services.resend_email"] = fake_email_mod

    fake_sms_mod = type(sys)("services.twilio_sms")
    fake_sms_mod.send_sms = _fake_sms  # type: ignore
    sys.modules["services.twilio_sms"] = fake_sms_mod
    yield sent


# ─────────────────────────────────────────────────────────────────────
# Pure content tests
# ─────────────────────────────────────────────────────────────────────

def test_step_1_subject_mentions_trial_ended():
    c = trial_winback._step_content(1, "x@y.z", "BIN")
    assert "trial ended" in c["subject"].lower()
    assert "/billing" in c["html"]
    assert "/billing" in c["sms"]


def test_step_2_includes_discount_pct():
    c = trial_winback._step_content(2, "x@y.z", "BIN")
    pct = trial_winback.FOUNDER_DISCOUNT_PCT
    assert f"{pct}%" in c["subject"]
    assert "promo=founder" in c["html"]


def test_step_3_says_final():
    c = trial_winback._step_content(3, "x@y.z", "BIN")
    assert "final" in c["subject"].lower() or "last" in c["subject"].lower()


# ─────────────────────────────────────────────────────────────────────
# Arm + cancel
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_arm_creates_winback_doc():
    db = _FakeDB()
    res = await trial_winback.arm_trial_winback(db, "a@b.c", "BIN1")
    assert res["ok"]
    assert res.get("armed")
    row = await db.trial_winbacks.find_one({"email": "a@b.c"})
    assert row["last_step"] == 0
    assert row["completed"] is False
    assert row["cancelled"] is False


@pytest.mark.asyncio
async def test_arm_is_idempotent():
    db = _FakeDB()
    await trial_winback.arm_trial_winback(db, "a@b.c", "BIN1")
    res2 = await trial_winback.arm_trial_winback(db, "a@b.c", "BIN1")
    assert res2["ok"] and res2.get("already_armed") is True
    assert len(db.trial_winbacks.docs) == 1


@pytest.mark.asyncio
async def test_cancel_marks_doc_cancelled():
    db = _FakeDB()
    await trial_winback.arm_trial_winback(db, "a@b.c", "BIN1")
    await trial_winback.cancel_trial_winback(db, "a@b.c", reason="subscribed")
    row = await db.trial_winbacks.find_one({"email": "a@b.c"})
    assert row["cancelled"] is True
    assert row["cancelled_reason"] == "subscribed"


@pytest.mark.asyncio
async def test_arm_lowercases_email():
    db = _FakeDB()
    await trial_winback.arm_trial_winback(db, "MIXED@CASE.com", "BIN1")
    row = await db.trial_winbacks.find_one({"email": "mixed@case.com"})
    assert row is not None


# ─────────────────────────────────────────────────────────────────────
# Scheduler advance logic
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fire_due_steps_advances_step_1_immediately(_stub_senders):
    db = _FakeDB()
    await trial_winback.arm_trial_winback(db, "u@v.w", "BIN")
    res = await trial_winback.fire_due_steps(db)
    assert res["ok"]
    assert res["advanced"] == 1
    row = await db.trial_winbacks.find_one({"email": "u@v.w"})
    assert row["last_step"] == 1
    assert len(_stub_senders["emails"]) == 1


@pytest.mark.asyncio
async def test_fire_due_steps_skips_when_not_due(_stub_senders):
    db = _FakeDB()
    await trial_winback.arm_trial_winback(db, "u@v.w", "BIN")
    # First cycle fires step 1
    await trial_winback.fire_due_steps(db)
    # Second cycle should NOT fire step 2 (3 days away)
    res2 = await trial_winback.fire_due_steps(db)
    assert res2["advanced"] == 0
    assert res2["skipped_not_due"] == 1


@pytest.mark.asyncio
async def test_fire_due_steps_cancels_when_user_subscribes(_stub_senders):
    db = _FakeDB()
    await trial_winback.arm_trial_winback(db, "u@v.w", "BIN")
    # Add an active subscription
    await db.customer_subscriptions.insert_one({"email": "u@v.w", "status": "active"})
    res = await trial_winback.fire_due_steps(db)
    assert res["advanced"] == 0
    row = await db.trial_winbacks.find_one({"email": "u@v.w"})
    assert row["cancelled"] is True


@pytest.mark.asyncio
async def test_fire_due_steps_marks_completed_after_last(_stub_senders):
    db = _FakeDB()
    await trial_winback.arm_trial_winback(db, "u@v.w", "BIN")
    # Hand-roll the doc to be "step 2 done, armed 9 days ago" so step 3 fires
    await db.trial_winbacks.update_one(
        {"email": "u@v.w"},
        {"$set": {
            "last_step": 2,
            "armed_at": (datetime.now(timezone.utc) - timedelta(days=9)).isoformat(),
        }},
    )
    res = await trial_winback.fire_due_steps(db)
    assert res["advanced"] == 1
    row = await db.trial_winbacks.find_one({"email": "u@v.w"})
    assert row["last_step"] == 3
    assert row["completed"] is True
