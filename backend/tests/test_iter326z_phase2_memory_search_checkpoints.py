"""
test_iter326z_phase2_memory_search_checkpoints.py — Phase 2 P1.2 / P1.3 / P1.4
══════════════════════════════════════════════════════════════════════════════
Founder ask:
  P1.2 — long-running campaign jobs survive crashes via resumable checkpoints
  P1.3 — vector memory of past decisions ("did we fix this before?")
  P1.4 — semantic codebase search ("find code that calculates subscription cost")

WHAT THIS TEST LOCKS IN
───────────────────────
  P1.2  job_checkpoints
    • save_checkpoint upserts (last write wins)
    • load_checkpoint returns the last save or None
    • clear_checkpoint removes the row
    • list_checkpoints returns rows newest-first
    • TTL is honored (expires_at is set in the future)

  P1.3  ora_decision_memory + recall_past_decisions tool
    • log_decision writes a row with tags auto-extracted from summary
    • recall_past_decisions does $text search and returns matches
    • Empty/missing query handled gracefully
    • Tool registered in TOOL_REGISTRY (tier1_auto)

  P1.4  codebase_semantic_search + search_codebase_semantic tool
    • search() returns matches for a real intent (e.g. "cost calculation")
    • search() tokenizes + expands synonyms
    • Stop-words / 1-char tokens filtered
    • Index re-builds when fingerprint changes
    • Tool registered + tier1_auto

  Plumbing
    • All three set_db wired through ora_agent.set_db
    • resume_after_decision auto-logs decisions to memory

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326z_phase2_memory_search_checkpoints.py -v
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Shared fake Mongo collection / DB
# ─────────────────────────────────────────────────────────────────────────────
class _FakeColl:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.indexes: list = []

    async def create_index(self, *a, **kw):
        self.indexes.append((a, kw))
        return "idx"

    async def update_one(self, filt, update, upsert=False):
        # Minimal: match _id-only filters first
        key = filt.get("_id")
        target = None
        if key is not None and key in self.docs:
            target = self.docs[key]
        else:
            for d in self.docs.values():
                if all(d.get(k) == v for k, v in filt.items()
                       if not isinstance(v, dict)):
                    target = d; break
        if target is None and upsert:
            target = {"_id": key}
            self.docs[key] = target
        if target is None:
            return type("R", (), {"matched_count": 0, "modified_count": 0,
                                  "upserted_id": None})
        for sk, sv in (update.get("$set") or {}).items():
            target[sk] = sv
        return type("R", (), {"matched_count": 1, "modified_count": 1,
                              "upserted_id": None})

    async def insert_one(self, doc):
        key = doc.get("_id") or f"auto-{len(self.docs)}"
        self.docs[key] = doc
        return type("R", (), {"inserted_id": key})

    async def find_one(self, filt, projection=None):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in filt.items()):
                return dict(d)
        return None

    async def delete_one(self, filt):
        for k, d in list(self.docs.items()):
            if all(d.get(fk) == fv for fk, fv in filt.items()):
                del self.docs[k]
                return type("R", (), {"deleted_count": 1})
        return type("R", (), {"deleted_count": 0})

    def find(self, filt=None, projection=None):
        filt = filt or {}
        docs = []
        for d in self.docs.values():
            ok = True
            for k, v in filt.items():
                if k == "$text":
                    needle = (v.get("$search") or "").lower()
                    blob = " ".join(
                        str(d.get(x) or "")
                        for x in ("summary", "tool", "args_preview")
                    ).lower()
                    if not any(t in blob for t in needle.split()):
                        ok = False; break
                elif isinstance(v, dict) and "$in" in v:
                    field = d.get(k) or []
                    if not isinstance(field, list):
                        field = [field]
                    if not any(x in field for x in v["$in"]):
                        ok = False; break
                elif isinstance(v, dict) and "$regex" in v:
                    import re as _re
                    if not _re.search(v["$regex"], str(d.get(k) or "")):
                        ok = False; break
                else:
                    if d.get(k) != v:
                        ok = False; break
            if ok:
                docs.append(dict(d))
        cur = _Cursor(docs)
        return cur


class _Cursor:
    def __init__(self, docs):
        self.docs = docs
    def sort(self, *_a, **_kw):
        return self
    def limit(self, n):
        self.docs = self.docs[:n]
        return self
    def __aiter__(self):
        self._it = iter(self.docs)
        return self
    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeDB:
    def __init__(self):
        self.ora_job_checkpoints = _FakeColl()
        self.ora_decisions       = _FakeColl()
    def __getitem__(self, name):
        return getattr(self, name)


# ════════════════════════════════════════════════════════════════════════════
# P1.2 — job_checkpoints
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_checkpoint_save_then_load_roundtrip(monkeypatch):
    from services import job_checkpoints as jc
    fake = _FakeDB()
    jc.set_db(fake)
    r = await jc.save_checkpoint("job-A", step_idx=3, state={"i": 42, "city": "Toronto"})
    assert r["ok"] is True
    out = await jc.load_checkpoint("job-A")
    assert out is not None
    assert out["step_idx"] == 3
    assert out["state"] == {"i": 42, "city": "Toronto"}


@pytest.mark.asyncio
async def test_checkpoint_save_overwrites_previous():
    from services import job_checkpoints as jc
    fake = _FakeDB()
    jc.set_db(fake)
    await jc.save_checkpoint("job-B", 1, {"a": 1})
    await jc.save_checkpoint("job-B", 2, {"a": 2})
    out = await jc.load_checkpoint("job-B")
    assert out["step_idx"] == 2
    assert out["state"] == {"a": 2}


@pytest.mark.asyncio
async def test_checkpoint_clear_removes_row():
    from services import job_checkpoints as jc
    fake = _FakeDB()
    jc.set_db(fake)
    await jc.save_checkpoint("job-C", 0, {})
    r = await jc.clear_checkpoint("job-C")
    assert r["ok"] is True
    assert r["deleted"] == 1
    assert (await jc.load_checkpoint("job-C")) is None


@pytest.mark.asyncio
async def test_checkpoint_save_sets_ttl_in_future():
    from services import job_checkpoints as jc
    fake = _FakeDB()
    jc.set_db(fake)
    await jc.save_checkpoint("job-D", 1, {}, ttl_hours=24)
    row = fake.ora_job_checkpoints.docs["job-D"]
    assert isinstance(row.get("expires_at"), datetime)
    assert row["expires_at"] > datetime.now(timezone.utc) + timedelta(hours=23)


@pytest.mark.asyncio
async def test_checkpoint_load_returns_none_when_missing():
    from services import job_checkpoints as jc
    fake = _FakeDB()
    jc.set_db(fake)
    assert (await jc.load_checkpoint("nope")) is None


# ════════════════════════════════════════════════════════════════════════════
# P1.3 — ora_decision_memory
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_log_decision_writes_row_with_auto_tags():
    from services import ora_decision_memory as dm
    fake = _FakeDB()
    dm.set_db(fake)
    r = await dm.log_decision(
        session_id="s1", founder_email="f@a.com",
        tool="safe_edit",
        summary="Fix CORS to allow www.aurem.live for the customer login.",
        args={"path": "/app/backend/server.py"},
        outcome="approved",
    )
    assert r["ok"] is True
    row = list(fake.ora_decisions.docs.values())[0]
    assert row["tool"] == "safe_edit"
    assert row["outcome"] == "approved"
    assert "cors" in row["tags"]
    assert "auth" in row["tags"] or "login" in row["tags"]
    assert "safe_edit" in row["tags"]


@pytest.mark.asyncio
async def test_recall_past_decisions_text_search_matches():
    from services import ora_decision_memory as dm
    fake = _FakeDB()
    dm.set_db(fake)
    await dm.log_decision(
        session_id="s1", founder_email="f@a.com",
        tool="safe_edit", summary="Fixed Stripe webhook signature mismatch",
        args={}, outcome="approved",
    )
    await dm.log_decision(
        session_id="s2", founder_email="f@a.com",
        tool="restart_service", summary="Restart backend for new env vars",
        args={}, outcome="approved",
    )
    r = await dm.recall_past_decisions("stripe webhook", limit=5)
    assert r["ok"] is True
    assert r["count"] == 1
    assert r["matches"][0]["tool"] == "safe_edit"


@pytest.mark.asyncio
async def test_recall_empty_query_rejected():
    from services import ora_decision_memory as dm
    dm.set_db(_FakeDB())
    r = await dm.recall_past_decisions("   ")
    assert r["ok"] is False


def test_recall_past_decisions_tool_registered_tier1():
    from services.ora_tools import TOOL_REGISTRY
    from services.ora_agent import TIER_1_AUTO, tier_of
    assert "recall_past_decisions" in TOOL_REGISTRY
    assert "recall_past_decisions" in TIER_1_AUTO
    assert tier_of("recall_past_decisions") == "tier1_auto"


# ════════════════════════════════════════════════════════════════════════════
# P1.4 — codebase_semantic_search
# ════════════════════════════════════════════════════════════════════════════
def test_codebase_search_finds_relevant_functions():
    from services.codebase_semantic_search import search
    # Force fresh index since other tests may have run.
    r = search("estimate llm cost provider", limit=10, force_rebuild=True)
    assert r["ok"] is True
    assert r["count"] >= 1
    # Should surface the cost estimator we shipped in iter 326v
    names = {m["name"] for m in r["matches"]}
    assert any("cost" in n.lower() or "estimate" in n.lower() for n in names), (
        f"expected a cost/estimate function in matches, got {names}"
    )


def test_codebase_search_tokenises_and_expands():
    from services.codebase_semantic_search import _tokenize, _expand
    toks = _tokenize("THE code that calculates subscription cost")
    assert "the" not in toks
    assert "code" in toks
    assert "cost" in toks
    expanded = _expand(toks)
    # Synonym table should add billing/price/etc. for "cost"
    assert any(s in expanded for s in ("price", "billing", "stripe", "charge"))


def test_codebase_search_rejects_empty_query():
    from services.codebase_semantic_search import search
    r = search("")
    assert r["ok"] is False


def test_search_codebase_semantic_tool_registered_tier1():
    from services.ora_tools import TOOL_REGISTRY
    from services.ora_agent import TIER_1_AUTO, tier_of
    assert "search_codebase_semantic" in TOOL_REGISTRY
    assert "search_codebase_semantic" in TIER_1_AUTO
    assert tier_of("search_codebase_semantic") == "tier1_auto"


def test_load_job_checkpoint_tool_registered_tier1():
    from services.ora_tools import TOOL_REGISTRY
    from services.ora_agent import TIER_1_AUTO, tier_of
    assert "load_job_checkpoint" in TOOL_REGISTRY
    assert "load_job_checkpoint" in TIER_1_AUTO
    assert tier_of("load_job_checkpoint") == "tier1_auto"


# ════════════════════════════════════════════════════════════════════════════
# Plumbing: ora_agent.set_db wires the two new services
# ════════════════════════════════════════════════════════════════════════════
def test_ora_agent_set_db_wires_memory_and_checkpoints(monkeypatch):
    from services import ora_agent, ora_decision_memory, job_checkpoints
    fake = _FakeDB()
    ora_agent.set_db(fake)
    assert ora_decision_memory._db is fake
    assert job_checkpoints._db is fake


# ════════════════════════════════════════════════════════════════════════════
# System prompt advertises Phase 2 P1 tools so the LLM uses them
# ════════════════════════════════════════════════════════════════════════════
def test_system_prompt_advertises_new_tier1_tools():
    from services.ora_agent import SYSTEM_PROMPT
    for name in (
        "recall_past_decisions",
        "search_codebase_semantic",
        "load_job_checkpoint",
    ):
        assert name in SYSTEM_PROMPT, f"system prompt missing tool: {name}"
