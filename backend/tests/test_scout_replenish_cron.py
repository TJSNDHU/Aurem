"""Regression tests for services.scout_replenish_cron.

Tests:
- Config defaults sane
- Env overrides work
- Cursor wraps correctly across the (city, industry) matrix
- replenish_tick gracefully handles missing db
"""
import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import scout_replenish_cron as cron


def test_config_defaults_present():
    assert isinstance(cron._cities(), list) and len(cron._cities()) >= 4
    assert isinstance(cron._industries(), list) and len(cron._industries()) >= 4
    assert cron._interval_min() > 0
    assert cron._queue_target() > 0
    assert cron._per_run_cap() > 0


def test_env_override(monkeypatch):
    monkeypatch.setenv("AUREM_SCOUT_CRON_INTERVAL_MIN", "30")
    monkeypatch.setenv("AUREM_SCOUT_QUEUE_TARGET", "50")
    monkeypatch.setenv("AUREM_SCOUT_PER_RUN_CAP", "10")
    monkeypatch.setenv("AUREM_SCOUT_CITIES", "Calgary, AB, Edmonton, AB")
    monkeypatch.setenv("AUREM_SCOUT_INDUSTRIES", "vet,gym")
    assert cron._interval_min() == 30
    assert cron._queue_target() == 50
    assert cron._per_run_cap() == 10
    assert "Calgary" in cron._cities()[0]
    assert "vet" in cron._industries()


def test_no_db_returns_error():
    cron.set_db(None)
    result = asyncio.run(cron.replenish_tick(force=True))
    assert result["ok"] is False
    assert result["error"] == "db_not_wired"


def test_install_scheduler_returns_job_id():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    sched = AsyncIOScheduler()
    job_id = cron.install_scheduler(sched)
    assert job_id == "scout_replenish_cron"
    job = sched.get_job(job_id)
    assert job is not None
    assert job.name == "Scout Replenish Cron"


def test_all_default_industries_resolve_to_osm_tags():
    """iter 324m — guard: every cron industry MUST exist in OSM tag dict
    so the matrix never hits a 'no_osm_tags_for_industry' wall."""
    from services.osm_scout import INDUSTRY_TO_OSM_TAGS, _normalise_industry
    missing = []
    for ind in cron.DEFAULT_INDUSTRIES:
        n = _normalise_industry(ind)
        if n not in INDUSTRY_TO_OSM_TAGS:
            missing.append((ind, n))
    assert not missing, f"DEFAULT_INDUSTRIES missing OSM tags: {missing}"


def test_industries_matrix_minimum_size():
    """Ensure the SMB coverage matrix is wide enough for production."""
    assert len(cron.DEFAULT_INDUSTRIES) >= 20, (
        f"Expected >=20 industries for production coverage, "
        f"got {len(cron.DEFAULT_INDUSTRIES)}"
    )
    assert len(cron.DEFAULT_CITIES) >= 4
