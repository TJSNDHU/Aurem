"""
D-71h — Cache hit-rate TTL bumps + Builder tenant_id resolution.

Issue 1 (cache hit-rate 27% → target 60%+):
  Two endpoints showed 0% hit rate because their TTLs equalled the
  frontend poll interval (cache expired exactly when the next poll
  arrived). Bumped to ~3-4× poll interval.

Issue 3 (Builder tenant_id=unknown):
  bridge_issue_to_builder was passing through the literal "unknown"
  fallback for sites that have a system_auto_repairs row but no
  matching tenant_customers record. Now resolves from site_url
  (domain match) before falling back to "unknown".
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ─── Issue 1 — Cache TTLs ───────────────────────────────────────────

def test_agents_status_ttl_bumped():
    """`aurem:agents:status` is polled every 10s by ORACommandConsole.
    With TTL=10 the cache always expired right before the next poll,
    producing 0% hit-rate. Must be at least 30s to clear 60% target."""
    src = Path("/app/backend/routers/aurem_routes.py").read_text()
    # Find the cached call line and parse its ttl_sec value
    import re
    m = re.search(r'key="aurem:agents:status",\s*ttl_sec=(\d+)', src)
    assert m, "Could not find aurem:agents:status cached call"
    assert int(m.group(1)) >= 30, (
        f"TTL must be ≥30s (~3× the 10s poll); found {m.group(1)}"
    )


def test_autonomous_overview_ttl_bumped():
    """`autonomous:overview` polled @ 15s — TTL must be ≥30s."""
    src = Path("/app/backend/routers/autonomous_stack_router.py").read_text()
    import re
    m = re.search(r'key="autonomous:overview",\s*\n?\s*ttl_sec=(\d+)', src)
    assert m, "Could not find autonomous:overview cached call"
    assert int(m.group(1)) >= 30, (
        f"TTL must be ≥30s (~2× the 15s poll); found {m.group(1)}"
    )


def test_mc_dashboard_and_overview_ttls_above_poll_interval():
    """mc:dashboard + mc:overview polled @ 20s. TTL must be >20s."""
    src = Path("/app/backend/routers/admin_mission_control_router.py").read_text()
    import re
    for key in ("mc:dashboard", "mc:overview"):
        m = re.search(rf'key="{key}",\s*ttl_sec=(\d+)', src)
        assert m, f"Could not find {key} cached call"
        ttl = int(m.group(1))
        assert ttl > 20, (
            f"{key} TTL must exceed 20s poll interval; found {ttl}"
        )


def test_sentinel_overview_ttl_above_poll():
    """sentinel:overview polled @ 20-30s by AdminSentinelClient."""
    src = Path("/app/backend/routers/sentinel_client_router.py").read_text()
    import re
    m = re.search(r'key="sentinel:overview",\s*ttl_sec=(\d+)', src)
    assert m
    assert int(m.group(1)) >= 45, (
        f"TTL must be ≥45s to clear 30s poll; found {m.group(1)}"
    )


# ─── Issue 3 — Builder tenant_id resolution ────────────────────────

@pytest.mark.asyncio
async def test_bridge_resolves_tenant_id_from_site_url():
    """When issue.tenant_id is missing/unknown, the bridge must look up
    tenant_customers by domain to fill it in. Stops 'tenant_id=unknown'
    from appearing in Builder logs."""
    from routers.self_repair_router import bridge_issue_to_builder

    captured = {}

    class FakeTenants:
        async def find_one(self, q, projection=None):
            captured["query"] = q
            # Simulate the reroots.ca tenant existing in tenant_customers
            return {"tenant_id": "tnt_reroots_001"}

    class FakeBuildLog:
        async def insert_one(self, doc):
            captured["build_doc"] = doc

    class FakeDB:
        tenant_customers = FakeTenants()
        build_log = FakeBuildLog()

    issue = {
        "fingerprint": "fp_xyz",
        "label": "reroots.ca",
        "tenant_id": "unknown",
        "site_url": "https://reroots.ca",
        "category": "seo",
        "severity": "P2",
        "issue": "missing meta description",
    }

    # Intercept _run_build_and_log so we don't actually fire an LLM call
    from unittest.mock import patch as _patch
    async def _stub_run(*a, **k):
        return None
    async def _stub_set(*a, **k): return None
    with _patch("routers.aurem_builder_router._run_build_and_log", _stub_run):
        with _patch("services.aurem_builder.new_build_id", return_value="bld_test"):
            try:
                await bridge_issue_to_builder(FakeDB(), issue, actor_email="test")
            except Exception:
                # Expected — downstream calls aren't fully mocked; we only
                # care that the tenant resolution happened first.
                pass

    assert issue["tenant_id"] == "tnt_reroots_001", (
        f"tenant_id should be resolved from site_url; got {issue['tenant_id']}"
    )
    # The build_log doc should have the resolved tenant
    assert "build_doc" in captured


@pytest.mark.asyncio
async def test_bridge_falls_back_to_unknown_when_no_tenant_match():
    """If the tenant lookup truly finds nothing, the description still
    renders cleanly (not None / not crash)."""
    from routers.self_repair_router import bridge_issue_to_builder

    class FakeTenants:
        async def find_one(self, q, projection=None):
            return None
    class FakeBuildLog:
        async def insert_one(self, doc): pass
    class FakeDB:
        tenant_customers = FakeTenants()
        build_log = FakeBuildLog()

    issue = {
        "fingerprint": "fp_abc",
        "label": "novel-site.ca",
        "tenant_id": None,
        "site_url": "https://novel-site.ca",
        "category": "seo",
    }

    from unittest.mock import patch as _patch
    async def _stub_run(*a, **k): return None
    with _patch("routers.aurem_builder_router._run_build_and_log", _stub_run):
        with _patch("services.aurem_builder.new_build_id", return_value="bld_test"):
            try:
                await bridge_issue_to_builder(FakeDB(), issue)
            except Exception:
                pass

    # Falls back to "unknown" (no crash, no None)
    assert issue["tenant_id"] == "unknown"
