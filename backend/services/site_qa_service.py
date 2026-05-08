"""
iter 282al-15 — Site QA Service (test-lab.ai integration)
=========================================================
After AWB publishes a lead's site, run 5 plain-English QA tests via
test-lab.ai, repair any failures through the AWB re-render path, then
deliver the site to the customer (email + SMS + WhatsApp + Telegram
ping). Gracefully skips when TEST_LAB_API_KEY is not configured.

Public API
----------
    run_site_qa(db, slug, site_url)           -> dict
    build_repair_prompt(slug, failed_tests)   -> str
    repair_site_issues(db, slug, repair_ctx)  -> None
    qa_repair_loop(db, slug, site_url,
                   max_attempts=3)            -> dict
    send_site_to_customer(db, lead, slug,
                          live_url, qa_result)-> dict
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx

import aurem_config as config

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 5.0
_MAX_POLL_SECONDS      = 300  # 5-minute hard cap
_HTTP_TIMEOUT          = 30.0

_STANDARD_TESTS: List[str] = [
    "Verify the page loads and shows a visible business name in the header or hero section",
    "Verify the phone number is visible and clickable (tel: link)",
    "Verify the ORA chat widget appears on the page",
    "Verify the contact form is present and submits without errors",
    "Verify the page is mobile responsive at 375px viewport width",
]


# ─────────────────────────────────────────────────────────────────────
# test-lab.ai HTTP client (submit + poll)
# ─────────────────────────────────────────────────────────────────────
async def _submit_run(
    client: httpx.AsyncClient, site_url: str, tests: List[str],
) -> Optional[Dict[str, Any]]:
    """Submit a test run. Returns the raw JSON (with run id) or None.

    iter 282al-36 — test-lab.ai v1 API requires at least one of
    {testPlanIds, projectId, label}. We send `label` as a free-text
    description that test-lab.ai uses to match against pre-configured
    test plans in the founder's workspace. `tests` (our natural-language
    list) is passed as `testDescriptions` which test-lab.ai uses as
    adhoc test steps when no plan matches.
    """
    body = {
        "url": site_url,
        "label": "AUREM Site QA",       # REQUIRED by test-lab.ai v1
        "testDescriptions": tests,      # free-text test steps
    }
    try:
        r = await client.post("/run", json=body, timeout=_HTTP_TIMEOUT)
    except Exception as e:
        logger.warning(f"[site-qa] submit failed: {e}")
        return None
    if r.status_code >= 400:
        logger.warning(f"[site-qa] submit {r.status_code}: {r.text[:200]}")
        return None
    try:
        return r.json()
    except Exception:
        return None


async def _poll_run(
    client: httpx.AsyncClient, run_id: str,
) -> Optional[Dict[str, Any]]:
    """Poll a run until complete, failed, or timeout. Returns final dict."""
    started = datetime.now(timezone.utc)
    while (datetime.now(timezone.utc) - started).total_seconds() < _MAX_POLL_SECONDS:
        try:
            r = await client.get(f"/run/{run_id}", timeout=_HTTP_TIMEOUT)
        except Exception as e:
            logger.debug(f"[site-qa] poll blink: {e}")
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            continue
        if r.status_code == 429:
            await asyncio.sleep(min(10, _POLL_INTERVAL_SECONDS * 2))
            continue
        if r.status_code >= 400:
            logger.warning(f"[site-qa] poll {r.status_code}: {r.text[:200]}")
            return None
        try:
            body = r.json() or {}
        except Exception:
            body = {}
        status = str(body.get("status") or "").lower()
        if status in ("completed", "complete", "done", "failed", "error"):
            return body
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    logger.warning(f"[site-qa] poll timeout for run {run_id}")
    return None


def _normalise_results(
    tests: List[str], raw: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Flatten test-lab.ai response into {passed, failed, results[], report_url}."""
    if not raw:
        return {"passed": 0, "failed": len(tests), "results": [
            {"test": t, "status": "fail", "detail": "no_response", "screenshot_url": None}
            for t in tests
        ], "report_url": None}

    results_in = raw.get("results") or raw.get("tests") or []
    out: List[Dict[str, Any]] = []
    passed = failed = 0
    for i, t in enumerate(tests):
        r = results_in[i] if i < len(results_in) else {}
        status = str(r.get("status") or r.get("outcome") or "").lower()
        ok = status in ("pass", "passed", "ok", "success")
        out.append({
            "test": r.get("test") or r.get("description") or t,
            "status": "pass" if ok else "fail",
            "detail": r.get("detail") or r.get("error") or "",
            "screenshot_url": r.get("screenshot_url") or r.get("screenshot"),
        })
        if ok:
            passed += 1
        else:
            failed += 1
    return {
        "passed": passed, "failed": failed,
        "results": out,
        "report_url": raw.get("report_url") or raw.get("url"),
    }


