"""
iter 332b C-2 — Trust Center + Compliance UI + Org Switcher
==============================================================

Public endpoints covering Trust Center hydration, plus source-level
wiring sanity for the 3 new frontend pages.
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    from services.organizations import set_db as _o
    from services.data_residency import set_db as _r
    from services.soc2_export import set_db as _s
    _o(database); _r(database); _s(database)
    yield database
    client.close()


# ═══════════════════════════════════════════════════════════════════
# New public endpoints (Trust Center hydration)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_subprocessors_endpoint_returns_rows(db):
    from routers.compliance_router import subprocessors_public
    r = await subprocessors_public()
    assert r["ok"] is True
    assert isinstance(r["rows"], list)
    assert len(r["rows"]) >= 5
    # Each row has the expected shape
    for row in r["rows"]:
        assert "name" in row
        assert "region" in row
        assert "purpose" in row


@pytest.mark.asyncio
async def test_regions_endpoint_returns_three_options(db):
    from routers.compliance_router import regions_public
    r = await regions_public()
    assert r["ok"] is True
    assert set(r["rows"].keys()) == {"ca", "us", "eu"}
    assert r["rows"]["ca"]["primary"] is True
    assert r["rows"]["ca"]["pipeda"] is True


@pytest.mark.asyncio
async def test_sla_endpoint_still_works(db):
    """Regression — adding subprocessors + regions didn't break SLA."""
    from routers.compliance_router import sla_msa_public
    r = await sla_msa_public()
    assert r["ok"] is True
    assert r["sla"]["uptime_target"] == "99.9%"
    assert "msa" in r


# ═══════════════════════════════════════════════════════════════════
# Source-level wiring sanity
# ═══════════════════════════════════════════════════════════════════

def test_trust_center_page_exists_and_calls_three_endpoints():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/TrustCenter.jsx").read_text()
    assert "trust-center-page" in src
    assert "/api/compliance/sla" in src
    assert "/api/compliance/subprocessors" in src
    assert "/api/compliance/regions" in src
    # Has SOC 2 link to admin, SLA link, MSA + DPA links, sales link
    assert "trust-soc2-download-btn" in src
    assert "trust-sla-link" in src
    assert "trust-msa-link" in src
    assert "trust-dpa-link" in src
    assert "trust-contact-sales-link" in src


def test_enterprise_compliance_admin_page_exists():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/enterprise/EnterpriseCompliance.jsx").read_text()
    assert "compliance-residency-card" in src
    assert "compliance-soc2-card" in src
    assert "compliance-residency-save-btn" in src
    assert "compliance-soc2-download-btn" in src
    # Residency tile per region (testid is template-literal in source)
    assert "compliance-region-${code}" in src
    # Org selector + date pickers
    assert "compliance-soc2-start" in src
    assert "compliance-soc2-end" in src


def test_org_switcher_component_exists():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/OrgSwitcher.jsx").read_text()
    assert "org-switcher" in src
    assert "org-switcher-btn" in src
    assert "org-switcher-dropdown" in src
    assert "/api/orgs/me" in src
    assert "/api/orgs/switch" in src


def test_admin_shell_wires_org_switcher():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/AdminShell.jsx").read_text()
    assert "OrgSwitcher" in src
    assert "import OrgSwitcher" in src


def test_admin_shell_compliance_nav_pill():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/enterprise/EnterpriseAdminShell.jsx").read_text()
    assert "ent-nav-compliance" in src
    assert "/enterprise/admin/compliance" in src


def test_app_js_wires_three_new_routes():
    from pathlib import Path
    src = Path("/app/frontend/src/App.js").read_text()
    assert "/enterprise/security" in src
    assert "/enterprise/admin/compliance" in src
    assert "TrustCenter" in src
    assert "EnterpriseCompliance" in src
