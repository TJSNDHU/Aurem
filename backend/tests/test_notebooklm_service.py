"""Tests for the NotebookLM research skill — iter 282al.

The SDK requires a live Google auth blob, which we don't have in CI. Every
test here verifies the **graceful fallback** path: skill never crashes,
returns a stable error string, and ORA's main chat is unaffected.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.notebooklm_service import (  # noqa: E402
    DISABLED_MSG,
    research_lead_sync,
)


MOCK_LEAD = {
    "business_name": "Test Plumbing Co",
    "website":       "https://example.com",
}


def test_notebooklm_skill_fallback_without_auth(monkeypatch):
    """No NOTEBOOKLM_AUTH_JSON → graceful disabled message."""
    monkeypatch.delenv("NOTEBOOKLM_AUTH_JSON", raising=False)
    result = research_lead_sync(MOCK_LEAD, "What services do they offer?")
    assert isinstance(result, str)
    assert result != ""
    assert ("unavailable" in result.lower()
             or "not connected" in result.lower()
             or result == DISABLED_MSG)


def test_notebooklm_skill_empty_question(monkeypatch):
    """Empty question triggers the dedicated guard — never raises."""
    monkeypatch.setenv("NOTEBOOKLM_AUTH_JSON", "{}")  # valid JSON sentinel
    result = research_lead_sync(MOCK_LEAD, "")
    assert isinstance(result, str)
    # Either empty-question guard OR auth-invalid path — both acceptable
    assert result != ""


def test_notebooklm_skill_invalid_auth_blob_is_graceful(monkeypatch):
    """Malformed NOTEBOOKLM_AUTH_JSON → treated as no auth, not crash."""
    monkeypatch.setenv("NOTEBOOKLM_AUTH_JSON", "not-valid-json-not-a-path")
    result = research_lead_sync(MOCK_LEAD, "research this")
    assert result == DISABLED_MSG


def test_skill_registered_in_router():
    """Regression — skill is wired into SKILLS list + SKILL_TO_AGENT map."""
    from services.skill_router import SKILLS, SKILL_TO_AGENT
    assert "notebooklm_research" in SKILLS
    assert "notebooklm_research" in SKILL_TO_AGENT
    assert SKILL_TO_AGENT["notebooklm_research"] is not None


def test_skill_md_file_exists():
    skill_md = Path("/app/ora_skills/notebooklm_research.md")
    assert skill_md.exists()
    body = skill_md.read_text(encoding="utf-8")
    assert "NOTEBOOKLM_AUTH_JSON" in body
    assert "not connected" in body.lower() or "disabled" in body.lower()
