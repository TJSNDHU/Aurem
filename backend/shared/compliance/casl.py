"""
AUREM CASL/Anti-Spam Compliance Helpers
========================================
Every outbound message (email / whatsapp / sms) must pass through these
helpers. Source of truth for legally required footers.

Reads brand identity from env vars so a new tenant can override:
  AUREM_LEGAL_NAME, AUREM_LEGAL_ADDRESS, AUREM_UNSUBSCRIBE_URL,
  AUREM_COMPLIANCE_HST, AUREM_CONTACT_EMAIL

Canadian coverage:
  • CASL (Canada's Anti-Spam Legislation) — Section 6(6) B2B implied consent
  • PIPEDA — privacy language in email footer
  • CRA HST — business number referenced for audit
"""
import os

LEGAL_NAME = os.environ.get("AUREM_LEGAL_NAME", "AUREM Intelligence AI | Polaris Built Inc.")
LEGAL_ADDRESS = os.environ.get("AUREM_LEGAL_ADDRESS", "7221 Sigsbee Dr, Mississauga, ON L4T 3L6")
UNSUBSCRIBE_URL = os.environ.get("AUREM_UNSUBSCRIBE_URL", "https://aurem.live/unsubscribe")
CONTACT_EMAIL = os.environ.get("AUREM_CONTACT_EMAIL", "ora@aurem.live")
HST_NUMBER = os.environ.get("AUREM_COMPLIANCE_HST", "769426800 RT0001")


def email_footer_html(lead_id: str = "") -> str:
    """Append this HTML block to every outbound marketing email."""
    unsub = f"{UNSUBSCRIBE_URL}?lead={lead_id}" if lead_id else UNSUBSCRIBE_URL
    return f"""
<hr style="border:none;border-top:1px solid #e5e5e5;margin:24px 0 12px 0"/>
<div style="color:#888;font-size:11px;line-height:1.5;font-family:Arial,sans-serif">
  {LEGAL_NAME}<br/>
  {LEGAL_ADDRESS}<br/>
  <a href="mailto:{CONTACT_EMAIL}" style="color:#888">{CONTACT_EMAIL}</a>
  &nbsp;·&nbsp;
  <a href="{unsub}" style="color:#888">Unsubscribe</a><br/>
  <em>B2B communication under CASL Section 6(6) implied consent.</em>
</div>""".strip()


def email_footer_text(lead_id: str = "") -> str:
    """Plain-text equivalent for plain-text email bodies."""
    unsub = f"{UNSUBSCRIBE_URL}?lead={lead_id}" if lead_id else UNSUBSCRIBE_URL
    return (
        f"\n\n---\n{LEGAL_NAME}\n{LEGAL_ADDRESS}\n"
        f"{CONTACT_EMAIL} · Unsubscribe: {unsub}\n"
        f"B2B communication under CASL Section 6(6)."
    )


def sms_footer() -> str:
    """Short CASL footer for SMS/WhatsApp (160-char budget — keep tight)."""
    return "Reply STOP to unsubscribe. AUREM Intelligence AI, Mississauga ON."


def wrap_email_html(body_html: str, lead_id: str = "") -> str:
    """Inject the footer into an email HTML body, idempotent."""
    if "unsubscribe" in (body_html or "").lower():
        return body_html
    return (body_html or "") + email_footer_html(lead_id)


def wrap_sms(body: str) -> str:
    """Append SMS footer if missing, respecting length budget."""
    if "stop" in (body or "").lower() and "unsubscribe" in (body or "").lower():
        return body
    footer = sms_footer()
    # If total would exceed 320 chars (2 SMS segments), truncate body
    max_body = 320 - len(footer) - 2
    body = (body or "")[:max_body].rstrip()
    return f"{body}\n{footer}"


def wrap_whatsapp(body: str) -> str:
    """WhatsApp supports longer messages; always include CASL footer."""
    if "stop" in (body or "").lower() and "unsubscribe" in (body or "").lower():
        return body
    return f"{(body or '').rstrip()}\n\n{sms_footer()}"


def compliance_snapshot() -> dict:
    """Expose current compliance configuration for /api/compliance/status."""
    return {
        "legal_name": LEGAL_NAME,
        "legal_address": LEGAL_ADDRESS,
        "unsubscribe_url": UNSUBSCRIBE_URL,
        "contact_email": CONTACT_EMAIL,
        "hst_number": HST_NUMBER,
        "casl_section": "6(6) implied consent (B2B)",
        "pipeda_notice": "Personal information handled under PIPEDA compliance framework",
    }
