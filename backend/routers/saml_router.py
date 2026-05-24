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

from fastapi import APIRouter, HTTPException, Request, Response
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
    """Public — IdP downloads this to configure us as a Service Provider."""
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    org = await _db.organizations.find_one(
        {"org_id": org_id}, {"_id": 0, "slug": 1},
    )
    if not org:
        raise HTTPException(404, "org_not_found")
    site = (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")
    xml = f"""<?xml version="1.0"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
                   entityID="{site}/saml/{org['slug']}/metadata">
  <SPSSODescriptor AuthnRequestsSigned="false"
                    WantAssertionsSigned="true"
                    protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
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
async def saml_login_init(org_id: str) -> dict[str, Any]:
    """STUB — full SP-init AuthnRequest XML generation lands in the
    next slice once python3-saml or onelogin-saml-py is installed.
    Today this returns the IdP SSO URL so the UI can do a manual
    redirect (which is how Google Workspace + Okta tier-1 setups work
    out of the box)."""
    from services.saml_sso import get_saml_config
    cfg = await get_saml_config(org_id)
    if not cfg or cfg.get("status") != "active":
        raise HTTPException(404, "sso_not_configured")
    return {"ok": True, "redirect_to": cfg["idp_sso_url"],
             "note": "Manual SP-init (proper signed AuthnRequest will replace this soon)"}


@router.post("/{org_id}/acs")
async def saml_acs_endpoint(org_id: str, request: Request) -> dict[str, Any]:
    """STUB — receives the IdP's SAML response.

    The full implementation validates the response signature, decrypts
    the assertion, checks audience + recipient, extracts the email + name,
    upserts the user in db.users, adds them to the org as a member, mints
    a JWT, and 302s to /admin/mission-control.

    For now this stub records the attempt to db.saml_logins so we know
    the IdP is wired correctly, and returns a 501 with a clear message."""
    from services.saml_sso import get_saml_config, record_saml_login
    cfg = await get_saml_config(org_id)
    if not cfg:
        raise HTTPException(404, "sso_not_configured")
    body = (await request.body())[:6000]   # Cap to avoid log bloat
    await record_saml_login(
        org_id, email="(unknown — pre-parse)", name_id="",
        success=False,
        extra={"raw_bytes": len(body),
                "user_agent": request.headers.get("user-agent", "")[:200]},
    )
    raise HTTPException(
        501,
        "SAML response parsing not yet wired. Config is saved — finish setup once python3-saml is installed.",
    )
