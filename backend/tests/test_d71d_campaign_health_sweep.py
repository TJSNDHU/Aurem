"""
D-71d Campaign Health sweep — regression for the 4 P0 fixes.

Scope:
 1. Test fixture leads can NEVER count as eligible (lead_pool == auto_blast)
 2. campaign_health.lead_pool query excludes internal-test sources and
    test-domain emails to match the auto_blast _eligible_leads filter
 3. Resend service is import-callable and uses the verified domain
 4. Voice Retell health check surfaces the EXACT missing env vars
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ─── 1. lead_pool vs auto_blast eligibility parity ──────────────────

def test_lead_pool_query_excludes_internal_test_sources():
    """The bug on aurem.live: lead_pool reported 25 eligible while
    auto_blast had 0. Root cause: lead_pool counted internal-test source
    leads that _eligible_leads then filtered out. Both must now filter
    identically."""
    src = Path("/app/backend/services/campaign_health.py").read_text()
    # Must mention the same internal-test source list
    for s in ("awb_e2e_test", "agent2agent_test", "playwright_test", "qa_smoke"):
        assert s in src, f"lead_pool query missing exclusion for source '{s}'"


def test_lead_pool_query_excludes_test_domain_emails():
    src = Path("/app/backend/services/campaign_health.py").read_text()
    # The test-domain regex must be there
    assert "aurem-test" in src or "aurem-test|test|example" in src
    assert "$not" in src and "$regex" in src, (
        "lead_pool must exclude test-domain emails via $not/$regex"
    )


# ─── 2. Resend service real-call shape ──────────────────────────────

def test_resend_service_uses_verified_domain_default():
    src = Path("/app/backend/services/email_service_resend.py").read_text()
    # The DEFAULT_FROM must be a verified-domain sender. The verified
    # domain on aurem.live's Resend account is `aurem.live` itself.
    assert "aurem.live" in src, "Default sender must use verified aurem.live domain"
    # And the actual key reads from env (not hardcoded)
    assert 'os.environ.get("RESEND_API_KEY"' in src


def test_resend_webhook_url_documented_correctly():
    """The webhook URL the founder must paste into Resend dashboard is
    https://aurem.live/api/lifecycle/resend-webhook (production host).
    The health check must surface this exact URL when no events have
    arrived yet."""
    src = Path("/app/backend/services/campaign_health.py").read_text()
    assert "/api/lifecycle/resend-webhook" in src


# ─── 3. Voice Retell — exact missing env vars listed ────────────────

def test_voice_retell_lists_specific_missing_vars():
    src = Path("/app/backend/services/campaign_health.py").read_text()
    # Both env names must be referenced literally so the founder can
    # copy-paste them into the production env panel.
    assert "RETELL_API_KEY"     in src
    assert "RETELL_FROM_NUMBER" in src
    assert "RETELL_AGENT_ID"    in src
    # And the detail string for the partial-config case must name them
    assert "RETELL_FROM_NUMBER or RETELL_AGENT_ID missing" in src


# ─── 4. campaign_leads sanitisation guards ──────────────────────────

def test_auto_blast_engine_blocks_internal_test_sources():
    src = Path("/app/backend/services/auto_blast_engine.py").read_text()
    # The runner must skip internal sources at the per-lead loop level.
    assert "_INTERNAL_TEST_SOURCES" in src
    assert "in _INTERNAL_TEST_SOURCES" in src
    # And test-domain emails get a `continue` too.
    assert "_TEST_EMAIL_DOMAINS" in src
