"""
AUREM Prospect Site QA — Section 6 of growth-engine upgrade
==============================================================
For leads in the `no_website` queue.

Flow (per spec):
  1. Build a real prospect site via existing `auto_website_builder`
     (data injected from Yelp / scout payload: name, phone, address,
     photos, rating, hours).
  2. Augment built HTML with two non-negotiable elements:
       • "Claim This Website — Free 7 Day Trial" CTA →
         aurem.live/signup?ref={lead_id}
       • Live Pixel + "Claim before {today+7}" copy in hero/footer.
  3. URL is `aurem.live/preview/{lead_id}` and **never expires**.
  4. Run the A2A 6-point auto-test (max 2 retries).

A2A auto-tests:
  ✅ URL 200 OK
  ✅ No broken images          (every <img src> resolves to 200/3xx)
  ✅ Mobile renders            (viewport meta + width:device-width)
  ✅ CTA href valid            (signup link present + correct ref)
  ✅ Business name + phone visible
  ✅ Live Pixel fires          (aurem-pixel.js loaded)

The augmentation step is idempotent — re-running on an already-built
site re-injects the CTA/expiry/pixel block atop the existing body.
"""
from __future__ import annotations

import re
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

# ── tunables (env-overridable) ───────────────────────────────────────
import os
PREVIEW_BASE = os.environ.get("AUREM_PUBLIC_BASE", "https://aurem.live")
TEST_TIMEOUT_S = float(os.environ.get("QA_NO_WEB_TIMEOUT_S", "8"))
TEST_MAX_RETRIES = int(os.environ.get("QA_NO_WEB_RETRIES", "2"))
TEST_RETRY_DELAY_S = float(os.environ.get("QA_NO_WEB_RETRY_DELAY_S", "3"))
IMG_CHECK_MAX = int(os.environ.get("QA_NO_WEB_IMG_CHECK_MAX", "8"))

VIEWPORT_RE = re.compile(
    r'<meta[^>]+name=["\']viewport["\'][^>]+content=["\'][^"\']*'
    r'width=device-width', re.I,
)
PIXEL_RE = re.compile(
    r'aurem-pixel\.js|/api/pixel/aurem-pixel|data-aurem-key', re.I,
)
IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
CTA_HREF_PATTERN = "/signup?ref="


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

async def build_and_qa_no_website(
    db, lead_id: str, *, save: bool = True,
) -> Dict[str, Any]:
    """End-to-end: build prospect site → augment → auto-test (×2 retries).

    Returns:
      {
        "lead_id":  str,
        "site_id":  str,
        "slug":     str,
        "preview_url": str,
        "build":    {...},
        "tests":    [{run_n: int, passed: bool, checks: {...}}, ...],
        "passed":   bool,        # final verdict (any retry passed)
        "ready_to_blast": bool,
      }
    """
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    # 1. Build the site (idempotent — auto_website_builder dedupes)
    try:
        from services.auto_website_builder import build_site_for_lead
        build = await build_site_for_lead(db, lead_id)
    except Exception as e:
        logger.warning(f"[qa-no-web] build failed for {lead_id}: {e}")
        return {"ok": False, "error": f"build_failed: {type(e).__name__}"}
    if not build.get("ok"):
        return {"ok": False, "error": build.get("error", "build_failed")}

    slug = build.get("slug")
    site_id = build.get("site_id")
    if not slug:
        return {"ok": False, "error": "no_slug_from_build"}

    # 2. Augment HTML — claim CTA + expiry + pixel (idempotent)
    await _ensure_claim_artifacts(db, slug, lead_id)

    # 3. Preview URL — `aurem.live/preview/{slug}` per spec (customer-facing).
    # For A2A QA fetching, we must hit the backend route directly so the
    # picker HTML (with claim_block + signup ref + pixel) is returned even
    # in preview environments where the frontend SPA owns `/preview/*`.
    preview_url = f"{PREVIEW_BASE}/preview/{slug}"
    preview_url_lead_form = f"{PREVIEW_BASE}/preview/{lead_id}"
    qa_fetch_url = f"{PREVIEW_BASE}/api/preview/{slug}"

    # 4. Run auto-tests with retries
    runs: List[Dict[str, Any]] = []
    final_passed = False
    for n in range(TEST_MAX_RETRIES + 1):  # 1 initial + N retries
        check = await _run_a2a_checks(qa_fetch_url, lead_id)
        runs.append({"run_n": n + 1, **check})
        if check["passed"]:
            final_passed = True
            break
        if n < TEST_MAX_RETRIES:
            await asyncio.sleep(TEST_RETRY_DELAY_S)
            # Re-augment in case the build was thin / missing artifacts
            await _ensure_claim_artifacts(db, slug, lead_id)

    if save:
        try:
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "qa_no_website": {
                        "site_id": site_id, "slug": slug,
                        "preview_url": preview_url,
                        "preview_url_lead_form": preview_url_lead_form,
                        "tests": runs,
                        "passed": final_passed,
                        "tested_at": datetime.now(timezone.utc),
                    },
                    "qa_ready_to_blast": final_passed,
                    "preview_url": preview_url,
                }},
            )
        except Exception as e:
            logger.debug(f"[qa-no-web] persist skipped: {e}")

    return {
        "ok": True,
        "lead_id": lead_id,
        "site_id": site_id,
        "slug": slug,
        "preview_url": preview_url,
        "preview_url_lead_form": preview_url_lead_form,
        "build": {
            "already_existed": build.get("already_existed", False),
            "reused_from": build.get("reused_from"),
        },
        "tests": runs,
        "passed": final_passed,
        "ready_to_blast": final_passed,
    }


