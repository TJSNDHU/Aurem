"""
Tests for the public SEO funnel revenue path (iter 325c).

Covers:
- Health endpoint
- Scan endpoint contract (does not call real_audit in CI — patched)
- Checkout endpoint contract (does not hit live Stripe — patched)
- Stripe metadata wiring (so the existing /api/webhook/stripe handler
  can route the paid event to the right tenant).
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/app/backend")

from routers import seo_funnel_router


class _FakeColl:
    """Minimal Motor-like async collection for unit tests."""
    def __init__(self):
        self.inserted = []
        self.updated = []
        self.docs = {}

    async def insert_one(self, doc):
        self.inserted.append(doc)
        return MagicMock(inserted_id="oid")

    async def find_one(self, q, projection=None):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in q.items()):
                return {k: v for k, v in d.items() if k != "_id"}
        return None

    async def update_one(self, q, update, upsert=False):
        self.updated.append((q, update))
        return MagicMock(modified_count=1)


class _FakeDB:
    def __init__(self):
        self.leads = _FakeColl()
        self.website_repair_reports = _FakeColl()
        self.payment_transactions = _FakeColl()

    def __getitem__(self, name):
        return getattr(self, name)


@pytest.fixture
def db():
    fake = _FakeDB()
    seo_funnel_router.set_db(fake)
    return fake


def test_router_mounted_with_correct_prefix():
    assert seo_funnel_router.router.prefix == "/api/public/seo-funnel"
    paths = {r.path for r in seo_funnel_router.router.routes}
    assert "/api/public/seo-funnel/scan" in paths
    assert "/api/public/seo-funnel/checkout" in paths
    assert "/api/public/seo-funnel/health" in paths


def test_starter_price_matches_aurem_starter_tier():
    """The funnel CTA must charge the same price as in-app Starter,
    otherwise we leak pricing inconsistency to the customer."""
    # Match aurem_routes.SUBSCRIPTION_TIERS['starter']['price'] = 49.00
    assert seo_funnel_router.STARTER_PRICE_USD == 49.00
    assert seo_funnel_router.STARTER_PLAN_ID == "plan_starter"


def test_top_issues_picks_first_n_and_normalises():
    audit = {
        "issues": [
            {"title": "SSL expired", "severity": "high", "detail": "Cert expired 3d ago"},
            {"title": "Slow PageSpeed"},
            "broken_form",  # raw string — should still be normalised
            {"name": "Missing alt", "priority": "low"},
        ],
    }
    out = seo_funnel_router._top_issues(audit, limit=5)
    assert len(out) == 4
    assert out[0]["title"] == "SSL expired"
    assert out[0]["severity"] == "high"
    assert out[2]["title"] == "broken_form"
    assert out[2]["severity"] == "medium"  # default
    assert out[3]["severity"] == "low"


@pytest.mark.asyncio
async def test_health_reports_db_wired(db):
    h = await seo_funnel_router.health()
    assert h["ok"] is True
    assert h["db_wired"] is True


@pytest.mark.asyncio
async def test_scan_persists_lead_and_returns_top_issues(db):
    fake_audit = {
        "ok": True,
        "url": "https://example.com",
        "overall_score": 42,
        "issues": [
            {"title": "SSL invalid", "severity": "high", "detail": "x"},
            {"title": "Slow LCP", "severity": "medium", "detail": "y"},
            {"title": "Missing form", "severity": "low", "detail": "z"},
        ],
    }
    with patch.object(
        seo_funnel_router, "real_audit", new=None, create=True
    ), patch("services.website_audit_service.real_audit", new=AsyncMock(return_value=fake_audit)):
        req = seo_funnel_router.ScanRequest(url="example.com", email=None)
        request = MagicMock()
        request.client.host = "1.2.3.4"
        request.headers.get.return_value = "pytest"
        out = await seo_funnel_router.public_scan(req, request)
    assert out["ok"] is True
    assert out["overall_score"] == 42
    assert len(out["issues"]) == 3
    assert out["plan"]["price_usd"] == 49.00
    # Persisted to both leads + reports collections
    assert len(db.leads.inserted) == 1
    assert db.leads.inserted[0]["source"] == "seo_funnel"
    assert len(db.website_repair_reports.inserted) == 1


@pytest.mark.asyncio
async def test_checkout_404s_when_scan_not_found(db):
    """Front-end should resurface the error so user can re-scan."""
    from fastapi import HTTPException
    req = seo_funnel_router.CheckoutRequest(email="x@y.com", scan_id="missing-id")
    request = MagicMock()
    request.base_url = "https://aurem.live/"
    with pytest.raises(HTTPException) as exc:
        await seo_funnel_router.public_checkout(req, request)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_checkout_wires_stripe_metadata_for_webhook(db):
    """The /api/webhook/stripe handler keys off session metadata to
    provision the tenant. The funnel MUST set source + scan_id + email."""
    # Pre-seed a scan
    db.website_repair_reports.docs["x"] = {"report_id": "scan-abc", "url": "https://e.com"}

    fake_session = MagicMock(session_id="cs_test_x", url="https://stripe.test/cs_test_x")
    fake_checkout = MagicMock()
    fake_checkout.create_checkout_session = AsyncMock(return_value=fake_session)

    captured = {}

    def _capture_req(**kwargs):
        captured.update(kwargs)
        return MagicMock(**kwargs)

    with patch(
        "emergentintegrations.payments.stripe.checkout.StripeCheckout",
        return_value=fake_checkout,
    ), patch(
        "emergentintegrations.payments.stripe.checkout.CheckoutSessionRequest",
        side_effect=_capture_req,
    ), patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_dummy"}, clear=False):
        req = seo_funnel_router.CheckoutRequest(
            email="founder@biz.com",
            scan_id="scan-abc",
            business_name="Biz Inc",
        )
        request = MagicMock()
        request.base_url = "https://aurem.live/"
        out = await seo_funnel_router.public_checkout(req, request)

    assert out["ok"] is True
    assert out["checkout_url"].startswith("https://stripe.test/")
    md = captured["metadata"]
    assert md["source"] == "seo_funnel"
    assert md["scan_id"] == "scan-abc"
    assert md["user_email"] == "founder@biz.com"
    assert md["plan_id"] == "plan_starter"
    assert md["tier"] == "starter"
    assert captured["amount"] == 49.00
    # Lead updated + tx persisted
    assert any("checkout_started" in str(u) for u in db.leads.updated)
    assert len(db.payment_transactions.inserted) == 1
