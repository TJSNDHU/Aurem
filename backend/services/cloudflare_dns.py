"""
Cloudflare DNS helper (iter 298)
================================
Thin async wrapper around Cloudflare API v4 for AWB site publishing.

Used by auto_website_builder.py to point {slug}.aurem.live → aurem.live
(same origin) so each generated site gets a pretty subdomain.

Public API:
  await cf_create_cname(slug, target=None) -> {ok, record_id, name, ...}
  await cf_delete_record(record_id)        -> {ok}
  await cf_list_records(prefix=None)       -> [{id, name, type, content, ...}]
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

CF_API = "https://api.cloudflare.com/client/v4"
SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _env(name: str) -> str:
    v = os.environ.get(name, "")
    return v.strip()


def safe_slug(text: str, max_len: int = 40) -> str:
    s = (text or "").lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = SLUG_RE.sub("", s).strip("-")
    return (s or "site")[:max_len]


async def _cf_request(method: str, path: str, json_body: Optional[Dict] = None) -> Dict[str, Any]:
    token = _env("CLOUDFLARE_API_TOKEN")
    if not token:
        return {"success": False, "errors": [{"message": "CLOUDFLARE_API_TOKEN missing"}]}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{CF_API}{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.request(method, url, headers=headers, json=json_body)
            try:
                return r.json()
            except Exception:
                return {"success": False, "errors": [{"message": f"non-json {r.status_code}"}]}
    except Exception as e:
        return {"success": False, "errors": [{"message": str(e)[:200]}]}


async def cf_create_cname(slug: str, target: Optional[str] = None,
                          proxied: bool = True) -> Dict[str, Any]:
    """Create {slug}.{root_domain} CNAME → target (default = root_domain)."""
    zone = _env("CLOUDFLARE_ZONE_ID")
    root = _env("CLOUDFLARE_ROOT_DOMAIN")
    if not zone or not root:
        return {"ok": False, "error": "zone/root not configured"}

    fqdn = f"{slug}.{root}"
    cname_target = target or root

    # Idempotent: if record already exists, return it
    existing = await cf_list_records(prefix=slug)
    for rec in existing:
        if rec.get("name") == fqdn:
            return {"ok": True, "record_id": rec.get("id"), "name": fqdn,
                    "url": f"https://{fqdn}", "existed": True}

    body = {
        "type": "CNAME",
        "name": slug,                 # CF auto-appends zone domain
        "content": cname_target,
        "ttl": 1,                     # auto
        "proxied": bool(proxied),
        "comment": "AUREM auto-built site",
    }
    resp = await _cf_request("POST", f"/zones/{zone}/dns_records", body)
    if not resp.get("success"):
        return {"ok": False, "error": (resp.get("errors") or [{}])[0].get("message", "unknown")}
    res = resp.get("result") or {}
    return {"ok": True, "record_id": res.get("id"), "name": res.get("name"),
            "url": f"https://{fqdn}", "existed": False}


async def cf_delete_record(record_id: str) -> Dict[str, Any]:
    zone = _env("CLOUDFLARE_ZONE_ID")
    if not zone or not record_id:
        return {"ok": False, "error": "missing zone or record_id"}
    resp = await _cf_request("DELETE", f"/zones/{zone}/dns_records/{record_id}")
    return {"ok": bool(resp.get("success"))}


async def cf_list_records(prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    zone = _env("CLOUDFLARE_ZONE_ID")
    root = _env("CLOUDFLARE_ROOT_DOMAIN")
    if not zone:
        return []
    params = "?per_page=200&type=CNAME"
    if prefix and root:
        params += f"&name={prefix}.{root}"
    resp = await _cf_request("GET", f"/zones/{zone}/dns_records{params}")
    if not resp.get("success"):
        return []
    return resp.get("result") or []


def is_configured() -> bool:
    return bool(_env("CLOUDFLARE_API_TOKEN") and _env("CLOUDFLARE_ZONE_ID")
                and _env("CLOUDFLARE_ROOT_DOMAIN"))
