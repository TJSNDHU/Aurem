"""
services/saml_sso.py — iter 332b Batch B (Step 2)

SAML 2.0 SSO config storage + flow stubs.

Each Organization can configure a SAML Identity Provider (Okta, Azure AD,
Google Workspace, OneLogin, etc). This module persists the config and
exposes the helper surfaces a future python3-saml integration will need.

Storage: db.saml_configs  (org_id unique)

Fields:
  org_id           — links to organizations.org_id
  idp_provider     — okta|azure_ad|google|onelogin|generic
  idp_entity_id    — IdP-side identifier (XML metadata `entityID`)
  idp_sso_url      — IdP-side SAML SSO endpoint
  idp_cert         — IdP X.509 certificate (PEM)
  sp_entity_id     — AUREM-side identifier (always
                     https://aurem.live/saml/<org_slug>/metadata)
  acs_url          — Where the IdP POSTs the SAML response
                     (https://aurem.live/api/saml/<org_id>/acs)
  attribute_map    — {"email": "Email", "first_name": "FirstName", ...}
  default_role     — role assigned to first-time SSO logins (member by default)
  status           — pending|active|disabled
  created_at, updated_at

NOTE on the real SAML message handling: validating the SAML AuthnResponse
signature, decrypting the assertion, checking the audience, and minting
our JWT happen in a follow-up slice once python3-saml or onelogin-saml-py
is installed. This module ships the config storage + stub endpoints so
the UI can collect the IdP metadata + admin can flip status=active.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None

VALID_PROVIDERS = ("okta", "azure_ad", "google", "onelogin", "generic")
VALID_STATUS = ("pending", "active", "disabled")
DEFAULT_ATTRIBUTE_MAP = {
    "email": "Email",
    "first_name": "FirstName",
    "last_name":  "LastName",
}


def set_db(database) -> None:
    global _db
    _db = database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _site_base() -> str:
    import os
    return (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")


# ── Config CRUD ─────────────────────────────────────────────────────

async def get_saml_config(org_id: str) -> Optional[dict]:
    if _db is None:
        return None
    return await _db.saml_configs.find_one({"org_id": org_id}, {"_id": 0})


async def upsert_saml_config(org_id: str, updates: dict) -> dict:
    """Owner/admin sets the IdP metadata. Validates required fields."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if not org_id:
        return {"ok": False, "error": "org_id_required"}

    # Pull the slug for sp_entity_id derivation
    org = await _db.organizations.find_one(
        {"org_id": org_id}, {"_id": 0, "slug": 1, "name": 1},
    )
    if not org:
        return {"ok": False, "error": "org_not_found"}

    provider = (updates.get("idp_provider") or "generic").lower()
    if provider not in VALID_PROVIDERS:
        return {"ok": False, "error": "invalid_provider"}

    existing = await get_saml_config(org_id) or {}
    config_id = existing.get("config_id") or uuid.uuid4().hex
    site = _site_base()

    doc = {
        "config_id":      config_id,
        "org_id":         org_id,
        "idp_provider":   provider,
        "idp_entity_id":  str(updates.get("idp_entity_id") or "").strip()[:400],
        "idp_sso_url":    str(updates.get("idp_sso_url") or "").strip()[:400],
        "idp_cert":       str(updates.get("idp_cert") or "").strip()[:8000],
        "sp_entity_id":   f"{site}/saml/{org['slug']}/metadata",
        "acs_url":        f"{site}/api/saml/{org_id}/acs",
        "attribute_map":  updates.get("attribute_map") or DEFAULT_ATTRIBUTE_MAP,
        "default_role":   updates.get("default_role") or "member",
        "status":         updates.get("status") or existing.get("status") or "pending",
        "updated_at":     _now_iso(),
        "created_at":     existing.get("created_at") or _now_iso(),
    }
    if doc["status"] not in VALID_STATUS:
        return {"ok": False, "error": "invalid_status"}

    await _db.saml_configs.update_one(
        {"org_id": org_id},
        {"$set": doc},
        upsert=True,
    )
    doc.pop("_id", None)
    return {"ok": True, "config": doc}


async def delete_saml_config(org_id: str) -> dict:
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    r = await _db.saml_configs.delete_one({"org_id": org_id})
    return {"ok": True, "deleted": r.deleted_count > 0}


async def list_active_saml_orgs() -> list[dict]:
    """Used by the public SAML discovery endpoint
    (POST /api/saml/discover {email}) — finds the org whose domain
    matches the email's domain AND has status='active'."""
    if _db is None:
        return []
    cur = _db.saml_configs.find({"status": "active"}, {"_id": 0})
    return await cur.to_list(length=200)


async def discover_org_by_email(email: str) -> Optional[dict]:
    """Returns the active SAML config whose org.domain matches
    the email's domain, or None."""
    if _db is None or not email or "@" not in email:
        return None
    domain = email.split("@", 1)[1].lower().strip()
    # Join: find orgs with this domain, then check saml_configs.status=active
    orgs_cur = _db.organizations.find(
        {"domain": domain, "status": "active"}, {"_id": 0, "org_id": 1, "name": 1},
    )
    orgs = await orgs_cur.to_list(length=10)
    for org in orgs:
        cfg = await _db.saml_configs.find_one(
            {"org_id": org["org_id"], "status": "active"},
            {"_id": 0},
        )
        if cfg:
            return {"org": org, "saml": cfg}
    return None


# ── Login records (audit who came through SAML) ─────────────────────

async def record_saml_login(
    org_id: str,
    email: str,
    name_id: str,
    success: bool,
    extra: Optional[dict] = None,
) -> None:
    if _db is None:
        return
    try:
        await _db.saml_logins.insert_one({
            "ts":       _now_iso(),
            "org_id":   org_id,
            "email":    email.lower(),
            "name_id":  name_id,
            "success":  success,
            "extra":    extra or {},
        })
    except Exception as e:
        logger.debug(f"[saml] login record skipped: {e}")
