"""
Public AWB site server (iter 298)
=================================
Serves auto-built sites at:
  GET /sites/{slug}     — pretty path-based URL (no auth)
  GET /sites/site/{site_id} — direct lookup by site_id
  GET /robots.txt       — basic crawl rules

Also responds to {slug}.aurem.live host header (Cloudflare CNAME proxied).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, JSONResponse
from pydantic import BaseModel

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Public Sites"])

_db = None


def _is_safe_external_url(url: str) -> bool:
    """Bug-fix #161 (R19): SSRF guard for user-supplied URLs.
    Rejects non-http(s) schemes and private / link-local / loopback IPs."""
    try:
        from urllib.parse import urlparse
        import ipaddress
        import socket
    except Exception:
        return False
    if not url or not isinstance(url, str):
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    host = (p.hostname or "").strip().lower()
    if not host or host in ("localhost",):
        return False
    # Resolve and reject if any answer is private/loopback/link-local.
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        ip = info[4][0]
        try:
            ipo = ipaddress.ip_address(ip)
        except Exception:
            return False
        if (ipo.is_private or ipo.is_loopback or ipo.is_link_local
                or ipo.is_multicast or ipo.is_reserved or ipo.is_unspecified):
            return False
    return True


_SITE_NOT_FOUND_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Site is being built — AUREM</title>
<style>
  :root{--gold:#C9A227;--bg:#0A0A0B;--ink:#F2EDE4;--muted:#8A8279}
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
    font:16px/1.6 'DM Sans',system-ui,sans-serif;background:var(--bg);color:var(--ink);
    padding:24px}
  .wrap{max-width:560px;text-align:center}
  .logo{font:700 14px/1 'DM Mono',monospace;letter-spacing:.32em;color:var(--gold);
    text-transform:uppercase;margin-bottom:36px}
  h1{font:400 42px/1.15 'Cormorant Garamond',serif;margin:0 0 18px;color:var(--ink)}
  p{color:var(--muted);font-size:16px;margin:0 0 14px}
  .pulse{display:inline-block;width:10px;height:10px;border-radius:50%;
    background:var(--gold);margin-right:10px;vertical-align:middle;
    animation:pulse 1.6s ease-in-out infinite}
  @keyframes pulse{0%,100%{opacity:.35;transform:scale(.85)}50%{opacity:1;transform:scale(1.15)}}
  .cta{display:inline-block;margin-top:30px;padding:14px 28px;
    background:rgba(201,162,39,.1);color:var(--gold);text-decoration:none;
    border:1px solid rgba(201,162,39,.4);border-radius:6px;
    font:700 12px/1 'DM Mono',monospace;letter-spacing:.18em;text-transform:uppercase;
    transition:background .2s,border-color .2s;cursor:pointer}
  .cta:hover{background:rgba(201,162,39,.2);border-color:var(--gold)}
  .cta.ghost{background:transparent;margin-left:10px}
  .cta:disabled{opacity:.5;cursor:wait}
  .msg{display:none;color:var(--gold);margin-top:14px;font-size:13px;
    font-family:'DM Mono',monospace;letter-spacing:.05em}
  .foot{margin-top:40px;font:400 12px/1.4 'DM Mono',monospace;color:var(--muted);
    letter-spacing:.08em}
  .foot a{color:var(--gold);text-decoration:none}
</style></head>
<body>
  <div class="wrap" data-testid="awb-404-page">
    <div class="logo">AUREM</div>
    <h1><span class="pulse"></span>Your site is being built</h1>
    <p>This preview is not ready yet, or the link has expired. Our system is
       either still generating it, or an older slug was shared.</p>
    <p>Please check back in a few minutes — or reply to the email
       we sent you and we'll send a fresh link.</p>
    <a class="cta" href="https://aurem.live" data-testid="awb-404-home">Visit AUREM</a>
    <button class="cta ghost" id="rebuild-btn"
            onclick="requestRebuild()"
            data-testid="awb-404-rebuild">Request a Fresh Preview</button>
    <p class="msg" id="rebuild-msg" data-testid="awb-404-rebuild-msg">
       &#x2713; Request sent! We'll rebuild your site shortly.</p>
    <div class="foot">Need help? <a href="mailto:tj@aurem.live">tj@aurem.live</a></div>
  </div>
<script>
async function requestRebuild(){
  var btn = document.getElementById('rebuild-btn');
  var msg = document.getElementById('rebuild-msg');
  btn.disabled = true;
  try {
    var slug = window.location.pathname.split('/sites/').pop().split('/')[0];
    await fetch('/api/sites/' + encodeURIComponent(slug) + '/rebuild-request',
                {method:'POST'});
  } catch(e) { /* swallow */ }
  msg.style.display = 'block';
  btn.textContent = 'Requested';
}
</script>
</body></html>"""