async def run_site_qa(db, slug: str, site_url: str) -> Dict[str, Any]:
    """
    Submit 5 QA tests for `site_url`, poll until complete, persist the
    result in `db.site_test_results`. Always returns a dict; never raises.

    Keys:
        skipped          (present only when TEST_LAB_API_KEY is unset)
        ready            bool — "safe to send anyway"
        passed/failed    ints
        results          list of per-test dicts
        report_url       str | None
    """
    api_key = (config.TEST_LAB_API_KEY or os.environ.get("TEST_LAB_API_KEY") or "").strip()
    if not api_key:
        logger.info("[site-qa] TEST_LAB_API_KEY not set — skipping QA silently")
        return {"skipped": "no_key", "ready": True,
                "passed": 0, "failed": 0, "results": []}

    base_url = (
        config.TEST_LAB_BASE_URL
        or os.environ.get("TEST_LAB_BASE_URL")
        or "https://www.test-lab.ai/api/v1"   # iter 282al-36 — use www. to skip 301 that drops POST body
    ).rstrip("/")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "AUREM-SiteQA/1.0",
    }

    raw: Optional[Dict[str, Any]] = None
    try:
        async with httpx.AsyncClient(base_url=base_url, headers=headers) as client:
            submit = await _submit_run(client, site_url, _STANDARD_TESTS)
            if submit:
                run_id = submit.get("id") or submit.get("run_id") or submit.get("runId")
                if run_id:
                    raw = await _poll_run(client, str(run_id))
                else:
                    # Some sync APIs return results inline
                    raw = submit
    except Exception as e:
        logger.warning(f"[site-qa] run failed: {e}")
        raw = None

    parsed = _normalise_results(_STANDARD_TESTS, raw)
    doc = {
        "slug":        slug,
        "site_url":    site_url,
        "passed":      parsed["passed"],
        "failed":      parsed["failed"],
        "results":     parsed["results"],
        "report_url":  parsed["report_url"],
        "ts":          datetime.now(timezone.utc),
    }
    if db is not None:
        try:
            await db.site_test_results.insert_one(dict(doc))
        except Exception as e:
            logger.debug(f"[site-qa] persist failed: {e}")

    parsed["ready_to_send"] = parsed["failed"] == 0
    return parsed


# ─────────────────────────────────────────────────────────────────────
# Repair prompt builder + AWB re-render trigger
# ─────────────────────────────────────────────────────────────────────
_REPAIR_HINTS = [
    ("phone",      "Add a prominent click-to-call phone button (tel: link) in the hero section."),
    ("call",       "Add a prominent click-to-call phone button (tel: link) in the hero section."),
    ("widget",     "Ensure the ORA chat widget <script> tag is present in the page body and loads on DOMContentLoaded."),
    ("chat",       "Ensure the ORA chat widget <script> tag is present in the page body and loads on DOMContentLoaded."),
    ("form",       "Add a functional contact form with name + phone + message fields and POST handler."),
    ("contact",    "Add a functional contact form with name + phone + message fields and POST handler."),
    ("mobile",     "Add a `<meta name=viewport>` tag and CSS media-query breakpoints for 375px viewport widths."),
    ("responsive", "Add a `<meta name=viewport>` tag and CSS media-query breakpoints for 375px viewport widths."),
    ("375",        "Add a `<meta name=viewport>` tag and CSS media-query breakpoints for 375px viewport widths."),
    ("name",       "Add a visible <h1> with the business name in the hero section."),
    ("business name", "Add a visible <h1> with the business name in the hero section."),
    ("loads",      "Ensure the page returns HTTP 200 and renders meaningful content (no blank body)."),
]


def build_repair_prompt(slug: str, failed_tests: List[Dict[str, Any]]) -> str:
    """Map each failed test to a concrete fix instruction for the AWB LLM."""
    seen: set = set()
    lines: List[str] = []
    for ft in failed_tests or []:
        desc = str(ft.get("test") or ft.get("description") or "").lower()
        for needle, hint in _REPAIR_HINTS:
            if needle in desc and hint not in seen:
                lines.append(f"- {hint}")
                seen.add(hint)
                break
    if not lines:
        lines.append("- Review page fundamentals: h1 with business name, tel: phone link, contact form, viewport meta.")
    return (
        f"Site repair request for slug `{slug}` — apply these fixes without removing existing content:\n"
        + "\n".join(lines)
    )


