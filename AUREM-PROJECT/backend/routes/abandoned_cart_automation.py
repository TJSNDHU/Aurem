# ============================================================
# REROOTS — ABANDONED CART WIN-BACK AUTOMATION
# 3-Step Recovery Sequence: Immediate → 24hr (10% off) → 72hr Final
# ============================================================

import os
import random
import string
from datetime import datetime, date, timedelta
from fastapi import APIRouter, HTTPException, Body
from bson import ObjectId

router = APIRouter(prefix="/api/abandoned", tags=["Abandoned Cart Recovery"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

SITE_URL = "https://www.reroots.ca"
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "hello@reroots.ca")
FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "ReRoots")

sg = None

def init_sendgrid():
    global sg
    api_key = os.environ.get("SENDGRID_API_KEY")
    if api_key:
        try:
            from sendgrid import SendGridAPIClient
            sg = SendGridAPIClient(api_key)
            print("[ABANDONED CART] SendGrid initialized")
        except Exception as e:
            print(f"[ABANDONED CART] SendGrid init error: {e}")


async def send_email(to_email, to_name, subject, html):
    """Send email via SendGrid"""
    if not sg:
        print(f"[EMAIL SKIPPED] {to_email} | {subject}")
        return False
    try:
        from sendgrid.helpers.mail import Mail, To, From
        msg = Mail(
            from_email=From(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email, to_name),
            subject=subject,
            html_content=html
        )
        r = sg.send(msg)
        print(f"[EMAIL SENT] {to_email} | {subject} | {r.status_code}")
        return r.status_code in [200, 201, 202]
    except Exception as e:
        print(f"[EMAIL ERROR] {to_email} | {e}")
        return False


def generate_unique_code(customer_name: str) -> str:
    """Generate a unique, single-use discount code. Format: SAVE-XXXX"""
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"SAVE-{suffix}"


async def create_cart_discount_code(cart_id: str, customer_email: str, discount_pct: int = 10, expiry_days: int = 7) -> str:
    """Create a unique discount code for abandoned cart, save to DB"""
    code = generate_unique_code("")
    expiry = (date.today() + timedelta(days=expiry_days)).isoformat()

    await db["discount_codes"].insert_one({
        "code": code,
        "customerEmail": customer_email,
        "cartId": cart_id,
        "discountPct": discount_pct,
        "expiryDate": expiry,
        "used": False,
        "createdAt": datetime.utcnow().isoformat(),
        "type": "abandoned_cart_recovery"
    })
    print(f"[DISCOUNT CODE] Created: {code} for abandoned cart {cart_id}")
    return code


# ════════════════════════════════════════════════════════════
# EMAIL TEMPLATES - 3-STEP WIN-BACK SEQUENCE
# ════════════════════════════════════════════════════════════

