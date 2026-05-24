"""
iter 332b D — Renewal nudges (D-1) + SAML SP-side signing (D-2)
=================================================================
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    from services.organizations import set_db as _o
    from services.renewal_nudges import set_db as _r
    from services.saml_sp_keys import set_db as _k
    from services.saml_sso import set_db as _s
    _o(database); _r(database); _k(database); _s(database)
    yield database
    # cleanup
    await database.organizations.delete_many({"name": {"$regex": "^pytest_"}})
    await database.renewal_nudges_sent.delete_many(
        {"org_id": {"$regex": "."}},
    )
    await database.saml_sp_keys.delete_many({"key_id": "pytest_sp"})
    client.close()


# ═══════════════════════════════════════════════════════════════════
# Renewal nudges (D-1)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_find_due_renewals_fires_at_each_window(db):
    """Org with renewal_date exactly 90/60/30/14 days out → flagged."""
    from services.organizations import create_organization
    from services.renewal_nudges import find_due_renewals
    today = date(2026, 5, 1)
    for w in (90, 60, 30, 14):
        uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
        r = await create_organization(
            name=f"pytest_Renew_{w}d_{uuid.uuid4().hex[:4]}", created_by=uid,
        )
        await db.organizations.update_one(
            {"org_id": r["org"]["org_id"]},
            {"$set": {
                "contract_renewal_date": (today + timedelta(days=w)).isoformat(),
                "mrr_usd": 500 * w,
            }},
        )
    due = await find_due_renewals(today=today)
    assert len(due) == 4
    assert sorted([d["window_days"] for d in due]) == [14, 30, 60, 90]


@pytest.mark.asyncio
async def test_find_due_renewals_ignores_off_window_dates(db):
    """Renewal 45 days out (not in {90/60/30/14}) → NOT flagged."""
    from services.organizations import create_organization
    from services.renewal_nudges import find_due_renewals
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_OffWindow", created_by=uid)
    today = date(2026, 6, 1)
    await db.organizations.update_one(
        {"org_id": r["org"]["org_id"]},
        {"$set": {"contract_renewal_date": (today + timedelta(days=45)).isoformat()}},
    )
    due = await find_due_renewals(today=today)
    assert all(d["org"]["org_id"] != r["org"]["org_id"] for d in due)


@pytest.mark.asyncio
async def test_find_due_renewals_idempotent_within_day(db):
    """Once a nudge fires for (org, window, due_date), it doesn't re-fire."""
    from services.organizations import create_organization
    from services.renewal_nudges import (
        find_due_renewals, send_renewal_nudge,
    )
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_Idemp", created_by=uid)
    today = date(2026, 7, 1)
    await db.organizations.update_one(
        {"org_id": r["org"]["org_id"]},
        {"$set": {"contract_renewal_date": (today + timedelta(days=60)).isoformat()}},
    )
    due = await find_due_renewals(today=today)
    mine = [d for d in due if d["org"]["org_id"] == r["org"]["org_id"]]
    assert len(mine) == 1
    # Fire once
    await send_renewal_nudge(mine[0])
    # Re-run — must not flag again
    due2 = await find_due_renewals(today=today)
    mine2 = [d for d in due2 if d["org"]["org_id"] == r["org"]["org_id"]]
    assert len(mine2) == 0


@pytest.mark.asyncio
async def test_send_renewal_nudge_writes_idempotency_row(db):
    from services.organizations import create_organization
    from services.renewal_nudges import send_renewal_nudge
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_NudgeRow", created_by=uid)
    item = {
        "org": {"org_id": r["org"]["org_id"], "name": "pytest_NudgeRow",
                 "plan": "growth", "mrr_usd": 800},
        "window_days": 30,
        "due_date":    "2026-06-01",
    }
    res = await send_renewal_nudge(item)
    assert res["ok"] is True
    row = await db.renewal_nudges_sent.find_one(
        {"org_id": r["org"]["org_id"], "window_days": 30,
          "due_date": "2026-06-01"}, {"_id": 0},
    )
    assert row is not None
    assert "sent_at" in row
    assert "telegram_ok" in row


@pytest.mark.asyncio
async def test_run_renewal_tick_returns_summary(db):
    from services.organizations import create_organization
    from services.renewal_nudges import run_renewal_tick
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_Tick", created_by=uid)
    today = date(2026, 8, 1)
    await db.organizations.update_one(
        {"org_id": r["org"]["org_id"]},
        {"$set": {"contract_renewal_date": (today + timedelta(days=14)).isoformat()}},
    )
    summary = await run_renewal_tick(today=today)
    assert summary["ok"] is True
    assert summary["nudges_fired"] >= 1
    assert summary["checked_today"] == "2026-08-01"


def test_renewal_parse_handles_iso_strings_and_dates():
    from services.renewal_nudges import _parse_renewal_date
    assert _parse_renewal_date("2026-08-15") == date(2026, 8, 15)
    assert _parse_renewal_date("2026-08-15T00:00:00+00:00") == date(2026, 8, 15)
    assert _parse_renewal_date("2026-08-15T00:00:00Z") == date(2026, 8, 15)
    assert _parse_renewal_date(None) is None
    assert _parse_renewal_date("garbage") is None


def test_registry_wires_renewal_cron():
    from pathlib import Path
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "renewal_nudges" in src
    assert "_install_renewal" in src


# ═══════════════════════════════════════════════════════════════════
# SAML SP-side signing (D-2)
# ═══════════════════════════════════════════════════════════════════

def test_sp_keypair_generates_valid_pem():
    from services.saml_sp_keys import _generate_keypair
    cert, key = _generate_keypair()
    assert "BEGIN CERTIFICATE" in cert
    assert "END CERTIFICATE"   in cert
    assert "PRIVATE KEY"       in key
    assert len(cert) > 500
    assert len(key)  > 500


