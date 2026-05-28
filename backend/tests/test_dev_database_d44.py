"""
tests/test_dev_database_d44.py — iter D-44

Tests the read-only /api/developers/database/info endpoint and the URL
masking helper. Auth-gating is enforced by the FastAPI dependency
require_admin and is covered by the live curl smoke test in CI.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_mask_strips_credentials_for_atlas_url():
    from routers.developer_database_router import _mask_mongo_url
    url = "mongodb+srv://founderuser:s3cr3tPass@cluster0.abcdef.mongodb.net/aurem"
    out = _mask_mongo_url(url)
    assert "founderuser" not in out
    assert "s3cr3tPass"  not in out
    assert "****:****"   in out
    assert "db.net" in out  # host tail preserved so user recognizes it


def test_mask_handles_standard_url():
    from routers.developer_database_router import _mask_mongo_url
    out = _mask_mongo_url("mongodb://root:rootpw@localhost:27017/mydb")
    assert "root"   not in out
    assert "rootpw" not in out


def test_mask_handles_empty_input():
    from routers.developer_database_router import _mask_mongo_url
    assert _mask_mongo_url("") == ""


def test_mask_handles_unparseable_input():
    from routers.developer_database_router import _mask_mongo_url
    assert _mask_mongo_url("not-a-mongo-url") == "***masked***"


@pytest.mark.asyncio
async def test_db_info_returns_masked_url_only(monkeypatch):
    """db_info() must NEVER include the raw MONGO_URL in its payload."""
    monkeypatch.setenv(
        "MONGO_URL",
        "mongodb+srv://founder:supersecret@cluster.mongodb.net/aurem",
    )
    monkeypatch.setenv("DB_NAME", "aurem_test")
    from routers.developer_database_router import db_info
    out = await db_info()
    assert out["app_name"] == "AUREM Platform"
    assert out["db_name"]  == "aurem_test"
    assert out["provider"] == "MongoDB Atlas"
    assert "supersecret" not in out["mongo_url_masked"]
    assert "founder"     not in out["mongo_url_masked"]
    # Every value must be free of plaintext credentials
    flat = " ".join(str(v) for v in out.values())
    assert "supersecret" not in flat


@pytest.mark.asyncio
async def test_db_info_raises_when_url_missing(monkeypatch):
    """503 when the platform isn't configured."""
    monkeypatch.delenv("MONGO_URL", raising=False)
    from fastapi import HTTPException
    from routers.developer_database_router import db_info
    with pytest.raises(HTTPException) as exc:
        await db_info()
    assert exc.value.status_code == 503


def test_dash_nav_has_d44_pages():
    """The sidebar nav constant must list all 13 routes from the spec."""
    path = os.path.join(
        ROOT, "..", "frontend", "src", "platform", "developers",
        "DeveloperShell.jsx",
    )
    src = open(path).read()
    for route in (
        "/developers/dashboard",  "/developers/connect",
        "/developers/projects",   "/developers/deploy",
        "/developers/domain",     "/developers/database",
        "/developers/analytics",  "/developers/examples",
        "/developers/tokens",     "/developers/docs",
        "/developers/status",     "/developers/settings",
        "/developers/terms",
    ):
        assert route in src, f"sidebar nav missing {route}"


def test_devsettings_no_longer_has_byok_rotate():
    """BYOK rotate was moved to Connect; settings page should not
    reference the old `settings-byok-rotate-btn` testid anymore."""
    path = os.path.join(
        ROOT, "..", "frontend", "src", "platform", "developers",
        "DevSettings.jsx",
    )
    src = open(path).read()
    assert "settings-byok-rotate-btn" not in src
    assert "SectionTitle title=\"Rotate BYOK keys\"" not in src
