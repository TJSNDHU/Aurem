"""
routers/saml_router.py — iter 332b Batch B (Step 2)

Admin surface for SAML SSO config + public discovery endpoint.

Endpoints:
  GET    /api/saml/{org_id}/config          — read config (org member)
  PUT    /api/saml/{org_id}/config          — write config (owner/admin)
  DELETE /api/saml/{org_id}/config          — disable + delete
  GET    /api/saml/{org_id}/metadata        — SP metadata XML (PUBLIC)
  POST   /api/saml/discover                  — find SSO config by email
  POST   /api/saml/{org_id}/acs              — IdP posts SAML response (stub)
  GET    /api/saml/{org_id}/login            — initiate SP-init SSO (stub)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException, Request, Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/saml", tags=["saml-sso"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    try:
        from services.saml_sso import set_db as _ssml
        _ssml(database)
    except Exception as e:
        logger.warning(f"[saml] wiring failed: {e}")


async def _require_user(request: Request) -> dict:
    try:
        from utils.auth import get_current_user
        user = await get_current_user(request)
    except Exception:
        user = None
    if not user or not user.get("id"):
        raise HTTPException(401, "auth_required")
    return user


class SamlConfigBody(BaseModel):
    idp_provider:   str = Field("generic", max_length=20)
    idp_entity_id:  str = Field("", max_length=400)
    idp_sso_url:    str = Field("", max_length=400)
    idp_cert:       str = Field("", max_length=8000)
    attribute_map:  Optional[dict] = None
    default_role:   str = Field("member", max_length=20)
    status:         str = Field("pending", max_length=20)


class DiscoverBody(BaseModel):
    email: str = Field(..., max_length=160)


@router.get("/{org_id}/config")
async def get_config(org_id: str, request: Request) -> dict[str, Any]:
    user = await _require_user(request)
    from services.organizations import get_user_role
    from services.saml_sso import get_saml_config
    role = await get_user_role(org_id, user["id"])
    if not role:
        raise HTTPException(403, "not_a_member")
    cfg = await get_saml_config(org_id)
    return {"ok": True, "config": cfg, "configured": bool(cfg)}


@router.put("/{org_id}/config")
async def put_config(org_id: str, body: SamlConfigBody,
                       request: Request) -> dict[str, Any]:
    user = await _require_user(request)
    from services.organizations import get_user_role
    from services.saml_sso import upsert_saml_config
    role = await get_user_role(org_id, user["id"])
    if role not in ("owner", "admin"):
        raise HTTPException(403, "permission_denied")
    r = await upsert_saml_config(org_id, body.model_dump())
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "saml_config_failed"))
    # Audit
    try:
        from services.unified_audit import write_event
        await write_event(
            action="saml_config_updated", resource=f"org:{org_id}",
            result="ok", user_id=user["id"], org_id=org_id,
            source_collection="saml_configs",
            extra={"provider": r["config"]["idp_provider"],
                    "status": r["config"]["status"]},
        )
    except Exception:
        pass
    return r


@router.delete("/{org_id}/config")
async def delete_config(org_id: str, request: Request) -> dict[str, Any]:
    user = await _require_user(request)
    from services.organizations import get_user_role
    from services.saml_sso import delete_saml_config
    role = await get_user_role(org_id, user["id"])
    if role not in ("owner", "admin"):
        raise HTTPException(403, "permission_denied")
    r = await delete_saml_config(org_id)
    return r


@router.get("/{org_id}/metadata")
async def sp_metadata(org_id: str) -> Response:
    """Public — IdP downloads this to configure us as a Service Provider.
    iter 332b D-2: now embeds our SP X.509 cert so the IdP can verify
    our signed AuthnRequests."""
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    org = await _db.organizations.find_one(
        {"org_id": org_id}, {"_id": 0, "slug": 1, "org_id": 1},
    )
    if not org:
        raise HTTPException(404, "org_not_found")
    from services.saml_sp_keys import get_sp_keypair, cert_for_metadata_xml
    kp = await get_sp_keypair()
    cert_b64 = cert_for_metadata_xml(kp["cert"])
    site = (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")
    xml = f"""<?xml version="1.0"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
                   entityID="{site}/saml/{org['slug']}/metadata">
  <SPSSODescriptor AuthnRequestsSigned="true"
                    WantAssertionsSigned="true"
                    protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <KeyDescriptor use="signing">
      <KeyInfo xmlns="http://www.w3.org/2000/09/xmldsig#">
        <X509Data><X509Certificate>{cert_b64}</X509Certificate></X509Data>
      </KeyInfo>
    </KeyDescriptor>
    <NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</NameIDFormat>
    <AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                               Location="{site}/api/saml/{org_id}/acs"
                               index="0" isDefault="true"/>
  </SPSSODescriptor>
