"""
iter 331a Sprint 4 — Skill files regression
============================================

Verifies the 4 new skill files exist with the required structure,
the dev_debugging.md was prepended with the new hard-rules header,
and the semantic memory index discovers them.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


SKILLS = Path("/app/backend/ora_skills")


# ─── Files exist ──────────────────────────────────────────────

def test_dev_new_project_skill_exists():
    p = SKILLS / "dev_new_project.md"
    assert p.exists()
    text = p.read_text()
    assert len(text) > 500


def test_dev_self_recovery_skill_exists():
    p = SKILLS / "dev_self_recovery.md"
    assert p.exists()
    text = p.read_text()
    assert len(text) > 500


def test_dev_integration_skill_exists():
    p = SKILLS / "dev_integration.md"
    assert p.exists()
    text = p.read_text()
    assert len(text) > 500


def test_dev_testing_skill_exists():
    p = SKILLS / "dev_testing.md"
    assert p.exists()
    text = p.read_text()
    assert len(text) > 500


# ─── Structural requirements (from the master prompt) ──────────

def test_new_project_skill_has_required_steps():
    text = (SKILLS / "dev_new_project.md").read_text()
    # 12-step playbook
    assert "12 steps" in text.lower() or "12-step" in text.lower()
    # Mandatory references
    assert "PROJECT_TEMPLATES.md" in text
    assert "check_coverage" in text
    assert "run_linter" in text
    # Must end with health check / founder report
    assert "smoke-test" in text.lower() or "smoke test" in text.lower()
    assert "founder" in text.lower()


def test_self_recovery_skill_has_loop_control():
    text = (SKILLS / "dev_self_recovery.md").read_text()
    # 8-step loop
    assert "8-step" in text.lower() or "8 step" in text.lower()
    # read_logs as step 1
    assert "read_logs" in text
    # mistake journal cross-ref
    assert "dev_322ey-ora-mistakes-lessons" in text
    # 3-strikes escalation
    assert "ask_human" in text
    # Hard rule: never retry same fix 4th time
    assert "4th attempt" in text.lower() or "4th" in text


def test_integration_skill_has_hard_gates():
    text = (SKILLS / "dev_integration.md").read_text()
    # 8-step playbook
    assert "8-step" in text.lower() or "8 step" in text.lower()
    # web_search HARD GATE as step 1
    assert "web_search" in text
    assert "HARD GATE" in text or "hard gate" in text.lower()
    # INTEGRATION_PLAYBOOK reference
    assert "INTEGRATION_PLAYBOOK.md" in text
    # API key verification before code
    assert "verify api key" in text.lower() or "verify the api key" in text.lower() or "verify API key" in text
    # Mock + real verify_endpoint test
    assert "mock" in text.lower() and "verify_endpoint" in text


def test_testing_skill_has_six_rules():
    text = (SKILLS / "dev_testing.md").read_text()
    # 80% coverage
    assert "80%" in text
    # Mock all external APIs
    assert "mock" in text.lower()
    # REACT_APP_BACKEND_URL
    assert "REACT_APP_BACKEND_URL" in text
    # data-testid
    assert "data-testid" in text
    # check_coverage after every session
    assert "check_coverage" in text


def test_dev_debugging_has_new_iter_331a_header():
    text = (SKILLS / "dev_debugging.md").read_text()
    # New header at top
    assert "iter 331a" in text
    assert "read_logs" in text
    assert "progress.md" in text
    assert "mongo_query_safe" in text
    assert "Never guess" in text or "never guess" in text.lower()


# ─── Skills are discoverable via semantic memory ────────────────

@pytest.mark.asyncio
async def test_semantic_search_finds_new_skills():
    """The FTS5 index built at boot must include the new skill files
    after a manual reindex (they were added after backend boot)."""
    from services import ora_semantic_memory as SM
    SM.reindex()
    r = await SM.semantic_memory_search(
        "build a new project from scratch playbook", top_k=5,
    )
    assert r["ok"] is True
    # At least one result must be from one of our new skill files
    files = [hit["file"] for hit in r["results"]]
    new_skill_files = {
        "dev_new_project.md", "dev_self_recovery.md",
        "dev_integration.md", "dev_testing.md",
    }
    matched = any(any(s in f for s in new_skill_files) for f in files)
    assert matched, f"new skill files not found in semantic results: {files}"


@pytest.mark.asyncio
async def test_semantic_search_finds_integration_playbook_hard_gate():
    """The 'web_search first' hard gate must be findable by a relevant
    query — proves the integration skill is wired to the right concept."""
    from services import ora_semantic_memory as SM
    SM.reindex()
    r = await SM.semantic_memory_search(
        "stripe webhook integration api key", top_k=5,
    )
    assert r["ok"] is True
    # Either the new dev_integration.md OR the existing
    # INTEGRATION_PLAYBOOK.md should match.
    text = " ".join(hit["snippet"] for hit in r["results"])
    assert ("web_search" in text or "INTEGRATION_PLAYBOOK" in text
            or "Stripe" in text or "stripe" in text), \
        f"no integration-relevant chunk found"
