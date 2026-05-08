"""Shared helpers, templates, and constants for the Sales/Campaign routes.

Split from the former monolithic routers/campaign_router.py (2,068 LOC) as
part of Pillar 1 (Sales) logic modularization — iter 262.
"""
"""
AUREM Campaign Router — Outbound acquisition campaign management.
Handles lead scraping, email sequences, WhatsApp outreach, call scheduling,
campaign stats, CASL compliance, and do-not-contact list.
"""
import logging
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET")
        payload = jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")
# ══════════════════════════════════════════════
# WhatsApp Message Templates
# ══════════════════════════════════════════════
WHATSAPP_TEMPLATES = {
    "initial": (
        "Hi {first_name}\n\n"
        "This is ORA from AUREM — we're in Mississauga.\n\n"
        "I scanned {business_name}'s website and found "
        "{issues_count} issues affecting your Google ranking.\n\n"
        "Your score: {score}/100\n\n"
        "I can send you a free report showing exactly what to fix.\n\n"
        "Interested? Reply YES\n\n"
        "Reply STOP to opt out."
    ),
    "after_yes": (
        "Great!\n\n"
        "Here's your free website report:\n"
        "{report_link}\n\n"
        "Top issue found:\n"
        "{top_issue}\n\n"
        "AUREM fixes this automatically.\n"
        "$97 CAD/month. Cancel anytime.\n\n"
        "Want to see a quick demo?\n"
        "aurem.live/pricing\n\n"
        "Reply STOP to opt out."
    ),
    "followup": (
        "Hi {first_name}\n\n"
        "Just checking — did you get a chance to look at "
        "the report for {business_name}?\n\n"
        "Happy to answer any questions.\n\n"
        "— ORA, AUREM AI\n\n"
        "Reply STOP to opt out."
    ),
}

# Email subject line A/B options
EMAIL_SUBJECTS = {
    "outbound_1": [
        "Your website scored {score}/100 — free report inside",
        "Found {issues_count} issues on {business_name}'s website",
        "Quick question about {business_name}",
    ],
    "outbound_2": [
        "Did you see your website report?",
    ],
    "outbound_3": [
        "Last message from AUREM",
    ],
}

TARGET_CATEGORIES = [
    "hair salon", "spa", "beauty clinic", "physiotherapy",
    "dental clinic", "accountant", "bookkeeper",
    "HVAC contractor", "plumber", "real estate agent",
    "restaurant", "retail store",
]

# ══════════════════════════════════════════════
# Competitor Comparison Campaign Templates
# Position AUREM vs generic agencies — no names
# ══════════════════════════════════════════════

