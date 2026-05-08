"""
AUREM Prospect Website Audit — Section 5 of growth-engine upgrade
==================================================================
Runs against a single PROSPECT URL (lead's existing website) and emits:
  • load_time_ms      — full HTTP GET wall-clock
  • ssl_valid         — HTTPS reachable, cert not expired, not self-signed
  • mobile_responsive — viewport meta tag present + width:device-width
  • cta_present       — at least one CTA-shaped link/button (`tel:`,
                        `mailto:`, "contact", "book", "quote", "call now")
  • issues_count      — total red flags (used by templates)
  • issues_summary    — humanised list ("No SSL", "Slow site", …)

Produces a `WebsiteAudit` dict the QA pipeline persists onto the lead
under `website_audit` and uses to render the public report page at
`aurem.live/report/{lead_id}`.

Also exposes `qa_has_website_checklist(lead, audit)` — the A2A gate
every "has_website" lead must clear before Council promotion + Blast.
"""
from __future__ import annotations

import re
import ssl
import socket
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Reasonable bounds for a small-business website
LOAD_TIME_TIMEOUT_S = 10.0
SLOW_THRESHOLD_MS = 3500   # spec says "avg 2.1s" — flag anything >3.5s

CTA_PATTERNS = [
    re.compile(r"\btel:\+?[\d\-\(\)\s]{6,}", re.I),
    re.compile(r"\bmailto:[a-z0-9._%+\-]+@", re.I),
    re.compile(r"\b(book\s+now|book\s+online|book\s+a)\b", re.I),
    re.compile(r"\b(get\s+a?\s*quote|free\s+quote|request\s+quote)\b", re.I),
    re.compile(r"\b(call\s+now|call\s+today|call\s+us)\b", re.I),
    re.compile(r"\b(contact\s+us|schedule|appointment)\b", re.I),
]
VIEWPORT_RE = re.compile(
    r'<meta[^>]+name=["\']viewport["\'][^>]+content=["\'][^"\']*'
    r'width=device-width', re.I,
)


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

async def audit_website(url: str) -> Dict[str, Any]:
    """Audit a single prospect website. Always returns a structured dict.

    Never raises — all probes fail-soft. Caller should treat fields with
    `None` as "could not measure".
    """
    out: Dict[str, Any] = {
        "url": url,
        "load_time_ms": None,
        "ssl_valid": False,
        "mobile_responsive": False,
        "cta_present": False,
        "http_status": None,
        "content_len": 0,
        "issues_count": 0,
        "issues_summary": [],
        "audited_at": datetime.now(timezone.utc).isoformat(),
    }
    if not url:
        out["issues_summary"].append("No website URL")
        out["issues_count"] += 1
        return out

    parsed = urlparse(url if "://" in url else f"https://{url}")
    full_url = parsed.geturl()

    # 1. SSL — only meaningful if HTTPS is reachable
    ssl_task = _check_ssl(parsed.netloc) if parsed.scheme == "https" else _placeholder()
    # 2. HTTP fetch + load time (one round-trip drives 4 checks)
    fetch_task = _fetch_with_timing(full_url)

    ssl_res, fetch_res = await asyncio.gather(ssl_task, fetch_task)

    out["ssl_valid"] = bool(ssl_res.get("valid"))
    if not out["ssl_valid"]:
        out["issues_summary"].append("Insecure / no SSL")
        out["issues_count"] += 1

    out["load_time_ms"] = fetch_res.get("load_time_ms")
    out["http_status"] = fetch_res.get("status")
    body = fetch_res.get("body") or ""
    out["content_len"] = len(body)

    if out["http_status"] != 200:
        out["issues_summary"].append(f"Site returns {out['http_status']}")
        out["issues_count"] += 1

    if out["load_time_ms"] is not None and out["load_time_ms"] > SLOW_THRESHOLD_MS:
        out["issues_summary"].append(
            f"Slow load — {out['load_time_ms']/1000:.1f}s vs avg 2.1s"
        )
        out["issues_count"] += 1

    # 3. Mobile responsive — viewport meta tag scan
    if body:
        out["mobile_responsive"] = bool(VIEWPORT_RE.search(body))
        if not out["mobile_responsive"]:
            out["issues_summary"].append("Not mobile-responsive")
            out["issues_count"] += 1

    # 4. CTA — any tel/mailto/call/book/quote pattern
    if body:
        out["cta_present"] = any(p.search(body) for p in CTA_PATTERNS)
        if not out["cta_present"]:
            out["issues_summary"].append("No clear call-to-action")
            out["issues_count"] += 1

    return out