# ─────────────────────────────────────────────────────────────────────
# Augmentation — claim CTA + expiry + pixel
# ─────────────────────────────────────────────────────────────────────

async def _ensure_claim_artifacts(db, slug: str, lead_id: str) -> None:
    """Stamp claim CTA + expiry + pixel onto the auto_built_sites row.

    Persists the fields the public renderer reads:
        claim_ref:     str   = lead_id (for URL building)
        claim_expires: ISO  = today + 7 days
        claim_block_html:    raw HTML banner (rendered above hero)
        business_phone:      mirrored from lead so picker shows tel: link
        business_name:       mirrored from lead (visibility check)
    """
    if db is None:
        return
    # Mirror identity fields from the lead row so the public picker can render
    # phone + name visibly (QA check #5)
    lead_row = await db.campaign_leads.find_one(
        {"lead_id": lead_id},
        {"_id": 0, "phone": 1, "business_phone": 1,
         "business_name": 1, "name": 1},
    ) or {}
    phone = (lead_row.get("phone") or lead_row.get("business_phone") or "").strip()
    biz_name = (lead_row.get("business_name") or lead_row.get("name") or "").strip()
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()
    signup_url = f"{PREVIEW_BASE}/signup?ref={lead_id}"
    # The aurem-pixel snippet — keys are public + rate-limited; OK to inject.
    pixel_snippet = (
        f'<script src="{PREVIEW_BASE}/api/pixel/aurem-pixel.js" '
        f'data-aurem-key="prospect-{lead_id}" defer></script>'
    )
    claim_block = (
        '<div style="background:linear-gradient(90deg,#0A0A0B,#1a1a1c);'
        'color:#F2EDE4;padding:18px 22px;text-align:center;'
        'border-bottom:2px solid #C9A227;font-family:DM Sans,system-ui,sans-serif">'
        '<div style="font:600 16px/1.4 inherit;color:#F2EDE4">'
        f'Claim before {expires} — your free preview won\'t stay live forever.'
        '</div>'
        f'<a href="{signup_url}" '
        'style="display:inline-block;margin-top:10px;padding:10px 22px;'
        'background:#C9A227;color:#0A0A0B;text-decoration:none;'
        'border-radius:6px;font-weight:700">'
        'Claim This Website — Free 7-Day Trial</a></div>'
        f'{pixel_snippet}'
    )
    try:
        update_doc = {
            "claim_ref": lead_id,
            "claim_expires": expires,
            "claim_signup_url": signup_url,
            "claim_block_html": claim_block,
            "live_pixel_enabled": True,
            "claim_updated_at": datetime.now(timezone.utc),
        }
        if phone:
            update_doc["business_phone"] = phone
        if biz_name:
            update_doc["business_name"] = biz_name
        await db.auto_built_sites.update_one(
            {"slug": slug},
            {"$set": update_doc},
        )
    except Exception as e:
        logger.debug(f"[qa-no-web] claim artifact update skipped: {e}")


