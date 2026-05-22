"""
ORA First Contact Email Service
================================
Sends a professional welcome email to every new lead captured via Live Chat,
WhatsApp, or any omnichannel entry point. Uses Resend API.
"""
import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


FIRST_CONTACT_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#050507;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#050507;padding:40px 20px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#0C0C14;border:1px solid rgba(212,175,55,0.15);border-radius:16px;overflow:hidden;">

        <!-- Header -->
        <tr><td style="padding:32px 40px 20px;text-align:center;">
          <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#D4AF37,#8B6914);display:inline-flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:#050507;">A</div>
          <h1 style="margin:16px 0 0;font-size:22px;font-weight:700;color:#D4AF37;letter-spacing:0.05em;">Welcome to AUREM</h1>
          <p style="margin:6px 0 0;font-size:12px;color:#9A9490;letter-spacing:0.1em;">THE AI EMPLOYEE THAT NEVER SLEEPS</p>
        </td></tr>

        <!-- Divider -->
        <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid rgba(212,175,55,0.12);margin:0;"></td></tr>

        <!-- Body -->
        <tr><td style="padding:28px 40px;">
          <p style="font-size:15px;color:#E8E0D0;line-height:1.7;margin:0 0 16px;">
            Hi {name},
          </p>
          <p style="font-size:14px;color:#C8C0B0;line-height:1.7;margin:0 0 16px;">
            Thank you for connecting with AUREM. I'm ORA, your dedicated AI business assistant.
          </p>
          <p style="font-size:14px;color:#C8C0B0;line-height:1.7;margin:0 0 20px;">
            Based on our conversation, here's what I can do for you right now:
          </p>

          <!-- Value Props -->
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
            <tr>
              <td style="padding:12px 16px;background:rgba(212,175,55,0.06);border:1px solid rgba(212,175,55,0.1);border-radius:10px;margin-bottom:8px;">
                <p style="margin:0;font-size:13px;color:#D4AF37;font-weight:600;">Free System Scan</p>
                <p style="margin:4px 0 0;font-size:12px;color:#9A9490;">I'll analyze your website for security, performance, SEO, and accessibility issues in 60 seconds.</p>
              </td>
            </tr>
            <tr><td style="height:8px;"></td></tr>
            <tr>
              <td style="padding:12px 16px;background:rgba(74,222,128,0.06);border:1px solid rgba(74,222,128,0.1);border-radius:10px;">
                <p style="margin:0;font-size:13px;color:#4ADE80;font-weight:600;">Automatic Fixes</p>
                <p style="margin:4px 0 0;font-size:12px;color:#9A9490;">Found issues? I generate and deploy root-cause fixes automatically. No developer needed.</p>
              </td>
            </tr>
            <tr><td style="height:8px;"></td></tr>
            <tr>
              <td style="padding:12px 16px;background:rgba(100,200,255,0.06);border:1px solid rgba(100,200,255,0.1);border-radius:10px;">
                <p style="margin:0;font-size:13px;color:#64C8FF;font-weight:600;">24/7 Business Automation</p>
                <p style="margin:4px 0 0;font-size:12px;color:#9A9490;">From invoicing to lead scoring to morning briefings &mdash; AUREM runs your business while you sleep.</p>
              </td>
            </tr>
          </table>

          <!-- CTA -->
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td align="center" style="padding:8px 0 20px;">
              <a href="https://aurem.live" style="display:inline-block;padding:14px 40px;border-radius:10px;background:linear-gradient(135deg,#D4AF37,#8B6914);color:#050507;font-size:14px;font-weight:700;text-decoration:none;letter-spacing:0.05em;">
                Start Your Free Trial
              </a>
            </td></tr>
          </table>

          <p style="font-size:13px;color:#C8C0B0;line-height:1.7;margin:0 0 8px;">
            Plans start at <strong style="color:#D4AF37;">$97 CAD/month</strong>. No contracts. Cancel anytime.
          </p>
          <p style="font-size:13px;color:#9A9490;line-height:1.7;margin:0;">
            Reply to this email anytime &mdash; I'm always here.
          </p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid rgba(212,175,55,0.08);margin:0;"></td></tr>
        <tr><td style="padding:20px 40px 28px;text-align:center;">
          <p style="margin:0;font-size:10px;color:#5A5468;letter-spacing:0.1em;">
            AUREM AI &mdash; Polaris Built Inc. | Mississauga, Ontario, Canada
          </p>
          <p style="margin:6px 0 0;font-size:9px;color:#3A3448;">
            You're receiving this because you connected with ORA at aurem.live.
            <a href="https://aurem.live" style="color:#D4AF37;text-decoration:none;">Unsubscribe</a>
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""

