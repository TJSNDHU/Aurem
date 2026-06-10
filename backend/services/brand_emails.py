"""
Brand Email Templates — iter 282g
=================================
Centralised renderer for the 4 branded HTML emails (iter 282g spec):

  • trial_ending   — T-1 to trial expiry, stats + urgency + upgrade
  • site_live      — AWB build complete, screenshot + what's included
  • site_down      — site monitor detected outage, red theme
  • password_reset — transactional, 1-hour expiry CTA

All share:
  * #0A0A0A dark bg
  * #F97316 orange primary + #EA580C secondary
  * Cinzel display heading
  * CASL-compliant Polaris Built Inc. footer + unsubscribe

Public API:
    render_trial_ending(user_doc, *, issues_fixed, score_delta,
                         uptime_pct, upgrade_url) -> str
    render_site_live(user_doc, *, site_url, screenshot_url,
                      portal_url) -> str
    render_site_down(*, site_url, status_code, status_text,
                      down_since, downtime_counter, incident_url,
                      unsubscribe_url) -> str
    render_password_reset(*, reset_url) -> str
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def _unsub_url(email: Optional[str], reason: str = "") -> str:
    base = os.environ.get("AUREM_PUBLIC_URL") or "https://aurem.live"
    q = f"?e={quote_plus(email)}" if email else ""
    if reason:
        q += ("&" if q else "?") + "src=" + quote_plus(reason)
    return f"{base.rstrip('/')}/unsubscribe{q}"


def _load(name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"[brand_emails] load {name} failed: {e}")
        return ""


def _fill(html: str, data: Dict[str, Any]) -> str:
    for k, v in data.items():
        html = html.replace("{{" + k + "}}", str(v if v is not None else ""))
    return html


# ─── Trial ending (T-1 day) ─────────────────────────────────────────────────
def render_trial_ending(
    user_doc: Dict[str, Any],
    *,
    issues_fixed: int = 0,
    score_delta: int = 0,
    uptime_pct: float = 100.0,
    upgrade_url: Optional[str] = None,
) -> str:
    first_name = (user_doc.get("first_name")
                   or (user_doc.get("name") or "").split(" ")[0]
                   or "there")
    biz = user_doc.get("business_name") or user_doc.get("company") or "your business"
    email = user_doc.get("email")
    base = os.environ.get("AUREM_PUBLIC_URL") or "https://aurem.live"
    return _fill(_load("trial_ending_email.html"), {
        "first_name": first_name,
        "business_name": biz,
        "issues_fixed": issues_fixed,
        "score_delta": score_delta,
        "uptime_pct": f"{uptime_pct:.1f}",
        "upgrade_url": upgrade_url or f"{base.rstrip('/')}/my/billing?src=trial_t1",
        "unsubscribe_url": _unsub_url(email, "trial_ending"),
    })


# ─── Site Is Live ───────────────────────────────────────────────────────────
def _screenshot_usable(url: Optional[str]) -> bool:
    """Return True iff `url` is a fetchable absolute image URL.

    Guards against the pre-fix case where R2 uploads fell back to
    `aurem.live/browser-screenshots/...` — that path hits the SPA and
    returns HTML, which Gmail/Outlook render as a broken image icon.
    Only accept presigned R2 URLs or an explicit public CDN origin.
    """
    if not url:
        return False
    if not url.startswith(("http://", "https://")):
        return False
    # Presigned R2 URLs (contain X-Amz-Signature) — always usable.
    if "X-Amz-Signature" in url or "r2.cloudflarestorage.com" in url:
        return True
    # Custom public R2 domain — trust if R2_PUBLIC_BASE env is set AND url
    # starts with it.
    public_base = os.environ.get("R2_PUBLIC_BASE", "").strip().rstrip("/")
    if public_base and url.startswith(public_base):
        return True
    # r2.dev pub URLs
    if ".r2.dev/" in url:
        return True
    # Known-bad fallback that used to be generated pre-iter282h:
    # aurem.live/browser-screenshots/... — this path hits the SPA, not R2.
    if "aurem.live/browser-screenshots" in url:
        return False
    # Any other absolute HTTPS URL — accept (customer may upload their own)
    return True


def render_site_live(
    user_doc: Dict[str, Any],
    *,
    site_url: str,
    screenshot_url: Optional[str] = None,
    portal_url: Optional[str] = None,
) -> str:
    first_name = (user_doc.get("first_name")
                   or (user_doc.get("name") or "").split(" ")[0]
                   or "there")
    biz = user_doc.get("business_name") or user_doc.get("company") or "your business"
    email = user_doc.get("email")
    base = os.environ.get("AUREM_PUBLIC_URL") or "https://aurem.live"

    screenshot_block = ""
    if _screenshot_usable(screenshot_url):
        screenshot_block = (
            '<tr><td style="padding:4px 32px 16px;">'
            f'<a href="{site_url}" target="_blank" rel="noopener noreferrer">'
            f'<img src="{screenshot_url}" alt="{biz} site preview" '
            'style="width:100%;max-width:456px;border-radius:10px;'
            'border:1px solid rgba(249,115,22,0.25);display:block;" />'
            '</a></td></tr>'
        )
    else:
        # Styled placeholder — no broken <img>, no "site preview" text
        # that could mislead if the image didn't render.
        screenshot_block = (
            '<tr><td style="padding:4px 32px 16px;">'
            '<div style="background:linear-gradient(135deg,#0A0A0A,#1A1A1A);'
            'border:1px solid rgba(249,115,22,0.25);border-radius:10px;'
            'padding:40px 24px;text-align:center;">'
            '<div style="font-family:\'Cinzel\',serif;font-size:16px;'
            'color:#F97316;letter-spacing:2px;margin-bottom:6px;">'
            f'{biz.upper()}</div>'
            '<div style="font-size:11px;color:#6A6070;letter-spacing:2px;'
            'text-transform:uppercase;">Live now</div>'
            '</div></td></tr>'
        )

    return _fill(_load("site_live_email.html"), {
        "first_name": first_name,
        "business_name": biz,
        "site_url": site_url,
        "screenshot_block": screenshot_block,
        "portal_url": portal_url or f"{base.rstrip('/')}/my",
        "unsubscribe_url": _unsub_url(email, "site_live"),
    })


# ─── Site Down Alert ────────────────────────────────────────────────────────
def render_site_down(
    *,
    site_url: str,
    status_code: int = 0,
    status_text: str = "connection failed",
    down_since: str = "",
    downtime_counter: str = "",
    incident_url: Optional[str] = None,
    to_email: Optional[str] = None,
) -> str:
    base = os.environ.get("AUREM_PUBLIC_URL") or "https://aurem.live"
    if not incident_url:
        incident_url = f"{base.rstrip('/')}/my/monitor"
    return _fill(_load("site_down_email.html"), {
        "site_url": site_url,
        "status_code": status_code or "—",
        "status_text": status_text,
        "down_since": down_since or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "downtime_counter": downtime_counter or "just now",
        "incident_url": incident_url,
        "unsubscribe_url": _unsub_url(to_email, "site_down"),
    })


# ─── Password Reset ─────────────────────────────────────────────────────────
def render_password_reset(*, reset_url: str) -> str:
    return _fill(_load("password_reset_email.html"), {
        "reset_url": reset_url,
    })


# ─── Repair Plan deliverable (iter D-77) ────────────────────────────────────
_SEVERITY_TONE = {
    "high":   {"label": "HIGH",   "color": "#ef4444", "bg": "rgba(239,68,68,0.10)"},
    "medium": {"label": "MEDIUM", "color": "#f59e0b", "bg": "rgba(245,158,11,0.10)"},
    "low":    {"label": "LOW",    "color": "#22c55e", "bg": "rgba(34,197,94,0.10)"},
}


def _score_color(score: int) -> str:
    if score >= 80:
        return "#22c55e"
    if score >= 50:
        return "#f59e0b"
    return "#ef4444"


def _render_plan_item(idx: int, item: Dict[str, Any]) -> str:
    """Render one plan card as an HTML table row block.
    `item` keys (per customer_website_repair_router): issue_title, severity, llm_response."""
    sev = str(item.get("severity") or "medium").lower()
    tone = _SEVERITY_TONE.get(sev, _SEVERITY_TONE["medium"])
    # The LLM body sometimes contains code fences — convert to a styled <pre>
    body = str(item.get("llm_response") or item.get("body") or "").strip()
    # Escape HTML so customer code samples don't render as markup
    import html as _html
    safe_body = _html.escape(body)
    # Light code-fence styling: preserve fenced blocks visually with monospace background
    safe_body = safe_body.replace("```", "")
    title = _html.escape(str(item.get("issue_title") or item.get("title") or "Issue"))
    return (
        '<tr><td style="padding:0 32px 14px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:#0A0A0A;border:1px solid {tone["color"]}33;border-left:3px solid {tone["color"]};border-radius:8px;">'
        '<tr><td style="padding:16px 18px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr>'
        f'<td style="font-size:11px;color:#6A6070;letter-spacing:2px;font-weight:700;">#{idx:02d}</td>'
        '<td align="right">'
        f'<span style="display:inline-block;background:{tone["bg"]};color:{tone["color"]};'
        f'font-size:10px;font-weight:700;letter-spacing:2px;padding:3px 10px;border-radius:99px;border:1px solid {tone["color"]}66;">'
        f'{tone["label"]}'
        '</span>'
        '</td></tr></table>'
        f'<div style="font-family:\'Cinzel\',serif;font-size:16px;color:#F2F2F2;margin:8px 0 10px;line-height:1.4;">{title}</div>'
        f'<pre style="font-family:\'Courier New\',monospace;font-size:12px;color:#E8E0D0;background:#000;border-radius:6px;padding:14px;margin:0;white-space:pre-wrap;word-break:break-word;line-height:1.6;">{safe_body}</pre>'
        '</td></tr></table>'
        '</td></tr>'
    )


def render_repair_plan(
    *,
    customer_email: Optional[str],
    website: str,
    audit: Dict[str, Any],
    plan: list,
    first_name: Optional[str] = None,
    portal_url: Optional[str] = None,
) -> str:
    """Render the customer-facing repair plan deliverable.

    `audit` carries `overall_score` + `issues`; `plan` is the list of
    LLM-generated items from `customer_website_repair_router._generate_repair_plan_via_llm`.

    No mocks: counts come straight from the inputs. If `plan` is empty
    the items block renders an honest empty notice instead of fake
    placeholder rows."""
    base = (os.environ.get("AUREM_PUBLIC_URL") or "https://aurem.live").rstrip("/")
    portal = portal_url or f"{base}/my/scans?src=repair_plan_email"
    score = int(audit.get("overall_score") or 0)
    issue_count = len(audit.get("issues") or [])

    if plan:
        items_html = "".join(_render_plan_item(i, item) for i, item in enumerate(plan, 1))
    else:
        items_html = (
            '<tr><td style="padding:0 32px 20px;">'
            '<div style="font-size:13px;color:#9A9490;background:#0A0A0A;'
            'border:1px dashed rgba(249,115,22,0.3);border-radius:8px;padding:24px;text-align:center;">'
            'No actionable items in this pass — the engine did not find any high-impact repairs '
            'for this URL in the current scan window. Re-run the scan in a few hours or contact '
            'us at <a href="mailto:hello@aurem.live" style="color:#F97316;text-decoration:none;">hello@aurem.live</a>.'
            '</div></td></tr>'
        )

    return _fill(_load("repair_plan_email.html"), {
        "first_name": first_name or "there",
        "website": website,
        "score": score,
        "score_color": _score_color(score),
        "issue_count": issue_count,
        "plan_count": len(plan),
        "plan_items_block": items_html,
        "portal_url": portal,
        "unsubscribe_url": _unsub_url(customer_email, "repair_plan"),
    })
