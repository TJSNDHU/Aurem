"""
tests/test_iter327q_ora_capability_expansion.py

Regression for the iter 327q five-fix capability expansion:
  FIX 1 — Wall-clock 300→900 s, iterations 8→60, mid-task checkpoint
          every 50 iters, auto-resume queue + scheduler tick.
  FIX 2 — Nightly self-test cron + Telegram alert on failure.
  FIX 3 — propose_build_plan Tier-2 tool (BUILD MODE phased flow).
  FIX 4 — legion_exec risk-based tiering (low → Tier-2, else Tier-3).
  FIX 5 — long-job progress 30-min pings + auto-retry x3 on failure.

P0 frontend admin Memory tab + P1 self-journaling lesson proposal
covered alongside.
"""
import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ───────────────────────────────────────────────────────────────────────
# FIX 1 — Wall-clock + iterations + checkpoint + auto-resume
# ───────────────────────────────────────────────────────────────────────


def test_max_loop_wall_seconds_bumped_to_900():
    import services.ora_agent as a
    assert a.MAX_LOOP_WALL_SECONDS >= 900, (
        f"ORA_MAX_LOOP_S default should be ≥900 for multi-file refactors, "
        f"got {a.MAX_LOOP_WALL_SECONDS}"
    )


def test_max_tool_iterations_bumped_to_60():
    import services.ora_agent as a
    assert a.MAX_TOOL_ITERATIONS >= 60, (
        f"ORA_MAX_TOOL_ITERATIONS should be ≥60 for 30+ tool-call jobs, "
        f"got {a.MAX_TOOL_ITERATIONS}"
    )


def test_checkpoint_every_n_iters_configured():
    import services.ora_agent as a
    assert a.CHECKPOINT_EVERY_N_ITERS == 50, (
        f"checkpoint cadence should be every 50 iters by default, "
        f"got {a.CHECKPOINT_EVERY_N_ITERS}"
    )


def test_auto_resume_helpers_exist():
    import services.ora_agent as a
    assert callable(a.auto_resume_tick)
    assert callable(a.resume_session)
    assert callable(a._enqueue_auto_resume)


def test_continue_loop_uses_checkpoint_save():
    """The checkpoint-every-50 path must call save_checkpoint."""
    src = Path("/app/backend/services/ora_agent.py").read_text()
    assert "from services.job_checkpoints import save_checkpoint" in src
    assert "iterations % CHECKPOINT_EVERY_N_ITERS == 0" in src


def test_wall_clock_halt_enqueues_auto_resume():
    src = Path("/app/backend/services/ora_agent.py").read_text()
    assert "_enqueue_auto_resume" in src
    assert "halted_for" in src
    assert "auto_resume" in src


def test_long_job_progress_telegram_ping_wired():
    """FIX 5 — 30-min progress ping during long jobs."""
    src = Path("/app/backend/services/ora_agent.py").read_text()
    assert "LONG_JOB_PROGRESS_MINUTES" in src
    assert "last_progress_ping" in src
    assert "long-job progress" in src.lower() or "long_job" in src


def test_auto_resume_retry_logic_in_tick():
    src = Path("/app/backend/services/ora_agent.py").read_text()
    assert '"failed"' in src
    assert "max_retries" in src
    assert "backoff" in src.lower()


# ───────────────────────────────────────────────────────────────────────
# FIX 2 — Nightly self-test
# ───────────────────────────────────────────────────────────────────────


def test_nightly_self_test_module_exists():
    from services import ora_nightly_self_test
    assert callable(ora_nightly_self_test.run_nightly_self_test)