@pytest.mark.asyncio
async def test_sp_keypair_persists_across_calls(db):
    from services.saml_sp_keys import get_sp_keypair, SP_KEY_ID
    # Clear any existing keypair so we test the create path cleanly
    await db.saml_sp_keys.delete_many({"key_id": SP_KEY_ID})
    # Reset in-process cache (next call refetches)
    from services import saml_sp_keys as _m
    _m._cache = {}
    kp1 = await get_sp_keypair()
    _m._cache = {}
    kp2 = await get_sp_keypair()
    assert kp1["cert"] == kp2["cert"]
    assert kp1["key"]  == kp2["key"]


@pytest.mark.asyncio
async def test_sp_keypair_force_regen_rotates(db):
    from services.saml_sp_keys import get_sp_keypair, SP_KEY_ID
    from services import saml_sp_keys as _m
    await db.saml_sp_keys.delete_many({"key_id": SP_KEY_ID})
    _m._cache = {}
    kp1 = await get_sp_keypair()
    kp2 = await get_sp_keypair(force_regen=True)
    assert kp1["cert"] != kp2["cert"]
    # Persisted row reflects the rotated cert
    row = await db.saml_sp_keys.find_one({"key_id": SP_KEY_ID}, {"_id": 0})
    assert row["cert"] == kp2["cert"]


def test_cert_for_metadata_xml_strips_pem_envelope():
    from services.saml_sp_keys import cert_for_metadata_xml
    pem = (
        "-----BEGIN CERTIFICATE-----\n"
        "AAAA\nBBBB\nCCCC\n"
        "-----END CERTIFICATE-----\n"
    )
    out = cert_for_metadata_xml(pem)
    assert out == "AAAABBBBCCCC"


def test_build_saml_settings_with_sp_keys_marks_signed():
    from services.saml_sso import build_saml_settings
    org = {"slug": "acme", "org_id": "abc"}
    cfg = {
        "idp_provider": "okta",
        "idp_entity_id": "http://okta.com/exk1",
        "idp_sso_url":   "https://acme.okta.com/sso",
        "idp_cert":      "-----BEGIN CERTIFICATE-----\nXX\n-----END CERTIFICATE-----",
    }
    s_unsigned = build_saml_settings(org, cfg)
    assert s_unsigned["security"]["authnRequestsSigned"] is False
    assert "x509cert"   not in s_unsigned["sp"]
    assert "privateKey" not in s_unsigned["sp"]

    s_signed = build_saml_settings(
        org, cfg,
        sp_cert="-----BEGIN CERTIFICATE-----\nYY\n-----END CERTIFICATE-----",
        sp_key="-----BEGIN PRIVATE KEY-----\nZZ\n-----END PRIVATE KEY-----",
    )
    assert s_signed["security"]["authnRequestsSigned"] is True
    assert s_signed["sp"]["x509cert"].startswith("-----BEGIN CERTIFICATE")
    assert s_signed["sp"]["privateKey"].startswith("-----BEGIN PRIVATE KEY")
    assert s_signed["security"]["signatureAlgorithm"].endswith("rsa-sha256")


@pytest.mark.asyncio
async def test_metadata_xml_embeds_sp_cert(db):
    """SP metadata XML must contain <X509Certificate> with our cert."""
    from services.organizations import create_organization
    from services.saml_sp_keys import get_sp_keypair
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_MetaXML", created_by=uid)
    # Ensure SP keypair exists
    kp = await get_sp_keypair()
    # Call the endpoint function directly (sidestep TestClient loop bug)
    from routers.saml_router import sp_metadata, set_db
    set_db(db)
    resp = await sp_metadata(r["org"]["org_id"])
    xml = resp.body.decode("utf-8") if hasattr(resp, "body") else str(resp)
    assert 'AuthnRequestsSigned="true"' in xml
    assert "<X509Certificate>" in xml
    assert "</X509Certificate>" in xml
    # The cert body (sans PEM envelope) is embedded
    from services.saml_sp_keys import cert_for_metadata_xml
    needle = cert_for_metadata_xml(kp["cert"])[:80]
    assert needle in xml


@pytest.mark.asyncio
async def test_login_init_returns_signed_redirect(db):
    """SP-initiated login builds a signed AuthnRequest URL."""
    from services.organizations import create_organization
    from services.saml_sso import upsert_saml_config
    from services.saml_sp_keys import get_sp_keypair
    from routers.saml_router import saml_login_init, set_db
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_LoginInit", created_by=uid)
    # Use a realistic-shape self-signed cert as the IdP cert.
    kp = await get_sp_keypair()  # reuse our own keypair as the fake IdP one
    await upsert_saml_config(r["org"]["org_id"], {
        "idp_provider": "okta",
        "idp_entity_id": "http://okta.com/exk_test",
        "idp_sso_url":   "https://acme.okta.com/app/abc/sso/saml",
        "idp_cert":      kp["cert"],
        "status":        "active",
    })
    set_db(db)

    class FakeURL:
        scheme = "https"
        hostname = "aurem.live"
        port = 443
        path = "/api/saml/abc/login"
        query = ""

    class FakeReq:
        url = FakeURL()
        headers = {}
        query_params = {}

    out = await saml_login_init(r["org"]["org_id"], FakeReq())
    assert out["ok"] is True
    assert "SAMLRequest=" in out["redirect_to"]
    assert out["signed"] is True
    assert out["relay_state"].endswith("/saml/landing")


def test_saml_router_metadata_now_advertises_signed():
    from pathlib import Path
    src = Path("/app/backend/routers/saml_router.py").read_text()
    assert "AuthnRequestsSigned=\"true\"" in src
    assert "X509Certificate" in src
    assert "saml_sp_keys" in src
