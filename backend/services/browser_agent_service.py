"""
Browser Agent Service — Phase 2.5F (iter 282e)
===============================================
Thin, safe wrapper around the existing `routers/browser_agent_router.py`
Playwright implementation that adds:

  1. **Admin approval gate** — any EXTERNAL URL browser action is queued
     in `db.ora_dev_actions` with `action_type="browser_navigate"` and
     `status="pending"`. Nothing fires until an admin calls the existing
     `/api/ora-dev-actions/{id}/approve` endpoint.
     Internal URLs (same-host preview builds, already-rendered AWB sites)
     are auto-approved — the gate exists to stop ORA from hitting 3rd
     party sites without human sign-off.

  2. **Screenshot persistence** — screenshots captured by the agent get
     uploaded to R2 (bucket already wired via `services/cloudflare_r2.py`)
     and a public URL is returned. Falls back to local `/tmp` path + the
     existing `/api/static/*` proxy if R2 is unavailable.

  3. **Safe public API** — three async entry points the rest of AUREM
     can import:
        await screenshot_url(url, *, full_page=True, wait_ms=1500,
                              requires_approval=None, reason=None,
                              triggered_by="system")
        await extract_url(url, selector=None, *, multiple=False,
                            requires_approval=None)
        await list_recent_actions(limit=50)

  No changes to the sealed `ora_brain.py`. No new Playwright install —
  reuses the existing Chromium binary + `BrowserSession` class that
  already lives inside `browser_agent_router`.
"""
from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_db = None

# iter 325x — Playwright/Chromium browser availability cache.
# Production Emergent K8s images do NOT ship the Playwright Chromium
# binary (it adds ~280 MB). Calling `pw.chromium.launch()` without the
# binary throws `BrowserType.launch: Executable doesn't exist at
# /pw-browsers/...` for every single screenshot, spamming stderr and
# tripping the deploy logs as "errors".
#
# Fix: probe the binary path ONCE per process. If missing, every call
# into _launch_page() short-circuits with a clean None return so callers
# (e.g. `screenshot_url`) log a single one-line warning and skip — no
# stack trace, no log flood, no false-positive deploy failure.
_BROWSER_AVAILABLE: Optional[bool] = None
_BROWSER_AVAILABLE_REASON: str = ""


def _probe_browser_available() -> bool:
    """One-shot detection of usable Chromium binary. Cached after first call.

    iter 325x — Pure filesystem probe (NO Playwright import) so we don't
    trigger Playwright's "Please run playwright install" banner that
    floods the deploy logs with ASCII art on every cold start.

    Checks both PLAYWRIGHT_BROWSERS_PATH and the bundled default location
    for any `chrome*` executable. Cached after first call.
    """
    global _BROWSER_AVAILABLE, _BROWSER_AVAILABLE_REASON
    if _BROWSER_AVAILABLE is not None:
        return _BROWSER_AVAILABLE
    candidates = []
    env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if env_path:
        candidates.append(env_path)
    # Bundled default (Python site-packages cache)
    candidates.extend([
        "/pw-browsers",
        "/root/.cache/ms-playwright",
        os.path.expanduser("~/.cache/ms-playwright"),
        "/ms-playwright",
    ])
    found_at = None
    for base in candidates:
        if not base or not os.path.isdir(base):
            continue
        try:
            for root, _dirs, files in os.walk(base):
                for fn in files:
                    if fn in ("chrome-headless-shell", "headless_shell", "chrome", "chromium"):
                        candidate = os.path.join(root, fn)
                        if os.access(candidate, os.X_OK):
                            found_at = candidate
                            break
                if found_at:
                    break
        except Exception:
            continue
        if found_at:
            break
    if found_at:
        _BROWSER_AVAILABLE = True
        _BROWSER_AVAILABLE_REASON = f"chromium at {found_at}"
    else:
        _BROWSER_AVAILABLE = False
        _BROWSER_AVAILABLE_REASON = (
            f"chromium binary not found in any of {candidates} — "
            "run `playwright install chromium` to enable screenshots "
            "(screenshots will be silently skipped)"
        )
        logger.warning(f"[browser-agent] DISABLED — {_BROWSER_AVAILABLE_REASON}")
    return _BROWSER_AVAILABLE


def is_browser_available() -> bool:
    """Public read for any caller that wants to skip screenshot logic upfront."""
    return _probe_browser_available()


def set_db(database) -> None:
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server  # type: ignore
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