</EntityDescriptor>
"""
    return Response(content=xml, media_type="application/xml")


@router.post("/discover")
async def discover_endpoint(body: DiscoverBody) -> dict[str, Any]:
    """Public — front-end calls this with the user's email. If their
    domain has an active SAML config, returns the SSO redirect URL.
    Otherwise returns ok=true, sso=false (so the regular password form
    keeps working)."""
    from services.saml_sso import discover_org_by_email
    found = await discover_org_by_email(body.email)
    if not found:
        return {"ok": True, "sso": False}
    site = (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")
    return {
        "ok":      True,
        "sso":     True,
        "org_id":  found["org"]["org_id"],
        "org_name": found["org"]["name"],
        "sso_url": f"{site}/api/saml/{found['org']['org_id']}/login",
        "provider": found["saml"]["idp_provider"],
    }


@router.get("/{org_id}/login")
async def saml_login_init(org_id: str, request: Request) -> dict[str, Any]:
    """SP-initiated SSO start. iter 332b D-2: builds a properly signed
    AuthnRequest via python3-saml using our self-generated SP keypair.
    Returns {ok, redirect_to} where redirect_to is the full IdP URL
    with the SAMLRequest + RelayState query parameters."""
    from services.saml_sso import (
        get_saml_config, build_saml_settings, prepare_fastapi_request,
    )
    from services.saml_sp_keys import get_sp_keypair
    cfg = await get_saml_config(org_id)
    if not cfg or cfg.get("status") != "active":
        raise HTTPException(404, "sso_not_configured")
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    org = await _db.organizations.find_one(
        {"org_id": org_id}, {"_id": 0, "slug": 1, "org_id": 1},
    )
    if not org:
        raise HTTPException(404, "org_not_found")
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
    except Exception:
        # Fallback: return the unsigned IdP SSO URL.
        return {"ok": True, "redirect_to": cfg["idp_sso_url"],
                 "signed": False,
                 "note": "python3-saml not available — returning raw IdP URL"}

    kp = await get_sp_keypair()
    settings = build_saml_settings(org, cfg, sp_cert=kp["cert"], sp_key=kp["key"])
    req_data = prepare_fastapi_request(request)
    try:
        auth = OneLogin_Saml2_Auth(req_data, old_settings=settings)
        site = (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")
        relay = f"{site}/saml/landing"
        redirect_to = auth.login(return_to=relay)
        return {"ok": True, "redirect_to": redirect_to,
                 "signed": True,
                 "relay_state": relay}
    except Exception as e:
        logger.warning(f"[saml] login_init failed: {e}")
        # Graceful fallback so a misconfigured IdP doesn't 500 the UI.
        return {"ok": True, "redirect_to": cfg["idp_sso_url"],
                 "signed": False,
                 "note": f"AuthnRequest build failed: {str(e)[:200]}"}


@router.post("/{org_id}/acs")
async def saml_acs_endpoint(
    org_id: str,
    request: Request,
    SAMLResponse: str = Form(...),
    RelayState: Optional[str] = Form(default=None),
) -> Response:
    """IdP-initiated callback. python3-saml validates the response,
    we mint an AUREM JWT and 302 to /admin/mission-control with the
    token in the URL hash so the React app can pluck it client-side
    (avoids leaking the JWT through server logs)."""
    from fastapi.responses import RedirectResponse
    from services.saml_sso import (
        get_saml_config, parse_acs_response, record_saml_login,
        upsert_saml_user,
    )
    from utils.auth import create_token

    cfg = await get_saml_config(org_id)
    if not cfg:
        raise HTTPException(404, "sso_not_configured")
    if cfg.get("status") != "active":
        raise HTTPException(403, "sso_not_active")
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    org = await _db.organizations.find_one(
        {"org_id": org_id}, {"_id": 0, "slug": 1, "name": 1, "org_id": 1},
    )
    if not org:
        raise HTTPException(404, "org_not_found")

    parsed = await parse_acs_response(request, SAMLResponse, RelayState, org, cfg)
    if not parsed.get("ok"):
        await record_saml_login(
            org_id, email="(unknown)", name_id="", success=False,
            extra={"error": parsed.get("error"),
                    "detail":  parsed.get("detail", "")[:300]},
        )
        raise HTTPException(401, parsed.get("error", "saml_failed"))

    u = parsed["user"]
    upserted = await upsert_saml_user(
        email=u["email"], first_name=u["first_name"],
        last_name=u["last_name"], org_id=org_id,
        default_role=cfg.get("default_role", "member"),
    )

    # Mint the AUREM JWT.
    jwt_token = create_token(
        upserted["user_id"], upserted["is_admin"], email=upserted["email"],
    )

    await record_saml_login(
        org_id, email=upserted["email"], name_id=u["name_id"],
        success=True,
        extra={"user_id": upserted["user_id"],
                "created": upserted["created"]},
    )
    try:
        from services.unified_audit import write_event
        await write_event(
            action="saml_sso_login", resource=f"user:{upserted['user_id']}",
            result="ok", user_id=upserted["user_id"], org_id=org_id,
            source_collection="saml_logins",
            extra={"email": upserted["email"],
                    "created_user": upserted["created"]},
        )
    except Exception:
        pass

    # The React app reads window.location.hash on mount and stores the
    # token in the appropriate slot. Hash (not query) so the token is
    # never logged in any nginx access log.
    site = (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")
    target = RelayState or f"{site}/saml/landing"
    sep = "&" if "#" in target else "#"
    return RedirectResponse(
        url=f"{target}{sep}t={jwt_token}",
        status_code=303,
    )