@pytest.mark.asyncio
async def test_nightly_self_test_runs_5_checks():
    """Module must run exactly 5 checks regardless of pass/fail."""
    from services.ora_nightly_self_test import run_nightly_self_test

    class FakeColl:
        def __init__(self): self.inserted = []
        async def insert_one(self, doc): self.inserted.append(doc)
        async def count_documents(self, q): return 7
        async def update_one(self, *a, **k): return None
        async def find_one(self, *a, **k):
            return {"_id": "probe", "token": "selftest_X"}

    class FakeDB:
        def __init__(self):
            self.ora_nightly_self_tests = FakeColl()
            self.ora_nightly_self_tests_probe = FakeColl()
            self.ora_learning_journal = FakeColl()
        # update_one on probe must remember the token we wrote so the
        # subsequent find_one round-trip check passes.
        def __getattr__(self, n):
            c = FakeColl()
            setattr(self, n, c)
            return c

    # Patch the probe round-trip to actually pass.
    class ProbeColl:
        def __init__(self): self._token = None
        async def update_one(self, q, u, upsert=False):
            self._token = u["$set"]["token"]
        async def find_one(self, q, *a, **k):
            return {"_id": "probe", "token": self._token}

    db = FakeDB()
    db.ora_nightly_self_tests_probe = ProbeColl()
    db.ora_nightly_self_tests = FakeColl()
    db.ora_learning_journal = FakeColl()

    out = await run_nightly_self_test(db)
    assert isinstance(out, dict)
    assert out.get("total") == 5
    assert "checks" in out
    assert len(out["checks"]) == 5


def test_nightly_self_test_cron_wired_at_02_utc():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_ora_nightly_self_test" in src
    assert "ora_nightly_self_test" in src
    assert "hour=2, minute=0" in src or "hour=2,minute=0" in src


def test_auto_resume_scheduler_wired_30s():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_ora_auto_resume" in src
    assert "seconds=30" in src
    assert "auto_resume_tick" in src


# ───────────────────────────────────────────────────────────────────────
# FIX 3 — propose_build_plan (BUILD MODE phased flow)
# ───────────────────────────────────────────────────────────────────────


def test_propose_build_plan_registered_in_tool_registry():
    from services.ora_tools import TOOL_REGISTRY
    assert "propose_build_plan" in TOOL_REGISTRY
    assert callable(TOOL_REGISTRY["propose_build_plan"]["fn"])


def test_propose_build_plan_is_tier2():
    from services.ora_agent import TIER_2_APPROVE
    assert "propose_build_plan" in TIER_2_APPROVE


@pytest.mark.asyncio
async def test_propose_build_plan_validates_inputs():
    from services import ora_build_mode

    class FakeColl:
        async def insert_one(self, doc): self.last = doc
    class FakeDB:
        def __init__(self): self.ora_build_plans = FakeColl()
        def __getitem__(self, k): return getattr(self, k)
    db = FakeDB()
    ora_build_mode.set_db(db)

    # Missing plan
    r = await ora_build_mode.propose_build_plan(plan_md="", rationale="x" * 20)
    assert not r["ok"]

    # Short rationale rejected
    r = await ora_build_mode.propose_build_plan(plan_md="step 1", rationale="too short")
    assert not r["ok"]

    # Happy path
    r = await ora_build_mode.propose_build_plan(
        plan_md="# Plan\n1. add file A\n2. test",
        files=["/app/foo.py"], tests=["/app/tests/test_foo.py"],
        rationale="founder asked for this build",
    )
    assert r["ok"] is True
    assert "plan_id" in r


def test_system_prompt_teaches_propose_build_plan_for_large_features():
    src = Path("/app/backend/services/ora_agent.py").read_text()
    assert "propose_build_plan" in src
    assert "MORE THAN 2 files" in src or "more than 2 files" in src.lower()


# ───────────────────────────────────────────────────────────────────────
# FIX 4 — legion_exec risk-based tiering
# ───────────────────────────────────────────────────────────────────────


def test_legion_exec_low_risk_routes_tier2():
    from services.ora_agent import tier_of
    assert tier_of("legion_exec", {"risk_hint": "low"}) == "tier2_approve"
    assert tier_of("legion_exec", {"risk_hint": "read"}) == "tier2_approve"


def test_legion_exec_high_risk_stays_tier3():
    from services.ora_agent import tier_of
    assert tier_of("legion_exec", {"risk_hint": "high"}) == "tier3_high_risk"
    assert tier_of("legion_exec", {"risk_hint": "medium"}) == "tier3_high_risk"
    # No risk_hint defaults to high (safe).
    assert tier_of("legion_exec", {}) == "tier3_high_risk"
    assert tier_of("legion_exec", None) == "tier3_high_risk"