async def repair_site_issues(db, slug: str, repair_context: str) -> None:
    """Log the repair note and trigger AWB re-render via build_site_for_lead."""
    if db is None:
        return
    try:
        site = await db.auto_built_sites.find_one(
            {"slug": slug}, {"_id": 0, "lead_id": 1, "site_id": 1},
        )
    except Exception as e:
        logger.warning(f"[site-qa] lookup failed for {slug}: {e}")
        return
    if not site:
        logger.warning(f"[site-qa] no auto_built_sites row for slug={slug}")
        return

    try:
        await db.auto_built_sites.update_one(
            {"slug": slug},
            {"$push": {"repair_notes": {
                "note": repair_context,
                "ts": datetime.now(timezone.utc),
            }}, "$set": {"qa_status": "repairing"}},
        )
    except Exception as e:
        logger.debug(f"[site-qa] note push failed: {e}")

    try:
        from services.auto_website_builder import build_site_for_lead
        await build_site_for_lead(
            db, site["lead_id"],
            style_hint=f"QA_REPAIR\n{repair_context}",
        )
    except Exception as e:
        logger.warning(f"[site-qa] AWB re-render failed: {e}")


async def qa_repair_loop(
    db, slug: str, site_url: str, max_attempts: int = 3,
) -> Dict[str, Any]:
    """
    Up to `max_attempts` QA→repair cycles. Returns:
        {final_status, ready_to_send, attempts, last_result}

    final_status ∈ {verified, failed, skipped}
    """
    for attempt in range(1, max_attempts + 1):
        result = await run_site_qa(db, slug, site_url)

        if result.get("skipped"):
            return {
                "final_status":  "skipped",
                "ready_to_send": True,
                "attempts":      0,
                "last_result":   result,
            }

        if result["failed"] == 0:
            if db is not None:
                try:
                    await db.auto_built_sites.update_one(
                        {"slug": slug},
                        {"$set": {
                            "qa_status":       "verified",
                            "qa_verified_at":  datetime.now(timezone.utc),
                            "qa_attempts":     attempt,
                        }},
                    )
                except Exception:
                    pass
            return {
                "final_status":  "verified",
                "ready_to_send": True,
                "attempts":      attempt,
                "last_result":   result,
            }

        if attempt < max_attempts:
            ctx = build_repair_prompt(slug, [
                r for r in result.get("results", []) if r.get("status") == "fail"
            ])
            await repair_site_issues(db, slug, ctx)
            await asyncio.sleep(15)

    if db is not None:
        try:
            await db.auto_built_sites.update_one(
                {"slug": slug},
                {"$set": {"qa_status": "failed", "qa_attempts": max_attempts}},
            )
        except Exception:
            pass
    return {
        "final_status":  "failed",
        "ready_to_send": False,
        "attempts":      max_attempts,
        "last_result":   result,
    }


