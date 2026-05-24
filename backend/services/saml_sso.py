"""
services/saml_sso.py — iter 332b Batch B (Step 2) — REAL python3-saml flow
================================================================

Org-scoped SAML 2.0 SSO. Each Organization configures its own IdP.

  • get_saml_config / upsert_saml_config / delete_saml_config — admin CRUD
  • discover_org_by_email                   — public, by email domain
  • build_saml_settings(org_row, cfg_row)   — assemble OneLogin settings
  • prepare_fastapi_request(req, post)      — convert FastAPI Request to
                                              the dict python3-saml wants
  • parse_acs_response(req, post, org, cfg) — validate + decode → user dict
  • record_saml_login                       — audit trail
"""
from __future__ import annotations

import logging
import os
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
    return (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")


# ── Config CRUD ─────────────────────────────────────────────────────

async def get_saml_config(org_id: str) -> Optional[dict]:
    if _db is None:
        return None
    return await _db.saml_configs.find_one({"org_id": org_id}, {"_id": 0})


async def upsert_saml_config(org_id: str, updates: dict) -> dict:
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if not org_id:
        return {"ok": False, "error": "org_id_required"}
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
        {"org_id": org_id}, {"$set": doc}, upsert=True,
    )
    doc.pop("_id", None)
    return {"ok": True, "config": doc}


async def delete_saml_config(org_id: str) -> dict:
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    r = await _db.saml_configs.delete_one({"org_id": org_id})
    return {"ok": True, "deleted": r.deleted_count > 0}


async def discover_org_by_email(email: str) -> Optional[dict]:
    if _db is None or not email or "@" not in email:
        return None
    domain = email.split("@", 1)[1].lower().strip()
    orgs_cur = _db.organizations.find(
        {"domain": domain, "status": "active"}, {"_id": 0, "org_id": 1, "name": 1, "slug": 1},
    )
    orgs = await orgs_cur.to_list(length=10)
    for org in orgs:
        cfg = await _db.saml_configs.find_one(
            {"org_id": org["org_id"], "status": "active"}, {"_id": 0},
        )
        if cfg:
            return {"org": org, "saml": cfg}
    return None


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
            "email":    (email or "").lower(),
            "name_id":  name_id or "",
            "success":  success,
            "extra":    extra or {},
        })
    except Exception as e:
        logger.debug(f"[saml] login record skipped: {e}")


# ── python3-saml integration ────────────────────────────────────────

