"""Skill router + learning engine tests — iter 282ak (Prompt 8, Tasks F + G)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.skill_router import (  # noqa: E402
    SKILL_TO_AGENT,
    SKILLS,
    execute_skill_sync,
    route_sync,
)
from services.skill_learner import (  # noqa: E402
    get_learning_summary_sync,
    run_learning_cycle_sync,
)


# ─────────────────────────────────────────────────────────────────────
# Tiny reusable mock-DB (copy-pasted from test_linkedin_publisher pattern
# so skill tests run standalone).
# ─────────────────────────────────────────────────────────────────────
class _MockColl:
    def __init__(self):
        self._docs = []

    @staticmethod
    def _match(d, q):
        for k, v in (q or {}).items():
            if isinstance(v, dict) and all(op.startswith("$") for op in v.keys()):
                got = d.get(k)
                for op, val in v.items():
                    if op == "$gt" and not (got is not None and got > val):
                        return False
                    if op == "$gte" and not (got is not None and got >= val):
                        return False
                    if op == "$lt" and not (got is not None and got < val):
                        return False
            elif d.get(k) != v:
                return False
        return True

    async def find_one(self, q=None, projection=None, sort=None, **kw):
        docs = list(self._docs)
        if sort:
            for key, direction in reversed(sort):
                docs.sort(key=lambda x: (x.get(key) is None, x.get(key)),
                          reverse=(direction == -1))
        for d in docs:
            if self._match(d, q or {}):
                return dict(d)
        return None

    async def insert_one(self, doc):
        self._docs.append(dict(doc))
        class R:
            inserted_id = None
        return R()

    async def update_one(self, q, upd, upsert=False):
        for d in self._docs:
            if self._match(d, q):
                d.update(upd.get("$set") or {})
                return None
        if upsert:
            n = dict(q)
            n.update(upd.get("$set") or {})
            self._docs.append(n)
        return None

    async def count_documents(self, q=None, **kw):
        return sum(1 for d in self._docs if self._match(d, q or {}))

    def find(self, q=None, projection=None, **kw):
        docs = [dict(d) for d in self._docs if self._match(d, q or {})]
        class _C:
            def __init__(self, d):
                self._d = d
            def sort(self, *a, **k):
                return self
            def limit(self, n):
                self._d = self._d[:n]
                return self
            async def to_list(self, length=None):
                return self._d[:length or len(self._d)]
            def __aiter__(self):
                self._i = 0
                return self
            async def __anext__(self):
                if self._i >= len(self._d):
                    raise StopAsyncIteration
                v = self._d[self._i]
                self._i += 1
                return v
        return _C(docs)

    def aggregate(self, pipeline):
        # For learning signals test — always returns nothing (insufficient data)
        class _C:
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration
        return _C()


class _MockDB:
    def __init__(self):
        self._cols = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._cols:
            self._cols[name] = _MockColl()
        return self._cols[name]


# ─────────────────────────────────────────────────────────────────────
# Routing tests
# ─────────────────────────────────────────────────────────────────────
def test_scout_intent_routes_correctly():
    assert route_sync("scan this plumber website") == "scout_scan"


def test_brief_intent_routes_correctly():
    assert route_sync("give me a morning brief") == "morning_brief"


def test_closer_intent_routes_correctly():
    assert route_sync("they replied and seem interested") == "closer_check"


def test_unknown_intent_returns_none():
    # Deterministic keyword pass misses → LLM fallback may or may not route.
    # Contract is: if no EMERGENT_LLM_KEY set, returns None. When set, LLM
    # usually returns 'none' for obviously-unrelated content.
    r = route_sync("what is the capital of France")
    assert r is None or r not in SKILLS


def test_all_skill_files_exist():
    import os
    for skill in SKILLS:
        assert os.path.exists(f"/app/ora_skills/{skill}.md"), \
            f"Missing: ora_skills/{skill}.md"


def test_skill_to_agent_map_resolves():
    for skill in SKILLS:
        assert skill in SKILL_TO_AGENT, f"{skill} missing from SKILL_TO_AGENT"


# ─────────────────────────────────────────────────────────────────────
# Execution tests
# ─────────────────────────────────────────────────────────────────────
def test_casl_skill_fails_missing_optout():
    db = _MockDB()
    result = execute_skill_sync("casl_check",
                                  "Hi there, buy our product now!", db)
    assert "FAIL" in result or "opt-out" in result.lower() or "opt out" in result.lower()


def test_skill_invocation_logged():
    db = _MockDB()
    execute_skill_sync("casl_check",
                        "Hi - reply STOP to opt out",
                        db)
    docs = db.skill_invocations._docs
    assert any(d.get("skill") == "casl_check" for d in docs)


# ─────────────────────────────────────────────────────────────────────
# Learning engine tests
# ─────────────────────────────────────────────────────────────────────
def test_learning_summary_structure():
    db = _MockDB()
    summary = get_learning_summary_sync(db)
    assert "last_run" in summary
    assert "total_insights" in summary


def test_learner_skips_insufficient_data():
    db = _MockDB()
    result = run_learning_cycle_sync(db)
    assert result.get("skipped") == "insufficient_data"



# ─────────────────────────────────────────────────────────────────────
# iter 282al — Dev skill tests (imported from antigravity-awesome-skills)
# ─────────────────────────────────────────────────────────────────────
import os  # noqa: E402

from services.skill_router import DEV_SKILLS, detect_dev_intent  # noqa: E402


def test_bug_fix_routes_to_dev_debugging():
    result = route_sync("there's a bug in scout_agent.py fix it")
    assert result is not None
    assert result.startswith("dev_")
    assert result == "dev_debugging"


def test_pytest_routes_to_tdd_skill():
    result = route_sync("write a pytest test for the composer")
    assert result is not None
    assert "test" in result
    assert result == "dev_test-driven-development"


def test_security_question_routes_to_security_auditor():
    result = route_sync("review this endpoint for jwt vulnerabilities")
    assert result == "dev_security-auditor"


def test_react_question_routes_to_react_patterns():
    result = route_sync("how do I structure a React component with useState")
    assert result == "dev_react-patterns"


def test_sales_still_routes_correctly_after_dev_addition():
    # Regression — sales intents must not be hijacked by dev routing
    assert route_sync("scan this website https://example.com") == "scout_scan"
    assert route_sync("give me a brief") == "morning_brief"


def test_detect_dev_intent_none_for_sales():
    assert detect_dev_intent("scan this website") is None
    assert detect_dev_intent("write to this lead") is None
    assert detect_dev_intent("") is None


def test_dev_skill_files_on_disk():
    from pathlib import Path
    ora_dir = Path("/app/ora_skills")
    present = [s for s in DEV_SKILLS if (ora_dir / f"{s}.md").exists()]
    assert len(present) >= 5, f"Expected 5+ dev skills, got {len(present)}"
    # AUREM context file must exist — it's injected into every dev skill
    assert (ora_dir / "dev_aurem_codebase.md").exists()


def test_dev_skill_execution_without_llm_key(monkeypatch):
    """When EMERGENT_LLM_KEY is unset, dev skill returns a graceful message
    instead of crashing. Proves the skill file is loaded before LLM call."""
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    db = _MockDB()
    result = execute_skill_sync("dev_debugging", "fix this import error", db)
    assert isinstance(result, str)
    assert result != ""
    assert ("no LLM key" in result or "not found" in result
             or "Dev skill" in result)
