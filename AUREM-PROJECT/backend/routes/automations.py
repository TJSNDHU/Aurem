# ============================================================
# REROOTS — 28-DAY REPURCHASE AUTOMATION SYSTEM
# Email: SendGrid | SMS: Twilio
# ============================================================

import os
import asyncio
from datetime import datetime, date, timedelta
from fastapi import APIRouter, HTTPException, Body
from typing import Optional

router = APIRouter(prefix="/api/admin/automations", tags=["Automations"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    global db
    db = database

# ─── CONFIG ─────────────────────────────────────────────────
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "hello@reroots.ca")
FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "ReRoots")
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_PHONE_NUMBER")
SITE_URL = "https://www.reroots.ca"

sg = None
twilio_client = None

def init_clients():
    global sg, twilio_client
    if SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            print("[AUTOMATION] SendGrid client initialized")
        except Exception as e:
            print(f"[AUTOMATION] SendGrid init failed: {e}")
    
    if TWILIO_SID and TWILIO_TOKEN:
        try:
            from twilio.rest import Client as TwilioClient
            twilio_client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
            print("[AUTOMATION] Twilio client initialized")
        except Exception as e:
            print(f"[AUTOMATION] Twilio init failed: {e}")

# ─── EMAIL TEMPLATES ────────────────────────────────────────

