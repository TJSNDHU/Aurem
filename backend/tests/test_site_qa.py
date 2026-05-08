"""
iter 282al-15 — Tests for services/site_qa_service.py

Covers:
  - run_site_qa skips silently when TEST_LAB_API_KEY unset
  - qa_repair_loop short-circuits to ready_to_send=True when skipped
  - build_repair_prompt maps phone / widget / form / mobile / name
  - _normalise_results handles missing + mixed shapes
  - get_qa_health returns grey/green/yellow correctly
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import AsyncMock, MagicMock


# ─────────── run_site_qa: no-key short-circuit ───────────
@pytest.mark.asyncio
async def test_run_site_qa_skips_without_key(monkeypatch):
    monkeypatch.delenv("TEST_LAB_API_KEY", raising=False)
    monkeypatch.setattr("aurem_config.TEST_LAB_API_KEY", "", raising=False)
    from services.site_qa_service import run_site_qa

    mock_db = MagicMock()
    result = await run_site_qa(mock_db, "some-slug", "https://example.com")

    assert result["skipped"] == "no_key"
    assert result["ready"] is True
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_qa_repair_loop_skips_without_key(monkeypatch):
    monkeypatch.delenv("TEST_LAB_API_KEY", raising=False)
    monkeypatch.setattr("aurem_config.TEST_LAB_API_KEY", "", raising=False)
    from services.site_qa_service import qa_repair_loop

    mock_db = MagicMock()
    out = await qa_repair_loop(mock_db, "slug", "https://example.com", max_attempts=3)
    assert out["final_status"] == "skipped"
    assert out["ready_to_send"] is True
    assert out["attempts"] == 0


# ─────────── build_repair_prompt ───────────
def test_build_repair_prompt_phone():
    from services.site_qa_service import build_repair_prompt
    p = build_repair_prompt("slug", [{"test": "Verify the phone number is visible"}])
    pl = p.lower()
    assert "phone" in pl or "click-to-call" in pl


def test_build_repair_prompt_widget():
    from services.site_qa_service import build_repair_prompt
    p = build_repair_prompt("slug", [{"test": "Verify the ORA chat widget appears"}])
    pl = p.lower()
    assert "widget" in pl or "script" in pl


def test_build_repair_prompt_form():
    from services.site_qa_service import build_repair_prompt
    p = build_repair_prompt("slug", [{"test": "Verify the contact form is functional"}])
    pl = p.lower()
    assert "form" in pl or "contact" in pl


def test_build_repair_prompt_mobile():
    from services.site_qa_service import build_repair_prompt
    p = build_repair_prompt("slug", [{"test": "Verify the page is mobile responsive at 375px"}])
    pl = p.lower()
    assert "viewport" in pl or "mobile" in pl or "375" in pl or "breakpoint" in pl


def test_build_repair_prompt_name():
    from services.site_qa_service import build_repair_prompt
    p = build_repair_prompt("slug", [{"test": "Page loads and shows a business name"}])
    pl = p.lower()
    assert "name" in pl or "h1" in pl or "hero" in pl


def test_build_repair_prompt_empty_uses_fallback():
    from services.site_qa_service import build_repair_prompt
    p = build_repair_prompt("slug", [])
    assert "review page fundamentals" in p.lower() or "fix" in p.lower()


# ─────────── _normalise_results ───────────
def test_normalise_results_none_marks_all_failed():
    from services.site_qa_service import _normalise_results, _STANDARD_TESTS
    out = _normalise_results(_STANDARD_TESTS, None)
    assert out["passed"] == 0
    assert out["failed"] == len(_STANDARD_TESTS)
    assert all(r["status"] == "fail" for r in out["results"])


def test_normalise_results_mixed():
    from services.site_qa_service import _normalise_results, _STANDARD_TESTS
    raw = {"results": [
        {"status": "pass"},
        {"status": "pass"},
        {"status": "fail", "detail": "widget missing"},
        {"status": "pass"},
        {"status": "pass"},
    ], "report_url": "https://test-lab.ai/runs/abc"}
    out = _normalise_results(_STANDARD_TESTS, raw)
    assert out["passed"] == 4
    assert out["failed"] == 1
    assert out["report_url"] == "https://test-lab.ai/runs/abc"
    assert out["results"][2]["status"] == "fail"


# ─────────── get_qa_health ───────────
@pytest.mark.asyncio
async def test_get_qa_health_grey_without_key(monkeypatch):
    monkeypatch.delenv("TEST_LAB_API_KEY", raising=False)
    monkeypatch.setattr("aurem_config.TEST_LAB_API_KEY", "", raising=False)
    from services.site_qa_service import get_qa_health
    out = await get_qa_health(MagicMock())
    assert out["status"] == "grey"
    assert out["message"] == "no_key"


@pytest.mark.asyncio
async def test_get_qa_health_green_when_all_passed(monkeypatch):
    monkeypatch.setenv("TEST_LAB_API_KEY", "tl_fake")
    monkeypatch.setattr("aurem_config.TEST_LAB_API_KEY", "tl_fake", raising=False)
    from services.site_qa_service import get_qa_health

    # Build a fake motor-style cursor
    class _Cursor:
        def __init__(self, rows): self._rows = rows
        def sort(self, *_a, **_k): return self
        def limit(self, *_a, **_k): return self
        async def to_list(self, length=None): return self._rows

    mock_db = MagicMock()
    mock_db.site_test_results.find = MagicMock(
        return_value=_Cursor([{"failed": 0}, {"failed": 0}, {"failed": 0}])
    )
    out = await get_qa_health(mock_db)
    assert out["status"] == "green"
    assert out["last_runs"] == 3


@pytest.mark.asyncio
async def test_get_qa_health_yellow_when_any_failed(monkeypatch):
    monkeypatch.setenv("TEST_LAB_API_KEY", "tl_fake")
    monkeypatch.setattr("aurem_config.TEST_LAB_API_KEY", "tl_fake", raising=False)
    from services.site_qa_service import get_qa_health

    class _Cursor:
        def __init__(self, rows): self._rows = rows
        def sort(self, *_a, **_k): return self
        def limit(self, *_a, **_k): return self
        async def to_list(self, length=None): return self._rows

    mock_db = MagicMock()
    mock_db.site_test_results.find = MagicMock(
        return_value=_Cursor([{"failed": 0}, {"failed": 2}, {"failed": 0}])
    )
    out = await get_qa_health(mock_db)
    assert out["status"] == "yellow"


@pytest.mark.asyncio
async def test_get_qa_health_grey_when_no_runs(monkeypatch):
    monkeypatch.setenv("TEST_LAB_API_KEY", "tl_fake")
    monkeypatch.setattr("aurem_config.TEST_LAB_API_KEY", "tl_fake", raising=False)
    from services.site_qa_service import get_qa_health

    class _Cursor:
        def __init__(self, rows): self._rows = rows
        def sort(self, *_a, **_k): return self
        def limit(self, *_a, **_k): return self
        async def to_list(self, length=None): return self._rows

    mock_db = MagicMock()
    mock_db.site_test_results.find = MagicMock(return_value=_Cursor([]))
    out = await get_qa_health(mock_db)
    assert out["status"] == "grey"
    assert out["message"] == "no_runs"
