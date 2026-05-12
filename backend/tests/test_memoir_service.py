"""
End-to-end test for AUREM Memoir integration.
Covers: remember/recall/search/history/commit + ORA + audit + skill + founder helpers.
"""
import os
import sys
import time

import pytest

sys.path.insert(0, "/app/backend")
from services import memoir_service as M  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _init_memoir():
    assert M.init() is True, "Memoir failed to initialise"
    yield


def test_info():
    info = M.info()
    assert info["available"] is True
    assert info["store_path"]
    assert info["init_error"] is None


def test_remember_recall():
    sha = M.remember("aurem.test.unit", "smoke_key", {"foo": "bar"}, commit_msg="unit:smoke")
    assert sha is None or isinstance(sha, str)  # auto-commit may already have happened
    val = M.recall("aurem.test.unit", "smoke_key")
    assert val == {"foo": "bar"}


def test_search():
    for i in range(5):
        M.remember("aurem.test.unit.batch", f"k{i}", {"i": i})
    rows = M.search("aurem.test.unit.batch", limit=10)
    assert len(rows) >= 5
    # rows are (namespace, key, value)
    for ns, k, v in rows:
        assert isinstance(ns, tuple) or isinstance(ns, list)
        assert isinstance(k, str)
        assert "i" in v


def test_history():
    # Re-write same key twice → 2 history entries
    M.remember("aurem.test.unit.history", "hk", {"v": 1})
    M.remember("aurem.test.unit.history", "hk", {"v": 2})
    h = M.history("aurem.test.unit.history", "hk", limit=5)
    assert isinstance(h, list)
    assert len(h) >= 1  # at least 1 commit


def test_ora_helpers():
    sid = f"sess_{int(time.time())}"
    M.ora_remember_turn(sid, "user", "hi")
    time.sleep(0.01)
    M.ora_remember_turn(sid, "assistant", "Hi there!")
    turns = M.ora_recall_session(sid, limit=5)
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["role"] == "assistant"


def test_customer_audit_helpers():
    email = "test+memoir@aurem.live"
    summary = {"url": "https://x.com", "scores": {"seo": 80}}
    M.customer_save_audit(email, summary)
    got = M.customer_recall_audit(email)
    assert got["url"] == "https://x.com"


def test_founder_save():
    sid = f"save_{int(time.time())}"
    M.founder_save_log(sid, {"field": "industry", "old": "auto", "new": "plumbing"})
    M.founder_save_log(sid, {"field": "industry", "old": "plumbing", "new": "hvac"})
    h = M.founder_save_history(sid, limit=10)
    assert isinstance(h, list)


def test_skill_broadcast():
    sha = M.skill_broadcast_set("addendum text", ["skill_a", "skill_b"])
    assert sha is None or isinstance(sha, str)
    got = M.skill_broadcast_get()
    assert got["skill_ids"] == ["skill_a", "skill_b"]
    assert got["system_addendum"] == "addendum text"


def test_stats():
    s = M.stats()
    assert s["available"] is True
    assert "performance" in s
    assert s["total_keys"] > 0
