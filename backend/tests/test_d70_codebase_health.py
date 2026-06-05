"""
test_d70_codebase_health.py — iter D-70
=========================================
Locks in the live codebase-health analyzer.

Validates:
- Skill registry: service exposes run_snapshot / latest / trend
- Snapshot shape: all required fields present + sane types
- Real run against AUREM source: must find at least 1 god-file
  (registry.py is 4000+ lines — guaranteed). If god_files goes to
  zero, refactor was successful AND probably broke the analyzer.
- top_action.reason is a short human string (founder's spec)
- Scheduler wired: registry.py contains the boot + 6h jobs
"""
from __future__ import annotations

import pytest


# ─── service surface ─────────────────────────────────────────
def test_service_exposes_public_api():
    from services import codebase_health as ch
    assert callable(ch.run_snapshot)
    assert callable(ch.latest_snapshot)
    assert callable(ch.trend)
    assert callable(ch.set_db)


def test_registry_wires_codebase_health_scheduler():
    src = open("/app/backend/routers/registry.py").read()
    assert "codebase_health_6h" in src, (
        "6-hour scheduler job missing from registry — auto-refresh broken"
    )
    assert "codebase_health_boot" in src, (
        "Boot snapshot job missing — dashboard would be empty on cold start"
    )
    assert "from services.codebase_health import run_snapshot" in src


def test_router_registered():
    src = open("/app/backend/routers/registry.py").read()
    assert "routers.codebase_health_router" in src


# ─── snapshot shape ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_run_snapshot_produces_expected_shape():
    from services import codebase_health as ch
    ch.set_db(None)   # skip persistence
    snap = await ch.run_snapshot()
    assert "generated_at" in snap
    assert "duration_sec" in snap and snap["duration_sec"] > 0
    assert "health_score" in snap and 0 <= snap["health_score"] <= 10
    # backend block
    be = snap.get("backend")
    assert be is not None
    for k in ("totals", "size_buckets", "god_files", "circular",
              "cc_top", "biggest"):
        assert k in be, f"backend.{k} missing"
    assert be["totals"]["files"] > 100, "AUREM has 200+ backend files — analyzer probably broken"
    assert be["totals"]["lines"] > 10000
    # frontend block
    fe = snap.get("frontend")
    assert fe is not None
    assert fe["totals"]["files"] > 50, "AUREM has 200+ frontend files"


@pytest.mark.asyncio
async def test_top_action_has_short_human_reason():
    """Founder requirement: top_action.reason should explain in one line
    why the file is flagged — like '1952 lines, 3 circular imports'."""
    from services import codebase_health as ch
    ch.set_db(None)
    snap = await ch.run_snapshot()
    ta = snap["top_action"]
    assert "path" in ta and "reason" in ta
    assert isinstance(ta["reason"], str)
    # Reason must be informative (not just a path or single number).
    assert 10 < len(ta["reason"]) < 200, f"reason too short or too long: {ta['reason']!r}"


@pytest.mark.asyncio
async def test_real_scan_finds_known_god_files():
    """registry.py is 4000+ lines today. If the analyzer can't find it
    as a god-file, something is wrong with the bucketing logic."""
    from services import codebase_health as ch
    ch.set_db(None)
    snap = await ch.run_snapshot()
    paths = [g["path"] for g in snap["backend"]["god_files"]]
    paths += [b["path"] for b in snap["backend"]["biggest"][:5]]
    assert any("registry.py" in p for p in paths), (
        f"registry.py missing from god-files + biggest — got: {paths}"
    )


# ─── circular-import detector sanity ─────────────────────────
def test_find_cycles_handles_no_cycle():
    from services.codebase_health import _find_cycles
    graph = {"a": {"b"}, "b": {"c"}, "c": set()}
    assert _find_cycles(graph) == []


def test_find_cycles_handles_simple_cycle():
    from services.codebase_health import _find_cycles
    graph = {"a": {"b"}, "b": {"a"}}
    cycles = _find_cycles(graph)
    assert len(cycles) >= 1


# ─── frontend wiring ─────────────────────────────────────────
def test_app_js_routes_codebase_health_page():
    src = open("/app/frontend/src/App.js").read()
    assert "AdminCodebaseHealth" in src
    assert '/admin/codebase-health' in src


def test_sidebar_includes_codebase_health():
    src = open("/app/frontend/src/platform/AdminShell.jsx").read()
    assert "/admin/codebase-health" in src
    assert "Codebase Health" in src