FIRST_CONTACT_TEXT = """Welcome to AUREM, {name}!

Thank you for connecting with us. I'm ORA, your AI business assistant.

Here's what I can do for you:
- Free System Scan: Analyze your website in 60 seconds
- Automatic Fixes: Root-cause repairs deployed automatically
- 24/7 Automation: Invoicing, leads, morning briefings

Start your free trial: https://aurem.live
Plans start at $97 CAD/month. No contracts.

Reply anytime - I'm always here.

AUREM AI - Polaris Built Inc., Mississauga, Ontario, Canada
"""


async def send_first_contact_email(
    to_email: str,
    to_name: str = "there",
    channel: str = "live_chat",
) -> dict:
    """
    Send the First Contact welcome email to a new lead.
    Uses Resend API. Falls back gracefully if not configured.
    """
    try:
        from services.email_engine import resend  # iter 326x defensive
        api_key = os.environ.get("RESEND_API_KEY", "")
        if not api_key:
            logger.warning("[FirstContact] RESEND_API_KEY not set")
            return {"success": False, "error": "RESEND_API_KEY not configured"}

        resend.api_key = api_key

        # Use verified domain or Resend default
        from_email = "ORA <ora@aurem.live>"
        # If domain not verified, fall back to Resend's shared domain
        try:
            result = resend.Emails.send({
                "from": from_email,
                "to": [to_email],
                "subject": f"Welcome to AUREM, {to_name} — Your AI Employee Awaits",
                "html": FIRST_CONTACT_HTML.replace("{name}", to_name),
                "text": FIRST_CONTACT_TEXT.replace("{name}", to_name),
                "tags": [
                    {"name": "channel", "value": channel},
                    {"name": "type", "value": "first_contact"},
                ],
            })
            logger.info(f"[FirstContact] Email sent to {to_email} via {channel}: {result}")
            return {"success": True, "email_id": result.get("id", ""), "to": to_email}
        except Exception as send_err:
            # If aurem.live not verified, try with Resend's default
            if "not verified" in str(send_err).lower() or "not a verified" in str(send_err).lower():
                logger.warning(f"[FirstContact] Domain not verified, trying onboarding@resend.dev")
                result = resend.Emails.send({
                    "from": "AUREM ORA <onboarding@resend.dev>",
                    "to": [to_email],
                    "subject": f"Welcome to AUREM, {to_name} — Your AI Employee Awaits",
                    "html": FIRST_CONTACT_HTML.replace("{name}", to_name),
                    "text": FIRST_CONTACT_TEXT.replace("{name}", to_name),
                })
                return {"success": True, "email_id": result.get("id", ""), "to": to_email, "fallback_domain": True}
            raise

    except Exception as e:
        logger.error(f"[FirstContact] Failed to send to {to_email}: {e}")
        return {"success": False, "error": str(e)}


async def auto_send_first_contact(db, email: str, name: str = "there", channel: str = "live_chat"):
    """
    Auto-trigger: checks if we've already sent a first contact to this email.
    If not, sends and records it.
    """
    if not db or not email:
        return

    try:
        existing = await db.first_contact_emails.find_one({"email": email})
        if existing:
            logger.debug(f"[FirstContact] Already sent to {email}, skipping")
            return

        result = await send_first_contact_email(email, name, channel)

        await db.first_contact_emails.insert_one({
            "email": email,
            "name": name,
            "channel": channel,
            "result": result,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })

        return result
    except Exception as e:
        logger.warning(f"[FirstContact] Auto-send error: {e}")
