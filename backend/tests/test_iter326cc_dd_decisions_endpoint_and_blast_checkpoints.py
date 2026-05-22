"""
test_iter326cc_dd_decisions_endpoint_and_blast_checkpoints.py
══════════════════════════════════════════════════════════════════════════════
Two safety items the founder asked for right after Phase 2:

  iter 326cc — Recent decisions panel (admin sidebar)
    Backend: GET /api/admin/ora/decisions?days=7&limit=50&outcome=&tag=
    Returns the last N decisions ORA approved / rejected / auto-executed,
    plus an outcome_counts rollup, so the founder can glance at overnight
    autonomous runs.

  iter 326dd — Wire job_checkpoints into auto_blast_engine.run_auto_blast_cycle
    Cycle now writes a checkpoint after every successfully-processed lead
    (key="auto_blast::<tenant_id>") and clears it on cycle completion. A
    pod crash mid-cycle leaves a resume point so the next cycle skips
    already-processed lead_ids instead of double-sending.

WHAT THIS TEST LOCKS IN
───────────────────────
  • /api/admin/ora/decisions endpoint is defined on admin_ora_router.
  • Endpoint accepts days, limit, outcome, tag query params (FastAPI sig).
  • auto_blast_engine.run_auto_blast_cycle imports the checkpoint helpers
    and uses the job-id format `auto_blast::<tenant_id>`.
  • auto_blast_engine.set_db also wires job_checkpoints.set_db (so
    checkpoints land in the same Mongo handle).
  • RecentDecisionsPanel frontend component exists and exports a default
    React component (smoke check via a regex — full UI test is e2e).

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326cc_dd_decisions_endpoint_and_blast_checkpoints.py -v
"""
from __future__ import annotations

import inspect
import pathlib
import re

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# iter 326cc — /api/admin/ora/decisions endpoint exists and accepts filters
# ─────────────────────────────────────────────────────────────────────────────
def test_decisions_endpoint_registered_on_admin_ora_router():
    from routers import admin_ora_router
    paths = [
        getattr(r, "path", None)
        for r in getattr(admin_ora_router.router, "routes", [])
    ]
    assert "/api/admin/ora/decisions" in paths, (
        f"endpoint not registered. Routes: {paths}"
    )


def test_decisions_endpoint_accepts_expected_query_params():
    """Founder UI sends days, limit, outcome, tag — endpoint must accept them."""
    from routers.admin_ora_router import admin_ora_decisions
    sig = inspect.signature(admin_ora_decisions)
    for p in ("days", "limit", "outcome", "tag"):
        assert p in sig.parameters, f"missing query param: {p}"


def test_decisions_endpoint_is_protected_by_admin_check():
    """The handler MUST call _ensure_admin — otherwise anyone with a
    valid customer token could read the founder's decision log."""
    from routers.admin_ora_router import admin_ora_decisions
    src = inspect.getsource(admin_ora_decisions)
    assert "_ensure_admin" in src, (
        "admin_ora_decisions does not call _ensure_admin — auth bypass risk."
    )


def test_decisions_endpoint_excludes_mongo_object_id():
    """Mongo _id is BSON ObjectId — we never JSON-serialise it. Verify
    the projection / mapping omits it."""
    from routers.admin_ora_router import admin_ora_decisions
    src = inspect.getsource(admin_ora_decisions)
    # We map d.get("_id") into "id" — that's the only acceptable surface
    assert '"_id": 1' in src or "'_id': 1" in src
    # And the response field is "id" not "_id"
    assert '"id":' in src
    assert '"_id":' not in src.split('rows.append')[1].split('})')[0]


# ─────────────────────────────────────────────────────────────────────────────
# iter 326dd — auto_blast_engine wires job_checkpoints
# ─────────────────────────────────────────────────────────────────────────────
def test_auto_blast_engine_set_db_wires_job_checkpoints():
    """When ora_agent.set_db / startup wires DB into auto_blast_engine,
    job_checkpoints must get the same handle so cycle checkpoints land
    in the right Mongo."""
    from services import auto_blast_engine
    src = inspect.getsource(auto_blast_engine.set_db)
    assert "job_checkpoints" in src, (
        "auto_blast_engine.set_db must propagate the DB to job_checkpoints"
    )


def test_run_auto_blast_cycle_uses_checkpoint_helpers():
    """run_auto_blast_cycle MUST load+save+clear checkpoints, otherwise
    a mid-cycle crash will double-send. Verifies the wiring is in place."""
    from services.auto_blast_engine import run_auto_blast_cycle
    src = inspect.getsource(run_auto_blast_cycle)
    for needle in (
        "load_checkpoint",
        "save_checkpoint",
        "clear_checkpoint",
        "auto_blast::",          # job-id format
        "processed_lead_ids",
    ):
        assert needle in src, f"missing in run_auto_blast_cycle: {needle}"


def test_run_auto_blast_cycle_skips_already_processed_leads():
    """Resume contract: leads in the stored processed_lead_ids set must
    be filtered out before the loop."""
    from services.auto_blast_engine import run_auto_blast_cycle
    src = inspect.getsource(run_auto_blast_cycle)
    # We use a `_seen = set(_processed_ids)` filter
    assert "_seen" in src
    assert "processed_lead_ids" in src


def test_blast_cycle_checkpoints_use_short_ttl():
    """Resume points for a blast cycle should expire fast (we only need
    them for in-progress runs) — long TTL would clutter the DB."""
    from services.auto_blast_engine import run_auto_blast_cycle
    src = inspect.getsource(run_auto_blast_cycle)
    # ttl_hours=6 was chosen — short enough to clean up, long enough to
    # survive a pod restart cycle.
    assert "ttl_hours=6" in src


# ─────────────────────────────────────────────────────────────────────────────
# Frontend smoke check — RecentDecisionsPanel.jsx exists + exports default
# ─────────────────────────────────────────────────────────────────────────────
_PANEL_PATH = pathlib.Path(
    "/app/frontend/src/platform/admin/RecentDecisionsPanel.jsx"
)


def test_recent_decisions_panel_file_exists():
    assert _PANEL_PATH.exists(), (
        f"frontend panel file missing: {_PANEL_PATH}"
    )


def test_recent_decisions_panel_exports_default_component():
    src = _PANEL_PATH.read_text()
    assert re.search(r"export default function RecentDecisionsPanel", src), (
        "Default export must be a React function component named "
        "RecentDecisionsPanel."
    )


def test_recent_decisions_panel_uses_correct_endpoint():
    src = _PANEL_PATH.read_text()
    assert "/api/admin/ora/decisions" in src
    # Auto-refresh every 30s for overnight runs
    assert "30_000" in src or "30000" in src


def test_recent_decisions_panel_uses_admin_token():
    """Panel must send the admin bearer token from secureTokenStore
    (matches OraChat.jsx convention) — NOT the customer token."""
    src = _PANEL_PATH.read_text()
    assert "aurem_admin_token" in src


def test_recent_decisions_panel_has_data_testids():
    """Per repo convention, every interactive element gets a data-testid."""
    src = _PANEL_PATH.read_text()
    for tid in (
        "recent-decisions-panel",
        "recent-decisions-title",
        "recent-decisions-refresh",
        "recent-decisions-days-select",
    ):
        assert f'data-testid="{tid}"' in src, f"missing data-testid: {tid}"
