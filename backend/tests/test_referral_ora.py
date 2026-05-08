"""Tests for Referral ORA engine (iter 322p)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest

from services import referral_ora_engine as roe


def _iso_ago(days: float = 0) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).isoformat()


class _FakeColl:
    def __init__(self, docs: List[Dict[str, Any]] | None = None):
        self.docs: List[Dict[str, Any]] = list(docs or [])
        self.inserts: List[Dict[str, Any]] = []

    def find(self, q, proj=None):
        items = [d for d in self.docs if all(d.get(k) == v for k, v in q.items())]

        class _Cursor:
            def __init__(self, items):
                self._items = items
                self._n = None

            def limit(self, n):
                self._n = n
                return self

            def __aiter__(self):
                self._iter = iter(
                    self._items[: self._n] if self._n else self._items
                )
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration

        return _Cursor(items)

    async def find_one(self, q, proj=None):
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
                return d
        return None

    async def insert_one(self, doc):
        self.inserts.append(doc)
        self.docs.append(doc)


class _FakeDB:
    def __init__(self):
        self.customer_subscriptions = _FakeColl()
        self.referrals_outbox = _FakeColl()
        self.agent_ledger_entries = _FakeColl()


@pytest.mark.asyncio
async def test_no_db_safe():
    out = await roe.run_referral_tick(db=None)
    assert out["ok"] is False


@pytest.mark.asyncio
async def test_active_customer_gets_referral_ask():
    db = _FakeDB()
    db.customer_subscriptions.docs.append({
        "email": "alice@example.com", "status": "active",
        "tenant_bin": "AURE-XYZ", "service_id": "svc-1",
        "started_at": _iso_ago(days=45),
    })
    out = await roe.run_referral_tick(db)
    assert out["ok"] is True
    assert out["customers_scanned"] == 1
    assert out["asks"] == 1
    assert len(db.referrals_outbox.inserts) == 1
    row = db.referrals_outbox.inserts[0]
    assert row["customer_email"] == "alice@example.com"
    assert row["agent"] == "referral_ora"
    assert row["channel"] == "in_app"  # dry-run default
    assert row["status"] == "queued"

    # Heartbeat ledger row must exist so wedge-detector sees agent alive
    pings = [d for d in db.agent_ledger_entries.inserts
             if d.get("agent_id") == "referral_ora"]
    assert len(pings) == 1


@pytest.mark.asyncio
async def test_recently_asked_customer_skipped():
    db = _FakeDB()
    db.customer_subscriptions.docs.append({
        "email": "alice@example.com", "status": "active",
    })
    db.referrals_outbox.docs.append({
        "customer_email": "alice@example.com",
        "ts": _iso_ago(days=5),  # within 30-day gap
    })
    out = await roe.run_referral_tick(db)
    assert out["customers_scanned"] == 1
    assert out["asks"] == 0
    assert out["skipped_in_cooldown"] == 1


@pytest.mark.asyncio
async def test_inactive_customer_skipped():
    db = _FakeDB()
    db.customer_subscriptions.docs.append({
        "email": "alice@example.com", "status": "cancelled",
    })
    out = await roe.run_referral_tick(db)
    # find filter is status=active, so inactive customers don't even surface
    assert out["customers_scanned"] == 0


@pytest.mark.asyncio
async def test_invalid_email_skipped():
    db = _FakeDB()
    db.customer_subscriptions.docs.append({
        "email": "not-an-email", "status": "active",
    })
    out = await roe.run_referral_tick(db)
    assert out["customers_scanned"] == 1
    assert out["asks"] == 0