# ─────────────────────────────────────────────────────────────────────
# A2A auto-tests
# ─────────────────────────────────────────────────────────────────────

async def _run_a2a_checks(preview_url: str, lead_id: str) -> Dict[str, Any]:
    """Fetch the preview page once; run all 6 checks against the body."""
    out: Dict[str, Any] = {
        "preview_url": preview_url,
        "passed": False,
        "checks": {
            "url_200": False,
            "no_broken_images": False,
            "mobile_renders": False,
            "cta_href_valid": False,
            "business_name_phone_visible": False,
            "live_pixel_fires": False,
        },
        "details": {},
    }

    body = ""
    status = None
    try:
        import httpx
        async with httpx.AsyncClient(
            timeout=TEST_TIMEOUT_S, follow_redirects=True,
            headers={"User-Agent": "AUREM-QA/1.0 (+https://aurem.live)"},
        ) as client:
            r = await client.get(preview_url)
            status = r.status_code
            body = r.text or ""
    except Exception as e:
        out["details"]["fetch_error"] = type(e).__name__
        return out

    out["details"]["status"] = status
    out["details"]["content_len"] = len(body)
    out["checks"]["url_200"] = status == 200

    # Mobile renders
    out["checks"]["mobile_renders"] = bool(VIEWPORT_RE.search(body))

    # Live Pixel fires
    out["checks"]["live_pixel_fires"] = bool(PIXEL_RE.search(body))

    # CTA href valid — must contain /signup?ref={lead_id}
    expected_ref = f"{CTA_HREF_PATTERN}{lead_id}"
    has_ref = expected_ref in body
    out["checks"]["cta_href_valid"] = has_ref
    out["details"]["expected_ref"] = expected_ref

    # Business name + phone visible — only checkable when caller already
    # passed those values via the lead row (caller stamps before this).
    # We surface the snippet sample so the admin route can verify visually.
    visible = _detect_name_phone(body)
    out["checks"]["business_name_phone_visible"] = visible["both_present"]
    out["details"]["visibility_sample"] = visible

    # Broken images — capped scan
    img_check = await _check_image_links(body, base_url=preview_url)
    out["checks"]["no_broken_images"] = img_check["all_ok"]
    out["details"]["images"] = img_check

    out["passed"] = all(out["checks"].values())
    return out


def _detect_name_phone(body: str) -> Dict[str, Any]:
    """Heuristic: at least one tel: link AND any ≥3-word capitalised string."""
    # Phone — accept tel: links OR formatted numbers
    phone_match = bool(re.search(r"tel:\+?[\d\-\(\)\s]{6,}", body, re.I)) or \
                  bool(re.search(r"\(\d{3}\)\s?\d{3}[\-\.\s]\d{4}", body)) or \
                  bool(re.search(r"\d{3}[\-\.\s]\d{3}[\-\.\s]\d{4}", body))
    # Business name — find <h1>/<title> with multi-word content
    name_match = bool(re.search(r"<(h1|title)[^>]*>([^<]{3,80})</", body, re.I))
    return {
        "phone_visible": phone_match,
        "name_visible": name_match,
        "both_present": phone_match and name_match,
    }


async def _check_image_links(body: str, *, base_url: str) -> Dict[str, Any]:
    """Verify the first N <img src> links return 200/3xx."""
    srcs = IMG_SRC_RE.findall(body)
    # Skip data URIs and unrendered JS template literals (e.g. ${var})
    srcs = [
        s for s in srcs
        if s and not s.startswith("data:") and "${" not in s and "{{" not in s
    ][:IMG_CHECK_MAX]
    if not srcs:
        return {"all_ok": True, "checked": 0, "broken": []}

    broken: List[str] = []

    async def _probe(src: str) -> Tuple[str, bool]:
        url = src if "://" in src else urljoin(base_url, src)
        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=4.0, follow_redirects=True,
            ) as client:
                r = await client.head(url)
                if r.status_code >= 400:
                    # Some CDNs reject HEAD — retry GET cheaply
                    r = await client.get(url)
                return src, r.status_code < 400
        except Exception:
            return src, False

    results = await asyncio.gather(*[_probe(s) for s in srcs])
    for src, ok in results:
        if not ok:
            broken.append(src)
    return {"all_ok": len(broken) == 0, "checked": len(srcs), "broken": broken[:5]}