def email_day25(customer_name: str, product: str, customer_email: str) -> dict:
    """Day 25 — Gentle repurchase nudge"""
    first = customer_name.split()[0] if customer_name else "there"
    subject = f"{first}, your PDRN serum is running low"
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: Georgia, serif; background: #FDF9F9; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 40px 20px; }}
    .logo {{ text-align: center; letter-spacing: 0.3em; font-size: 22px; color: #2D2A2E; margin-bottom: 40px; }}
    .logo span {{ color: #F8A5B8; }}
    .body-text {{ font-size: 16px; line-height: 1.8; color: #2D2A2E; margin-bottom: 24px; }}
    .highlight {{ background: #FEF2F4; border-left: 3px solid #F8A5B8; padding: 16px 20px; margin: 24px 0; font-size: 15px; color: #2D2A2E; line-height: 1.7; }}
    .btn {{ display: block; width: fit-content; margin: 32px auto; background: #F8A5B8; color: #FFFFFF; text-decoration: none; padding: 14px 36px; font-size: 14px; letter-spacing: 0.15em; text-transform: uppercase; font-family: Georgia, serif; }}
    .footer {{ text-align: center; font-size: 12px; color: #C4BAC0; margin-top: 48px; line-height: 1.8; }}
    .divider {{ border: none; border-top: 1px solid #F0E8E8; margin: 32px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">RE<span>ROOTS</span></div>
    <p class="body-text">Hi {first},</p>
    <p class="body-text">
      You're on day 25 of your PDRN cycle — which means your <strong>{product}</strong>
      is likely running low right now.
    </p>
    <div class="highlight">
      PDRN works cumulatively. The cellular repair you've been building over the past
      25 days compounds with each application. A gap in your routine means starting
      that process over.
    </div>
    <p class="body-text">
      Reorder today and your next bottle will arrive before you run out — keeping
      your results uninterrupted.
    </p>
    <a href="{SITE_URL}/shop" class="btn">Reorder Now</a>
    <hr class="divider">
    <div class="footer">
      ReRoots · Premium Biotech Skincare · Canada<br>
      <a href="{SITE_URL}/unsubscribe?email={customer_email}" style="color: #C4BAC0;">Unsubscribe</a>
    </div>
  </div>
</body>
</html>
"""
    return {"subject": subject, "html": html}


def email_day28(customer_name: str, product: str, customer_email: str) -> dict:
    """Day 28 — Repurchase reminder, cycle complete"""
    first = customer_name.split()[0] if customer_name else "there"
    subject = f"Your 28-day PDRN cycle is complete, {first}"
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: Georgia, serif; background: #FDF9F9; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 40px 20px; }}
    .logo {{ text-align: center; letter-spacing: 0.3em; font-size: 22px; color: #2D2A2E; margin-bottom: 40px; }}
    .logo span {{ color: #F8A5B8; }}
    .body-text {{ font-size: 16px; line-height: 1.8; color: #2D2A2E; margin-bottom: 24px; }}
    .cycle-badge {{ text-align: center; background: #FEF2F4; border: 1px solid #F8A5B8; padding: 24px; margin: 24px 0; }}
    .cycle-number {{ font-size: 48px; color: #F8A5B8; margin-bottom: 4px; }}
    .cycle-label {{ font-size: 12px; letter-spacing: 0.25em; color: #8A8490; text-transform: uppercase; }}
    .results {{ background: #F9FDF9; border-left: 3px solid #72B08A; padding: 16px 20px; margin: 24px 0; font-size: 15px; color: #2D2A2E; line-height: 1.8; }}
    .btn {{ display: block; width: fit-content; margin: 32px auto; background: #F8A5B8; color: #FFFFFF; text-decoration: none; padding: 14px 36px; font-size: 14px; letter-spacing: 0.15em; text-transform: uppercase; font-family: Georgia, serif; }}
    .btn-secondary {{ display: block; width: fit-content; margin: 0 auto 32px; color: #F8A5B8; text-decoration: none; padding: 10px 36px; font-size: 13px; letter-spacing: 0.1em; border: 1px solid #F8A5B8; }}
    .footer {{ text-align: center; font-size: 12px; color: #C4BAC0; margin-top: 48px; line-height: 1.8; }}
    .divider {{ border: none; border-top: 1px solid #F0E8E8; margin: 32px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">RE<span>ROOTS</span></div>
    <div class="cycle-badge">
      <div class="cycle-number">28</div>
      <div class="cycle-label">Days Complete</div>
    </div>
    <p class="body-text">Hi {first},</p>
    <p class="body-text">
      You've completed your first full PDRN repair cycle. By now you should be
      noticing visible improvements in skin texture, tone, and elasticity.
    </p>
    <div class="results">
      <strong>What's happening in your skin right now:</strong><br>
      ✓ DNA repair pathways actively stimulated<br>
      ✓ Fibroblast activity increased<br>
      ✓ Collagen synthesis in progress<br>
      ✓ Cellular turnover accelerated
    </div>
    <p class="body-text">Cycle 2 is where results compound. Don't let your skin reset.</p>
    <a href="{SITE_URL}/shop" class="btn">Start Cycle 2 →</a>
    <a href="{SITE_URL}/shop/bundles" class="btn-secondary">View Bundle & Save</a>
    <hr class="divider">
    <div class="footer">
      ReRoots · Premium Biotech Skincare · Canada<br>
      <a href="{SITE_URL}/unsubscribe?email={customer_email}" style="color: #C4BAC0;">Unsubscribe</a>
    </div>
  </div>
</body>
</html>
"""
    return {"subject": subject, "html": html}


def email_day35(customer_name: str, product: str, customer_email: str) -> dict:
    """Day 35 — Win-back with 10% offer"""
    first = customer_name.split()[0] if customer_name else "there"
    subject = f"We saved 10% for you, {first} — come back to your routine"
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: Georgia, serif; background: #FDF9F9; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 40px 20px; }}
    .logo {{ text-align: center; letter-spacing: 0.3em; font-size: 22px; color: #2D2A2E; margin-bottom: 40px; }}
    .logo span {{ color: #F8A5B8; }}
    .body-text {{ font-size: 16px; line-height: 1.8; color: #2D2A2E; margin-bottom: 24px; }}
    .offer-box {{ text-align: center; background: #2D2A2E; padding: 32px; margin: 24px 0; }}
    .offer-pct {{ font-size: 52px; color: #F8A5B8; line-height: 1; }}
    .offer-label {{ font-size: 13px; color: #FFFFFF; letter-spacing: 0.2em; text-transform: uppercase; margin-top: 8px; }}
    .code-box {{ background: #FEF2F4; border: 1px dashed #F8A5B8; padding: 12px 24px; text-align: center; margin: 16px 0; font-size: 20px; letter-spacing: 0.3em; color: #2D2A2E; }}
    .btn {{ display: block; width: fit-content; margin: 32px auto; background: #F8A5B8; color: #FFFFFF; text-decoration: none; padding: 14px 36px; font-size: 14px; letter-spacing: 0.15em; text-transform: uppercase; font-family: Georgia, serif; }}
    .expiry {{ text-align: center; font-size: 12px; color: #8A8490; margin-top: -16px; margin-bottom: 24px; }}
    .footer {{ text-align: center; font-size: 12px; color: #C4BAC0; margin-top: 48px; line-height: 1.8; }}
    .divider {{ border: none; border-top: 1px solid #F0E8E8; margin: 32px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">RE<span>ROOTS</span></div>
    <p class="body-text">Hi {first},</p>
    <p class="body-text">
      We noticed you haven't reordered your <strong>{product}</strong> yet.
      Your skin's regeneration cycle works best with consistency — and we want
      to make it easy for you to get back on track.
    </p>
    <div class="offer-box">
      <div class="offer-pct">10%</div>
      <div class="offer-label">Off Your Next Order</div>
    </div>
    <p class="body-text" style="text-align:center;">Use code at checkout:</p>
    <div class="code-box">COMEBACK10</div>
    <a href="{SITE_URL}/shop" class="btn">Claim My 10% Off</a>
    <p class="expiry">Offer expires in 7 days</p>
    <hr class="divider">
    <div class="footer">
      ReRoots · Premium Biotech Skincare · Canada<br>
      <a href="{SITE_URL}/unsubscribe?email={customer_email}" style="color: #C4BAC0;">Unsubscribe</a>
    </div>
  </div>
</body>
</html>
"""
    return {"subject": subject, "html": html}


def email_welcome(customer_name: str, product: str, customer_email: str) -> dict:
    """Day 1 — Welcome & PDRN education"""
    first = customer_name.split()[0] if customer_name else "there"
    subject = f"Welcome to ReRoots, {first} — your PDRN journey starts now"
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: Georgia, serif; background: #FDF9F9; margin: 0; padding: 0; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 40px 20px; }}
    .logo {{ text-align: center; letter-spacing: 0.3em; font-size: 22px; color: #2D2A2E; margin-bottom: 8px; }}
    .logo span {{ color: #F8A5B8; }}
    .tagline {{ text-align: center; font-size: 12px; letter-spacing: 0.2em; color: #C4BAC0; text-transform: uppercase; margin-bottom: 40px; }}
    .body-text {{ font-size: 16px; line-height: 1.8; color: #2D2A2E; margin-bottom: 24px; }}
    .steps {{ margin: 24px 0; }}
    .step {{ display: flex; gap: 16px; margin-bottom: 20px; align-items: flex-start; }}
    .step-num {{ background: #F8A5B8; color: #FFFFFF; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; margin-top: 2px; }}
    .step-text {{ font-size: 15px; color: #2D2A2E; line-height: 1.7; }}
    .step-label {{ font-weight: bold; color: #2D2A2E; }}
    .science-box {{ background: #FEF2F4; border-left: 3px solid #F8A5B8; padding: 16px 20px; margin: 24px 0; font-size: 14px; color: #8A8490; line-height: 1.8; font-style: italic; }}
    .btn {{ display: block; width: fit-content; margin: 32px auto; background: #F8A5B8; color: #FFFFFF; text-decoration: none; padding: 14px 36px; font-size: 14px; letter-spacing: 0.15em; text-transform: uppercase; font-family: Georgia, serif; }}
    .footer {{ text-align: center; font-size: 12px; color: #C4BAC0; margin-top: 48px; line-height: 1.8; }}
    .divider {{ border: none; border-top: 1px solid #F0E8E8; margin: 32px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">RE<span>ROOTS</span></div>
    <div class="tagline">Premium Biotech Skincare · Canada</div>
    <p class="body-text">Hi {first},</p>
    <p class="body-text">
      Your <strong>{product}</strong> is on its way. While you wait,
      here's everything you need to know to get the most out of your PDRN routine.
    </p>
    <div class="science-box">
      PDRN (Polynucleotide) works by activating A2A receptors in your skin cells,
      triggering a DNA repair cascade that rebuilds collagen and restores your skin's regenerative capacity.
    </div>
    <div class="steps">
      <div class="step">
        <div class="step-num">1</div>
        <div class="step-text"><span class="step-label">Apply to clean skin.</span> After cleansing, apply 3–4 drops and press gently into face and neck.</div>
      </div>
      <div class="step">
        <div class="step-num">2</div>
        <div class="step-text"><span class="step-label">Morning and evening.</span> Twice daily for consistent cellular signals.</div>
      </div>
      <div class="step">
        <div class="step-num">3</div>
        <div class="step-text"><span class="step-label">Be consistent for 28 days.</span> Most customers see visible improvement between days 14–21.</div>
      </div>
      <div class="step">
        <div class="step-num">4</div>
        <div class="step-text"><span class="step-label">Follow with SPF.</span> Active cell renewal makes skin temporarily more photosensitive.</div>
      </div>
    </div>
    <a href="{SITE_URL}/pdrn-guide" class="btn">Read the Full PDRN Guide</a>
    <hr class="divider">
    <div class="footer">
      ReRoots · Premium Biotech Skincare · Canada<br>
      Questions? Reply to this email — we respond within 24 hours.<br><br>
      <a href="{SITE_URL}/unsubscribe?email={customer_email}" style="color: #C4BAC0;">Unsubscribe</a>
    </div>
  </div>
</body>
</html>
"""
    return {"subject": subject, "html": html}


# ─── SMS TEMPLATES ───────────────────────────────────────────

def sms_day25(customer_name: str, product: str) -> str:
    first = customer_name.split()[0] if customer_name else "Hi"
    return f"Hi {first}, your {product} is running low — day 25 of your PDRN cycle. Reorder now: {SITE_URL}/shop · Reply STOP to unsubscribe"

def sms_day28(customer_name: str) -> str:
    first = customer_name.split()[0] if customer_name else "Hi"
    return f"ReRoots: {first}, your 28-day PDRN cycle is complete! Start cycle 2: {SITE_URL}/shop · Reply STOP to unsubscribe"

def sms_day35(customer_name: str) -> str:
    first = customer_name.split()[0] if customer_name else "Hi"
    return f"ReRoots: {first}, use code COMEBACK10 for 10% off. Your skin misses its routine: {SITE_URL}/shop · Reply STOP to unsubscribe"


# ─── SEND FUNCTIONS ──────────────────────────────────────────

async def send_email(to_email: str, to_name: str, subject: str, html_content: str) -> bool:
    """Send email via SendGrid"""
    if not sg:
        print(f"[EMAIL SKIPPED — no API key] To: {to_email} | Subject: {subject}")
        return False
    try:
        from sendgrid.helpers.mail import Mail, To, From
        message = Mail(
            from_email=From(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email, to_name),
            subject=subject,
            html_content=html_content
        )
        response = sg.send(message)
        print(f"[EMAIL SENT] {to_email} | {subject} | Status: {response.status_code}")
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"[EMAIL ERROR] {to_email} | {e}")
        return False


async def send_sms(to_phone: str, message: str) -> bool:
    """Send SMS via Twilio"""
    if not twilio_client or not to_phone:
        print(f"[SMS SKIPPED — no config or phone] Message: {message[:50]}...")
        return False
    try:
        phone = to_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not phone.startswith("+"):
            phone = "+1" + phone.lstrip("1")
        msg = twilio_client.messages.create(body=message, from_=TWILIO_FROM, to=phone)
        print(f"[SMS SENT] {phone} | SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"[SMS ERROR] {to_phone} | {e}")
        return False


async def log_automation_send(customer_id: str, automation_type: str, channel: str, success: bool):
    """Log every automation send to database"""
    await db["automation_logs"].insert_one({
        "customerId": customer_id,
        "automationType": automation_type,
        "channel": channel,
        "success": success,
        "sentAt": datetime.utcnow().isoformat(),
        "date": date.today().isoformat()
    })
    if success:
        await db["crm_automations"].update_one(
            {"trigger": f"Day {automation_type.split('_')[1]} of Cycle"},
            {"$inc": {"sent": 1}}
        )


# ─── CORE AUTOMATION ENGINE ──────────────────────────────────

async def run_repurchase_automations():
    """Main automation engine — runs daily at 10:00 AM."""
    print(f"\n[AUTOMATION] Running repurchase cycle check — {date.today()}")
    
    customers = await db["crm_customers"].find(
        {"lastPurchase": {"$exists": True}, "email": {"$exists": True}}
    ).to_list(10000)
    
    sent_count = 0
    
    for customer in customers:
        try:
            name = customer.get("name", "")
            email = customer.get("email", "")
            phone = customer.get("phone", "")
            product = customer.get("lastProduct", "PDRN Repair Serum 30ml")
            cid = str(customer.get("_id", ""))
            
            if not email:
                continue
            
            last_purchase = customer.get("lastPurchase")
            if not last_purchase:
                continue
            
            last = datetime.strptime(last_purchase, "%Y-%m-%d").date()
            cycle_day = (date.today() - last).days
            
            # Check already sent today
            already_sent = await db["automation_logs"].find_one({
                "customerId": cid,
                "date": date.today().isoformat()
            })
            if already_sent:
                continue
            
            # Day 1: Welcome
            if cycle_day == 1:
                tmpl = email_welcome(name, product, email)
                ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                await log_automation_send(cid, "day_1_welcome", "email", ok)
                if ok: sent_count += 1
            
            # Day 7: Check-in (P1-C)
            elif cycle_day == 7:
                try:
                    from routes.reroots_email_templates import cycle_day7_checkin
                    customer_dict = {"name": name, "email": email}
                    tmpl = cycle_day7_checkin(customer_dict)
                    ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                    await log_automation_send(cid, "day_7_checkin", "email", ok)
                    if ok: sent_count += 1
                except Exception as e:
                    print(f"[AUTOMATION] Day 7 template error: {e}")
            
            # Day 14: Progress update (P1-C)
            elif cycle_day == 14:
                try:
                    from routes.reroots_email_templates import cycle_day14_progress
                    customer_dict = {"name": name, "email": email}
                    tmpl = cycle_day14_progress(customer_dict)
                    ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                    await log_automation_send(cid, "day_14_progress", "email", ok)
                    if ok: sent_count += 1
                except Exception as e:
                    print(f"[AUTOMATION] Day 14 template error: {e}")
            
            # Day 21: Review request (P1-C)
            elif cycle_day == 21:
                try:
                    from routes.reroots_email_templates import review_request_d21
                    customer_dict = {"name": name, "email": email}
                    tmpl = review_request_d21(customer_dict)
                    ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                    await log_automation_send(cid, "day_21_review", "email", ok)
                    if ok: 
                        sent_count += 1
                        # Track review request in DB
                        await db.review_requests.insert_one({
                            "customerEmail": email,
                            "customerName": name,
                            "sentAt": datetime.utcnow(),
                            "status": "pending"
                        })
                except Exception as e:
                    print(f"[AUTOMATION] Day 21 template error: {e}")
            
            # Day 25: Nudge
            elif cycle_day == 25:
                tmpl = email_day25(name, product, email)
                ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                await log_automation_send(cid, "day_25_nudge", "email", ok)
                if phone:
                    sms_ok = await send_sms(phone, sms_day25(name, product))
                    await log_automation_send(cid, "day_25_nudge", "sms", sms_ok)
                if ok: sent_count += 1
            
            # Day 28: Cycle complete
            elif cycle_day == 28:
                tmpl = email_day28(name, product, email)
                ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                await log_automation_send(cid, "day_28_repurchase", "email", ok)
                if phone:
                    sms_ok = await send_sms(phone, sms_day28(name))
                    await log_automation_send(cid, "day_28_repurchase", "sms", sms_ok)
                if ok: sent_count += 1
            
            # Day 35: Win-back
            elif cycle_day == 35:
                tmpl = email_day35(name, product, email)
                ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                await log_automation_send(cid, "day_35_winback", "email", ok)
                if phone:
                    sms_ok = await send_sms(phone, sms_day35(name))
                    await log_automation_send(cid, "day_35_winback", "sms", sms_ok)
                if ok: sent_count += 1
                
        except Exception as e:
            print(f"[AUTOMATION ERROR] Customer {customer.get('name')} | {e}")
            continue
    
    print(f"[AUTOMATION COMPLETE] {sent_count} messages sent\n")
    return sent_count


# ─── API ENDPOINTS ───────────────────────────────────────────

@router.post("/run")
async def trigger_automations_manually():
    """Manually trigger the automation engine."""
    try:
        count = await run_repurchase_automations()
        return {"success": True, "messagesSent": count, "runAt": datetime.utcnow().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-email")
async def send_test_email(data: dict = Body(...)):
    """Send a test email. Body: { email, template: "welcome"|"day25"|"day28"|"day35", name }"""
    try:
        email = data.get("email")
        tmpl = data.get("template", "welcome")
        name = data.get("name", "Test Customer")
        product = "PDRN Repair Serum 30ml"
        
        templates = {
            "welcome": email_welcome,
            "day25": email_day25,
            "day28": email_day28,
            "day35": email_day35,
        }
        fn = templates.get(tmpl, email_welcome)
        result = fn(name, product, email)
        ok = await send_email(email, name, f"[TEST] {result['subject']}", result["html"])
        return {"success": ok, "template": tmpl, "sentTo": email}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-sms")
async def send_test_sms(data: dict = Body(...)):
    """Send a test SMS. Body: { phone }"""
    try:
        phone = data.get("phone")
        ok = await send_sms(phone, f"ReRoots test message — your automation system is working! {SITE_URL}")
        return {"success": ok, "sentTo": phone}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_automation_logs(limit: int = 100):
    """Get recent automation send logs"""
    try:
        logs = await db["automation_logs"].find().sort("sentAt", -1).to_list(limit)
        for log in logs:
            log["_id"] = str(log["_id"])
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_automation_stats():
    """Get automation performance stats"""
    try:
        total_sent = await db["automation_logs"].count_documents({"success": True})
        today_sent = await db["automation_logs"].count_documents({
            "success": True,
            "date": date.today().isoformat()
        })
        
        # Get breakdown by type
        pipeline = [
            {"$match": {"success": True}},
            {"$group": {"_id": "$automationType", "count": {"$sum": 1}}}
        ]
        by_type = await db["automation_logs"].aggregate(pipeline).to_list(100)
        
        return {
            "totalSent": total_sent,
            "sentToday": today_sent,
            "byType": {item["_id"]: item["count"] for item in by_type}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
