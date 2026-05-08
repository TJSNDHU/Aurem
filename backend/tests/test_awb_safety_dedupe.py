"""
iter 282al-24 — Tests for awb_safety dedupe-then-retry index ensure.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class _AsyncCursor:
    def __init__(self, rows):
        self._rows = rows

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self._rows):
            raise StopAsyncIteration
        r = self._rows[self._i]
        self._i += 1
        return r


@pytest.mark.asyncio
async def test_ensure_indexes_dedupes_then_retries_on_e11000():
    """When create_index raises E11000, dedupe runs and create_index retries."""
    from services import awb_safety as mod

    db = MagicMock()
    coll = MagicMock()
    db.auto_built_sites = coll

    # First call raises E11000, second call succeeds
    coll.create_index = AsyncMock(side_effect=[
        Exception("E11000 duplicate key error"),
        "unique_lead_active_site",
    ])
    # Aggregate returns one duplicate group with 2 site_ids
    coll.aggregate = MagicMock(return_value=_AsyncCursor([
        {"_id": {"lead_id": "lead-x", "status": "deployed"},
         "ids": [
             {"site_id": "s1", "created_at": "2026-02-01"},
             {"site_id": "s2", "created_at": "2026-02-10"},
         ],
         "count": 2},
    ]))
    res = MagicMock(); res.modified_count = 1
    coll.update_many = AsyncMock(return_value=res)

    out = await mod.ensure_indexes(db)
    assert out["ok"] is True
    assert out["index"] == "unique_lead_active_site"
    assert out["deduped"] == 1
    # The newest (s2) is the keeper, s1 demoted
    args, _ = coll.update_many.call_args
    assert args[0] == {"site_id": {"$in": ["s1"]}}
    assert args[1]["$set"]["status"] == "archived"


@pytest.mark.asyncio
async def test_ensure_indexes_returns_ok_on_first_try():
    from services import awb_safety as mod
    db = MagicMock()
    db.auto_built_sites.create_index = AsyncMock(return_value="unique_lead_active_site")
    out = await mod.ensure_indexes(db)
    assert out["ok"] is True
    assert "deduped" not in out


@pytest.mark.asyncio
async def test_ensure_indexes_no_db():
    from services.awb_safety import ensure_indexes
    out = await ensure_indexes(None)
    assert out["ok"] is False


@pytest.mark.asyncio
async def test_ensure_indexes_non_e11000_does_not_retry():
    """Other errors should NOT trigger dedupe."""
    from services import awb_safety as mod
    db = MagicMock()
    db.auto_built_sites.create_index = AsyncMock(side_effect=Exception("connection lost"))
    db.auto_built_sites.aggregate = MagicMock()
    out = await mod.ensure_indexes(db)
    assert out["ok"] is False
    db.auto_built_sites.aggregate.assert_not_called()
