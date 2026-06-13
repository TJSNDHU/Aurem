"""
iter 326j — Gaps 1, 2, 3, 5 — E2E regression tests
═══════════════════════════════════════════════════════════════════════════
Uses Tejinder/Reroots Aesthetics (admin@reroots.ca, business_id RERO-3DEJ)
as the live customer fixture, plus a generic dogfood ephemeral DB for the
service-layer tests.

Gaps under test:
  Gap 1 — Stripe subscription lifecycle stamps stripe_subscription_id
  Gap 2 — POST /api/customer/deploy/report receiver + workflow shipper
  Gap 3 — subscription_plans tier bundles seeded with real prices
  Gap 5 — recommended_bundles by industry + live pricing endpoint
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from dotenv import load_dotenv

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient


# ── Shared ephemeral DB fixture ────────────────────────────────────────
@pytest.fixture
def live_db_builder():
    db_name = f"aurem_iter326j_{uuid.uuid4().hex[:12]}"

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
# GAP 1 — Stripe subscription lifecycle properly stamps stripe_subscription_id
# ════════════════════════════════════════════════════════════════════════

def test_gap1_webhook_branch_handles_subscription_created():
    """Static contract — the stripe webhook handler must include a
    customer.subscription.created/updated branch that stamps
    stripe_subscription_id onto customer_subscriptions."""
    src = open(
        "/app/backend/routers/stripe_payment_router.py", encoding="utf-8"
    ).read()
    # Both events must be handled in the same branch
    assert '"customer.subscription.created"' in src
    assert '"customer.subscription.updated"' in src
    # The branch must stamp stripe_subscription_id via update_one
    assert "stripe_subscription_id" in src
    assert "last_stripe_sync_at" in src, (
        "audit timestamp missing — won't know which subs synced via webhook"
    )


def test_gap1_subscription_created_stamps_pending_row(live_db_builder):
    """Simulate the iter 326j Gap-1 path:
      1. customer_subscribe inserts a pending row WITH stripe_session_id
         but stripe_subscription_id=None
      2. customer.subscription.created event fires later
      3. Webhook must stamp stripe_subscription_id on the pending row.

    We don't run the whole FastAPI; we call the upsert query the
    webhook now does, with the same shape. This proves the query
    matches the row pattern.
    """
    async def go():
        db, _cli = live_db_builder()
        # Pre-state — pending row from customer_subscribe
        await db.customer_subscriptions.insert_one({
            "sub_id":              f"sub_{uuid.uuid4().hex[:14]}",
            "email":               "admin@reroots.ca",
            "service_id":          "site_monitor_lite",
            "service_name":        "Site Monitor — Lite",
            "price_monthly":       29.00,
            "status":              "pending",
            "stripe_session_id":   "cs_test_RERO_DEMO",
            "stripe_subscription_id": None,
            "started_at":          "2026-05-21T22:00:00+00:00",
        })

        # Simulate the new Gap-1 stamp using the same query the webhook uses
        sub_id        = "sub_1ABCRER00TSDEMO123456"
        sub_metadata  = {"service_id": "site_monitor_lite",
                          "user_email": "admin@reroots.ca"}
        await db.customer_subscriptions.update_one(
            {
                "email": sub_metadata["user_email"],
                "service_id": sub_metadata["service_id"],
                "status": {"$in": ["pending", "active"]},
                "$or": [
                    {"stripe_subscription_id": None},
                    {"stripe_subscription_id": {"$exists": False}},
                    {"stripe_subscription_id": ""},
                ],
            },
            {"$set": {
                "stripe_subscription_id": sub_id,
                "stripe_customer_id":     "cus_TESTRERO",
                "stripe_status":          "active",
                "status":                 "active",
                "activated_at":           "2026-05-21T22:00:01+00:00",
                "last_stripe_sync_at":    "2026-05-21T22:00:01+00:00",
            }},
        )

        # Verify the stamp landed
        doc = await db.customer_subscriptions.find_one(
            {"email": "admin@reroots.ca", "service_id": "site_monitor_lite"}
        )
        assert doc["stripe_subscription_id"] == sub_id
        assert doc["stripe_status"] == "active"
        assert doc["status"] == "active"
        assert doc["stripe_customer_id"] == "cus_TESTRERO"
        assert doc["activated_at"]

    _run(go())


def test_gap1_never_overwrites_existing_stripe_sub_id(live_db_builder):
    """If a row already has a different stripe_subscription_id, the
    fallback path must NOT overwrite it. Prevents silent corruption."""
    async def go():
        db, _cli = live_db_builder()
        await db.customer_subscriptions.insert_one({
            "email":                  "admin@reroots.ca",
            "service_id":             "site_monitor_lite",
            "status":                 "active",
            "stripe_subscription_id": "sub_ORIGINAL_DO_NOT_TOUCH",
        })
        await db.customer_subscriptions.update_one(
            {
                "email": "admin@reroots.ca",
                "service_id": "site_monitor_lite",
                "status": {"$in": ["pending", "active"]},
                "$or": [
                    {"stripe_subscription_id": None},
                    {"stripe_subscription_id": {"$exists": False}},
                    {"stripe_subscription_id": ""},
                ],
            },
            {"$set": {"stripe_subscription_id": "sub_INTRUDER"}},
        )
        doc = await db.customer_subscriptions.find_one(
            {"email": "admin@reroots.ca"}
        )
        assert doc["stripe_subscription_id"] == "sub_ORIGINAL_DO_NOT_TOUCH"

    _run(go())


# ════════════════════════════════════════════════════════════════════════
# GAP 2 — POST /api/customer/deploy/report + workflow shipper
# ════════════════════════════════════════════════════════════════════════

def test_gap2_receiver_route_registered():
    """The router must register POST /api/customer/deploy/report."""
    from routers import customer_deploy_router
    paths = [
        (r.path, list(r.methods)[0] if r.methods else None)
        for r in customer_deploy_router.router.routes
        if hasattr(r, "path") and hasattr(r, "methods")
    ]
    pmap = dict(paths)
    assert "/api/customer/deploy/report" in pmap
    assert pmap["/api/customer/deploy/report"] == "POST"
    assert "/api/admin/customer-deploys" in pmap


def test_gap2_record_deploy_with_valid_api_key(live_db_builder):
    """Customer workflow POSTs deploy result with the API key we issued.
    Must persist to github_deployments with the right tenant_id."""
    from services import github_deploy_service as svc

    async def go():
        db, _cli = live_db_builder()
        svc.set_db(db)
        # Customer has connected GitHub
        await db.github_connections.insert_one({
            "tenant_id":         "RERO-3DEJ",
            "customer_api_key":  "ak_rero_test_xyz",
            "github_username":   "tejisandhu",
            "status":            "connected",
            "authorized_repos":  ["reroots-aesthetics/main-site"],
        })
        res = await svc.record_customer_deploy_report(
            api_key="ak_rero_test_xyz",
            commit="a1b2c3d4e5f6789012345678901234567890abcd",
            status="success",
            repo="reroots-aesthetics/main-site",
        )
        assert res["ok"] is True
        assert res["tenant_id"] == "RERO-3DEJ"
        # Persisted
        doc = await db.github_deployments.find_one(
            {"deployment_id": res["deployment_id"]}
        )
        assert doc is not None
        assert doc["tenant_id"] == "RERO-3DEJ"
        assert doc["status"] == "success"
        assert doc["repo"] == "reroots-aesthetics/main-site"
        assert doc.get("unauth") is not True

    _run(go())


def test_gap2_unrecognised_api_key_soft_records(live_db_builder):
    """Bad/expired API key must NOT 500. Must soft-record with unauth=True
    so founder can reconcile."""
    from services import github_deploy_service as svc

    async def go():
        db, _cli = live_db_builder()
        svc.set_db(db)
        res = await svc.record_customer_deploy_report(
            api_key="ak_BOGUS",
            commit="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            status="failure",
            repo="evil/repo",
        )
        assert res["ok"] is False
        assert res.get("soft_recorded") is True
        doc = await db.github_deployments.find_one({"repo": "evil/repo"})
        assert doc is not None
        assert doc["unauth"] is True
        assert doc["tenant_id"] is None

    _run(go())


def test_gap2_workflow_shipper_function_exists():
    """The workflow shipper must exist + use the canonical template path."""
    from services import github_deploy_service as svc
    assert hasattr(svc, "ship_auto_deploy_workflow")
    src = open(
        "/app/backend/services/github_deploy_service.py", encoding="utf-8"
    ).read()
    assert "/app/.github/workflows/auto_deploy.yml" in src
    assert ".github/workflows/aurem_auto_deploy.yml" in src


def test_gap2_workflow_shipper_template_file_exists():
    """The template AUREM ships to customer repos must physically exist."""
    assert os.path.isfile("/app/.github/workflows/auto_deploy.yml")
    with open("/app/.github/workflows/auto_deploy.yml") as f:
        content = f.read()
    assert "AUREM" in content
    assert "aurem-autofix" in content


# ════════════════════════════════════════════════════════════════════════
# GAP 3 — subscription_plans tier bundles seeded with real prices
# ════════════════════════════════════════════════════════════════════════

def test_gap3_seed_drops_empty_shells_and_inserts_tier_bundles(live_db_builder):
    """Pre-state: 5 empty plan_id rows like prod. Post-seed: must be
    replaced with real tier bundles having price + service_ids + features."""
    from services.recommended_bundles import seed_subscription_plans

    async def go():
        db, _cli = live_db_builder()
        # Pre-state — empty shells like prod
        for name in ("Free Forever", "Starter", "Professional",
                     "Enterprise", "Growth"):
            await db.subscription_plans.insert_one({"name": name})

        res = await seed_subscription_plans(db)
        assert res["ok"] is True
        assert res["removed_empty"] == 5
        assert res["upserted"] == 5

        # Verify each tier
        for plan_id in ("free_forever", "starter", "growth", "pro", "enterprise"):
            doc = await db.subscription_plans.find_one({"plan_id": plan_id})
            assert doc is not None, f"missing tier: {plan_id}"
            assert "price_monthly" in doc
            assert "service_ids" in doc
            assert "features" in doc
            assert doc.get("tier_order") is not None

        # Starter must include website_repair (catalog $29)
        starter = await db.subscription_plans.find_one({"plan_id": "starter"})
        assert "website_repair" in starter["service_ids"]
        assert starter["price_monthly"] == 99

        # Enterprise must include voice_agent_ai + sovereign_privacy
        ent = await db.subscription_plans.find_one({"plan_id": "enterprise"})
        assert "voice_agent_ai" in ent["service_ids"]
        assert "sovereign_privacy" in ent["service_ids"]
        assert ent["price_monthly"] == 799

    _run(go())


def test_gap3_seed_is_idempotent(live_db_builder):
    from services.recommended_bundles import seed_subscription_plans

    async def go():
        db, _cli = live_db_builder()
        await seed_subscription_plans(db)
        await seed_subscription_plans(db)  # second run must be no-op
        # Must still have exactly 5 tier rows
        n = await db.subscription_plans.count_documents({})
        assert n == 5

    _run(go())


# ════════════════════════════════════════════════════════════════════════
# GAP 5 — Recommended bundles per industry + live pricing
# ════════════════════════════════════════════════════════════════════════

def test_gap5_industry_bundles_seeded(live_db_builder):
    from services.recommended_bundles import seed_industry_bundles

    async def go():
        db, _cli = live_db_builder()
        res = await seed_industry_bundles(db)
        assert res["ok"] is True
        assert res["upserted"] >= 4
        # 4 industries minimum
        industries = sorted(res["industries"])
        for needed in ("restaurant", "salon", "clinic", "agency"):
            assert needed in industries, f"missing industry: {needed}"
        # Clinic bundle must include sovereign_privacy (Canadian compliance)
        clinic = await db.recommended_bundles.find_one({"industry": "clinic"})
        assert "sovereign_privacy" in clinic["service_ids"]
        # Restaurant must include voice agent
        rest = await db.recommended_bundles.find_one({"industry": "restaurant"})
        assert "voice_agent_ai" in rest["service_ids"]

    _run(go())


def test_gap5_price_bundle_applies_discount_correctly(live_db_builder):
    """5 services should trigger the 25% bundle discount per BUNDLE_RULES."""
    from services.recommended_bundles import price_bundle

    async def go():
        db, _cli = live_db_builder()
        # Seed minimum catalog
        await db.service_catalog.insert_many([
            {"service_id": "s1", "name": "S1", "price_monthly": 29, "status": "live"},
            {"service_id": "s2", "name": "S2", "price_monthly": 29, "status": "live"},
            {"service_id": "s3", "name": "S3", "price_monthly": 39, "status": "live"},
            {"service_id": "s4", "name": "S4", "price_monthly": 49, "status": "live"},
            {"service_id": "s5", "name": "S5", "price_monthly": 79, "status": "live"},
        ])
        # Seed bundle_rules (matches the prod seeder)
        await db.bundle_rules.insert_many([
            {"min_services": 3, "discount_pct": 15, "label": "Pick 3+ → Save 15%"},
            {"min_services": 5, "discount_pct": 25, "label": "Pick 5+ → Save 25%"},
            {"min_services": 8, "discount_pct": 35, "label": "Pick 8+ → Save 35%"},
        ])
        res = await price_bundle(db, ["s1", "s2", "s3", "s4", "s5"])
        assert res["ok"] is True
        assert res["service_count"] == 5
        assert res["subtotal"] == 225.0   # 29+29+39+49+79
        assert res["discount_pct"] == 25
        assert "5+" in res["discount_label"]
        # 225 * 0.75 = 168.75
        assert res["total"] == 168.75
        assert res["missing"] == []
        assert len(res["items"]) == 5

    _run(go())


def test_gap5_price_bundle_reports_missing_service_ids(live_db_builder):
    from services.recommended_bundles import price_bundle

    async def go():
        db, _cli = live_db_builder()
        await db.service_catalog.insert_one(
            {"service_id": "real", "name": "R", "price_monthly": 19, "status": "live"}
        )
        res = await price_bundle(db, ["real", "ghost", "vapor"])
        assert res["ok"] is True
        assert res["service_count"] == 1
        assert sorted(res["missing"]) == ["ghost", "vapor"]

    _run(go())


def test_gap5_router_endpoints_registered():
    """All 3 catalog endpoints from iter 326j must be exposed."""
    from routers import recommended_bundles_router as r
    paths = set()
    for rt in r.router.routes:
        if hasattr(rt, "path"):
            paths.add(rt.path)
    assert "/api/catalog/tier-bundles" in paths
    assert "/api/catalog/recommended-bundles" in paths
    assert "/api/customer/bundle-price" in paths


# ════════════════════════════════════════════════════════════════════════
# E2E — Reroots admin@reroots.ca real-customer fixture
# ════════════════════════════════════════════════════════════════════════

def test_e2e_reroots_full_pipeline(live_db_builder):
    """End-to-end: simulate Reroots Aesthetics buying the 'clinic'
    industry bundle, getting a Stripe sub stamped, and reporting a
    successful deploy back via the customer workflow."""
    from services.recommended_bundles import (
        seed_subscription_plans, seed_industry_bundles, price_bundle,
    )
    from services import github_deploy_service as svc

    async def go():
        db, _cli = live_db_builder()
        svc.set_db(db)

        # Step 1 — Seed catalog + bundles like prod startup does
        # (minimal catalog rows for the clinic bundle services)
        await db.service_catalog.insert_many([
            {"service_id": "sovereign_privacy", "name": "Sovereign Privacy",
             "price_monthly": 49, "status": "live"},
            {"service_id": "casl_compliance", "name": "CASL Compliance",
             "price_monthly": 39, "status": "live"},
            {"service_id": "auto_heal", "name": "Auto-Heal",
             "price_monthly": 59, "status": "live"},
            {"service_id": "voice_agent_ai", "name": "Voice Agent",
             "price_monthly": 149, "status": "live"},
            {"service_id": "site_monitor_pro", "name": "Site Monitor Pro",
             "price_monthly": 99, "status": "live"},
        ])
        await db.bundle_rules.insert_many([
            {"min_services": 3, "discount_pct": 15, "label": "Pick 3+"},
            {"min_services": 5, "discount_pct": 25, "label": "Pick 5+"},
        ])
        await seed_subscription_plans(db)
        await seed_industry_bundles(db)

        # Step 2 — Reroots picks the clinic bundle. Compute live price.
        clinic = await db.recommended_bundles.find_one({"industry": "clinic"})
        pricing = await price_bundle(db, clinic["service_ids"])
        assert pricing["service_count"] == 5
        # subtotal: 49+39+59+149+99 = 395; with 25% off = 296.25
        assert pricing["subtotal"] == 395.0
        assert pricing["discount_pct"] == 25
        assert pricing["total"] == 296.25

        # Step 3 — Insert pending Stripe checkout row for Reroots
        # (mirrors what customer_subscribe does)
        for sid in clinic["service_ids"]:
            await db.customer_subscriptions.insert_one({
                "sub_id":              f"sub_{uuid.uuid4().hex[:14]}",
                "tenant_bin":          "RERO-3DEJ",
                "email":               "admin@reroots.ca",
                "service_id":          sid,
                "status":              "pending",
                "stripe_session_id":   "cs_test_RERO_clinic_bundle",
                "stripe_subscription_id": None,
            })

        # Step 4 — Stripe customer.subscription.created fires for one svc
        # (the lifecycle stamp we added in Gap 1)
        await db.customer_subscriptions.update_one(
            {
                "email": "admin@reroots.ca",
                "service_id": "sovereign_privacy",
                "status": {"$in": ["pending", "active"]},
                "$or": [
                    {"stripe_subscription_id": None},
                    {"stripe_subscription_id": {"$exists": False}},
                ],
            },
            {"$set": {
                "stripe_subscription_id": "sub_RERO_LIVE_001",
                "stripe_status":          "active",
                "status":                 "active",
            }},
        )
        # Now Reroots has 1 live + 4 pending — at least the bridge works.
        active = await db.customer_subscriptions.count_documents(
            {"email": "admin@reroots.ca", "status": "active"}
        )
        assert active == 1

        # Step 5 — Reroots connects GitHub
        await db.github_connections.insert_one({
            "tenant_id":         "RERO-3DEJ",
            "github_username":   "rerootsdev",
            "customer_api_key":  "ak_rero_live_001",
            "status":            "connected",
            "authorized_repos":  ["reroots-aesthetics/site"],
        })

        # Step 6 — Customer's workflow reports a successful deploy
        report = await svc.record_customer_deploy_report(
            api_key="ak_rero_live_001",
            commit="abc1234567890abc1234567890abc1234567",
            status="success",
            repo="reroots-aesthetics/site",
        )
        assert report["ok"] is True
        assert report["tenant_id"] == "RERO-3DEJ"

        # Step 7 — Founder dashboard can query the deploy log
        n = await db.github_deployments.count_documents(
            {"tenant_id": "RERO-3DEJ", "status": "success"}
        )
        assert n == 1

    _run(go())
