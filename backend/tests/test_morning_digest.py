"""
Morning Digest — format + collection logic tests.
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.morning_digest import _format_digest, build_digest  # noqa: E402


class FakeAgg:
    def __init__(self, out):
        self.out = out

    async def to_list(self, length=None):
        return self.out


class FakeCollection:
    def __init__(self):
        self.docs = []
        self._agg_out = []
        self._count_default = 0
        self._find_one_out = None

    def aggregate(self, pipeline):
        return FakeAgg(self._agg_out)

    async def count_documents(self, q):
        return self._count_default

    async def find_one(self, q, projection=None, sort=None):
        return self._find_one_out

    def find(self, q, projection=None):
        class _Cursor:
            def __init__(self, items):
                self._items = items

            def limit(self, n):
                return self

            async def to_list(self, length=None):
                return self._items

            def __aiter__(self):
                self._idx = 0
                return self

            async def __anext__(self):
                if self._idx < len(self._items):
                    item = self._items[self._idx]
                    self._idx += 1
                    return item
                raise StopAsyncIteration

        return _Cursor(self.docs)


class FakeDB:
    def __init__(self):
        self.campaign_leads = FakeCollection()
        self.aurem_live_viewers = FakeCollection()
        self.voice_calls = FakeCollection()
        self.morning_digest_log = FakeCollection()


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_format_empty_day():
    data = {
        "opens": [], "clicks": [], "hottest": None, "replies": [],
        "calls_24h": 0, "stages": {"new": 0, "engaged": 0, "following_up": 0},
        "won_this_week": 0, "this_week_avg_days": 0, "last_week_avg_days": 0, "pct_change_days": 0,
    }
    body = _format_digest(data)
    assert "AUREM Morning Digest" in body
    assert "Emails opened last night: *0*" in body
    assert "Calls made: *0*" in body


def test_format_with_activity():
    data = {
        "opens": [{"business_name": "Cafe X"}, {"business_name": "Gym Y"}],
        "clicks": [{"business_name": "Gym Y"}],
        "hottest": {"business_name": "Gym Y", "ping_count": 15},
        "replies": [{"business_name": "Pizza Z", "body": "Yes I'm interested"}],
        "calls_24h": 3,
        "stages": {"new": 10, "engaged": 5, "following_up": 2},
        "won_this_week": 4,
        "this_week_avg_days": 3.2, "last_week_avg_days": 5.0, "pct_change_days": -36,
    }
    body = _format_digest(data)
    assert "Cafe X" in body
    assert "Gym Y" in body
    assert "Pizza Z" in body
    assert "Hottest lead" in body
    assert "Won this week: *4*" in body
    assert "↓" in body  # avg days went down
    assert "36%" in body


def test_format_pct_change_up():
    data = {
        "opens": [], "clicks": [], "hottest": None, "replies": [],
        "calls_24h": 0, "stages": {}, "won_this_week": 0,
        "this_week_avg_days": 5, "last_week_avg_days": 3, "pct_change_days": 67,
    }
    body = _format_digest(data)
    assert "↑" in body
    assert "67%" in body


def test_build_digest_runs_end_to_end():
    db = FakeDB()
    res = _run(build_digest(db))
    assert "body" in res
    assert "data" in res
    assert "AUREM Morning Digest" in res["body"]


if __name__ == "__main__":
    test_format_empty_day()
    test_format_with_activity()
    test_format_pct_change_up()
    test_build_digest_runs_end_to_end()
    print("All morning digest tests passed")
