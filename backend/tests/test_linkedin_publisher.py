"""
LinkedIn Publisher tests — iter 282aj (Prompt 7, Task G).

Mock-DB only. Real network is never hit; we verify:
  • publish returns no_token when disconnected
  • queue_post_if_offline persists the pending row
  • composer cache hit skips the LLM call
  • /api/linkedin/status returns not_connected on empty DB
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.linkedin_publisher import (  # noqa: E402
    publish_linkedin_post,
    queue_post_if_offline,
)


# ─────────────────────────────────────────────────────────────────────
# Tiny mock-DB — collection-name aware, in-memory
# ─────────────────────────────────────────────────────────────────────
class _MockCollection:
    def __init__(self):
        self._docs = []

    @staticmethod
    def _match(doc, q):
        for k, v in (q or {}).items():
            if isinstance(v, dict) and all(op.startswith("$") for op in v.keys()):
                got = doc.get(k)
                for op, val in v.items():
                    if op == "$gt" and not (got is not None and got > val):
                        return False
                    if op == "$gte" and not (got is not None and got >= val):
                        return False
                    if op == "$lt" and not (got is not None and got < val):
                        return False
                    if op == "$lte" and not (got is not None and got <= val):
                        return False
            elif doc.get(k) != v:
                return False
        return True

    async def find_one(self, q, projection=None, **kw):
        if not q:
            return self._docs[-1] if self._docs else None
        for d in self._docs:
            if self._match(d, q):
                return dict(d)
        return None

    async def insert_one(self, doc):
        self._docs.append(dict(doc))
        class R:
            inserted_id = None
        return R()

    async def update_one(self, q, upd, upsert=False):
        d = None
        for cand in self._docs:
            if all(cand.get(k) == v for k, v in q.items()):
                d = cand
                break
        if d is None and upsert:
            d = dict(q)
            self._docs.append(d)
        if d is not None:
            d.update(upd.get("$set") or {})
        class R:
            pass
        return R()

    async def delete_one(self, q):
        for i, d in enumerate(self._docs):
            if all(d.get(k) == v for k, v in q.items()):
                self._docs.pop(i)
                break
        class R:
            pass
        return R()

    async def count_documents(self, q, **kw):
        if not q:
            return len(self._docs)
        return sum(1 for d in self._docs
                    if all(d.get(k) == v for k, v in q.items()))

    def find(self, q=None, projection=None, **kw):
        docs = [dict(d) for d in self._docs
                 if not q or all(d.get(k) == v for k, v in q.items())]
        class _Cursor:
            def __init__(self, docs):
                self._docs = docs
            def sort(self, *a, **k):
                return self
            def limit(self, n):
                self._docs = self._docs[:n]
                return self
            async def to_list(self, length=None):
                return self._docs[:length or len(self._docs)]
            def __aiter__(self):
                self._i = 0
                return self
            async def __anext__(self):
                if self._i >= len(self._docs):
                    raise StopAsyncIteration
                v = self._docs[self._i]
                self._i += 1
                return v
        return _Cursor(docs)


class _MockDB:
    def __init__(self):
        self._cols = {}
    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._cols:
            self._cols[name] = _MockCollection()
        return self._cols[name]


def _run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────
def test_publish_returns_no_token_when_disconnected(monkeypatch):
    # Force the composer into fallback so the test doesn't hit a real LLM
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    db = _MockDB()
    ctx = {"business_name": "Acme HVAC", "category": "hvac", "city": "Toronto"}
    r = _run(publish_linkedin_post(db, "weekly_tip", ctx))
    assert r["published"] is False
    assert r["reason"] == "no_token"


def test_queue_post_saves_to_db():
    db = _MockDB()
    ctx = {"business_name": "Acme HVAC", "category": "hvac"}
    _run(queue_post_if_offline(db, "case_study", ctx))
    docs = db.linkedin_publish_queue._docs
    assert len(docs) == 1
    assert docs[0]["post_type"] == "case_study"
    assert docs[0]["status"] == "pending_auth"


def test_composer_cache_hit_skips_llm(monkeypatch):
    """Seed composed_outreach_cache, then verify compose_outreach returns it
    instantly with cache_hit=True (no LLM env needed even when key present)."""
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test-blocked-by-cache")
    db = _MockDB()
    seeded = {
        "channel":       "linkedin", "subject": None,
        "body":          "cached message",
        "tone_used":     "Tone: neutral and professional.",
        "model":         "anthropic:claude-sonnet-4-5-20250929",
        "composed_at":   datetime.now(timezone.utc),
        "fallback_used": False,
    }
    cache_key = "lead-xyz:linkedin:1"
    _run(db.composed_outreach_cache.insert_one({
        "key":     cache_key,
        "channel": "linkedin",
        "step":    1,
        "result":  seeded,
        "ts":      datetime.now(timezone.utc),
    }))
    from services.outreach_composer import compose_outreach
    r = _run(compose_outreach(
        {"lead_id": "lead-xyz", "business_name": "Test Inc."},
        "linkedin", 1, db,
    ))
    assert r["cache_hit"] is True
    assert r["body"] == "cached message"


def test_linkedin_status_not_connected():
    """Status endpoint's shape check — running via the helper directly so we
    don't need to boot FastAPI in the test process."""
    from routers.linkedin_router import get_token_doc
    async def _go():
        # Simulate empty DB by patching server.db to a fresh mock
        import server
        original = getattr(server, "db", None)
        server.db = _MockDB()
        try:
            doc = await get_token_doc()
            assert doc is None
        finally:
            server.db = original
    _run(_go())
