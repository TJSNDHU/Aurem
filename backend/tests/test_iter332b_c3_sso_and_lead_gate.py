"""
iter 332b C-3 — Footer link + SSO/SCIM settings page + SOC 2 lead gate
=======================================================================
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    from services.organizations import set_db as _o
    from services.data_residency import set_db as _r
    from services.soc2_export import set_db as _s
    _o(database); _r(database); _s(database)
    # Wire compliance router DB too
    from routers.compliance_router import set_db as _c
    _c(database)
    yield database
    await database.enterprise_leads.delete_many({"source": "trust_center_soc2"})
    await database.organizations.delete_many({"org_id": "sample_org_trust_center"})
    client.close()


# ═══════════════════════════════════════════════════════════════════
# Footer link to Trust Center + SLA
# ═══════════════════════════════════════════════════════════════════

def test_homepage_footer_links_to_trust_center():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/AuremHomepage.jsx").read_text()
    assert 'data-testid="footer-link-trust-center"' in src
    assert "/enterprise/security" in src


def test_homepage_footer_links_to_sla():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/AuremHomepage.jsx").read_text()
    assert 'data-testid="footer-link-sla"' in src
    assert "/enterprise/sla" in src


# ═══════════════════════════════════════════════════════════════════
# SOC 2 lead-gated sample endpoint
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_soc2_sample_captures_lead_and_returns_pdf(db):
    """End-to-end: direct async call (Motor + TestClient share an event-loop bug)."""
    from routers.compliance_router import soc2_sample_lead_gated, Soc2LeadBody

    class FakeReq:
        class _C: host = "127.0.0.1"
        client = _C()
        headers = {"user-agent": "pytest-curl"}

    resp = await soc2_sample_lead_gated(
        Soc2LeadBody(email="procurement@pytest.example",
                       company="Pytest Corp", role="Head of Security"),
        FakeReq(),
    )
    # StreamingResponse — body is the iterator. We assert headers + body magic.
    body = b""
    async for chunk in resp.body_iterator:
        body += chunk
    assert body.startswith(b"%PDF")
    assert resp.media_type == "application/pdf"
    assert "X-Aurem-Lead-Id" in resp.headers
    # Lead row persisted
    row = await db.enterprise_leads.find_one(
        {"email": "procurement@pytest.example"}, {"_id": 0},
    )
    assert row is not None
    assert row["source"] == "trust_center_soc2"
    assert row["company"] == "Pytest Corp"
    assert row["status"] == "new"


@pytest.mark.asyncio
async def test_soc2_sample_rejects_invalid_email(db):
    from routers.compliance_router import soc2_sample_lead_gated, Soc2LeadBody
    from fastapi import HTTPException

    class FakeReq:
        client = None
        headers = {}

    with pytest.raises(HTTPException) as exc:
        await soc2_sample_lead_gated(
            Soc2LeadBody(email="nope-no-domain", company="Bad Corp"),
            FakeReq(),
        )
    assert exc.value.status_code == 400
    assert "invalid_email" in str(exc.value.detail)


# ═══════════════════════════════════════════════════════════════════
# Trust Center modal wiring
# ═══════════════════════════════════════════════════════════════════

def test_trust_center_uses_lead_capture_modal():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/TrustCenter.jsx").read_text()
    assert "trust-lead-modal" in src
    assert "trust-lead-email" in src
    assert "trust-lead-company" in src
    assert "trust-lead-submit-btn" in src
    assert "trust-lead-success" in src
    # Modal opens on the SOC 2 button click (not just a sign-in link)
    assert "setLeadOpen(true)" in src
    assert "/api/compliance/soc2/sample" in src


# ═══════════════════════════════════════════════════════════════════
# Enterprise SSO/SCIM settings page wiring
# ═══════════════════════════════════════════════════════════════════

def test_enterprise_sso_page_exists_with_all_testids():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/enterprise/EnterpriseSSO.jsx").read_text()
    # SAML half
    assert "sso-saml-card" in src
    assert "sso-saml-provider" in src
    assert "sso-saml-entity-id" in src
    assert "sso-saml-sso-url" in src
    assert "sso-saml-cert" in src
    assert "sso-saml-status" in src
    assert "sso-saml-default-role" in src
    assert "sso-saml-save-btn" in src
    assert "sso-saml-test-btn" in src
    assert "sso-sp-metadata-box" in src
    # SCIM half
    assert "sso-scim-card" in src
    assert "sso-scim-issue-btn" in src
    assert "sso-scim-name" in src
    assert "sso-scim-list" in src
    # Backend wiring
    assert "/api/saml/" in src
    assert "/api/scim/" in src
    assert "/api/saml/${orgId}/metadata" in src


def test_enterprise_admin_shell_includes_sso_nav():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/enterprise/EnterpriseAdminShell.jsx").read_text()
    assert "ent-nav-sso" in src
    assert "/enterprise/admin/sso" in src
    assert '"SSO & SCIM"' in src


def test_app_js_wires_sso_route():
    from pathlib import Path
    src = Path("/app/frontend/src/App.js").read_text()
    assert "EnterpriseSSO" in src
    assert "/enterprise/admin/sso" in src


# ═══════════════════════════════════════════════════════════════════
# Compliance router endpoint registration
# ═══════════════════════════════════════════════════════════════════

def test_compliance_router_registers_soc2_sample():
    from routers.compliance_router import router
    paths = {r.path for r in router.routes}
    assert "/api/compliance/soc2/sample" in paths
    assert "/api/compliance/subprocessors" in paths
    assert "/api/compliance/regions" in paths