# ── allow-list of host suffixes that NEVER require approval ──
# (our own preview + prod + internal loopback)
def _internal_hosts() -> set:
    hosts = {"localhost", "127.0.0.1"}
    for env_key in ("AUREM_PUBLIC_URL", "PUBLIC_APP_URL"):
        url = os.environ.get(env_key, "").strip()
        if url:
            try:
                hosts.add(urlparse(url).hostname or "")
            except Exception:
                pass
    # Always auto-approve production AUREM hosts (preview only via env)
    hosts.update({
        "aurem.live",
        "www.aurem.live",
    })
    return {h for h in hosts if h}


def _is_internal(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    internal = _internal_hosts()
    for allowed in internal:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


# ── Core Playwright operations (reuses existing BrowserSession) ─────────────
# iter 282j Task 3 — auto-stealth for hard-to-scrape targets
_STEALTH_HOST_HINTS = (
    "linkedin.com", "google.com/maps", "maps.google.",
    "facebook.com", "instagram.com",
    "x.com", "twitter.com",
    "indeed.com", "glassdoor.com",
    "yelp.com",
)


def _should_use_stealth(url: str) -> bool:
    """Auto-detect targets that fingerprint regular Playwright."""
    if not url:
        return False
    u = url.lower()
    return any(hint in u for hint in _STEALTH_HOST_HINTS)


async def _launch_page(headless: bool = True, stealth: Optional[bool] = None,
                        target_url: str = ""):
    """Spin up a throwaway Playwright page. Caller MUST close it.

    iter 282j Task 3 — pass stealth=True or pass target_url and we'll
    auto-enable stealth for known-fingerprinted hosts (LinkedIn, Google
    Maps, etc.). Stealth uses `rebrowser-playwright` which patches
    Chromium's automation flags + canvas/webgl/timezone fingerprints.

    iter 325x — Returns (None, None, None) if Chromium binary is missing
    so callers can detect-and-skip without try/except gymnastics.
    """
    if not _probe_browser_available():
        return None, None, None
    if stealth is None:
        stealth = _should_use_stealth(target_url)
    if stealth:
        try:
            from rebrowser_playwright.async_api import async_playwright as _stealth_pw  # type: ignore
            pw = await _stealth_pw().start()
            logger.info(f"[browser-agent] stealth mode ON for {target_url[:80]}")
        except Exception as e:
            logger.warning(f"[browser-agent] stealth fallback to vanilla: {e}")
            from playwright.async_api import async_playwright  # type: ignore
            pw = await async_playwright().start()
            stealth = False
    else:
        from playwright.async_api import async_playwright  # type: ignore
        pw = await async_playwright().start()
    try:
        browser = await pw.chromium.launch(
            headless=headless,
            args=([
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ] if stealth else []),
        )
    except Exception as e:
        # Defensive — probe said browsers were present but launch still
        # failed (e.g. corrupted binary, permission issue). Don't crash
        # the whole service; mark unavailable and degrade gracefully.
        global _BROWSER_AVAILABLE, _BROWSER_AVAILABLE_REASON
        _BROWSER_AVAILABLE = False
        _BROWSER_AVAILABLE_REASON = f"chromium.launch failed at runtime: {e}"
        logger.warning(f"[browser-agent] {_BROWSER_AVAILABLE_REASON}")
        try:
            await pw.stop()
        except Exception:
            pass
        return None, None, None
    ctx = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
            + ("" if stealth else " AUREM-Scout/1.0")
        ),
        locale="en-US",
        timezone_id="America/Toronto",
    )
    if stealth:
        # Mask the most common automation tells before any page JS runs.
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            window.chrome = window.chrome || { runtime: {} };
        """)
    page = await ctx.new_page()
    return pw, browser, page


async def _close_all(pw, browser) -> None:
    try:
        await browser.close()
    except Exception:
        pass
    try:
        await pw.stop()
    except Exception:
        pass


async def _upload_screenshot_to_r2(png_bytes: bytes, slug: str) -> Optional[str]:
    """Upload PNG bytes to R2 and return a PUBLIC-ACCESSIBLE URL.

    Because our `aurem-sites` bucket is private by default, we generate a
    **presigned GET URL** that embeds temporary credentials inline. The
    URL is valid for 7 days — long enough for email recipients to load
    the screenshot, short enough to auto-expire without leaking access.

    If a custom public domain is bound (set `R2_PUBLIC_BASE`) the helper
    prefers that over presigning. Key layout:
        browser-screenshots/{YYYY-MM-DD}/{slug}-{token}.png
    """
    try:
        from services.cloudflare_r2 import is_configured as r2_ok
        import boto3  # type: ignore
        from botocore.config import Config as _BotoConfig  # type: ignore
    except Exception:
        return None
    if not r2_ok():
        return None
    try:
        endpoint_url = (
            f"https://{os.environ['CLOUDFLARE_ACCOUNT_ID']}"
            f".r2.cloudflarestorage.com"
        )
        cli = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=_BotoConfig(signature_version="s3v4"),
        )
        bucket = os.environ.get("R2_BUCKET_NAME", "aurem-sites")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        token = secrets.token_hex(5)
        key = f"browser-screenshots/{today}/{slug}-{token}.png"
        cli.put_object(
            Bucket=bucket,
            Key=key,
            Body=png_bytes,
            ContentType="image/png",
            CacheControl="public, max-age=3600",
        )
        # Prefer custom domain if configured — clean, permanent URL.
        public_base = os.environ.get("R2_PUBLIC_BASE", "").strip().rstrip("/")
        if public_base:
            return f"{public_base}/{key}"
        # Fallback: presigned URL (7-day expiry) — works with private bucket.
        try:
            url = cli.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=7 * 24 * 3600,
            )
            return url
        except Exception as _pe:
            logger.warning(f"[browser_agent] presign fallback failed: {_pe}")
            return None
    except Exception as e:
        logger.warning(f"[browser_agent] R2 upload failed: {e}")
        return None


# ── Approval gate integration ───────────────────────────────────────────────
async def _queue_approval(action_type: str, url: str, *, reason: str,
                           triggered_by: str, payload: Dict[str, Any]) -> str:
    """Write a pending row to ora_dev_actions. Returns proposal_id."""
    db = _get_db()
    proposal_id = f"browser_{secrets.token_hex(6)}"
    doc = {
        "proposal_id": proposal_id,
        "action_type": action_type,
        "kind": "browser_action",
        "target_url": url,
        "payload": payload,
        "reason": reason or f"{action_type} requested",
        "triggered_by": triggered_by,
        "status": "pending",
        "sealed_blocked": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if db is not None:
        try:
            await db.ora_dev_actions.insert_one(doc)
        except Exception as e:
            logger.warning(f"[browser_agent] approval queue insert failed: {e}")
    logger.info(f"[browser_agent] queued {action_type} for approval: {proposal_id} ({url})")
    return proposal_id


async def _is_approved(proposal_id: str) -> bool:
    db = _get_db()
    if db is None:
        return False
    row = await db.ora_dev_actions.find_one(
        {"proposal_id": proposal_id},
        {"_id": 0, "status": 1},
    )
    return bool(row) and row.get("status") == "approved"


async def _mark_applied(proposal_id: str, result: Dict[str, Any]) -> None:
    db = _get_db()
    if db is None:
        return
    try:
        await db.ora_dev_actions.update_one(
            {"proposal_id": proposal_id},
            {"$set": {
                "status": "applied",
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
            }},
        )
    except Exception as e:
        logger.warning(f"[browser_agent] mark_applied failed: {e}")


async def _log_action(kind: str, url: str, result: Dict[str, Any],
                       triggered_by: str) -> None:
    db = _get_db()
    if db is None:
        return
    try:
        await db.browser_actions.insert_one({
            "kind": kind,
            "url": url,
            "result": result,
            "triggered_by": triggered_by,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


# ── Public API ──────────────────────────────────────────────────────────────
async def screenshot_url(
    url: str,
    *,
    full_page: bool = True,
    wait_ms: int = 1500,
    requires_approval: Optional[bool] = None,
    reason: Optional[str] = None,
    triggered_by: str = "system",
    slug_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Navigate to `url` and capture a screenshot.

    Returns `{"ok": True, "image_url": "...", "title": "...",
              "final_url": "...", "pending": False}` on success,
    or `{"ok": False, "pending": True, "proposal_id": "...", ...}`
    when approval is required (the screenshot is NOT taken yet —
    caller should re-invoke once approved via the dev-actions router).
    """
    internal = _is_internal(url)
    if requires_approval is None:
        requires_approval = not internal
    if requires_approval:
        proposal_id = await _queue_approval(
            "browser_screenshot",
            url,
            reason=reason or "Capture screenshot of external URL",
            triggered_by=triggered_by,
            payload={"full_page": full_page, "wait_ms": wait_ms,
                      "slug_hint": slug_hint},
        )
        return {
            "ok": False,
            "pending": True,
            "proposal_id": proposal_id,
            "message": "External URL requires admin approval. "
                       "Approve in ORA Dev Console → browser actions.",
        }

    pw = browser = None
    try:
        pw, browser, page = await _launch_page(target_url=url)
        if page is None:
            # iter 325x — browser binary missing. Skip cleanly so deploy
            # logs stay clean and the rest of the API keeps serving.
            result = {
                "ok": False, "pending": False, "skipped": True,
                "error": "browser_unavailable",
                "reason": _BROWSER_AVAILABLE_REASON,
            }
            await _log_action("screenshot", url, result, triggered_by)
            return result
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if wait_ms:
            await page.wait_for_timeout(wait_ms)
        title = await page.title()
        final_url = page.url
        png_bytes = await page.screenshot(full_page=full_page, type="png")
        slug = (slug_hint
                or urlparse(url).hostname
                or "shot").replace(".", "-")
        r2_url = await _upload_screenshot_to_r2(png_bytes, slug)
        if not r2_url:
            # fallback — write to /tmp and serve via existing static proxy
            path = f"/tmp/browser_{slug}_{secrets.token_hex(4)}.png"
            try:
                with open(path, "wb") as f:
                    f.write(png_bytes)
                r2_url = path  # caller will surface as local path
            except Exception:
                r2_url = None
        result = {
            "ok": True, "pending": False,
            "image_url": r2_url,
            "title": title,
            "final_url": final_url,
            "size_bytes": len(png_bytes),
        }
        await _log_action("screenshot", url, result, triggered_by)
        return result
    except Exception as e:
        logger.warning(f"[browser_agent] screenshot failed for {url}: {e}")
        result = {"ok": False, "error": str(e)[:200], "pending": False}
        await _log_action("screenshot", url, result, triggered_by)
        return result
    finally:
        if browser is not None:
            await _close_all(pw, browser)


