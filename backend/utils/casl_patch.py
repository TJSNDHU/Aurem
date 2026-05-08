"""
Global CASL Patch
=================
Monkey-patches outbound send SDKs at startup so EVERY outbound message
automatically gets the legally required CASL footer — no matter which
call-site triggers it.

Covers:
  • resend.Emails.send  — 22 call-sites across services/routers
  • Twilio client.messages.create — wrapped at higher level already
  • WHAPI / Gmail helpers  — wrapped in their own helpers already

Idempotent: `wrap_email_html` / `wrap_sms` / `wrap_whatsapp` already skip
if a CASL footer is already present.
"""
import logging
import os

logger = logging.getLogger(__name__)


def install_casl_patches():
    """Call once at app startup. Safe to call multiple times (idempotent)."""

    # ═══ 1. Resend.Emails.send — patch globally ═══
    try:
        import resend
        from services.casl_compliance import wrap_email_html, email_footer_text

        if getattr(resend.Emails, "_aurem_casl_patched", False):
            return

        _orig_send = resend.Emails.send

        def _casl_send(params):
            try:
                lead_id = ""
                to_list = params.get("to") if isinstance(params, dict) else None
                if isinstance(to_list, list) and to_list:
                    lead_id = str(to_list[0])
                elif isinstance(to_list, str):
                    lead_id = to_list

                if isinstance(params, dict):
                    if params.get("html"):
                        params["html"] = wrap_email_html(params["html"], lead_id=lead_id)
                    if params.get("text") and "unsubscribe" not in (params["text"] or "").lower():
                        params["text"] = (params["text"] or "") + email_footer_text(lead_id)
            except Exception as e:
                logger.debug(f"[CASL patch] email wrap skipped: {e}")
            return _orig_send(params)

        resend.Emails.send = _casl_send
        resend.Emails._aurem_casl_patched = True
        logger.info("[CASL patch] Resend.Emails.send wrapped with CASL footer")
    except Exception as e:
        logger.warning(f"[CASL patch] Resend patch failed: {e}")

    # Twilio SMS / WhatsApp already wrapped in services/twilio_service.py
    # WHAPI already wrapped in services/whapi_service.py
    # Gmail already wrapped in services/aurem_commercial/gmail_service.py