def _site_not_found_response() -> HTMLResponse:
    return HTMLResponse(
        content=_SITE_NOT_FOUND_HTML,
        status_code=404,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is None:
        try:
            import server
            _db = getattr(server, "db", None)
        except Exception:
            pass
    return _db


def _inject_claim_block(html: Optional[str], claim_block: Optional[str]) -> Optional[str]:
    """Idempotently inject the claim-CTA banner right after <body>. If
    already present, return html untouched."""
    if not html or not claim_block:
        return html
    # Idempotency — skip if banner already injected
    if "data-aurem-claim-block" in html or "Claim This Website" in html:
        return html
    wrapped = f'<div data-aurem-claim-block>{claim_block}</div>'
    lower = html.lower()
    idx = lower.find("<body")
    if idx == -1:
        return wrapped + html
    end = html.find(">", idx)
    if end == -1:
        return wrapped + html
    return html[: end + 1] + wrapped + html[end + 1 :]


async def _fetch_html_by_slug(slug: str) -> Optional[str]:
    db = _get_db()
    if db is None or not slug:
        return None
    row = await db.auto_built_sites.find_one(
        {"slug": slug},
        {"_id": 0, "rendered_html": 1, "claim_block_html": 1},
    )
    if not row:
        return None
    return _inject_claim_block(row.get("rendered_html"), row.get("claim_block_html"))


async def _fetch_html_by_id(site_id: str) -> Optional[str]:
    db = _get_db()
    if db is None or not site_id:
        return None
    row = await db.auto_built_sites.find_one(
        {"site_id": site_id},
        {"_id": 0, "rendered_html": 1, "claim_block_html": 1},
    )
    if not row:
        return None
    return _inject_claim_block(row.get("rendered_html"), row.get("claim_block_html"))


@router.get("/sites/{slug}")
async def public_site_by_slug(slug: str, request: Request):
    html = await _fetch_html_by_slug(slug)
    if not html:
        logger.warning(f"[public_sites] 404 slug={slug!r} (no rendered_html)")
        return _site_not_found_response()
    # Increment public hit counter (best-effort)
    try:
        db = _get_db()
        if db is not None:
            await db.auto_built_sites.update_one(
                {"slug": slug}, {"$inc": {"public_hits": 1}},
            )
    except Exception:
        pass
    return HTMLResponse(content=html, headers={
        "Cache-Control": "public, max-age=300",
        "X-Robots-Tag": "index, follow",
    })


@router.get("/sites/site/{site_id}")
async def public_site_by_id(site_id: str):
    html = await _fetch_html_by_id(site_id)
    if not html:
        logger.warning(f"[public_sites] 404 site_id={site_id!r} (no rendered_html)")
        return _site_not_found_response()
    return HTMLResponse(content=html)


# ─── Iter 305b — Rebuild request from 404 page ──────────────────────────────
_rebuild_ttl_ensured = False


async def _ensure_rebuild_ttl_index(db) -> None:
    """Idempotent TTL index (90 days) on rebuild_requests.ts. Safe no-op
    if already created."""
    global _rebuild_ttl_ensured
    if _rebuild_ttl_ensured or db is None:
        return
    try:
        await db.rebuild_requests.create_index(
            "ts", expireAfterSeconds=60 * 60 * 24 * 90,
            name="rebuild_requests_ttl_90d",
        )
        _rebuild_ttl_ensured = True
    except Exception as e:
        logger.debug(f"[public_sites] rebuild TTL index ensure skipped: {e}")


async def _telegram_rebuild_ping(slug: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        return
    text = (
        "🔥 Abandoned link clicked!\n"
        f"Slug: {slug}\n"
        "Someone wants their site rebuilt.\n"
        "Check campaign_leads for this slug."
    )
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text},
            )
    except Exception as e:
        logger.warning(f"[public_sites] telegram rebuild ping failed: {e}")


@router.post("/sites/{slug}/rebuild-request")
async def rebuild_request(slug: str, request: Request):
    """Customer clicked 'Request Fresh Preview' on the 404 page.

    Logs abandoned-link interest, fires a Telegram ping to the founder,
    and always returns 200. Never raises — by design, so a flaky DB or
    network never blocks the customer-facing ack.
    """
    safe_slug = (slug or "")[:200]
    ip = request.client.host if request.client else None
    ua = (request.headers.get("user-agent") or "")[:300]

    try:
        db = _get_db()
        if db is not None:
            await _ensure_rebuild_ttl_index(db)
            await db.rebuild_requests.insert_one({
                "slug": safe_slug,
                "ts": datetime.now(timezone.utc),
                "ip": ip,
                "user_agent": ua,
            })
    except Exception as e:
        logger.warning(f"[public_sites] rebuild_request DB log failed: {e}")

    try:
        await _telegram_rebuild_ping(safe_slug)