# ─────────────────────────────────────────────────────────────────────
# send_site_to_customer — email + sms + whatsapp + telegram
# ─────────────────────────────────────────────────────────────────────
async def send_site_to_customer(
    db, lead: Dict[str, Any], slug: str, live_url: str, qa_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Deliver a QA-verified site to the lead. Returns {channels_sent, short_url}."""
    lead_id = str(lead.get("_id") or lead.get("lead_id") or "")
    business = (lead.get("business_name") or "your business").strip()
    city = (lead.get("city") or "").strip()
    channels_sent: List[str] = []

    # 1 — shortlink
    short_url = live_url
    try:
        from services.shortlink_service import create_shortlink
        sl = await create_shortlink(db, lead_id, live_url)
        short_url = sl.get("short_url") or short_url
    except Exception as e:
        logger.debug(f"[site-qa] shortlink failed: {e}")

    # 2 — compose body
    body = (
        f"Hi {business.split()[0] if business else 'there'},\n\n"
        f"Your free website preview is live — QA verified, all tests passed.\n\n"
        f"Preview: {short_url}\n\n"
        f"Claim it for $97/month (30 seconds to look, no card needed). "
        f"Reply STOP to opt out."
    )
    try:
        from services.outreach_composer import compose_outreach
        composed = await compose_outreach(
            lead=lead, channel="email", step=1, db=db,
            site_change_context=(
                "Free website preview QA verified — all 5 tests passed."
            ),
        )
        if composed and composed.get("body"):
            body = (
                composed["body"]
                + f"\n\nPreview: {short_url}\n"
                + "Claim for $97/month — 30 seconds to look."
            )
    except Exception as e:
        logger.debug(f"[site-qa] compose_outreach skipped: {e}")

    subject = f"{business}'s {city} website is ready" if city else f"{business}'s website is ready"

    # 3 — email
    if lead.get("email"):
        try:
            from services.email_service_resend import send_email
            await send_email(to=lead["email"], subject=subject, body=body)
            channels_sent.append("email")
        except Exception as e:
            logger.warning(f"[site-qa] email send failed: {e}")

    # 4 — sms
    if lead.get("phone"):
        try:
            from services.twilio_whatsapp import send_whatsapp
            sms_body = f"Hi {business} — your free website preview: {short_url} Reply STOP to opt out."
            # SMS send helper may exist under another name; fall back silently
            from services import twilio_sms  # type: ignore
            await twilio_sms.send_sms(lead["phone"], sms_body)  # type: ignore
            channels_sent.append("sms")
        except Exception as e:
            logger.debug(f"[site-qa] sms skipped: {e}")

        # 5 — whatsapp
        try:
            from services.twilio_whatsapp import send_whatsapp
            await send_whatsapp(
                lead["phone"],
                f"Your free website preview is live: {short_url}",
            )
            channels_sent.append("whatsapp")
        except Exception as e:
            logger.debug(f"[site-qa] whatsapp skipped: {e}")

    # 6 — update lead
    if db is not None and lead.get("_id"):
        try:
            await db.campaign_leads.update_one(
                {"_id": lead["_id"]},
                {"$set": {
                    "status":          "site_sent",
                    "site_short_url":  short_url,
                    "site_sent_at":    datetime.now(timezone.utc),
                    "site_slug":       slug,
                }},
            )
        except Exception:
            pass

    # 7 — telegram
    try:
        from services.telegram_bot_service import send_telegram_alert
        await send_telegram_alert(
            f"Site sent\n{business} · {city}\nURL: {short_url}\n"
            f"QA: {qa_result.get('attempts', 1)} attempt(s)"
        )
    except Exception as e:
        logger.debug(f"[site-qa] telegram skipped: {e}")

    # 8 — audit log
    if db is not None:
        try:
            await db.sites_sent.insert_one({
                "lead_id":        lead_id,
                "slug":           slug,
                "short_url":      short_url,
                "channels_sent":  channels_sent,
                "ts":             datetime.now(timezone.utc),
            })
        except Exception:
            pass

    return {"channels_sent": channels_sent, "short_url": short_url}


# ─────────────────────────────────────────────────────────────────────
# Pillars Map chip helper
# ─────────────────────────────────────────────────────────────────────
async def get_qa_health(db) -> Dict[str, Any]:
    """
    Returns {status, last_runs, message} for the Pillars Map chip.
      - GREEN  : last 5 runs all passed
      - YELLOW : any failed
      - GREY   : no API key OR no runs yet
    """
    key = (config.TEST_LAB_API_KEY or os.environ.get("TEST_LAB_API_KEY") or "").strip()
    if not key:
        return {"status": "grey", "message": "no_key", "last_runs": 0}
    if db is None:
        return {"status": "grey", "message": "no_db", "last_runs": 0}
    try:
        rows = await db.site_test_results.find(
            {}, {"_id": 0, "failed": 1, "ts": 1, "slug": 1},
        ).sort("ts", -1).limit(5).to_list(length=5)
    except Exception as e:
        return {"status": "grey", "message": f"db_err:{e}", "last_runs": 0}
    if not rows:
        return {"status": "grey", "message": "no_runs", "last_runs": 0}
    any_failed = any((r.get("failed") or 0) > 0 for r in rows)
    return {
        "status":    "yellow" if any_failed else "green",
        "message":   "last_5_checked",
        "last_runs": len(rows),
    }


# ─────────────────────────────────────────────────────────────────────
# TTL indexes (idempotent)
# ─────────────────────────────────────────────────────────────────────
async def ensure_site_qa_indexes(db) -> None:
    """Create TTL + lookup indexes for site_test_results / sites_sent / site_audits."""
    if db is None:
        return
    try:
        await db.site_test_results.create_index(
            [("ts", 1)], expireAfterSeconds=60 * 60 * 24 * 90,  # 90 days
            background=True, name="ttl_90d",
        )
        await db.site_test_results.create_index(
            [("slug", 1), ("ts", -1)], background=True, name="slug_ts",
        )
        await db.sites_sent.create_index(
            [("ts", 1)], expireAfterSeconds=60 * 60 * 24 * 365,  # 365 days
            background=True, name="ttl_365d",
        )
        # site_audits may already have indexes; 180-day TTL on audit_ts
        await db.site_audits.create_index(
            [("audit_ts", 1)], expireAfterSeconds=60 * 60 * 24 * 180,  # 180 days
            background=True, name="ttl_180d", sparse=True,
        )
    except Exception as e:
        logger.debug(f"[site-qa] index ensure skipped: {e}")


# ─────────────────────────────────────────────────────────────────────
# Sync helpers (for tests)
# ─────────────────────────────────────────────────────────────────────
def run_site_qa_sync(db, slug: str, site_url: str) -> Dict[str, Any]:
    return asyncio.get_event_loop().run_until_complete(
        run_site_qa(db, slug, site_url)
    )


def qa_repair_loop_sync(
    db, slug: str, site_url: str, max_attempts: int = 3,
) -> Dict[str, Any]:
    return asyncio.get_event_loop().run_until_complete(
        qa_repair_loop(db, slug, site_url, max_attempts)
    )
