"""
iter 326l-Option-B — auto-bootstrap on every signup
═══════════════════════════════════════════════════════════════════════════
Wires `bootstrap_tenant_dashboard()` into `_post_verify_kickoff()` so
EVERY newly-verified customer gets the baseline seed automatically.
No more "0 across the board" dashboards for fresh signups.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient


@pytest.fixture
def live_db_builder():
    db_name = f"aurem_iter326lb_{uuid.uuid4().hex[:12]}"

    def _builder():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        return client[db_name], client

    yield _builder

    async def _cleanup():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        await cli.drop_database(db_name)
        cli.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_cleanup())
    finally:
        loop.close()


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ════════════════════════════════════════════════════════════════════════
# 1. _post_verify_kickoff now invokes auto-bootstrap
# ════════════════════════════════════════════════════════════════════════

def test_kickoff_auto_bootstraps_baseline_scores(live_db_builder, monkeypatch):
    """The funnel function _post_verify_kickoff must seed baseline
    repair_scores via bootstrap_tenant_dashboard BEFORE the scan."""
    from routers.aurem_onboarding_router import _post_verify_kickoff

    async def go():
        db, _cli = live_db_builder()

        # Pre-seed onboarding row so kickoff can resolve email/business
        await db.aurem_onboarding.insert_one({
            "tenant_id":     "RERO-3DEJ",
            "email":         "admin@reroots.ca",
            "business_name": "Reroots Aesthetics Inc.",
            "pixel_installed": True,
        })

        # Stub scan_customer_site so we don't make real HTTP calls in CI.
        # The kickoff lazy-imports it, so we have to install the stub
        # into sys.modules BEFORE the import resolves.
        import sys, types
        fake_module = types.ModuleType("services.customer_scanner_service")
        called = {"count": 0}
        async def fake_scan(db_, tenant_id, url):
            called["count"] += 1
            return {"ok": True, "scan_id": "TEST"}
        fake_module.scan_customer_site = fake_scan
        monkeypatch.setitem(sys.modules,
                            "services.customer_scanner_service",
                            fake_module)

        await _post_verify_kickoff(db, "RERO-3DEJ", "https://reroots.ca")

        # Bootstrap baseline must have landed
        scores = await db.repair_scores.find_one({"tenant_id": "RERO-3DEJ"})
        assert scores is not None, "baseline repair_scores not seeded"
        assert scores["geo"]["score_after"] == 72
        assert scores["security"]["score_after"] == 84
        assert scores["accessibility"]["score_after"] == 78
        assert scores["seo"]["score_after"] == 81
        assert scores["composite"] == 78
        assert scores["source"] == "bootstrap_baseline"

        # Pixel row must have been upserted
        pixel = await db.aurem_pixels.find_one({"tenant_id": "RERO-3DEJ"})
        assert pixel is not None
        assert pixel["verified"] is True

        # And the real scan must have been ATTEMPTED (not blocked)
        assert called["count"] == 1, "scan_customer_site never invoked"

    _run(go())


def test_kickoff_baseline_does_NOT_recurse_into_self(live_db_builder, monkeypatch):
    """Critical safety — bootstrap must call with force_scan=False so
    it doesn't schedule another _post_verify_kickoff and infinite-recurse.

    Counts how many times _post_verify_kickoff is invoked by the chain.
    """
    from routers import aurem_onboarding_router

    invocations = {"count": 0}
    real_kickoff = aurem_onboarding_router._post_verify_kickoff

    async def go():
        db, _cli = live_db_builder()
        # Stub the scanner to be safe (same lazy-import trick)
        import sys, types
        fake_module = types.ModuleType("services.customer_scanner_service")
        async def fake_scan(db_, tenant_id, url):
            return {"ok": True}
        fake_module.scan_customer_site = fake_scan
        monkeypatch.setitem(sys.modules,
                            "services.customer_scanner_service",
                            fake_module)

        async def counting_kickoff(*args, **kw):
            invocations["count"] += 1
            return await real_kickoff(*args, **kw)

        # Replace the symbol the bootstrap module imports lazily
        import services.dashboard_bootstrap as bs_mod
        original_import = __import__

        # We don't need to patch the import; force_scan=False is enough.
        # Just call kickoff once and confirm it doesn't re-enter.
        monkeypatch.setattr(aurem_onboarding_router, "_post_verify_kickoff",
                            counting_kickoff)
        await counting_kickoff(db, "RERO-3DEJ", "https://reroots.ca")

        # Must be exactly 1 — bootstrap-with-force_scan=False didn't recurse
        assert invocations["count"] == 1, (
            f"infinite recursion suspected — kickoff invoked "
            f"{invocations['count']}x"
        )

    _run(go())


def test_kickoff_baseline_failure_does_not_block_scan(live_db_builder, monkeypatch):
    """If bootstrap throws, the kickoff must still proceed to fire the
    real scan. Baseline is a nice-to-have, the scan is essential."""
    from routers.aurem_onboarding_router import _post_verify_kickoff
    import services.dashboard_bootstrap as bs_mod

    scan_calls = {"count": 0}

    async def go():
        db, _cli = live_db_builder()

        # Force bootstrap to raise
        async def boom(*a, **kw):
            raise RuntimeError("simulated bootstrap failure")
        monkeypatch.setattr(bs_mod, "bootstrap_tenant_dashboard", boom)

        # Stub the scanner — it MUST still be reached
        import sys, types
        fake_module = types.ModuleType("services.customer_scanner_service")
        scan_calls_inner = scan_calls
        async def fake_scan(db_, tenant_id, url):
            scan_calls_inner["count"] += 1
            return {"ok": True}
        fake_module.scan_customer_site = fake_scan
        monkeypatch.setitem(sys.modules,
                            "services.customer_scanner_service",
                            fake_module)

        await _post_verify_kickoff(db, "RERO-3DEJ", "https://reroots.ca")

        # Bootstrap failed → no baseline scores
        scores = await db.repair_scores.find_one({"tenant_id": "RERO-3DEJ"})
        assert scores is None

        # But the scan was STILL fired
        assert scan_calls["count"] == 1, (
            "bootstrap failure blocked the scan — defeats the purpose"
        )

    _run(go())


# ════════════════════════════════════════════════════════════════════════
# 2. Static contract checks — source-code level
# ════════════════════════════════════════════════════════════════════════

def test_kickoff_source_imports_bootstrap_helper():
    """The kickoff function must import bootstrap_tenant_dashboard."""
    src = open(
        "/app/backend/routers/aurem_onboarding_router.py", encoding="utf-8"
    ).read()
    assert "from services.dashboard_bootstrap import bootstrap_tenant_dashboard" in src


def test_kickoff_passes_force_scan_false():
    """The kickoff's bootstrap call MUST pass force_scan=False to
    prevent recursion."""
    src = open(
        "/app/backend/routers/aurem_onboarding_router.py", encoding="utf-8"
    ).read()
    # Find the bootstrap call inside the kickoff
    idx = src.find("_post_verify_kickoff")
    assert idx > 0
    # Look for force_scan=False in the kickoff function body
    kickoff_body = src[idx:idx + 3000]  # generous window
    assert "force_scan=False" in kickoff_body, (
        "bootstrap call in kickoff must pass force_scan=False"
    )
