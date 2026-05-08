"""
Cloudflare Worker provisioning for {slug}.aurem.live → R2 (iter 299)
====================================================================
Single Worker that:
  • Reads Host header → extracts slug
  • Fetches `{slug}/index.html` from R2 binding `SITES_BUCKET`
  • Returns HTML or 404

Deployment via Cloudflare API:
  PUT /accounts/{acc}/workers/scripts/{name}            — upload script
  POST /zones/{zone}/workers/routes                     — bind *.aurem.live to it
  R2 binding configured via metadata.bindings on upload

Public API:
  await deploy_worker(name="awb-router") -> {ok, script_name, route_id, ...}
  await delete_worker(name)              -> {ok}
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

CF_API = "https://api.cloudflare.com/client/v4"

WORKER_SCRIPT = r"""
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const host = (request.headers.get('host') || '').toLowerCase();
    const root = (env.ROOT_DOMAIN || 'aurem.live').toLowerCase();

    // ── img.aurem.live → public R2 proxy (path = key) ─────────────────
    // Used for browser-screenshots, AWB site preview shots, and any
    // other public asset that wants a clean non-presigned URL.
    if (host === 'img.' + root) {
      const key = url.pathname.replace(/^\/+/, '');
      if (!key) {
        return new Response('img.aurem.live: missing key', { status: 400 });
      }
      try {
        const obj = await env.SITES_BUCKET.get(key);
        if (!obj) {
          return new Response('Asset not found: ' + key, { status: 404 });
        }
        const headers = new Headers();
        obj.writeHttpMetadata(headers);
        // Long cache for assets — they're immutable per key.
        headers.set('Cache-Control', 'public, max-age=86400, immutable');
        headers.set('Access-Control-Allow-Origin', '*');
        headers.set('X-Served-By', 'aurem-img-proxy');
        return new Response(obj.body, { headers });
      } catch (e) {
        return new Response('R2 error: ' + e.message, { status: 502 });
      }
    }

    // ── Default: {slug}.aurem.live → /{slug}/index.html ───────────────
    let slug = '';
    if (host.endsWith('.' + root)) {
      slug = host.slice(0, -1 - root.length);
    }
    if (!slug || slug === 'www') {
      return new Response('Not found', { status: 404 });
    }
    const key = `${slug}/index.html`;
    try {
      const obj = await env.SITES_BUCKET.get(key);
      if (!obj) {
        return new Response('Site not found', { status: 404 });
      }
      const headers = new Headers();
      obj.writeHttpMetadata(headers);
      headers.set('Cache-Control', 'public, max-age=300');
      headers.set('X-Robots-Tag', 'index, follow');
      headers.set('Content-Type', 'text/html; charset=utf-8');
      return new Response(obj.body, { headers });
    } catch (e) {
      return new Response('R2 error: ' + e.message, { status: 502 });
    }
  }
}
"""


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


async def _cf(method: str, path: str, **kwargs) -> Dict[str, Any]:
    # Workers operations need a token with Workers Scripts:Edit + Workers Routes:Edit
    token = _env("CLOUDFLARE_WORKERS_TOKEN") or _env("CLOUDFLARE_API_TOKEN")
    if not token:
        return {"success": False, "errors": [{"message": "no cloudflare workers token"}]}
    headers = kwargs.pop("headers", {}) or {}
    headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as cli:
            r = await cli.request(method, f"{CF_API}{path}", headers=headers, **kwargs)
            try:
                return r.json()
            except Exception:
                return {"success": False, "errors": [{"message": f"status {r.status_code}"}]}
    except Exception as e:
        return {"success": False, "errors": [{"message": str(e)[:200]}]}


async def deploy_worker(name: str = "awb-router",
                         bucket: str = "aurem-sites") -> Dict[str, Any]:
    """Upload the worker script + bind R2 + create *.aurem.live route."""
    acc = _env("CLOUDFLARE_ACCOUNT_ID")
    zone = _env("CLOUDFLARE_ZONE_ID")
    root = _env("CLOUDFLARE_ROOT_DOMAIN") or "aurem.live"
    if not acc or not zone:
        return {"ok": False, "error": "missing CF account/zone env"}

    metadata = {
        "main_module": "worker.mjs",
        "compatibility_date": "2025-01-01",
        "bindings": [
            {"type": "r2_bucket", "name": "SITES_BUCKET", "bucket_name": bucket},
            {"type": "plain_text", "name": "ROOT_DOMAIN", "text": root},
        ],
    }

    # multipart upload (CF Workers API)
    files = [
        ("metadata", (None, json.dumps(metadata), "application/json")),
        ("worker.mjs", ("worker.mjs", WORKER_SCRIPT, "application/javascript+module")),
    ]
    upload = await _cf("PUT", f"/accounts/{acc}/workers/scripts/{name}", files=files)
    if not upload.get("success"):
        return {"ok": False, "step": "upload",
                "error": (upload.get("errors") or [{}])[0].get("message", "unknown"),
                "raw": upload}

    # Create route *.{root_domain}/* → worker
    pattern = f"*.{root}/*"
    route_resp = await _cf(
        "POST", f"/zones/{zone}/workers/routes",
        json={"pattern": pattern, "script": name},
    )
    # If route already exists CF returns 10027 — fine
    route_id = None
    if route_resp.get("success"):
        route_id = (route_resp.get("result") or {}).get("id")
    else:
        existing = await _cf("GET", f"/zones/{zone}/workers/routes")
        for r in (existing.get("result") or []):
            if r.get("pattern") == pattern and r.get("script") == name:
                route_id = r.get("id")
                break

    return {
        "ok": True, "script_name": name, "pattern": pattern,
        "route_id": route_id, "bucket": bucket, "root_domain": root,
    }


async def delete_worker(name: str = "awb-router") -> Dict[str, Any]:
    acc = _env("CLOUDFLARE_ACCOUNT_ID")
    if not acc:
        return {"ok": False, "error": "no acc"}
    resp = await _cf("DELETE", f"/accounts/{acc}/workers/scripts/{name}")
    return {"ok": bool(resp.get("success")), "raw": resp}


async def list_routes() -> List[Dict[str, Any]]:
    zone = _env("CLOUDFLARE_ZONE_ID")
    if not zone:
        return []
    resp = await _cf("GET", f"/zones/{zone}/workers/routes")
    return resp.get("result") or []