def test_system_prompt_teaches_legion_risk_tiering():
    src = Path("/app/backend/services/ora_agent.py").read_text()
    assert "LEGION ACCESS" in src
    assert 'risk_hint="low"' in src
    assert 'risk_hint="high"' in src


# ───────────────────────────────────────────────────────────────────────
# P1 — propose_lesson self-journaling
# ───────────────────────────────────────────────────────────────────────


def test_propose_lesson_registered_in_tool_registry():
    from services.ora_tools import TOOL_REGISTRY
    assert "propose_lesson" in TOOL_REGISTRY
    assert callable(TOOL_REGISTRY["propose_lesson"]["fn"])


def test_propose_lesson_is_tier2():
    from services.ora_agent import TIER_2_APPROVE
    assert "propose_lesson" in TIER_2_APPROVE


@pytest.mark.asyncio
async def test_propose_lesson_appends_and_journals(tmp_path, monkeypatch):
    from services import ora_build_mode
    # Redirect lessons file to a sandbox.
    fake_lessons = tmp_path / "dev_lessons.md"
    fake_lessons.write_text("# existing\n\n", encoding="utf-8")
    monkeypatch.setattr(ora_build_mode, "_LESSONS_FILE", fake_lessons)

    class FakeColl:
        def __init__(self): self.docs = []
        async def insert_one(self, doc): self.docs.append(doc)
    class FakeDB:
        def __init__(self): self.ora_learning_journal = FakeColl()
        def __getitem__(self, k): return getattr(self, k)
    db = FakeDB()
    ora_build_mode.set_db(db)

    r = await ora_build_mode.propose_lesson(
        mistake_summary="said 8 leads when it was 0",
        lesson_text="Always run campaign_status before stating numbers.",
        code_diff="",
    )
    assert r["ok"] is True
    body = fake_lessons.read_text(encoding="utf-8")
    assert "said 8 leads when it was 0" in body
    assert "Always run campaign_status" in body
    # Journal recorded with unified diff.
    j = db.ora_learning_journal.docs
    assert len(j) == 1
    assert j[0]["kind"] == "lesson_proposal_applied"
    assert "unified_diff" in j[0]
    assert "@@" in j[0]["unified_diff"]


@pytest.mark.asyncio
async def test_propose_lesson_rejects_credentials_in_text():
    from services import ora_build_mode

    class FakeDB:
        def __getitem__(self, k): return type("C", (), {"insert_one": lambda *a, **k: None})
    ora_build_mode.set_db(FakeDB())

    r = await ora_build_mode.propose_lesson(
        mistake_summary="leaked a key",
        lesson_text="Use sk-abcdef1234567890 as a key — never do this",
        code_diff="",
    )
    assert not r["ok"]
    assert "credentials" in r["error"].lower() or "api keys" in r["error"].lower()


def test_system_prompt_teaches_self_learning_propose_lesson_only():
    src = Path("/app/backend/services/ora_agent.py").read_text()
    assert "SELF-LEARNING" in src
    assert "propose_lesson" in src


# ───────────────────────────────────────────────────────────────────────
# Admin endpoints — Lesson Sources router (iter 327p extended)
# ───────────────────────────────────────────────────────────────────────


def test_lesson_sources_router_exposes_snapshot_and_nightly():
    src = Path("/app/backend/routers/ora_lesson_sources_router.py").read_text()
    assert "lesson-snapshot" in src
    assert "nightly-self-tests" in src


# ───────────────────────────────────────────────────────────────────────
# Frontend — Memory tab presence
# ───────────────────────────────────────────────────────────────────────


def test_frontend_memory_tab_wired():
    src = Path("/app/frontend/src/platform/admin/OraAdminUnified.jsx").read_text()
    assert "LessonSources" in src
    assert 'id: "memory"' in src


def test_frontend_lesson_sources_has_testids():
    src = Path("/app/frontend/src/platform/admin/LessonSources.jsx").read_text()
    for tid in (
        "lesson-sources-page",
        "lesson-sources-refresh",
        "lesson-sources-snapshot",
        "tier1-panel",
        "tier2-panel",
        "journal-panel",
        "nightly-panel",
    ):
        assert f'data-testid="{tid}"' in src, f"missing testid {tid}"