def build_saml_settings(org: dict, cfg: dict) -> dict:
    """Assemble OneLogin_Saml2_Settings dict from MongoDB rows."""
    site = _site_base()
    return {
        "strict": True,
        "debug":  False,
        "sp": {
            "entityId": cfg.get("sp_entity_id")
                          or f"{site}/saml/{org['slug']}/metadata",
            "assertionConsumerService": {
                "url":     cfg.get("acs_url")
                            or f"{site}/api/saml/{org['org_id']}/acs",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat":
                "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
        "idp": {
            "entityId": cfg["idp_entity_id"],
            "singleSignOnService": {
                "url":     cfg["idp_sso_url"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": cfg["idp_cert"],
        },
        "security": {
            "authnRequestsSigned":   False,
            "wantAssertionsSigned":  True,
            "wantNameId":            True,
            "wantMessagesSigned":    False,
            "wantAssertionsEncrypted": False,
            "wantAttributeStatement": True,
            "relaxDestinationValidation": False,
        },
    }


def prepare_fastapi_request(
    request,
    saml_response: Optional[str] = None,
    relay_state:   Optional[str] = None,
) -> dict:
    """Convert FastAPI Request → the dict python3-saml's
    OneLogin_Saml2_Auth expects.

    Honors X-Forwarded-Proto / X-Forwarded-Host so that running behind
    a Kubernetes ingress / Cloudflare doesn't break Destination checks.
    """
    url = request.url
    scheme = (request.headers.get("x-forwarded-proto") or url.scheme).lower()
    host = (request.headers.get("x-forwarded-host")
             or url.hostname or "localhost")
    port = url.port or (443 if scheme == "https" else 80)
    post_data: dict = {}
    if saml_response is not None:
        post_data["SAMLResponse"] = saml_response
    if relay_state is not None:
        post_data["RelayState"] = relay_state
    return {
        "https":        "on" if scheme == "https" else "off",
        "http_host":    host,
        "server_port":  str(port),
        "script_name":  url.path,
        "get_data":     dict(request.query_params),
        "post_data":    post_data,
        "query_string": url.query or "",
    }


def map_saml_attributes(
    attributes: dict,
    name_id:    Optional[str],
    cfg:        dict,
) -> dict:
    """Pull email + first/last name out of the SAML assertion using
    either the org's custom attribute_map or sensible defaults that
    cover Okta, Azure AD, Google, OneLogin."""
    attribute_map = cfg.get("attribute_map") or DEFAULT_ATTRIBUTE_MAP

    def first_val(*keys: str) -> Optional[str]:
        for k in keys:
            if k and k in attributes and attributes[k]:
                v = attributes[k][0] if isinstance(attributes[k], list) \
                     else attributes[k]
                if v:
                    return str(v)
        return None

    email_key  = attribute_map.get("email", "Email")
    fname_key  = attribute_map.get("first_name", "FirstName")
    lname_key  = attribute_map.get("last_name",  "LastName")

    email = first_val(
        email_key, "email", "Email", "mail", "EmailAddress",
        "userPrincipalName",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    ) or name_id

    first_name = first_val(
        fname_key, "first_name", "FirstName", "given_name",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
    )
    last_name = first_val(
        lname_key, "last_name", "LastName", "family_name",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
    )
    return {
        "email":      (email or "").lower().strip(),
        "first_name": first_name or "",
        "last_name":  last_name or "",
        "name_id":    name_id or "",
    }


async def parse_acs_response(
    request,
    saml_response: str,
    relay_state: Optional[str],
    org: dict,
    cfg: dict,
) -> dict:
    """Validate the IdP's SAMLResponse via python3-saml.

    Returns:
      {ok: True,  user: {email, first_name, last_name, name_id},
                  attributes: {...}, name_id: ...}
      {ok: False, error: 'reason', detail: '...'}.
    """
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
    except Exception as e:
        return {"ok": False, "error": "python3_saml_not_installed",
                 "detail": str(e)}
    settings = build_saml_settings(org, cfg)
    req_data = prepare_fastapi_request(request, saml_response, relay_state)
    try:
        auth = OneLogin_Saml2_Auth(req_data, old_settings=settings)
        auth.process_response()
    except Exception as e:
        logger.warning(f"[saml] process_response crash: {e}")
        return {"ok": False, "error": "saml_parse_crash",
                 "detail": str(e)[:300]}
    errs = auth.get_errors()
    if errs:
        return {
            "ok": False, "error": "saml_validation_failed",
            "detail": auth.get_last_error_reason() or ", ".join(errs),
            "errors": errs,
        }
    if not auth.is_authenticated():
        return {"ok": False, "error": "saml_not_authenticated"}
    attrs = auth.get_attributes() or {}
    name_id = auth.get_nameid()
    user = map_saml_attributes(attrs, name_id, cfg)
    if not user["email"] or "@" not in user["email"]:
        return {"ok": False, "error": "saml_missing_email"}
    return {"ok": True, "user": user,
             "attributes": attrs, "name_id": name_id}


async def upsert_saml_user(
    email: str,
    first_name: str,
    last_name: str,
    org_id: str,
    default_role: str = "member",
) -> dict:
    """Find-or-create the user in db.users and add them to the org.
    Returns {user_id, created, email, first_name, last_name, is_admin}."""
    if _db is None:
        raise RuntimeError("db_not_ready")
    email = email.lower().strip()
    existing = await _db.users.find_one({"email": email}, {"_id": 0})
    created = False
    if existing:
        user_id = existing.get("id") or existing.get("user_id")
        await _db.users.update_one(
            {"email": email},
            {"$set": {"updated_at": _now_iso(),
                       "last_saml_login_at": _now_iso(),
                       "first_name": first_name or existing.get("first_name", ""),
                       "last_name":  last_name  or existing.get("last_name",  "")}},
        )
    else:
        user_id = "saml_" + uuid.uuid4().hex
        await _db.users.insert_one({
            "id":            user_id,
            "email":         email,
            "first_name":    first_name,
            "last_name":     last_name,
            "active":        True,
            "is_admin":      False,
            "provisioned_via": "saml",
            "provisioned_org_id": org_id,
            "created_at":    _now_iso(),
            "updated_at":    _now_iso(),
            "last_saml_login_at": _now_iso(),
        })
        created = True
    # Ensure org membership
    from services.organizations import add_member
    await add_member(org_id, user_id, role=default_role,
                      invited_by="saml_sso")
    row = await _db.users.find_one({"email": email}, {"_id": 0}) or {}
    return {
        "user_id":    user_id,
        "created":    created,
        "email":      email,
        "first_name": row.get("first_name", first_name),
        "last_name":  row.get("last_name",  last_name),
        "is_admin":   bool(row.get("is_admin", False)),
    }