def qa_has_website_checklist(
    lead: Dict[str, Any], audit: Dict[str, Any],
) -> Dict[str, Any]:
    """A2A pre-Council checklist for a `has_website` lead.

    Returns:
      {
        "passed": bool,
        "checks": {
            email_renders: bool,
            sms_under_160: bool,
            retell_script_populated: bool,
            report_url_ok: bool,
            phone_is_mobile: bool,
        },
        "failures": [str, ...],
      }
    All 5 must pass for `passed=True`.
    """
    checks: Dict[str, bool] = {}
    failures: List[str] = []

    # 1. Email renders with business name
    biz = (lead.get("business_name") or lead.get("name") or "").strip()
    email_subject = lead.get("blast_email_subject") or ""
    email_body = lead.get("blast_email_body") or ""
    has_biz_token = bool(biz) and (biz in email_subject or biz in email_body)
    checks["email_renders"] = has_biz_token
    if not has_biz_token:
        failures.append("email_missing_business_name")

    # 2. SMS <160 chars
    sms = lead.get("blast_sms_body") or ""
    checks["sms_under_160"] = 0 < len(sms) <= 160
    if not checks["sms_under_160"]:
        failures.append(f"sms_length_{len(sms)}")

    # 3. Retell script has [name] + [issue] populated
    script = lead.get("blast_retell_script") or ""
    name_token = (lead.get("first_name")
                  or (lead.get("owner_name") or "").split(" ")[0]
                  or "")
    has_name = bool(name_token) and name_token in script
    has_issue = (audit.get("issues_count") or 0) > 0 and any(
        s for s in audit.get("issues_summary", []) if s and s in script
    )
    checks["retell_script_populated"] = has_name and has_issue
    if not has_name:
        failures.append("retell_missing_name")
    if not has_issue:
        failures.append("retell_missing_issue")

    # 4. Report URL returns 200 — caller verifies separately; trust flag
    checks["report_url_ok"] = bool(lead.get("report_url_status_ok"))
    if not checks["report_url_ok"]:
        failures.append("report_url_unverified")

    # 5. Phone is mobile — landline = email-only flag (sort_email_only=True)
    is_mobile = not bool(lead.get("sort_email_only"))
    phone_e164 = lead.get("phone_e164") or ""
    checks["phone_is_mobile"] = bool(phone_e164) and is_mobile
    if not checks["phone_is_mobile"]:
        failures.append("phone_landline_or_missing")

    return {
        "passed": all(checks.values()),
        "checks": checks,
        "failures": failures,
    }


def get_owner_name_or_default(lead: Dict[str, Any]) -> str:
    """Pull owner first-name from any populated source. Fallback: 'there'."""
    raw = (lead.get("owner_first_name")
           or lead.get("first_name")
           or lead.get("owner_name")
           or "")
    if not raw:
        return "there"
    first = str(raw).strip().split()[0]
    return first or "there"