def email_step1_immediate(customer_name: str, cart_items: list, cart_total: float, cart_url: str) -> dict:
    """Step 1 — Immediate: Your cart is waiting"""
    first = customer_name.split()[0] if customer_name else "there"
    
    items_html = "".join([
        f'<div style="display:flex;gap:12px;padding:12px 0;border-bottom:1px solid #F0E8E8;">'
        f'<div style="width:60px;height:60px;background:#FEF2F4;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:24px;">✨</div>'
        f'<div style="flex:1;"><div style="font-weight:500;color:#2D2A2E;">{item.get("name", "Product")}</div>'
        f'<div style="font-size:13px;color:#8A8490;">Qty: {item.get("quantity", 1)}</div></div>'
        f'<div style="font-family:monospace;color:#F8A5B8;font-weight:500;">${item.get("price", 0):.2f}</div></div>'
        for item in cart_items[:3]
    ])
    
    subject = f"Hi {first}, you left something beautiful behind"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:560px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:8px;}}.logo span{{color:#F8A5B8;}}.tagline{{text-align:center;font-size:11px;letter-spacing:.2em;color:#C4BAC0;text-transform:uppercase;margin-bottom:40px;}}.body-text{{font-size:16px;line-height:1.8;color:#2D2A2E;margin-bottom:24px;}}.cart-box{{background:#fff;border:1px solid #F0E8E8;border-radius:12px;padding:20px;margin:24px 0;}}.total-row{{display:flex;justify-content:space-between;padding:16px 0 0;border-top:2px solid #F0E8E8;margin-top:12px;}}.btn{{display:block;width:fit-content;margin:24px auto;background:#F8A5B8;color:#fff;text-decoration:none;padding:14px 32px;font-size:14px;letter-spacing:.1em;text-transform:uppercase;font-family:Georgia,serif;border-radius:30px;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:48px;line-height:1.8;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span></div>
  <div class="tagline">Premium Biotech Skincare · Canada</div>
  <p class="body-text">Hi {first},</p>
  <p class="body-text">We noticed you left some items in your cart. Your skin transformation is just a click away.</p>
  <div class="cart-box">
    {items_html}
    <div class="total-row">
      <span style="font-weight:500;color:#2D2A2E;">Cart Total</span>
      <span style="font-family:monospace;font-size:18px;color:#F8A5B8;font-weight:600;">${cart_total:.2f} CAD</span>
    </div>
  </div>
  <a href="{cart_url}" class="btn">Complete My Order</a>
  <p class="body-text" style="font-size:14px;color:#8A8490;text-align:center;">Your cart is saved and waiting for you.</p>
  <div class="footer">ReRoots · Premium Biotech Skincare · Canada<br>Questions? Reply to this email.</div>
</div></body></html>"""
    return {"subject": subject, "html": html}


def email_step2_24hr(customer_name: str, cart_items: list, cart_total: float, cart_url: str, discount_code: str) -> dict:
    """Step 2 — 24 Hours: 10% off incentive"""
    first = customer_name.split()[0] if customer_name else "there"
    discounted_total = cart_total * 0.90
    
    subject = f"{first}, here's 10% off to complete your order"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:560px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:8px;}}.logo span{{color:#F8A5B8;}}.tagline{{text-align:center;font-size:11px;letter-spacing:.2em;color:#C4BAC0;text-transform:uppercase;margin-bottom:40px;}}.body-text{{font-size:16px;line-height:1.8;color:#2D2A2E;margin-bottom:24px;}}.offer-box{{text-align:center;background:#2D2A2E;border-radius:12px;padding:28px;margin:24px 0;}}.offer-pct{{font-size:48px;color:#F8A5B8;line-height:1;}}.offer-label{{font-size:12px;letter-spacing:.2em;color:#fff;text-transform:uppercase;margin-top:8px;}}.code-box{{background:#FEF2F4;border:2px dashed #F8A5B8;border-radius:8px;padding:16px;text-align:center;margin:20px 0;}}.code{{font-family:monospace;font-size:24px;letter-spacing:.2em;color:#2D2A2E;font-weight:600;}}.savings{{background:#F9FDF9;border-left:3px solid #72B08A;padding:16px;margin:20px 0;font-size:14px;}}.btn{{display:block;width:fit-content;margin:24px auto;background:#F8A5B8;color:#fff;text-decoration:none;padding:14px 32px;font-size:14px;letter-spacing:.1em;text-transform:uppercase;font-family:Georgia,serif;border-radius:30px;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:48px;line-height:1.8;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span></div>
  <div class="tagline">Premium Biotech Skincare · Canada</div>
  <p class="body-text">Hi {first},</p>
  <p class="body-text">Your cart is still waiting — and now we've added a little something extra to make it even better.</p>
  <div class="offer-box">
    <div class="offer-pct">10%</div>
    <div class="offer-label">Off Your Order</div>
  </div>
  <p class="body-text" style="text-align:center;">Use this code at checkout:</p>
  <div class="code-box">
    <div class="code">{discount_code}</div>
  </div>
  <div class="savings">
    <strong>Your savings:</strong><br>
    Original: <span style="text-decoration:line-through;color:#8A8490;">${cart_total:.2f}</span><br>
    With code: <span style="color:#72B08A;font-weight:600;">${discounted_total:.2f} CAD</span>
  </div>
  <a href="{cart_url}?discount={discount_code}" class="btn">Claim My 10% Off</a>
  <p class="body-text" style="font-size:13px;color:#8A8490;text-align:center;">Code expires in 48 hours. Single use only.</p>
  <div class="footer">ReRoots · Premium Biotech Skincare · Canada<br>Questions? Reply to this email.</div>
</div></body></html>"""
    return {"subject": subject, "html": html}


def email_step3_72hr(customer_name: str, cart_items: list, cart_url: str, discount_code: str) -> dict:
    """Step 3 — 72 Hours: Final reminder with urgency"""
    first = customer_name.split()[0] if customer_name else "there"
    
    subject = f"Final reminder: Your PDRN routine is waiting, {first}"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:560px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:8px;}}.logo span{{color:#F8A5B8;}}.tagline{{text-align:center;font-size:11px;letter-spacing:.2em;color:#C4BAC0;text-transform:uppercase;margin-bottom:40px;}}.body-text{{font-size:16px;line-height:1.8;color:#2D2A2E;margin-bottom:24px;}}.urgency-box{{background:linear-gradient(135deg,#FEF2F4 0%,#FFF8E7 100%);border:1px solid #F8A5B8;border-radius:12px;padding:24px;text-align:center;margin:24px 0;}}.urgency-icon{{font-size:36px;margin-bottom:8px;}}.urgency-text{{font-size:14px;color:#2D2A2E;line-height:1.6;}}.code-reminder{{background:#2D2A2E;color:#fff;padding:16px;border-radius:8px;text-align:center;margin:20px 0;}}.code{{font-family:monospace;font-size:20px;letter-spacing:.15em;color:#F8A5B8;}}.benefits{{background:#F9FDF9;border-left:3px solid #72B08A;padding:16px;margin:20px 0;font-size:14px;line-height:1.8;}}.btn{{display:block;width:fit-content;margin:24px auto;background:#F8A5B8;color:#fff;text-decoration:none;padding:14px 32px;font-size:14px;letter-spacing:.1em;text-transform:uppercase;font-family:Georgia,serif;border-radius:30px;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:48px;line-height:1.8;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span></div>
  <div class="tagline">Premium Biotech Skincare · Canada</div>
  <p class="body-text">Hi {first},</p>
  <p class="body-text">This is our final reminder — your cart (and your 10% discount) won't wait forever.</p>
  <div class="urgency-box">
    <div class="urgency-icon">⏰</div>
    <div class="urgency-text">
      <strong>Your cart expires soon</strong><br>
      We can only hold your items for a limited time.
    </div>
  </div>
  <div class="code-reminder">
    <div style="font-size:12px;letter-spacing:.15em;margin-bottom:8px;">YOUR 10% OFF CODE</div>
    <div class="code">{discount_code}</div>
  </div>
  <div class="benefits">
    <strong>What you're about to experience:</strong><br>
    ✓ Cellular DNA repair from day one<br>
    ✓ Visible results by day 14-21<br>
    ✓ Clinically-backed PDRN technology<br>
    ✓ Free shipping on orders over $150
  </div>
  <a href="{cart_url}?discount={discount_code}" class="btn">Complete My Order Now</a>
  <p class="body-text" style="font-size:13px;color:#8A8490;text-align:center;">After today, your cart and discount code will expire.</p>
  <div class="footer">ReRoots · Premium Biotech Skincare · Canada<br>Questions? Reply to this email.</div>
</div></body></html>"""
    return {"subject": subject, "html": html}


# ════════════════════════════════════════════════════════════
# AUTOMATION ENGINE - RUNS DAILY
# ════════════════════════════════════════════════════════════

async def run_abandoned_cart_automation():
    """
    Main automation engine for abandoned cart recovery.
    Runs daily and sends appropriate emails based on cart age:
    - Step 1: Immediately (1-2 hours after abandonment)
    - Step 2: 24 hours later (with 10% discount code)
    - Step 3: 72 hours later (final reminder)
    """
    print(f"\n[ABANDONED CART] Running win-back automation — {date.today()}")
    
    # Get all abandoned carts (inactive for more than 1 hour)
    cutoff_time = datetime.utcnow() - timedelta(hours=1)
    
    carts = await db["carts"].find({
        "updated_at": {"$lt": cutoff_time.isoformat()},
        "items": {"$exists": True, "$ne": []},
        "customer_email": {"$exists": True, "$ne": ""},
        "recovered": {"$ne": True}
    }).to_list(500)
    
    sent_count = 0
    
    for cart in carts:
        try:
            email = cart.get("customer_email", "")
            name = cart.get("customer_name", "")
            items = cart.get("items", [])
            session_id = cart.get("session_id", "")
            
            if not email or not items:
                continue
            
            # Calculate cart total
            cart_total = sum(
                item.get("price", 0) * item.get("quantity", 1) 
                for item in items
            )
            
            # Calculate hours since abandonment
            updated_at = cart.get("updated_at", "")
            try:
                if updated_at:
                    abandoned_time = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                    hours_abandoned = (datetime.utcnow().replace(tzinfo=abandoned_time.tzinfo) - abandoned_time).total_seconds() / 3600
                else:
                    hours_abandoned = 2  # Default to step 1
            except Exception:
                hours_abandoned = 2
            
            cart_url = f"{SITE_URL}/cart?session={session_id}"
            cart_id = cart.get("id", session_id)
            
            # Check what emails have been sent
            step1_sent = cart.get("recovery_step1_sent", False)
            step2_sent = cart.get("recovery_step2_sent", False)
            step3_sent = cart.get("recovery_step3_sent", False)
            
            # Determine which step to send
            if not step1_sent and hours_abandoned >= 1:
                # Step 1: Immediate recovery email
                tmpl = email_step1_immediate(name, items, cart_total, cart_url)
                ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                if ok:
                    await db["carts"].update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "recovery_step1_sent": True,
                            "recovery_step1_sent_at": datetime.utcnow().isoformat()
                        }}
                    )
                    await log_recovery_email(cart_id, email, "step1", ok)
                    sent_count += 1
                    print(f"[STEP 1] Sent to {email}")
            
            elif not step2_sent and hours_abandoned >= 24:
                # Step 2: 24hr with 10% discount
                discount_code = await create_cart_discount_code(cart_id, email, 10, 2)
                tmpl = email_step2_24hr(name, items, cart_total, cart_url, discount_code)
                ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                if ok:
                    await db["carts"].update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "recovery_step2_sent": True,
                            "recovery_step2_sent_at": datetime.utcnow().isoformat(),
                            "recovery_discount_code": discount_code
                        }}
                    )
                    await log_recovery_email(cart_id, email, "step2", ok, discount_code)
                    sent_count += 1
                    print(f"[STEP 2] Sent to {email} with code {discount_code}")
            
            elif not step3_sent and hours_abandoned >= 72:
                # Step 3: 72hr final reminder
                discount_code = cart.get("recovery_discount_code", "")
                if not discount_code:
                    discount_code = await create_cart_discount_code(cart_id, email, 10, 1)
                
                tmpl = email_step3_72hr(name, items, cart_url, discount_code)
                ok = await send_email(email, name, tmpl["subject"], tmpl["html"])
                if ok:
                    await db["carts"].update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "recovery_step3_sent": True,
                            "recovery_step3_sent_at": datetime.utcnow().isoformat()
                        }}
                    )
                    await log_recovery_email(cart_id, email, "step3", ok, discount_code)
                    sent_count += 1
                    print(f"[STEP 3] Sent to {email}")
        
        except Exception as e:
            print(f"[ABANDONED CART ERROR] Cart {cart.get('session_id', 'unknown')}: {e}")
            continue
    
    print(f"[ABANDONED CART] Complete — {sent_count} emails sent\n")
    return sent_count


async def log_recovery_email(cart_id: str, email: str, step: str, success: bool, discount_code: str = None):
    """Log recovery email sends"""
    await db["automation_logs"].insert_one({
        "automationType": f"abandoned_cart_{step}",
        "cartId": cart_id,
        "email": email,
        "discountCode": discount_code,
        "success": success,
        "sentAt": datetime.utcnow().isoformat(),
        "date": date.today().isoformat()
    })


# ════════════════════════════════════════════════════════════
# API ENDPOINTS
# ════════════════════════════════════════════════════════════

@router.post("/run-automation")
async def trigger_abandoned_cart_automation():
    """Manually trigger the abandoned cart recovery automation"""
    try:
        count = await run_abandoned_cart_automation()
        return {"success": True, "emailsSent": count, "runAt": datetime.utcnow().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_abandoned_cart_stats():
    """Get abandoned cart recovery statistics"""
    try:
        # Count carts by recovery stage
        total = await db["carts"].count_documents({
            "items": {"$exists": True, "$ne": []},
            "recovered": {"$ne": True}
        })
        
        step1_sent = await db["carts"].count_documents({"recovery_step1_sent": True})
        step2_sent = await db["carts"].count_documents({"recovery_step2_sent": True})
        step3_sent = await db["carts"].count_documents({"recovery_step3_sent": True})
        recovered = await db["carts"].count_documents({"recovered": True})
        
        # Get recovery logs for today
        today_logs = await db["automation_logs"].count_documents({
            "automationType": {"$regex": "^abandoned_cart"},
            "date": date.today().isoformat(),
            "success": True
        })
        
        return {
            "totalAbandoned": total,
            "step1Sent": step1_sent,
            "step2Sent": step2_sent,
            "step3Sent": step3_sent,
            "recovered": recovered,
            "recoveryRate": round((recovered / max(total, 1)) * 100, 1),
            "sentToday": today_logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-step/{cart_id}/{step}")
async def send_specific_step(cart_id: str, step: int):
    """Manually send a specific recovery step for a cart"""
    try:
        cart = await db["carts"].find_one({"$or": [
            {"id": cart_id},
            {"session_id": cart_id}
        ]})
        
        if not cart:
            raise HTTPException(status_code=404, detail="Cart not found")
        
        email = cart.get("customer_email", "")
        name = cart.get("customer_name", "")
        items = cart.get("items", [])
        session_id = cart.get("session_id", "")
        
        if not email:
            raise HTTPException(status_code=400, detail="No email address for this cart")
        
        cart_total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
        cart_url = f"{SITE_URL}/cart?session={session_id}"
        
        if step == 1:
            tmpl = email_step1_immediate(name, items, cart_total, cart_url)
        elif step == 2:
            discount_code = await create_cart_discount_code(cart_id, email, 10, 2)
            tmpl = email_step2_24hr(name, items, cart_total, cart_url, discount_code)
        elif step == 3:
            discount_code = cart.get("recovery_discount_code") or await create_cart_discount_code(cart_id, email, 10, 1)
            tmpl = email_step3_72hr(name, items, cart_url, discount_code)
        else:
            raise HTTPException(status_code=400, detail="Invalid step. Use 1, 2, or 3.")
        
        ok = await send_email(email, name, f"[TEST] {tmpl['subject']}", tmpl["html"])
        
        return {"success": ok, "step": step, "sentTo": email}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
