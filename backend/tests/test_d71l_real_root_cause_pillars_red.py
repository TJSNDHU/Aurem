"""
D-71l — REAL root-cause fix for pillars-map "DB side broken" red.

User correctly called out the patchwork: the previous D-71i fix patched
the WRONG endpoint (`/health`) when the actual source of the red badge
was `/overview` → `triple_pulse.db` for flows whose `activity_collections`
had ZERO documents. That's the same zero-data-≠-broken pattern we already
fixed for Intelligence Merge, skill_learner, Council, A2A, ORA Brain etc.

This iter applies the same empathic pattern at the engine root:
  _check_coll_activity:
    no docs at all      → yellow "awaiting first write"
    fresh within window → green
    stale beyond window → red "stale Nm (>Xm)"

ALSO broadens the Pillar-4 LITE-mode pod-name detection so the production
HOSTNAME patterns ("aurem-live-...", "prod-...") engage LITE-mode green
instead of leaving P4 stuck on "degraded/red".
"""
from __future__ import annotations

from pathlib import Path


def _src():
    return Path("/app/backend/routers/pillars_map_router.py").read_text()


def test_check_coll_activity_no_docs_returns_yellow_not_red():
    """The actual root cause: zero docs was hard-coded to red,
    which painted DB side as broken on every freshly-provisioned tenant."""
    src = _src()
    # The yellow path must exist with the empathic message.
    assert '"yellow", f"{name}: awaiting first write"' in src
    # And the old red-"no docs" string must be GONE.
    assert 'return "red", f"{name}: no docs"' not in src


def test_check_coll_activity_still_reds_on_stale_silent_failures():
    """True silent failures (had writes, then stopped) must still red.
    Don't fake-green real production outages."""
    src = _src()
    assert 'return "red", f"{name}: stale {int(age_min)}m' in src


def test_check_coll_activity_greens_on_fresh_writes():
    src = _src()
    assert 'return "green", f"{name}: fresh {int(age_min)}m"' in src


def test_lite_mode_detects_production_hostnames():
    """The LITE-mode detection was too narrow ("live-support"/"emergent.host"),
    so production pods named "aurem-live-prod-XXX" never engaged LITE
    mode and Pillar 4 stayed degraded."""
    src = _src()
    assert "aurem-live" in src and "prod-" in src, (
        "LITE-mode hostname detection must cover production-pod patterns"
    )


def test_lite_mode_still_excludes_dev_sandbox():
    src = _src()
    # The agent-env- prefix exclusion stays — that's the dev sandbox.
    assert 'not _host.startswith("agent-env-")' in src