async def render_blast_artifacts(
    lead: Dict[str, Any],
    audit: Dict[str, Any],
    *,
    base_report_url: str = "https://aurem.live",
) -> Dict[str, Any]:
    """Compose email/SMS/Retell payloads ready for the A2A checklist.

    Mutates `lead` with:
      blast_email_subject, blast_email_body, blast_sms_body,
      blast_retell_script, report_url, report_url_status_ok
    """
    biz = (lead.get("business_name") or lead.get("name") or "your business").strip()
    name = get_owner_name_or_default(lead)
    issues_n = audit.get("issues_count") or 0
    primary_issue = (audit.get("issues_summary") or [""])[0]

    # Specific number framing per spec ("Your site loads in Xs — avg 2.1s")
    load = audit.get("load_time_ms")
    if load and load > SLOW_THRESHOLD_MS:
        load_line = f"Your site loads in {load/1000:.1f}s — avg 2.1s."
    elif load:
        load_line = f"Your site loads in {load/1000:.1f}s."
    else:
        load_line = ""

    lead_id = lead.get("lead_id") or lead.get("phone_e164") or "x"
    report_url = f"{base_report_url}/report/{lead_id}"
    lead["report_url"] = report_url

    lead["blast_email_subject"] = f"{biz} — quick site audit"
    lead["blast_email_body"] = (
        f"Hi {name},\n\n"
        f"Ran a quick check on {biz}'s site. Found {issues_n} item"
        f"{'s' if issues_n != 1 else ''} worth a look. {load_line}\n\n"
        f"Full report (expires in 48 hours): {report_url}\n\n"
        f"— ORA / AUREM"
    )

    sms_body = (
        f"Hi {name}, ORA here. {biz} site has {issues_n} fixable issue"
        f"{'s' if issues_n != 1 else ''}. {report_url}"
    )
    if len(sms_body) > 160:
        sms_body = (f"Hi {name}, ORA here. {biz} site issues found. {report_url}")[:160]
    lead["blast_sms_body"] = sms_body

    retell_script = (
        f"Hi {name}, this is ORA from AUREM. I noticed {biz}'s website "
        f"{primary_issue.lower() if primary_issue else 'has a few items worth flagging'}. "
        f"Got 30 seconds for a no-pitch summary?"
    )
    lead["blast_retell_script"] = retell_script

    # Caller will set report_url_status_ok=True after /api/report/{slug} 200 OK
    return lead


async def verify_report_url(report_url: str) -> bool:
    """HEAD/GET the public report endpoint and confirm it returns 200."""
    if not report_url:
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            r = await client.get(report_url)
            return r.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────
# Internal probes
# ─────────────────────────────────────────────────────────────────────

async def _placeholder() -> Dict[str, Any]:
    return {"valid": False}


async def _check_ssl(host: str) -> Dict[str, Any]:
    """Real SSL handshake — checks expiry + chain. 3s max."""
    if not host:
        return {"valid": False}
    host_only = host.split(":")[0]
    loop = asyncio.get_running_loop()
    def _probe():
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host_only, 443), timeout=3) as sock:
                with ctx.wrap_socket(sock, server_hostname=host_only) as ssock:
                    cert = ssock.getpeercert()
                    not_after = cert.get("notAfter") if cert else None
                    if not not_after:
                        return {"valid": True}  # got handshake, no fields
                    # cryptography is heavyweight — quick string compare
                    return {"valid": True, "expires": not_after}
        except Exception as e:
            return {"valid": False, "reason": type(e).__name__}
    try:
        return await asyncio.wait_for(loop.run_in_executor(None, _probe), timeout=3.5)
    except asyncio.TimeoutError:
        return {"valid": False, "reason": "ssl_timeout"}


async def _fetch_with_timing(url: str) -> Dict[str, Any]:
    """GET with wall-clock + return body for body-level scans."""
    out = {"status": None, "body": "", "load_time_ms": None}
    try:
        import httpx
        t0 = time.perf_counter()
        async with httpx.AsyncClient(
            timeout=LOAD_TIME_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": "AUREM-QA/1.0 (+https://aurem.live)"},
        ) as client:
            r = await client.get(url)
            elapsed = (time.perf_counter() - t0) * 1000
            out["load_time_ms"] = round(elapsed, 1)
            out["status"] = r.status_code
            # Cap body to 800 KB — anything bigger is unreasonable for an audit
            text = r.text[:800_000]
            out["body"] = text
    except Exception as e:
        out["error"] = type(e).__name__
    return out
