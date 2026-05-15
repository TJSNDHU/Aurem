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
    except Exception as e:
        logger.warning(f"[public_sites] rebuild_request telegram failed: {e}")

    return JSONResponse(content={"status": "requested"})


@router.get("/sites-robots.txt", include_in_schema=False)
async def public_sites_robots():
    root = os.environ.get("CLOUDFLARE_ROOT_DOMAIN", "aurem.live")
    return PlainTextResponse(
        f"User-agent: *\nAllow: /\nSitemap: https://{root}/sites-sitemap.xml\n"
    )


# ─── Theme thumbnail proxy (R2) ─────────────────────────────────────────────
@router.get("/sites/_thumb/{thumb_id}")
async def public_thumb(thumb_id: str):
    db = _get_db()
    if db is None:
        raise HTTPException(404, "no")
    from services.awb_themes import get_thumb_bytes
    data = await get_thumb_bytes(db, thumb_id)
    if not data:
        raise HTTPException(404, "thumb not found")
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


# ─── Customer-facing Theme Picker (UNAUTH) ─────────────────────────────────
@router.get("/preview/{slug}/themes")
async def preview_themes(slug: str):
    """Return up to 4 theme candidates for the lead behind this slug."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB unavailable")
    site = await db.auto_built_sites.find_one(
        {"slug": slug}, {"_id": 0, "lead_id": 1, "business_name": 1, "niche": 1,
                          "theme_options": 1, "selected_template": 1},
    )
    if not site:
        raise HTTPException(404, "site not found")
    if site.get("theme_options"):
        themes = site["theme_options"]
        # Backfill SVG fallback for any cached entry missing a screenshot_url
        # (older cache from before the inline-SVG guarantee was added).
        from services.awb_themes import _svg_preview_data_url
        biz_for_fallback = (site.get("niche") or site.get("business_name") or "Preview")
        dirty = False
        for t in themes:
            if not t.get("screenshot_url"):
                t["screenshot_url"] = _svg_preview_data_url(
                    biz_for_fallback, t.get("style") or {},
                    title=t.get("name") or t.get("business_name"))
                t["screenshot_kind"] = "svg_inline"
                dirty = True
        if dirty:
            try:
                await db.auto_built_sites.update_one(
                    {"slug": slug}, {"$set": {"theme_options": themes}},
                )
            except Exception:
                pass
        return {"slug": slug, "business_name": site.get("business_name"),
                "selected_template_idx": site.get("selected_template", {}).get("idx"),
                "themes": themes}

    lead = await db.campaign_leads.find_one(
        {"lead_id": site.get("lead_id")}, {"_id": 0, "business_name": 1, "city": 1, "niche": 1, "category": 1},
    ) or {}
    site_niche = (site.get("niche") or "").strip().lower()
    if site_niche in ("", "service-business", "service business", "default"):
        site_niche = ""
    business_type = (site_niche or lead.get("niche") or lead.get("category")
                     or "service business")
    city = lead.get("city") or "Toronto"

    from services.awb_themes import discover_themes
    themes = await discover_themes(business_type=business_type, city=city, n=4)
    if themes:
        await db.auto_built_sites.update_one(
            {"slug": slug},
            {"$set": {"theme_options": themes,
                      "theme_options_at": __import__("datetime").datetime.utcnow().isoformat()}},
        )
    return {"slug": slug, "business_name": site.get("business_name"), "themes": themes}


class ThemeSelectPayload(BaseModel):
    template_idx: int


class CustomUrlPayload(BaseModel):
    url: str


@router.post("/preview/{slug}/custom-url")
async def preview_custom_url(slug: str, body: CustomUrlPayload, request: Request):
    """Customer submits a reference URL → scrape style → rebuild site.

    Bug-fix #161 (R19): admin-gated + SSRF-blocked. Previously zero-auth
    and unfiltered URL → attacker could submit
    `http://169.254.169.254/latest/meta-data/...` and exfiltrate AWS
    instance creds through the screenshot/style scraping pipeline.
    """
    from utils.admin_guard import verify_admin
    verify_admin(request.headers.get("Authorization", ""))

    target = (body.url or "").strip()
    if not _is_safe_external_url(target):
        raise HTTPException(400, "URL blocked (internal / non-http(s) target)")

    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB unavailable")
    site = await db.auto_built_sites.find_one(
        {"slug": slug}, {"_id": 0, "lead_id": 1, "site_id": 1},
    )
    if not site:
        raise HTTPException(404, "site not found")

    from services.awb_themes import scrape_one_url
    theme = await scrape_one_url(target)
    if not theme or not theme.get("style"):
        raise HTTPException(422, "could not scrape that URL — try another")

    style = theme["style"]
    custom_template = {
        "idx": -1, "src_url": theme.get("url"),
        "screenshot_url": theme.get("screenshot_url"),
        "style": style, "source": "user-supplied",
    }
    await db.campaign_leads.update_one(
        {"lead_id": site["lead_id"]},
        {"$set": {"selected_template": custom_template}},
    )
    await db.auto_built_sites.update_one(
        {"slug": slug},
        {"$set": {"selected_template": {"idx": -1, "src_url": theme.get("url")},
                  "style_hint": style}},
    )

    from services.auto_website_builder import build_site_for_lead
    res = await build_site_for_lead(db, site["lead_id"], style_hint=style)
    return {
        "ok": res.get("ok"),
        "scraped": {"url": theme.get("url"),
                    "screenshot_url": theme.get("screenshot_url"),
                    "style": style},
        "new_site": res,
    }


@router.post("/preview/{slug}/select-theme")
async def preview_select_theme(slug: str, body: ThemeSelectPayload, request: Request):
    """Customer picks a theme → rebuild site with that style_hint.

    Bug-fix #161 (R19): admin auth required. Previously zero-auth meant
    anyone who guessed a slug could trigger a full site rebuild.
    """
    from utils.admin_guard import verify_admin
    verify_admin(request.headers.get("Authorization", ""))

    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB unavailable")
    site = await db.auto_built_sites.find_one(
        {"slug": slug}, {"_id": 0, "lead_id": 1, "theme_options": 1, "site_id": 1},
    )
    if not site or not site.get("theme_options"):
        raise HTTPException(404, "no themes generated for this site yet")
    options = site["theme_options"]
    idx = body.template_idx
    if idx < 0 or idx >= len(options):
        raise HTTPException(400, f"template_idx out of range (0-{len(options)-1})")
    chosen = options[idx]
    style = chosen.get("style") or {}

    # Persist selection on lead + site
    await db.campaign_leads.update_one(
        {"lead_id": site["lead_id"]},
        {"$set": {"selected_template": {
            "idx": idx, "src_url": chosen.get("url"),
            "screenshot_url": chosen.get("screenshot_url"),
            "style": style,
        }}},
    )
    await db.auto_built_sites.update_one(
        {"slug": slug},
        {"$set": {"selected_template": {"idx": idx, "src_url": chosen.get("url")},
                  "style_hint": style}},
    )

    # Rebuild with style hint (suppress duplicate outreach)
    from services.auto_website_builder import build_site_for_lead
    res = await build_site_for_lead(db, site["lead_id"], style_hint=style)
    return {"ok": res.get("ok"), "new_site": res, "selected_idx": idx}


@router.get("/preview/{slug}", response_class=HTMLResponse)
async def preview_picker_page(slug: str):
    """Serves a self-contained customer-facing Theme Picker page."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB unavailable")
    site = await db.auto_built_sites.find_one(
        {"slug": slug},
        {"_id": 0, "business_name": 1, "live_url": 1,
         "business_phone": 1, "phone": 1,
         "claim_block_html": 1, "claim_signup_url": 1,
         "claim_expires": 1, "claim_ref": 1},
    )
    if not site:
        raise HTTPException(404, "site not found")

    biz = (site.get("business_name") or "your business").replace("<", "&lt;")
    live = site.get("live_url") or f"/api/sites/{slug}"
    phone = (site.get("business_phone") or site.get("phone") or "").strip()
    claim_block = site.get("claim_block_html") or ""
    phone_snippet = (
        f'<a href="tel:{phone}" data-aurem-phone '
        'style="color:#C9A227;font-family:DM Mono,monospace;'
        'font-size:13px;margin-left:14px;text-decoration:none">'
        f'{phone}</a>'
    ) if phone else ""

    return HTMLResponse(content=f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{biz} — Pick your style</title>
<style>
:root{{--gold:#C9A227;--bg:#0A0A0B;--ink:#F2EDE4;--muted:#8A8279}}
*{{box-sizing:border-box}}body{{margin:0;font:16px/1.6 'DM Sans',system-ui,sans-serif;
background:var(--bg);color:var(--ink)}}
.wrap{{max-width:1080px;margin:0 auto;padding:48px 20px}}
h1{{font:400 36px/1.1 'Cormorant Garamond',serif;margin:0 0 12px}}
p.sub{{color:var(--muted);max-width:680px;font-size:16px}}
.live-link{{display:inline-block;margin-top:14px;padding:10px 16px;border-radius:6px;
background:rgba(201,162,39,.12);color:var(--gold);text-decoration:none;
border:1px solid rgba(201,162,39,.35);font-size:13px}}
.grid{{margin-top:36px;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}}
.card{{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
border-radius:10px;overflow:hidden;cursor:pointer;transition:transform .18s,border-color .18s}}
.card:hover{{transform:translateY(-3px);border-color:rgba(201,162,39,.55)}}
.card img{{width:100%;display:block;aspect-ratio:16/10;object-fit:cover;background:#1A1A1B}}
.card .body{{padding:14px 16px}}
.card h3{{margin:0 0 6px;font-size:14px;font-weight:600}}
.card .meta{{font-size:11px;color:var(--muted);font-family:'DM Mono',monospace;letter-spacing:.5px}}
.card .palette{{margin-top:10px;display:flex;gap:6px}}
.dot{{width:18px;height:18px;border-radius:50%;border:1px solid rgba(255,255,255,.12)}}
.empty{{text-align:center;padding:60px 20px;color:var(--muted)}}
.spin{{display:inline-block;width:28px;height:28px;border-radius:50%;
border:2px solid rgba(201,162,39,.2);border-top-color:var(--gold);animation:s 1s linear infinite}}
@keyframes s{{to{{transform:rotate(360deg)}}}}
.toast{{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
padding:12px 20px;background:rgba(34,197,94,.18);border:1px solid rgba(34,197,94,.4);
color:#22C55E;border-radius:8px;font-size:14px;font-family:'DM Mono',monospace}}
.custom-box{{margin-top:60px;padding:32px;background:rgba(201,162,39,.06);
border:1px solid rgba(201,162,39,.25);border-radius:10px}}
.custom-box h3{{margin:0 0 8px;font:400 24px/1.2 'Cormorant Garamond',serif;color:var(--gold)}}
.custom-box p{{color:var(--muted);margin:0 0 18px;font-size:14px;max-width:560px}}
.custom-row{{display:flex;gap:10px;flex-wrap:wrap}}
.custom-row input{{flex:1;min-width:240px;padding:12px 14px;background:rgba(0,0,0,.35);
color:var(--ink);border:1px solid rgba(201,162,39,.35);border-radius:6px;font-size:14px;
outline:none;font-family:'DM Mono',monospace}}
.custom-row input:focus{{border-color:var(--gold)}}
.custom-row button{{padding:12px 22px;background:var(--gold);color:#0A0A0A;border:none;
border-radius:6px;font-weight:700;font-size:12px;letter-spacing:1.5px;cursor:pointer;
font-family:'DM Mono',monospace}}
.custom-row button:disabled{{opacity:.5;cursor:wait}}
.custom-status{{margin-top:14px;font-size:13px;color:var(--muted);
font-family:'DM Mono',monospace}}
footer{{margin-top:60px;text-align:center;color:var(--muted);font-size:12px}}
footer a{{color:var(--gold);text-decoration:none;font-weight:700}}
</style></head>
<body><div class="wrap">
  {claim_block}
  <h1>Pick your style for <em>{biz}</em>{phone_snippet}</h1>
  <p class="sub">We built you a free preview already — pick a different style if you'd like.
     We'll rebuild the site in 30 seconds and the same URL stays live.</p>
  <a class="live-link" href="{live}" target="_blank" rel="noopener">See current live site →</a>
  <div id="grid" class="grid"></div>
  <div id="empty" class="empty"><div class="spin"></div><p>Finding similar businesses…</p></div>

  <div class="custom-box">
    <h3>Don't like any of these?</h3>
    <p>Send us a website URL you like. We'll match the style and rebuild yours in 30 seconds.</p>
    <div class="custom-row">
      <input id="custom-url" type="url" placeholder="https://example.com" data-testid="custom-url-input">
      <button id="custom-go" data-testid="custom-url-submit">USE THIS STYLE</button>
    </div>
    <div id="custom-status" class="custom-status"></div>
  </div>

  <footer>Powered by <a href="https://aurem.live?utm_source=preview" target="_blank">AUREM</a></footer>
</div>
<script>
const slug = {slug!r};
async function load(){{
  try {{
    const r = await fetch(`/api/preview/${{slug}}/themes`);
    const d = await r.json();
    const grid = document.getElementById('grid');
    const empty = document.getElementById('empty');
    if (!d.themes || !d.themes.length) {{
      empty.innerHTML = '<p>No themes available right now. <a href="' + {live!r} + '">View your live site →</a></p>';
      return;
    }}
    empty.style.display = 'none';
    d.themes.forEach((t, i) => {{
      const el = document.createElement('div');
      el.className = 'card';
      const bg = t.style?.primary_bg || '#1A1410';
      const ac = t.style?.accent || '#C9A227';
      const hc = t.style?.heading_color || '#FFFFFF';
      const tc = t.style?.primary_text || '#E8DCC8';
      const hf = (t.style?.heading_font || 'Cormorant Garamond, serif').split(',')[0];
      const bf = (t.style?.body_font || 'DM Mono, monospace').split(',')[0];
      const label = ((t.business_name||'').slice(0,28) || 'Style ' + (i+1));
      const fallback = `<div style="width:100%;height:200px;background:${{bg}};
          display:flex;flex-direction:column;justify-content:center;padding:18px 20px;
          box-sizing:border-box;border-bottom:3px solid ${{ac}}">
            <div style="font-family:${{hf}};font-size:26px;font-weight:700;color:${{hc}};
              line-height:1.05;margin-bottom:8px">${{label}}</div>
            <div style="font-family:${{bf}};font-size:11px;color:${{tc}};opacity:.75;
              text-transform:uppercase;letter-spacing:1.5px">Crafted preview</div>
            <div style="margin-top:14px;display:inline-block;padding:6px 14px;
              background:${{ac}};color:#0A0A0A;font-family:${{bf}};font-size:10px;
              font-weight:700;letter-spacing:1.2px;width:fit-content">GET A QUOTE</div>
          </div>`;
      const imgHtml = t.screenshot_url
        ? `<img alt="" src="${{t.screenshot_url}}" loading="lazy"
             onerror="this.outerHTML=this.dataset.fallback"
             data-fallback='${{fallback.replace(/'/g, "&apos;")}}'>`
        : fallback;
      el.innerHTML = `
        ${{imgHtml}}
        <div class="body">
          <h3>${{label.slice(0,60) || 'Style ' + (i+1)}}</h3>
          <div class="meta">${{t.source||''}}</div>
          <div class="palette">
            <span class="dot" style="background:${{bg}}"></span>
            <span class="dot" style="background:${{ac}}"></span>
            <span class="dot" style="background:${{hc}}"></span>
          </div>
        </div>`;
      el.onclick = async () => {{
        document.querySelectorAll('.card').forEach(c => c.style.opacity='0.4');
        const sel = await fetch(`/api/preview/${{slug}}/select-theme`, {{
          method: 'POST', headers: {{'Content-Type':'application/json'}},
          body: JSON.stringify({{template_idx: i}}),
        }});
        const out = await sel.json();
        const t = document.createElement('div');
        t.className = 'toast';
        t.textContent = out.ok ? 'Style applied — your site is rebuilding.' : 'Could not apply.';
        document.body.appendChild(t);
        setTimeout(() => location.href = {live!r}, 1800);
      }};
      grid.appendChild(el);
    }});
  }} catch (e) {{
    document.getElementById('empty').innerHTML = '<p>Could not load themes.</p>';
  }}
}}
load();
document.getElementById('custom-go').addEventListener('click', async () => {{
  const inp = document.getElementById('custom-url');
  const btn = document.getElementById('custom-go');
  const status = document.getElementById('custom-status');
  const url = (inp.value || '').trim();
  if (!url.match(/^https?:\/\//)) {{
    status.textContent = 'Please enter a full URL starting with https://';
    status.style.color = '#EF4444';
    return;
  }}
  btn.disabled = true;
  status.style.color = ''; 
  status.textContent = 'Scraping ' + url + '…';
  try {{
    const r = await fetch(`/api/preview/${{slug}}/custom-url`, {{
      method: 'POST', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{url}}),
    }});
    const out = await r.json();
    if (!r.ok || !out.ok) {{
      status.style.color = '#EF4444';
      status.textContent = out.detail || 'Could not scrape that URL — try another.';
      btn.disabled = false;
      return;
    }}
    status.style.color = '#22C55E';
    status.textContent = 'Style captured — your site is rebuilding…';
    setTimeout(() => location.href = out.new_site && out.new_site.live_url ? out.new_site.live_url : {live!r}, 1800);
  }} catch (e) {{
    status.style.color = '#EF4444';
    status.textContent = 'Network error: ' + e.message;
    btn.disabled = false;
  }}
}});
</script>
</body></html>""")



# ─── Iter 304 — Public Repair Report Page ──────────────────────────────────
@router.get("/repair-report/{slug}", response_class=HTMLResponse)
async def public_repair_report(slug: str):
    """Unauth report page served when ORA outreach links a customer here."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB unavailable")
    audit = await db.customer_scans.find_one(
        {"public_slug": slug}, {"_id": 0}
    )
    if not audit:
        # Fallback — accept lead_id too so the URL works whether outbound
        # uses public_slug or lead_id (forward-compat for hybrid CTA).
        audit = await db.customer_scans.find_one(
            {"lead_id": slug}, {"_id": 0},
            sort=[("created_at", -1)],
        )
    if not audit:
        raise HTTPException(404, "report not found")
    slug = audit.get("public_slug") or slug

    biz_name = "Your Business"
    site_url = audit.get("website") or ""
    if audit.get("lead_id"):
        lead = await db.campaign_leads.find_one(
            {"lead_id": audit["lead_id"]},
            {"_id": 0, "business_name": 1, "website_url": 1, "audit_id": 1}
        ) or {}
        biz_name = lead.get("business_name") or biz_name
        site_url = site_url or lead.get("website_url") or ""

    score = int(audit.get("overall_score") or 0)
    issues = audit.get("issues") or []
    rebuild_recommended = bool(audit.get("rebuild_recommended"))
    score_color = "#22C55E" if score >= 70 else ("#F59E0B" if score >= 50 else "#EF4444")

    issue_li = "".join(
        f'<li><span class="ico">{_repair_icon(i.get("kind",""))}</span>'
        f'<div><strong>{(i.get("title") or "")[:90]}</strong>'
        f'<small>{(i.get("detail") or "")[:160]}</small></div>'
        f'<span class="sev sev-{i.get("severity","low")}">{i.get("severity","low")}</span></li>'
        for i in issues[:10]
    ) or '<li>Multiple issues affecting visibility, conversion, and trust.</li>'

    bd = audit.get("score_breakdown") or {}
    score_rows = "".join(
        f'<tr><td>{k.replace("_"," ").title()}</td>'
        f'<td><strong>{v}</strong></td></tr>'
        for k, v in bd.items()
    )

    return HTMLResponse(f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Website Audit — {biz_name}</title>
<style>
:root{{--gold:#C9A227;--bg:#0A0A0B;--ink:#F2EDE4;--muted:#8A8279;--card:rgba(255,255,255,0.03)}}
*{{box-sizing:border-box}}
body{{margin:0;font:16px/1.65 'DM Sans',system-ui,sans-serif;background:var(--bg);color:var(--ink)}}
.wrap{{max-width:980px;margin:0 auto;padding:48px 20px}}
h1{{font:400 36px/1.1 'Cormorant Garamond',serif;margin:0 0 8px}}
.biz{{color:var(--gold);font-size:14px;letter-spacing:.18em;text-transform:uppercase;font-family:'DM Mono',monospace}}
.site-link{{color:var(--muted);font-size:14px;word-break:break-all}}
.gauge{{display:flex;align-items:center;gap:24px;margin:32px 0;padding:24px;background:var(--card);
  border:1px solid rgba(255,255,255,.08);border-radius:12px}}
.gauge-num{{font:700 80px/1 'Cormorant Garamond',serif;color:{score_color}}}
.gauge-label{{font-size:13px;color:var(--muted);letter-spacing:.15em;text-transform:uppercase}}
.gauge-headline{{font-size:18px;color:var(--ink);margin-top:6px;line-height:1.4}}
table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}}
table td{{padding:6px 8px;border-bottom:1px solid rgba(255,255,255,.05)}}
table td:first-child{{color:var(--muted)}}
ul.issues{{list-style:none;padding:0;margin:0}}
ul.issues li{{display:flex;gap:14px;padding:14px 0;border-bottom:1px solid rgba(255,255,255,.06);align-items:flex-start}}
ul.issues li:last-child{{border-bottom:0}}
.ico{{font-size:22px;line-height:1.2;width:30px;flex-shrink:0}}
ul.issues small{{display:block;color:var(--muted);font-size:13px;margin-top:2px}}
.sev{{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.1em;padding:2px 8px;
  border-radius:99px;height:fit-content}}
.sev-high{{background:rgba(239,68,68,.16);color:#EF4444}}
.sev-medium{{background:rgba(245,158,11,.16);color:#F59E0B}}
.sev-low{{background:rgba(138,130,121,.16);color:var(--muted)}}
.tiers{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-top:36px}}
.tier{{padding:24px;background:var(--card);border:1px solid rgba(255,255,255,.08);border-radius:12px;
  display:flex;flex-direction:column}}
.tier.recommended{{border-color:var(--gold);box-shadow:0 0 22px rgba(201,162,39,.16)}}
.tier h3{{font:600 22px 'Cormorant Garamond',serif;margin:0 0 4px}}
.price{{font:700 36px 'Cormorant Garamond',serif;color:var(--gold)}}
.price small{{font-size:14px;color:var(--muted);font-weight:400}}
.tier ul{{list-style:none;padding:0;margin:14px 0 22px;font-size:14px;color:var(--ink)}}
.tier ul li{{padding:5px 0;color:#B8B0A4}}
.tier ul li::before{{content:"✓ ";color:var(--gold);font-weight:700}}
.btn{{display:inline-block;padding:12px 18px;background:var(--gold);color:#0A0A0A;
  border-radius:6px;font-weight:700;text-decoration:none;text-align:center;font-size:13px;
  letter-spacing:.1em;font-family:'DM Mono',monospace;cursor:pointer;border:none;width:100%}}
.domain-row{{margin-top:14px;padding:10px 12px;background:rgba(201,162,39,0.06);
  border:1px solid rgba(201,162,39,0.2);border-radius:6px;font-size:12px;color:#B8B0A4}}
.domain-row label{{display:flex;align-items:center;gap:8px;cursor:pointer}}
.domain-row input[type=checkbox]{{accent-color:var(--gold);width:14px;height:14px;cursor:pointer}}
.domain-row input[type=text]{{margin-top:8px;width:100%;padding:7px 9px;font-size:12px;
  background:rgba(0,0,0,0.35);color:var(--ink);border:1px solid rgba(201,162,39,0.25);
  border-radius:4px;font-family:inherit;outline:none;display:none}}
.domain-row.on input[type=text]{{display:block}}
.domain-row .price-up{{color:var(--gold);font-weight:700;font-family:'DM Mono',monospace}}
.btn:hover{{filter:brightness(1.08)}}
footer{{margin-top:60px;padding-top:24px;border-top:1px solid rgba(255,255,255,.08);
  text-align:center;color:var(--muted);font-size:12px}}
footer a{{color:var(--gold);text-decoration:none;font-weight:700}}
</style></head>
<body><div class="wrap">
  <p class="biz">Website Audit · {biz_name}</p>
  <h1>Audit Report</h1>
  <p class="site-link"><a href="{site_url}" target="_blank" rel="noopener" style="color:var(--muted)">{site_url}</a></p>

  <div class="gauge">
    <div>
      <div class="gauge-num" data-testid="report-score">{score}</div>
      <div class="gauge-label">/100</div>
    </div>
    <div style="flex:1">
      <div class="gauge-headline">{("Strong site — minor improvements." if score>=70 else ("Significant issues hurting conversions." if score>=40 else "Severe issues — repair recommended."))}</div>
      <table>{score_rows}</table>
    </div>
  </div>

  <h2 style="font:400 26px 'Cormorant Garamond',serif;margin:32px 0 12px">Issues Found ({len(issues)})</h2>
  <ul class="issues" data-testid="report-issues">{issue_li}</ul>

  <div class="tiers">
    <div class="tier {'' if rebuild_recommended else 'recommended'}">
      <h3>Repair Basic</h3>
      <div class="price">$149 <small>CAD</small></div>
      <ul>
        <li>SSL fix + mobile + speed</li>
        <li>Broken link cleanup</li>
        <li>Contact form + social</li>
        <li>Delivered in 24h</li>
      </ul>
      <div class="domain-row" data-tier="basic" data-testid="domain-row-basic">
        <label><input type="checkbox" data-testid="domain-checkbox-basic" />
          Add custom domain
          <span class="price-up">+ $29 CAD / yr</span></label>
        <input type="text" placeholder="yourbusiness.com"
          data-testid="domain-input-basic" />
      </div>
      <a class="btn" href="/api/repair/checkout?slug={slug}&tier=basic"
        data-tier="basic" data-base-amt="149"
        data-testid="report-buy-basic">Start Repair · $149</a>
    </div>
    <div class="tier {'recommended' if rebuild_recommended else ''}">
      <h3>Repair Full {'★ Recommended' if rebuild_recommended else ''}</h3>
      <div class="price">$299 <small>CAD</small></div>
      <ul>
        <li>Everything in Basic</li>
        <li>New design (score &lt; 40)</li>
        <li>AWB rebuild mode</li>
        <li>Delivered in 48h</li>
      </ul>
      <div class="domain-row" data-tier="full" data-testid="domain-row-full">
        <label><input type="checkbox" data-testid="domain-checkbox-full" />
          Add custom domain
          <span class="price-up">+ $29 CAD / yr</span></label>
        <input type="text" placeholder="yourbusiness.com"
          data-testid="domain-input-full" />
      </div>
      <a class="btn" href="/api/repair/checkout?slug={slug}&tier=full"
        data-tier="full" data-base-amt="299"
        data-testid="report-buy-full">Start Repair · $299</a>
    </div>
  </div>

  <script>
    (function() {{
      function rebuild(tier) {{
        var row  = document.querySelector('[data-testid="domain-row-' + tier + '"]');
        var cb   = row.querySelector('input[type=checkbox]');
        var txt  = row.querySelector('input[type=text]');
        var btn  = document.querySelector('a[data-tier="' + tier + '"]');
        var base = parseInt(btn.getAttribute('data-base-amt'), 10);
        if (cb.checked) {{
          row.classList.add('on');
          var dom = (txt.value || '').trim().toLowerCase();
          var url = '/api/repair/checkout?slug={slug}&tier=' + tier
                  + (dom ? '&domain_addon=true&domain=' + encodeURIComponent(dom) : '');
          btn.setAttribute('href', url);
          btn.textContent = 'Start Repair · $' + (base + 29) + (dom ? '' : ' (enter domain)');
        }} else {{
          row.classList.remove('on');
          btn.setAttribute('href', '/api/repair/checkout?slug={slug}&tier=' + tier);
          btn.textContent = 'Start Repair · $' + base;
        }}
      }}
      ['basic','full'].forEach(function(t) {{
        var row = document.querySelector('[data-testid="domain-row-' + t + '"]');
        if (!row) return;
        row.querySelector('input[type=checkbox]').addEventListener('change', function() {{ rebuild(t); }});
        row.querySelector('input[type=text]').addEventListener('input', function() {{ rebuild(t); }});
      }});
    }})();
  </script>

  <footer>Powered by <a href="https://aurem.live?utm_source=report" target="_blank">AUREM</a> · Polaris Built Inc.</footer>
</div></body></html>""")


def _repair_icon(kind: str) -> str:
    return {
        "ssl": "🔒", "speed": "⚡", "mobile": "📱",
        "broken_links": "🔗", "contact_form": "📝",
        "social_links": "📣", "copyright_year": "📅",
        "google_maps": "📍",
    }.get(kind, "•")