async def extract_url(
    url: str,
    selector: Optional[str] = None,
    *,
    multiple: bool = False,
    requires_approval: Optional[bool] = None,
    reason: Optional[str] = None,
    triggered_by: str = "system",
) -> Dict[str, Any]:
    """Navigate to `url` and extract text (optional selector)."""
    internal = _is_internal(url)
    if requires_approval is None:
        requires_approval = not internal
    if requires_approval:
        proposal_id = await _queue_approval(
            "browser_extract",
            url,
            reason=reason or "Extract text from external URL",
            triggered_by=triggered_by,
            payload={"selector": selector, "multiple": multiple},
        )
        return {"ok": False, "pending": True, "proposal_id": proposal_id}

    pw = browser = None
    try:
        pw, browser, page = await _launch_page(target_url=url)
        if page is None:
            # iter 325x — graceful skip when chromium binary missing.
            return {
                "ok": False, "pending": False, "skipped": True,
                "error": "browser_unavailable",
                "reason": _BROWSER_AVAILABLE_REASON,
            }
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(800)
        if selector:
            if multiple:
                els = await page.query_selector_all(selector)
                data = [await el.inner_text() for el in els]
            else:
                el = await page.query_selector(selector)
                data = await el.inner_text() if el else None
        else:
            data = await page.inner_text("body")
            if len(data) > 8000:
                data = data[:8000] + "\n…[truncated]"
        result = {"ok": True, "data": data, "final_url": page.url,
                   "title": await page.title(), "pending": False}
        await _log_action("extract", url, {"ok": True}, triggered_by)
        return result
    except Exception as e:
        logger.warning(f"[browser_agent] extract failed for {url}: {e}")
        return {"ok": False, "error": str(e)[:200], "pending": False}
    finally:
        if browser is not None:
            await _close_all(pw, browser)


