"""
Regression test — iter 322ep
Locks in:
  1. Broadcast addendum injects FULL body for the dev-engineering-protocol skill.
  2. ORA optimize router scan returns valid shape.
  3. Design extract summary endpoint is reachable.
"""
import os
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


def _db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


@pytest.mark.asyncio
async def test_broadcast_addendum_contains_3_proof_block():
    """Iter 322ep — broadcast must propagate full skill bodies so ORA
    actually sees the rules deeper than 600 chars."""
    from services.agent_skill_broadcast import get_addendum, invalidate_cache
    invalidate_cache()
    ad = await get_addendum(_db(), agent_name="GATEWAY")
    assert ad, "addendum empty — broadcast missing"
    # The dev-engineering-protocol skill's 3-proof block lives at ~6,700 chars
    # of its body. If we ever revert to 600-char head truncation, these fail.
    assert "MANDATORY 3 PROOFS" in ad, "3-proof block missing from addendum"
    assert "git log --oneline -3" in ad, "git log proof missing"
    assert "/api/platform/health" in ad, "health check proof missing"
    # The new content-injection-fix skill itself must be present
    assert "broadcast-content-injection-fix" in ad.lower(), \
        "iter 322ep self-skill missing from active broadcast"


@pytest.mark.asyncio
async def test_dev_engineering_protocol_skill_intact():
    """The library row must keep the full body — never replaced with description."""
    s = await _db().ora_skills_library.find_one(
        {"id": "aurem-322ei-developer-engineering-protocol"},
        {"_id": 0, "body": 1, "name": 1},
    )
    assert s is not None, "dev-engineering-protocol skill missing"
    assert len(s["body"]) > 5000, f"body too short: {len(s['body'])} chars"
    assert "MANDATORY 3 PROOFS" in s["body"]
    assert "git log --oneline -3" in s["body"]


@pytest.mark.asyncio
async def test_ora_optimize_scan_returns_valid_shape():
    """Smoke-test the _scan_data aggregator without hitting the HTTP layer."""
    from routers.ora_optimize_router import _scan_data
    data = await _scan_data(_db(), window_hours=24)
    assert "total_calls" in data
    assert "cache" in data
    assert "rows" in data["cache"]
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)


def test_design_extract_router_imports_clean():
    """Router module must import without raising — guards against
    accidental syntax breakage."""
    from routers import design_extract_router
    assert hasattr(design_extract_router, "router")
    paths = [r.path for r in design_extract_router.router.routes]
    assert "/api/admin/design-extract/run" in paths
    assert "/api/admin/design-extract/history" in paths
    assert "/api/admin/design-extract/summary" in paths
    assert "/api/admin/design-extract/export/{fmt}" in paths


def test_ora_optimize_router_imports_clean():
    """ORA optimize router smoke test."""
    from routers import ora_optimize_router
    paths = [r.path for r in ora_optimize_router.router.routes]
    assert "/api/admin/ora-optimize/scan" in paths
    assert "/api/admin/ora-optimize/summary" in paths
    assert "/api/admin/ora-optimize/purge-stale" in paths
