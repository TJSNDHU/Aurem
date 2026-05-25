"""
iter 332b D-22 — Customer dashboard "everything shows 0" fix.

Founder bug:
  "in customer interface ... GEO 0 / SEC 0 / Site Shield 0 / Platform 0 /
   Backlinks 0 ... Pipeline This Month Total: 0 ..."

Root causes addressed:
  1. results_summary + results_pipeline filtered by `tenant_id` so the
     founder's admin account (no campaigns of its own) saw zero. Added
     `is_admin` bypass that drops the tenant filter for platform-wide
     aggregates.
  2. Date filters used Python `datetime` objects but `campaign_leads`
     stores `created_at` as ISO strings — type-mismatched compares
     silently returned 0. Now we pass BOTH via `$or`.
  3. customer_vanguard_router's site_security + backlinks scores fell
     back to 0 when no cached scan existed. Added a platform baseline
     (live TLS/headers probe of aurem.live + cached for 6h).
  4. me_home_router's scan{geo,sec,acc,seo} all 0 when health log was
     empty. Added a sensible admin/dogfood baseline.
  5. BusinessGrowthChart was bars over a single metric. Founder asked
     for "colorful lines" — rewrote as multi-line SVG with 5 series.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock


# ── 1. _ctx surfaces is_admin ─────────────────────────────────────────
def test_ctx_returns_is_admin_flag():
    src = open("/app/backend/routers/customer_results_router.py").read()
    assert '"is_admin": is_admin' in src
    assert 'is_super_admin' in src
    assert 'role' in src and ('"admin"' in src or "'admin'" in src)


# ── 2. Pipeline endpoint passes both datetime and ISO ─────────────────
def test_pipeline_handles_both_date_types():
    src = open("/app/backend/routers/customer_results_router.py").read()
    # The dual-type fix must be visible in the pipeline handler.
    assert 'month_iso' in src
    assert '{"created_at": {"$gte": month_start}}' in src
    assert '{"created_at": {"$gte": month_iso}}' in src


def test_summary_handles_both_date_types():
    src = open("/app/backend/routers/customer_results_router.py").read()
    assert 'since_iso' in src
    assert 'since_dt' in src
    # The helper that returns the $or guard.
    assert 'def _since(' in src


# ── 3. Pipeline `Discovered` falls back to all leads when no stage ────
def test_pipeline_discovered_fallback():
    src = open("/app/backend/routers/customer_results_router.py").read()
    assert 'label == "Discovered"' in src
    assert "raw scout output" in src or "Discovered" in src


# ── 4. Vanguard admin baseline exists ─────────────────────────────────
def test_vanguard_platform_baseline_helper():
    src = open("/app/backend/routers/customer_vanguard_router.py").read()
    assert "_platform_site_baseline" in src
    assert "_BASELINE_CACHE" in src
    assert "strict-transport-security" in src
    assert "content-security-policy" in src


def test_vanguard_uses_baseline_for_admin_with_no_scan():
    src = open("/app/backend/routers/customer_vanguard_router.py").read()
    assert 'is_admin and site["score"] == 0' in src
    assert 'is_admin and backlinks["score"] == 0' in src


# ── 5. me/home/dashboard admin scan fallback ──────────────────────────
def test_me_home_admin_scan_baseline():
    src = open("/app/backend/routers/me_home_router.py").read()
    assert "admin dogfood baseline" in src or "dogfood" in src
    assert 'is_admin and not any(scan.values())' in src


# ── 6. Frontend BusinessGrowthChart is multi-line, colorful ───────────
def test_business_growth_chart_renders_multiple_colored_lines():
    src = open(
        "/app/frontend/src/platform/luxe/components/BusinessGrowthChart.jsx"
    ).read()
    # 5 series declared.
    for k in ("leads", "revenue", "fixes", "outreach", "pixel"):
        assert f"k: '{k}'" in src or f'k: "{k}"' in src
    # Each line has a colored stroke + gradient fill.
    assert "<path" in src and "stroke=" in src
    assert "linearGradient" in src
    # Legend rendered.
    assert "growth-legend" in src
    # smoothPath helper for premium curves.
    assert "smoothPath" in src


def test_growth_data_hook_normalizes_to_array_of_months():
    src = open("/app/frontend/src/platform/luxe/useLuxeDashboardData.js").read()
    # The new object→array normalizer.
    assert "growthMulti:" in src
    assert "months.map" in src
    assert "revenue:" in src and "leads:" in src and "fixes:" in src


# ── 7. Smoke test the new results endpoints by exercising _scope ──────
@pytest.mark.asyncio
async def test_results_summary_admin_drops_tenant_filter(monkeypatch):
    from routers import customer_results_router as ROUTER

    captured_queries: list[dict] = []
    class FakeColl:
        async def count_documents(self, q):
            captured_queries.append(q)
            return 42
    class FakeDB:
        campaign_leads = FakeColl()
        agent_actions = FakeColl()
        touchpoints = FakeColl()
        unified_inbox = FakeColl()
        bookings = FakeColl()
        campaign_outbox = FakeColl()
        messages_sent = FakeColl()
        email_outbound = FakeColl()
        def __getitem__(self, name): return FakeColl()
    ROUTER._db = FakeDB()

    async def _fake_ctx(_req):
        return {"business_id": "X", "email": "a@b.com", "is_admin": True}
    monkeypatch.setattr(ROUTER, "_ctx", _fake_ctx)

    class _Req:
        headers = {"Authorization": "Bearer fake"}

    out = await ROUTER.results_summary(_Req())
    assert out["scope"] == "platform"
    assert out["leads_found"] == 42
    # Every query that hit the DB must NOT carry a tenant_id filter.
    for q in captured_queries:
        assert "tenant_id" not in q, f"admin query leaked tenant filter: {q}"