async def execute_approved_action(proposal_id: str) -> Dict[str, Any]:
    """Called by the approve endpoint after an admin approves a queued
    browser action. Looks up the proposal, runs the real action, and
    marks it applied with the result."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "DB not ready"}
    row = await db.ora_dev_actions.find_one(
        {"proposal_id": proposal_id},
        {"_id": 0},
    )
    if not row:
        return {"ok": False, "error": "Proposal not found"}
    if row.get("status") != "approved":
        return {"ok": False, "error": f"Not approved (status={row.get('status')})"}
    action_type = row.get("action_type") or ""
    url = row.get("target_url") or ""
    payload = row.get("payload") or {}
    if action_type == "browser_screenshot":
        res = await screenshot_url(
            url,
            full_page=payload.get("full_page", True),
            wait_ms=payload.get("wait_ms", 1500),
            requires_approval=False,
            triggered_by=f"approval:{proposal_id}",
            slug_hint=payload.get("slug_hint"),
        )
    elif action_type == "browser_extract":
        res = await extract_url(
            url,
            selector=payload.get("selector"),
            multiple=payload.get("multiple", False),
            requires_approval=False,
            triggered_by=f"approval:{proposal_id}",
        )
    else:
        res = {"ok": False, "error": f"Unsupported action_type {action_type}"}
    await _mark_applied(proposal_id, res)
    return res


async def list_recent_actions(limit: int = 50) -> list:
    """Return latest browser actions for the Dev Console UI."""
    db = _get_db()
    if db is None:
        return []
    try:
        cur = db.browser_actions.find({}, {"_id": 0}) \
                                .sort("timestamp", -1) \
                                .limit(int(limit))
        return [d async for d in cur]
    except Exception:
        return []