COMPETITOR_TEMPLATES = {
    "whatsapp": {
        "switch_pitch": (
            "Hi {first_name}\n\n"
            "Quick question — is your current web agency actually scanning your site every day?\n\n"
            "Most agencies charge $300+/month and only check once a quarter.\n\n"
            "AUREM scans your site DAILY, auto-fixes issues, and sends you a morning report — all for $97/month.\n\n"
            "Your current score: {score}/100\n"
            "Issues we found that your agency missed: {issues_count}\n\n"
            "Free report: {report_link}\n\n"
            "Reply YES to see the difference.\n"
            "Reply STOP to opt out."
        ),
        "post_demo": (
            "Hi {first_name}\n\n"
            "Thanks for checking out AUREM.\n\n"
            "Here's what we do differently than traditional agencies:\n\n"
            "They charge $2,000+ for a website audit.\n"
            "We do it in 30 seconds, for free.\n\n"
            "They take 2 weeks to fix issues.\n"
            "ORA deploys fixes same day.\n\n"
            "They send you a PDF report once a quarter.\n"
            "We send you a live dashboard + morning brief every day.\n\n"
            "Ready to switch? aurem.live/pricing\n\n"
            "Reply STOP to opt out."
        ),
        "price_compare": (
            "Hi {first_name}\n\n"
            "Honest question — what are you paying for web maintenance right now?\n\n"
            "Most businesses pay:\n"
            "- Agency retainer: $500-2,000/mo\n"
            "- SEO tools: $100-300/mo\n"
            "- Ad management: $500-1,500/mo\n\n"
            "AUREM replaces all three for $97/mo:\n"
            "- Daily scanning + auto-repair\n"
            "- SEO monitoring + fixes\n"
            "- AI outreach to new leads\n"
            "- Voice AI for incoming calls\n\n"
            "See your site's score: {report_link}\n\n"
            "Reply STOP to opt out."
        ),
    },
    "email": {
        "switch_subject_lines": [
            "Is your web agency actually checking your site?",
            "What your current agency isn't telling you",
            "{business_name} — we found {issues_count} issues your agency missed",
            "Replace your $2,000/month agency with $97 AI",
        ],
        "switch_html": """
<div style="font-family:system-ui;max-width:600px;margin:0 auto;padding:24px;background:#fafafa;">
  <div style="background:#0A0A0F;border-radius:16px;padding:32px;color:#E8E4D9;">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#D4B977,#B19A5E);display:inline-flex;align-items:center;justify-content:center;font-weight:900;font-size:20px;color:#0A0A00;">A</div>
    </div>
    <h1 style="font-size:20px;text-align:center;margin-bottom:8px;">Hi {{first_name}},</h1>
    <p style="color:#8A8473;text-align:center;font-size:14px;margin-bottom:24px;">We scanned {{website}} and found something interesting.</p>
    
    <div style="background:rgba(255,107,0,0.08);border:1px solid rgba(255,107,0,0.15);border-radius:12px;padding:20px;margin-bottom:20px;">
      <p style="color:#FF6B00;font-weight:700;margin-bottom:8px;">Your site has {{issues_count}} issues</p>
      <p style="color:#8A8473;font-size:13px;">These are actively hurting your Google ranking. Most web agencies only catch these during quarterly reviews — by then you've already lost traffic.</p>
    </div>

    <h3 style="font-size:15px;margin-bottom:12px;">Traditional Agency vs AUREM</h3>
    <table style="width:100%;font-size:13px;color:#8A8473;border-collapse:collapse;">
      <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
        <td style="padding:8px 0;"></td>
        <td style="padding:8px 0;color:#E05252;font-weight:600;">Typical Agency</td>
        <td style="padding:8px 0;color:#68DA8D;font-weight:600;">AUREM</td>
      </tr>
      <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
        <td style="padding:8px 0;">Site scanning</td>
        <td style="padding:8px 0;">Quarterly</td>
        <td style="padding:8px 0;color:#68DA8D;">Every day</td>
      </tr>
      <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
        <td style="padding:8px 0;">Fix deployment</td>
        <td style="padding:8px 0;">2-4 weeks</td>
        <td style="padding:8px 0;color:#68DA8D;">Same day</td>
      </tr>
      <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
        <td style="padding:8px 0;">Reporting</td>
        <td style="padding:8px 0;">PDF quarterly</td>
        <td style="padding:8px 0;color:#68DA8D;">Live dashboard + daily brief</td>
      </tr>
      <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
        <td style="padding:8px 0;">Lead generation</td>
        <td style="padding:8px 0;">Manual</td>
        <td style="padding:8px 0;color:#68DA8D;">AI-powered autonomous</td>
      </tr>
      <tr>
        <td style="padding:8px 0;font-weight:600;">Monthly cost</td>
        <td style="padding:8px 0;color:#E05252;font-weight:600;">$500-2,000</td>
        <td style="padding:8px 0;color:#68DA8D;font-weight:600;">$97</td>
      </tr>
    </table>

    <div style="text-align:center;margin-top:24px;">
      <a href="https://aurem.live/pricing" style="display:inline-block;background:linear-gradient(135deg,#D4AF37,#8B6914);color:#0A0A00;padding:12px 32px;border-radius:12px;font-weight:700;text-decoration:none;font-size:14px;">See Your Free Report</a>
    </div>

    <p style="color:#5A5468;font-size:11px;text-align:center;margin-top:24px;">
      AUREM AI — Mississauga, ON<br/>
      <a href="{{unsubscribe_link}}" style="color:#5A5468;">Unsubscribe</a>
    </p>
  </div>
</div>
""",
    },
    "sms": {
        "switch_pitch": "Hi {first_name}, your website has {issues_count} issues a regular agency would miss. AUREM catches them daily for $97/mo. Free report: aurem.live/report/{lead_id}",
    },
    "voice": {
        "switch_script": (
            "Hi {first_name}, this is O R A from AUREM. "
            "I noticed {business_name} is currently using a web agency — and I found {issues_count} issues they missed on your site. "
            "Most agencies only check quarterly. We scan every day and fix issues the same day. "
            "Would you like to see a free comparison report? "
            "Press 1 for yes, press 2 to opt out."
        ),
    },
}
def _get_today_schedule():
    return [
        {"time": "9:00 AM", "task": "Scout scraping — find new businesses"},
        {"time": "10:00 AM", "task": "Website scanning — score new leads"},
        {"time": "11:00 AM", "task": "Outbound calls start"},
        {"time": "2:00 PM", "task": "Email follow-ups"},
        {"time": "4:00 PM", "task": "WhatsApp messages"},
    ]

