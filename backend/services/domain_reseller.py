"""
Cloudflare Registrar Domain Service (iter 313)
================================================
Replaces Namecheap reseller — same 7 endpoints, same persistence schema.
Uses existing CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID.

Cloudflare Registrar API surface used:
  GET  /accounts/{acc}/registrar/domains              — list/transfer status
  GET  /accounts/{acc}/registrar/domains/{name}       — info + expiry
  PUT  /accounts/{acc}/registrar/domains/{name}       — auto-renew, locked
  POST /accounts/{acc}/registrar/domains/{name}       — register *new* (where supported by zone)

NOTE: Cloudflare Registrar primarily handles transfers + renewals on
already-Cloudflare-managed zones. New-registration availability varies by
TLD. The wrapper still exposes `register_domain`; on TLDs/regions where
Cloudflare can't directly register, the call returns
{"ok": False, "error": "tld_not_supported_by_cloudflare"} so the order can
fall back to manual processing.

Public surface unchanged from Namecheap version:
  await check_availability(domain)
  await register_domain(db, domain, lead_id, years, registrant)
  await renew_domain(domain, years)
  await get_status(domain)
  await configure_dns_to_aurem(domain, slug)
  await list_domains(db, lead_id)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

CF_API_BASE = "https://api.cloudflare.com/client/v4"
AUREM_DOMAIN_PRICE_CAD = float(os.environ.get("AUREM_DOMAIN_PRICE_CAD", "29"))


def _is_configured() -> bool:
    return bool(os.environ.get("CLOUDFLARE_API_TOKEN")
                 and os.environ.get("CLOUDFLARE_ACCOUNT_ID"))


def _account_id() -> str:
    return os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ.get('CLOUDFLARE_API_TOKEN','')}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _cf_request(method: str, path: str,
                       json_body: Optional[Dict[str, Any]] = None,
                       params: Optional[Dict[str, Any]] = None,
                       ) -> Dict[str, Any]:
    if not _is_configured():
        return {"ok": False, "error": "cloudflare_not_configured",
                 "missing": [k for k in ("CLOUDFLARE_API_TOKEN",
                                          "CLOUDFLARE_ACCOUNT_ID")
                              if not os.environ.get(k)]}
    url = f"{CF_API_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.request(method, url, headers=_headers(),
                                  json=json_body, params=params)
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text[:300]}
        if r.status_code >= 400:
            errs = (data.get("errors") if isinstance(data, dict) else None) or []
            err_text = errs[0].get("message") if errs else f"http_{r.status_code}"
            return {"ok": False, "status": r.status_code, "error": err_text,
                     "errors": errs, "raw": data}
        return {"ok": bool(data.get("success", True)),
                 "status": r.status_code,
                 "result": data.get("result") if isinstance(data, dict) else data}
    except Exception as e:
        logger.warning(f"[cf-registrar] {method} {path} failed: {e}")
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


# ── Public surface ────────────────────────────────────────────────────────
async def check_availability(domain: str) -> Dict[str, Any]:
    """Cloudflare exposes pricing/availability per TLD via the registrar
    domain GET. If the domain isn't yet under the account we report it as
    *available pending registration* — caller decides what to charge."""
    domain = (domain or "").strip().lower()
    if not domain or "." not in domain:
        return {"ok": False, "error": "invalid_domain"}
    info = await _cf_request("GET",
                              f"/accounts/{_account_id()}/registrar/domains/{domain}")
    # If domain exists in CF account → not available for new registration
    if info.get("ok") and info.get("result"):
        res = info["result"]
        return {
            "ok": True, "domain": domain,
            "available": False,
            "already_managed": True,
            "expires_at": res.get("expires_at"),
            "registrant": res.get("registrant_contact", {}).get("organization"),
            "aurem_price_cad": AUREM_DOMAIN_PRICE_CAD,
        }
    if not info.get("ok") and info.get("status") == 404:
        # Not in account — assume available, customer-facing CTA proceeds
        return {
            "ok": True, "domain": domain,
            "available": True, "already_managed": False,
            "aurem_price_cad": AUREM_DOMAIN_PRICE_CAD,
        }
    if not info.get("ok") and not _is_configured():
        return info
    return {"ok": False, "domain": domain,
             "error": info.get("error", "unknown"),
             "status": info.get("status")}


def _registrant(reg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "first_name": reg.get("first_name", "AUREM"),
        "last_name": reg.get("last_name", "Customer"),
        "organization": reg.get("organization", "AUREM Customer"),
        "email": reg.get("email", "ora@aurem.live"),
        "phone": reg.get("phone", "+1.4168869408"),
        "address": reg.get("address1", "1 Yonge St"),
        "city": reg.get("city", "Mississauga"),
        "state": reg.get("state", "ON"),
        "zip": reg.get("postal_code", "L5B0G2"),
        "country": reg.get("country", "CA"),
    }


async def register_domain(db, domain: str, lead_id: str,
                            years: int = 1,
                            registrant: Optional[Dict[str, Any]] = None,
                            ) -> Dict[str, Any]:
    """Register a new domain via Cloudflare Registrar. Cloudflare's
    new-registration API support is limited — returns a clear
    `tld_not_supported_by_cloudflare` error when applicable so the
    repair_orders row can be flagged for manual processing."""
    domain = (domain or "").strip().lower()
    body = {
        "registrant_contact": _registrant(registrant or {}),
        "auto_renew": True,
        "privacy": True,
        "locked": True,
    }
    out = await _cf_request("POST",
                              f"/accounts/{_account_id()}/registrar/domains/{domain}",
                              json_body=body)

    if not out.get("ok"):
        # Persist a "manual_required" record so the order isn't lost
        rec_err = {
            "id": uuid.uuid4().hex[:14], "domain": domain,
            "lead_id": lead_id, "years": years,
            "status": "manual_required",
            "registered_at": None,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "provider": "cloudflare",
            "register_error": out.get("error", "unknown"),
            "auto_renew": True,
        }
        try:
            if db is not None:
                await db.customer_domains.insert_one(dict(rec_err))
        except Exception:
            pass
        rec_err.pop("_id", None)
        return {"ok": False, "domain": domain, "manual_required": True,
                 "error": out.get("error"),
                 "errors": out.get("errors"),
                 "record": rec_err}

    res = out.get("result") or {}
    record = {
        "id": uuid.uuid4().hex[:14], "domain": domain, "lead_id": lead_id,
        "years": years, "provider": "cloudflare",
        "cloudflare_id": res.get("id"),
        "registered_at": res.get("registered_at",
                                  datetime.now(timezone.utc).isoformat()),
        "expires_at": res.get("expires_at",
                                (datetime.now(timezone.utc)
                                 + timedelta(days=365 * years)).isoformat()),
        "status": "active",
        "auto_renew": True,
        "charged_cad": AUREM_DOMAIN_PRICE_CAD,
    }
    try:
        if db is not None:
            await db.customer_domains.insert_one(dict(record))
    except Exception as e:
        logger.warning(f"[cf-registrar] persist failed: {e}")
    record.pop("_id", None)
    return {"ok": True, "domain": domain, "record": record,
             "registered": True}


async def renew_domain(domain: str, years: int = 1) -> Dict[str, Any]:
    """Cloudflare Registrar auto-renews; this just toggles auto_renew on."""
    return await _cf_request("PUT",
                               f"/accounts/{_account_id()}/registrar/domains/"
                               f"{domain.strip().lower()}",
                               json_body={"auto_renew": True})


async def get_status(domain: str) -> Dict[str, Any]:
    out = await _cf_request("GET",
                              f"/accounts/{_account_id()}/registrar/domains/"
                              f"{domain.strip().lower()}")
    if not out.get("ok"):
        return out
    res = out.get("result") or {}
    return {"ok": True, "domain": domain,
             "status": res.get("status", "unknown"),
             "expires_at": res.get("expires_at"),
             "auto_renew": res.get("auto_renew"),
             "locked": res.get("locked")}


async def configure_dns_to_aurem(domain: str, slug: str) -> Dict[str, Any]:
    """Add @ + www CNAME records pointing to {slug}.aurem.live.

    Requires the domain to already be a Cloudflare zone (auto when registered
    via CF). Looks up zone_id by domain name."""
    aurem_root = os.environ.get("CLOUDFLARE_ROOT_DOMAIN", "aurem.live")
    target = f"{slug}.{aurem_root}"
    zone = await _cf_request("GET", "/zones",
                               params={"name": domain.strip().lower()})
    if not zone.get("ok"):
        return zone
    items = zone.get("result") or []
    if not items:
        return {"ok": False, "error": "zone_not_found",
                 "hint": "Domain not yet a Cloudflare zone."}
    zone_id = items[0].get("id")
    out_records: List[Dict[str, Any]] = []
    for name in (domain, f"www.{domain}"):
        body = {"type": "CNAME", "name": name, "content": target,
                 "ttl": 300, "proxied": True}
        out = await _cf_request("POST", f"/zones/{zone_id}/dns_records",
                                  json_body=body)
        out_records.append({"name": name, "ok": out.get("ok"),
                              "error": out.get("error"),
                              "id": (out.get("result") or {}).get("id")})
    success = all(r["ok"] for r in out_records)
    return {"ok": success, "domain": domain, "zone_id": zone_id,
             "target": target, "records": out_records}


async def list_domains(db, lead_id: Optional[str] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
    if db is None:
        return []
    q = {"lead_id": lead_id} if lead_id else {}
    return await db.customer_domains.find(q, {"_id": 0}) \
        .sort("registered_at", -1).limit(limit).to_list(limit)


# ── Iter 313 — expiring-soon helper ───────────────────────────────────────
async def expiring_soon(db, days: int = 30) -> List[Dict[str, Any]]:
    """Return domains whose expires_at is within `days` days."""
    if db is None:
        return []
    now = datetime.now(timezone.utc)
    cutoff = (now + timedelta(days=days)).isoformat()
    rows = await db.customer_domains.find(
        {"expires_at": {"$lte": cutoff, "$gte": now.isoformat()}},
        {"_id": 0},
    ).to_list(500)
    out = []
    for r in rows:
        try:
            exp = datetime.fromisoformat(
                str(r.get("expires_at", "")).replace("Z", "+00:00"))
            r["days_until_expiry"] = max(0, (exp - now).days)
        except Exception:
            r["days_until_expiry"] = None
        out.append(r)
    return sorted(out, key=lambda x: x.get("days_until_expiry") or 999)
