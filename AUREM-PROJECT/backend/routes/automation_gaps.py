# ============================================================
# REROOTS — COMPLETE AUTOMATION GAPS (All 8)
# ============================================================
#
# COVERS:
# 1. Auto-create CRM customer on new order
# 2. Order confirmation email to customer
# 3. Shipping notification with tracking number
# 4. Day 7 + Day 14 repurchase emails
# 5. Low stock alert email to owner
# 6. NPN expiry email reminders to owner
# 7. Monthly P&L auto-email to owner
# 8. Unique discount codes per customer
# ============================================================

import os
import random
import string
from datetime import datetime, date, timedelta
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

router = APIRouter(prefix="/api", tags=["Automation Gaps"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

SITE_URL = "https://www.reroots.ca"
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "hello@reroots.ca")
FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "ReRoots")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "admin@reroots.ca")
OWNER_NAME = os.environ.get("OWNER_NAME", "Tj")

sg = None

def init_sendgrid():
    global sg
    api_key = os.environ.get("SENDGRID_API_KEY")
    if api_key:
        try:
            from sendgrid import SendGridAPIClient
            sg = SendGridAPIClient(api_key)
            print("[AUTOMATION GAPS] SendGrid initialized")
        except Exception as e:
            print(f"[AUTOMATION GAPS] SendGrid init error: {e}")


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


fCur = lambda n: f"${float(n):,.2f}"
fDate = lambda s: datetime.strptime(s, "%Y-%m-%d").strftime("%B %d, %Y") if s else "—"


# ════════════════════════════════════════════════════════════
# 1. AUTO-CREATE CRM CUSTOMER ON NEW ORDER
# ════════════════════════════════════════════════════════════

async def auto_upsert_customer(order: dict):
    """
    Auto-create or update CRM customer record when an order is placed.
    - New customer → create full profile
    - Existing customer → update lastPurchase, totalSpend, order count
    """
    email = order.get("email", "").lower().strip()
    name = order.get("customer", "")
    total = float(order.get("total", 0))
    items = order.get("items", [])
    city = order.get("city", "")
    product = items[0].get("sku", "") if items else ""

    if not email:
        return

    existing = await db["crm_customers"].find_one({"email": email})

    if existing:
        new_spend = existing.get("totalSpend", 0) + total
        new_orders = existing.get("orders", 0) + 1

        tier = existing.get("tier", "New")
        if new_spend >= 500:
            tier = "VIP"
        elif new_orders >= 2:
            tier = "Regular"

        await db["crm_customers"].update_one(
            {"email": email},
            {"$set": {
                "lastPurchase": date.today().isoformat(),
                "lastProduct": product,
                "totalSpend": new_spend,
                "orders": new_orders,
                "tier": tier,
                "updatedAt": datetime.utcnow().isoformat()
            }}
        )
        print(f"[CRM] Updated customer: {name} ({email})")
    else:
        new_customer = {
            "name": name,
            "email": email,
            "phone": "",
            "city": city,
            "tier": "New",
            "totalSpend": total,
            "orders": 1,
            "lastPurchase": date.today().isoformat(),
            "lastProduct": product,
            "tags": ["new-customer"],
            "notes": f"Auto-created from order {order.get('id', '')}",
            "cycleDay": 0,
            "status": "On Track",
            "nextDue": (date.today() + timedelta(days=28)).isoformat(),
            "createdAt": datetime.utcnow().isoformat()
        }
        await db["crm_customers"].insert_one(new_customer)
        print(f"[CRM] Created new customer: {name} ({email})")


# ════════════════════════════════════════════════════════════
# 2. ORDER CONFIRMATION EMAIL TO CUSTOMER
# ════════════════════════════════════════════════════════════

async def send_order_confirmation(order: dict):
    """Send order confirmation email to customer immediately after order is placed."""
    name = order.get("customer", "Customer")
    email = order.get("email", "")
    first = name.split()[0] if name else "there"
    oid = order.get("id", "")
    items = order.get("items", [])
    city = order.get("city", "")

    if not email:
        return

    items_html = "".join([
        f"""<tr>
          <td style="padding:10px 0;border-bottom:1px solid #F0E8E8;font-family:Georgia,serif;font-size:15px;color:#2D2A2E;">{i.get('sku', i.get('name', 'Product'))}</td>
          <td style="padding:10px 0;border-bottom:1px solid #F0E8E8;text-align:center;font-family:monospace;font-size:14px;color:#8A8490;">×{i.get('qty', 1)}</td>
          <td style="padding:10px 0;border-bottom:1px solid #F0E8E8;text-align:right;font-family:monospace;font-size:14px;color:#2D2A2E;">{fCur(i.get('qty', 1)*i.get('price', 0))}</td>
        </tr>"""
        for i in items
    ])

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:560px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:8px;}}.logo span{{color:#F8A5B8;}}.tagline{{text-align:center;font-size:11px;letter-spacing:.2em;color:#C4BAC0;text-transform:uppercase;margin-bottom:40px;}}.body-text{{font-size:16px;line-height:1.8;color:#2D2A2E;margin-bottom:24px;}}.order-box{{background:#fff;border:1px solid #F0E8E8;border-radius:12px;padding:24px;margin:24px 0;}}.order-id{{font-family:monospace;font-size:13px;color:#F8A5B8;letter-spacing:.1em;margin-bottom:16px;}}.total-row{{display:flex;justify-content:space-between;padding:12px 0;border-top:2px solid #F0E8E8;margin-top:8px;}}.total-label{{font-size:14px;font-weight:bold;color:#2D2A2E;}}.total-value{{font-family:monospace;font-size:16px;color:#F8A5B8;font-weight:bold;}}.pdrn-box{{background:#FEF2F4;border-left:3px solid #F8A5B8;padding:16px 20px;margin:24px 0;font-size:14px;color:#2D2A2E;line-height:1.8;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:48px;line-height:1.8;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span></div>
  <div class="tagline">Premium Biotech Skincare · Canada</div>
  <p class="body-text">Hi {first}, your order is confirmed.</p>
  <div class="order-box">
    <div class="order-id">ORDER {oid}</div>
    <table style="width:100%;border-collapse:collapse;">
      <thead><tr>
        <th style="text-align:left;font-size:11px;letter-spacing:.15em;color:#C4BAC0;text-transform:uppercase;padding-bottom:8px;font-family:monospace;font-weight:400;">Product</th>
        <th style="text-align:center;font-size:11px;letter-spacing:.15em;color:#C4BAC0;text-transform:uppercase;padding-bottom:8px;font-family:monospace;font-weight:400;">Qty</th>
        <th style="text-align:right;font-size:11px;letter-spacing:.15em;color:#C4BAC0;text-transform:uppercase;padding-bottom:8px;font-family:monospace;font-weight:400;">Total</th>
      </tr></thead>
      <tbody>{items_html}</tbody>
    </table>
    <div class="total-row">
      <span class="total-label">Order Total</span>
      <span class="total-value">{fCur(order.get('total', 0))}</span>
    </div>
    <div style="font-size:12px;color:#8A8490;font-family:monospace;margin-top:8px;">Shipping to: {city}</div>
  </div>
  <div class="pdrn-box">
    <strong>While you wait:</strong> Your PDRN routine works best applied morning and evening to clean skin. Most customers notice visible improvement around day 14–21 of consistent use.
  </div>
  <p class="body-text" style="font-size:14px;color:#8A8490;">We'll send you a shipping notification with your tracking number once your order is dispatched — usually within 1–2 business days.</p>
  <div class="footer">ReRoots · Premium Biotech Skincare · Canada<br>Questions? Reply to this email — we respond within 24 hours.</div>
</div></body></html>"""

    await send_email(email, name, f"Order Confirmed — {oid} | ReRoots", html)
    print(f"[ORDER CONFIRM] Sent to {email} for {oid}")


# ════════════════════════════════════════════════════════════
# 3. SHIPPING NOTIFICATION WITH TRACKING NUMBER
# ════════════════════════════════════════════════════════════

CARRIER_TRACKING_URLS = {
    "Canada Post": "https://www.canadapost-postescanada.ca/track-reperage/en#/search?searchFor=",
    "Purolator": "https://www.purolator.com/en/shipping/tracker?pin=",
    "FedEx": "https://www.fedex.com/fedextrack/?trknbr=",
    "UPS": "https://www.ups.com/track?tracknum=",
    "Canpar": "https://www.canpar.com/en/package-tracking/track-package.page?reference=",
}

async def send_shipping_notification(order: dict, carrier: str, tracking: str):
    """Send shipping notification with tracking link to customer."""
    name = order.get("customer", "Customer")
    email = order.get("email", "")
    first = name.split()[0] if name else "there"
    oid = order.get("id", "")
    city = order.get("city", "")

    if not email:
        return

    tracking_url = CARRIER_TRACKING_URLS.get(carrier, "") + tracking
    est_delivery = (date.today() + timedelta(days=3)).strftime("%B %d")

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:560px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:8px;}}.logo span{{color:#F8A5B8;}}.tagline{{text-align:center;font-size:11px;letter-spacing:.2em;color:#C4BAC0;text-transform:uppercase;margin-bottom:40px;}}.body-text{{font-size:16px;line-height:1.8;color:#2D2A2E;margin-bottom:24px;}}.shipped-badge{{text-align:center;background:#F9FDF9;border:1px solid #72B08A;border-radius:12px;padding:24px;margin:24px 0;}}.shipped-icon{{font-size:36px;margin-bottom:8px;}}.shipped-label{{font-size:13px;letter-spacing:.2em;color:#72B08A;text-transform:uppercase;font-family:monospace;}}.tracking-box{{background:#fff;border:1px solid #F0E8E8;border-radius:12px;padding:20px 24px;margin:24px 0;}}.tracking-label{{font-size:11px;letter-spacing:.2em;color:#C4BAC0;text-transform:uppercase;font-family:monospace;margin-bottom:8px;}}.tracking-num{{font-family:monospace;font-size:18px;color:#2D2A2E;letter-spacing:.1em;margin-bottom:4px;}}.carrier-name{{font-size:12px;color:#8A8490;font-family:monospace;}}.btn{{display:block;width:fit-content;margin:8px auto 0;background:#F8A5B8;color:#fff;text-decoration:none;padding:12px 28px;font-size:13px;letter-spacing:.1em;text-transform:uppercase;font-family:Georgia,serif;border-radius:8px;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:48px;line-height:1.8;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span></div>
  <div class="tagline">Premium Biotech Skincare · Canada</div>
  <div class="shipped-badge">
    <div class="shipped-icon">📦</div>
    <div class="shipped-label">Your order has shipped</div>
  </div>
  <p class="body-text">Hi {first}, great news — your order <strong>{oid}</strong> is on its way to {city}.</p>
  <p class="body-text" style="font-size:14px;color:#8A8490;">Estimated delivery: <strong style="color:#2D2A2E;">{est_delivery}</strong></p>
  <div class="tracking-box">
    <div class="tracking-label">Tracking Number</div>
    <div class="tracking-num">{tracking}</div>
    <div class="carrier-name">{carrier}</div>
    <a href="{tracking_url}" class="btn">Track My Package</a>
  </div>
  <p class="body-text" style="font-size:14px;color:#8A8490;">Once your order arrives, you'll be starting your PDRN repair cycle. We'll be in touch around day 25 with tips to maximize your results.</p>
  <div class="footer">ReRoots · Premium Biotech Skincare · Canada<br>Questions? Reply to this email — we respond within 24 hours.</div>
</div></body></html>"""

    await send_email(email, name, f"Your ReRoots order is on its way — {oid}", html)
    print(f"[SHIPPING NOTIFY] Sent to {email} | Tracking: {tracking}")


# ════════════════════════════════════════════════════════════
# 4. DAY 7 + DAY 14 REPURCHASE EMAILS
# ════════════════════════════════════════════════════════════

def email_day7(customer_name: str, product: str, customer_email: str) -> dict:
    """Day 7 — Week 1 check-in + application tips"""
    first = customer_name.split()[0] if customer_name else "there"
    subject = f"Week 1 with ReRoots — what to expect, {first}"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:560px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:8px;}}.logo span{{color:#F8A5B8;}}.tagline{{text-align:center;font-size:11px;letter-spacing:.2em;color:#C4BAC0;text-transform:uppercase;margin-bottom:40px;}}.body-text{{font-size:16px;line-height:1.8;color:#2D2A2E;margin-bottom:24px;}}.timeline{{margin:24px 0;}}.tl-item{{display:flex;gap:16px;margin-bottom:20px;align-items:flex-start;}}.tl-dot{{width:32px;height:32px;border-radius:50%;background:#FEF2F4;border:2px solid #F8A5B8;display:flex;align-items:center;justify-content:center;font-family:monospace;font-size:12px;color:#F8A5B8;flex-shrink:0;}}.tl-active{{background:#F8A5B8;color:#fff;}}.tl-text{{font-size:15px;color:#2D2A2E;line-height:1.7;padding-top:4px;}}.tl-label{{font-weight:bold;}}.tip-box{{background:#FEF2F4;border-left:3px solid #F8A5B8;padding:16px 20px;margin:24px 0;font-size:14px;color:#2D2A2E;line-height:1.8;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:48px;line-height:1.8;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span></div><div class="tagline">Premium Biotech Skincare · Canada</div>
  <p class="body-text">Hi {first}, you're 7 days into your PDRN cycle.</p>
  <p class="body-text">At this stage, PDRN is working beneath the surface — stimulating your skin's repair pathways at a cellular level. Visible results typically arrive between days 14–21, so you're right on track.</p>
  <div class="timeline">
    <div class="tl-item"><div class="tl-dot tl-active">7</div><div class="tl-text"><span class="tl-label">Now (Day 7):</span> Cellular signalling active. Skin may feel more hydrated.</div></div>
    <div class="tl-item"><div class="tl-dot">14</div><div class="tl-text"><span class="tl-label">Day 14:</span> Fibroblast activity increases. Fine lines begin softening.</div></div>
    <div class="tl-item"><div class="tl-dot">21</div><div class="tl-text"><span class="tl-label">Day 21:</span> Visible results. Improved elasticity, reduced texture.</div></div>
    <div class="tl-item"><div class="tl-dot">28</div><div class="tl-text"><span class="tl-label">Day 28:</span> Full cycle complete. Peak results.</div></div>
  </div>
  <div class="tip-box">
    <strong>Tip for best results:</strong> Apply to slightly damp skin — PDRN absorbs more effectively with a small amount of water present.
  </div>
  <div class="footer">ReRoots · Premium Biotech Skincare · Canada<br><a href="{SITE_URL}/unsubscribe?email={customer_email}" style="color:#C4BAC0;">Unsubscribe</a></div>
</div></body></html>"""
    return {"subject": subject, "html": html}


def email_day14(customer_name: str, product: str, customer_email: str) -> dict:
    """Day 14 — Progress check-in + social share prompt"""
    first = customer_name.split()[0] if customer_name else "there"
    subject = f"Day 14 — are you seeing results yet, {first}?"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:560px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:8px;}}.logo span{{color:#F8A5B8;}}.tagline{{text-align:center;font-size:11px;letter-spacing:.2em;color:#C4BAC0;text-transform:uppercase;margin-bottom:40px;}}.body-text{{font-size:16px;line-height:1.8;color:#2D2A2E;margin-bottom:24px;}}.milestone{{text-align:center;background:#FEF2F4;border:1px solid #F8A5B8;border-radius:12px;padding:28px;margin:24px 0;}}.milestone-num{{font-size:52px;color:#F8A5B8;line-height:1;font-family:Georgia,serif;}}.milestone-label{{font-size:12px;letter-spacing:.2em;color:#8A8490;text-transform:uppercase;margin-top:6px;font-family:monospace;}}.results-box{{background:#F9FDF9;border-left:3px solid #72B08A;padding:16px 20px;margin:24px 0;font-size:15px;color:#2D2A2E;line-height:1.9;}}.btn{{display:block;width:fit-content;margin:24px auto;background:#F8A5B8;color:#fff;text-decoration:none;padding:12px 28px;font-size:13px;letter-spacing:.1em;text-transform:uppercase;font-family:Georgia,serif;border-radius:8px;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:48px;line-height:1.8;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span></div><div class="tagline">Premium Biotech Skincare · Canada</div>
  <div class="milestone"><div class="milestone-num">14</div><div class="milestone-label">Days In</div></div>
  <p class="body-text">Hi {first}, you've hit the halfway point of your first PDRN cycle.</p>
  <p class="body-text">This is typically when our customers start noticing real changes — not just a feeling, but something visible in the mirror.</p>
  <div class="results-box">
    <strong>What you might be noticing by now:</strong><br>
    · Fine lines around eyes appear softer<br>
    · Skin feels firmer to the touch<br>
    · Overall tone looks more even and luminous<br>
    · Texture is smoother — pores appear refined
  </div>
  <p class="body-text">If you're seeing results, we'd love to hear about it. Tag us <strong>@reroots.ca</strong> on Instagram!</p>
  <a href="https://instagram.com/reroots.ca" class="btn">Share My Results</a>
  <div class="footer">ReRoots · Premium Biotech Skincare · Canada<br><a href="{SITE_URL}/unsubscribe?email={customer_email}" style="color:#C4BAC0;">Unsubscribe</a></div>
</div></body></html>"""
    return {"subject": subject, "html": html}


# ════════════════════════════════════════════════════════════
# 5. LOW STOCK ALERT EMAIL TO OWNER
# ════════════════════════════════════════════════════════════

async def check_low_stock_alerts():
    """
    Check all ingredients against reorder point.
    Send alert email to owner if any are low or critical.
    Runs daily at 8:00 AM.
    """
    try:
        low = await db["ingredients"].find({
            "$expr": {"$lte": ["$stock", "$reorderPoint"]}
        }).to_list(100)

        critical = [i for i in low if i.get("stock", 0) == 0]
        warning = [i for i in low if i.get("stock", 0) > 0]

        if not low:
            print("[LOW STOCK] All ingredients above reorder point ✓")
            return

        already = await db["automation_logs"].find_one({
            "automationType": "low_stock_alert",
            "date": date.today().isoformat()
        })
        if already:
            return

        rows = ""
        for i in critical:
            rows += f'<tr><td style="padding:10px;border-bottom:1px solid #F0E8E8;font-family:Georgia,serif;color:#2D2A2E;">{i["name"]}</td><td style="padding:10px;border-bottom:1px solid #F0E8E8;text-align:center;color:#E07070;font-family:monospace;font-weight:bold;">OUT OF STOCK</td><td style="padding:10px;border-bottom:1px solid #F0E8E8;text-align:center;color:#8A8490;font-family:monospace;">{i.get("reorderPoint","—")} {i.get("unit","")}</td><td style="padding:10px;border-bottom:1px solid #F0E8E8;color:#8A8490;font-family:monospace;">{i.get("supplier","—")}</td></tr>'
        for i in warning:
            rows += f'<tr><td style="padding:10px;border-bottom:1px solid #F0E8E8;font-family:Georgia,serif;color:#2D2A2E;">{i["name"]}</td><td style="padding:10px;border-bottom:1px solid #F0E8E8;text-align:center;color:#E8A860;font-family:monospace;">{i["stock"]} {i.get("unit","")}</td><td style="padding:10px;border-bottom:1px solid #F0E8E8;text-align:center;color:#8A8490;font-family:monospace;">{i.get("reorderPoint","—")} {i.get("unit","")}</td><td style="padding:10px;border-bottom:1px solid #F0E8E8;color:#8A8490;font-family:monospace;">{i.get("supplier","—")}</td></tr>'

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:620px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:40px;}}.logo span{{color:#F8A5B8;}}.alert-header{{background:#E070700D;border:1px solid #E0707030;border-radius:10px;padding:16px 20px;margin-bottom:24px;display:flex;gap:12px;align-items:center;}}.body-text{{font-size:15px;line-height:1.8;color:#2D2A2E;margin-bottom:20px;}}.table-wrap{{border:1px solid #F0E8E8;border-radius:10px;overflow:hidden;margin-bottom:24px;}}table{{width:100%;border-collapse:collapse;}}th{{background:#FEF6F7;padding:10px;text-align:left;font-size:11px;letter-spacing:.15em;color:#C4BAC0;text-transform:uppercase;font-family:monospace;font-weight:400;}}.btn{{display:inline-block;background:#F8A5B8;color:#fff;text-decoration:none;padding:12px 24px;font-size:13px;letter-spacing:.1em;text-transform:uppercase;border-radius:8px;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:40px;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span> <span style="font-size:14px;color:#C4BAC0;letter-spacing:.1em;">· INVENTORY ALERT</span></div>
  <div class="alert-header">⚠️ <div><strong style="color:#E07070;">{len(critical)} out of stock</strong>, <strong style="color:#E8A860;">{len(warning)} below reorder point</strong> — {date.today().strftime("%B %d, %Y")}</div></div>
  <div class="table-wrap"><table><thead><tr><th>Ingredient</th><th>Current Stock</th><th>Reorder At</th><th>Supplier</th></tr></thead><tbody>{rows}</tbody></table></div>
  <p class="body-text">Log in to the inventory module to adjust stock or place a reorder.</p>
  <a href="{SITE_URL}/admin?section=inventory-batch" class="btn">View Inventory</a>
  <div class="footer">ReRoots Automated Alert · {date.today().strftime("%B %d, %Y")}</div>
</div></body></html>"""

        ok = await send_email(OWNER_EMAIL, OWNER_NAME, f"⚠️ ReRoots Low Stock Alert — {len(low)} ingredient{'s' if len(low)>1 else ''} need attention", html)

        await db["automation_logs"].insert_one({
            "automationType": "low_stock_alert",
            "date": date.today().isoformat(),
            "sentAt": datetime.utcnow().isoformat(),
            "itemsAlerted": len(low),
            "success": ok
        })
        print(f"[LOW STOCK ALERT] Sent to {OWNER_EMAIL} | {len(low)} items")

    except Exception as e:
        print(f"[LOW STOCK ALERT ERROR] {e}")


# ════════════════════════════════════════════════════════════
# 6. NPN EXPIRY REMINDER TO OWNER
# ════════════════════════════════════════════════════════════

async def check_npn_expiry_reminders():
    """Check NPN expiry dates and send reminders at 90, 30, and 7 days."""
    try:
        ingredients = await db["ingredients"].find(
            {"expiryDate": {"$exists": True}, "hcStatus": "Approved"}
        ).to_list(500)

        alerts = []
        for ing in ingredients:
            exp = ing.get("expiryDate")
            if not exp:
                continue
            try:
                days = (datetime.strptime(exp, "%Y-%m-%d").date() - date.today()).days
            except Exception:
                continue
            if days in [90, 30, 7]:
                urgency = "CRITICAL" if days <= 7 else "URGENT" if days <= 30 else "NOTICE"
                color = "#E07070" if days <= 7 else "#E8A860" if days <= 30 else "#7AAEC8"
                alerts.append({
                    "name": ing["name"], "npn": ing.get("hcNumber", "—"),
                    "days": days, "expiry": exp, "urgency": urgency,
                    "color": color, "supplier": ing.get("supplier", "—")
                })

        if not alerts:
            return

        rows = "".join([
            f'<tr><td style="padding:12px;border-bottom:1px solid #F0E8E8;font-family:Georgia,serif;color:#2D2A2E;">{a["name"]}</td><td style="padding:12px;border-bottom:1px solid #F0E8E8;font-family:monospace;color:#8A8490;">{a["npn"]}</td><td style="padding:12px;border-bottom:1px solid #F0E8E8;font-family:monospace;color:#2D2A2E;">{fDate(a["expiry"])}</td><td style="padding:12px;border-bottom:1px solid #F0E8E8;text-align:center;"><span style="background:{a["color"]}15;color:{a["color"]};border:1px solid {a["color"]}30;padding:3px 10px;border-radius:20px;font-size:12px;font-family:monospace;">{a["days"]} days</span></td></tr>'
            for a in alerts
        ])

        most_urgent = min(alerts, key=lambda x: x["days"])
        subject = f"{'🚨' if most_urgent['days'] <= 7 else '⚠️'} ReRoots NPN Expiry — {len(alerts)} certificate{'s' if len(alerts)>1 else ''} need attention"

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:620px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:40px;}}.logo span{{color:#F8A5B8;}}.body-text{{font-size:15px;line-height:1.8;color:#2D2A2E;margin-bottom:20px;}}.table-wrap{{border:1px solid #F0E8E8;border-radius:10px;overflow:hidden;margin-bottom:24px;}}table{{width:100%;border-collapse:collapse;}}th{{background:#FEF6F7;padding:10px;text-align:left;font-size:11px;letter-spacing:.15em;color:#C4BAC0;text-transform:uppercase;font-family:monospace;font-weight:400;}}.btn{{display:inline-block;background:#F8A5B8;color:#fff;text-decoration:none;padding:12px 24px;font-size:13px;letter-spacing:.1em;text-transform:uppercase;border-radius:8px;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:40px;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span> <span style="font-size:14px;color:#C4BAC0;">· NPN EXPIRY REMINDER</span></div>
  <p class="body-text">The following Health Canada NPN certificates are approaching expiry and require renewal action:</p>
  <div class="table-wrap"><table><thead><tr><th>Ingredient</th><th>NPN Number</th><th>Expiry Date</th><th>Days Left</th></tr></thead><tbody>{rows}</tbody></table></div>
  <p class="body-text" style="font-size:14px;color:#8A8490;">Log in to the compliance module to initiate renewal or update certificate status.</p>
  <a href="{SITE_URL}/admin?section=hc-compliance" class="btn">View Compliance Tracker</a>
  <div class="footer">ReRoots Automated Alert · {date.today().strftime("%B %d, %Y")}</div>
</div></body></html>"""

        await send_email(OWNER_EMAIL, OWNER_NAME, subject, html)
        print(f"[NPN EXPIRY ALERT] Sent | {len(alerts)} certificates")

    except Exception as e:
        print(f"[NPN EXPIRY ERROR] {e}")


# ════════════════════════════════════════════════════════════
# 7. MONTHLY P&L AUTO-EMAIL TO OWNER
# ════════════════════════════════════════════════════════════

async def send_monthly_pnl():
    """Send monthly P&L summary email to owner on the 1st of each month."""
    try:
        today_d = date.today()
        first_this = today_d.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        period_label = last_month_end.strftime("%B %Y")

        txns = await db["accounting_transactions"].find({
            "date": {
                "$gte": last_month_start.isoformat(),
                "$lte": last_month_end.isoformat()
            }
        }).to_list(2000)

        revenue = sum(t.get("amount", 0) for t in txns if t.get("type") == "Revenue" and t.get("amount", 0) > 0)
        cogs = sum(abs(t.get("amount", 0)) for t in txns if t.get("category") == "COGS")
        refunds = sum(abs(t.get("amount", 0)) for t in txns if t.get("category") == "Refund Issued")
        marketing = sum(abs(t.get("amount", 0)) for t in txns if t.get("category") == "Marketing")
        ops = sum(abs(t.get("amount", 0)) for t in txns if t.get("category") == "Operations")
        other_exp = sum(abs(t.get("amount", 0)) for t in txns if t.get("type") == "Expense" and t.get("category") not in ["COGS", "Refund Issued", "Marketing", "Operations"])
        total_exp = cogs + refunds + marketing + ops + other_exp
        gross = revenue - cogs
        net = revenue - total_exp
        tax_col = sum(t.get("tax", 0) for t in txns if t.get("type") == "Revenue")

        gm_pct = round(gross / revenue * 100, 1) if revenue > 0 else 0
        nm_pct = round(net / revenue * 100, 1) if revenue > 0 else 0
        net_color = "#72B08A" if net >= 0 else "#E07070"

        rows = [
            ("Gross Revenue", revenue, "#2D2A2E", True),
            ("Cost of Goods Sold", -cogs, "#E07070", False),
            ("Gross Profit", gross, "#72B08A", True),
            ("Marketing", -marketing, "#8A8490", False),
            ("Operations", -ops, "#8A8490", False),
            ("Refunds Issued", -refunds, "#8A8490", False),
            ("Other Expenses", -other_exp, "#8A8490", False),
            ("Net Profit", net, net_color, True),
        ]

        table_html = "".join([
            f'<tr style="background:{"#FEF2F4" if bold else "transparent"}"><td style="padding:{"12px" if bold else "9px"} 16px;font-family:Georgia,serif;font-size:{"15px" if bold else "14px"};color:#2D2A2E;{"font-weight:500;" if bold else "padding-left:28px;"}">{label}</td><td style="padding:{"12px" if bold else "9px"} 16px;text-align:right;font-family:monospace;font-size:{"15px" if bold else "14px"};color:{color};{"font-weight:500;" if bold else ""}">{"+" if val >= 0 else ""}{fCur(val)}</td></tr>'
            for label, val, color, bold in rows
        ])

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{font-family:Georgia,serif;background:#FDF9F9;margin:0;padding:0;}}.container{{max-width:580px;margin:0 auto;padding:40px 20px;}}.logo{{text-align:center;letter-spacing:.3em;font-size:22px;color:#2D2A2E;margin-bottom:8px;}}.logo span{{color:#F8A5B8;}}.period{{text-align:center;font-size:12px;letter-spacing:.2em;color:#C4BAC0;text-transform:uppercase;font-family:monospace;margin-bottom:40px;}}.kpis{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:#F0E8E8;margin-bottom:24px;}}.kpi{{background:#fff;padding:16px;text-align:center;}}.kpi-val{{font-size:22px;font-family:Georgia,serif;font-weight:300;color:#F8A5B8;line-height:1;}}.kpi-label{{font-size:11px;letter-spacing:.15em;color:#C4BAC0;text-transform:uppercase;font-family:monospace;margin-top:4px;}}.table-wrap{{border:1px solid #F0E8E8;border-radius:10px;overflow:hidden;margin-bottom:24px;}}table{{width:100%;border-collapse:collapse;}}.tax-note{{background:#FEF2F4;border-radius:8px;padding:12px 16px;font-size:13px;color:#8A8490;font-family:monospace;margin-bottom:24px;}}.btn{{display:inline-block;background:#F8A5B8;color:#fff;text-decoration:none;padding:12px 24px;font-size:13px;letter-spacing:.1em;text-transform:uppercase;border-radius:8px;}}.footer{{text-align:center;font-size:12px;color:#C4BAC0;margin-top:40px;line-height:1.8;}}</style></head>
<body><div class="container">
  <div class="logo">RE<span>ROOTS</span></div>
  <div class="period">Monthly P&L Report · {period_label}</div>
  <div class="kpis">
    <div class="kpi"><div class="kpi-val">{fCur(revenue)}</div><div class="kpi-label">Revenue</div></div>
    <div class="kpi"><div class="kpi-val" style="color:#72B08A;">{gm_pct}%</div><div class="kpi-label">Gross Margin</div></div>
    <div class="kpi"><div class="kpi-val" style="color:{net_color};">{nm_pct}%</div><div class="kpi-label">Net Margin</div></div>
  </div>
  <div class="table-wrap"><table>{table_html}</table></div>
  <div class="tax-note">GST/HST Collected: <strong style="color:#2D2A2E;">{fCur(tax_col)}</strong> — remit to CRA by quarterly deadline</div>
  <a href="{SITE_URL}/admin?section=accounting-gst" class="btn">View Full Accounting</a>
  <div class="footer">ReRoots Aesthetics Inc. · Automated Monthly Report<br>{period_label}</div>
</div></body></html>"""

        await send_email(OWNER_EMAIL, OWNER_NAME, f"ReRoots {period_label} P&L — {fCur(net)} net profit", html)
        print(f"[MONTHLY PNL] Sent for {period_label} | Net: {fCur(net)}")

    except Exception as e:
        print(f"[MONTHLY PNL ERROR] {e}")


# ════════════════════════════════════════════════════════════
# 8. UNIQUE DISCOUNT CODES PER CUSTOMER
# ════════════════════════════════════════════════════════════

def generate_discount_code(customer_name: str) -> str:
    """Generate a unique, single-use discount code per customer. Format: NAME-XXXX"""
    prefix = (customer_name.split()[0] if customer_name else "REROOTS").upper()[:5]
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{suffix}"


async def create_discount_code(customer_email: str, customer_name: str, discount_pct: int = 10, expiry_days: int = 7) -> str:
    """Create a unique discount code, save to DB, return the code string."""
    code = generate_discount_code(customer_name)
    expiry = (date.today() + timedelta(days=expiry_days)).isoformat()

    await db["discount_codes"].insert_one({
        "code": code,
        "customerEmail": customer_email,
        "discountPct": discount_pct,
        "expiryDate": expiry,
        "used": False,
        "createdAt": datetime.utcnow().isoformat(),
        "type": "winback"
    })
    print(f"[DISCOUNT CODE] Created: {code} for {customer_email} | Expires {expiry}")
    return code


async def validate_discount_code(code: str) -> dict:
    """Validate a discount code at checkout. Returns { valid, discountPct, message }"""
    record = await db["discount_codes"].find_one({"code": code.upper().strip()})
    if not record:
        return {"valid": False, "discountPct": 0, "message": "Invalid code."}
    if record.get("used"):
        return {"valid": False, "discountPct": 0, "message": "This code has already been used."}
    if record.get("expiryDate") and record["expiryDate"] < date.today().isoformat():
        return {"valid": False, "discountPct": 0, "message": "This code has expired."}
    return {"valid": True, "discountPct": record.get("discountPct", 10), "message": f"{record.get('discountPct',10)}% off applied"}


async def mark_discount_code_used(code: str):
    """Mark a code as used after successful checkout."""
    await db["discount_codes"].update_one(
        {"code": code.upper()},
        {"$set": {"used": True, "usedAt": datetime.utcnow().isoformat()}}
    )


# ─── API ENDPOINTS ───────────────────────────────────────────

@router.get("/discount/{code}")
async def check_discount_code(code: str):
    """Public endpoint — validate discount code at checkout."""
    result = await validate_discount_code(code)
    return result


@router.post("/discount/{code}/redeem")
async def redeem_discount_code(code: str):
    """Mark code as used after successful payment."""
    await mark_discount_code_used(code)
    return {"success": True}


@router.get("/admin/discount-codes")
async def get_discount_codes(limit: int = Query(100)):
    """Get all discount codes"""
    codes = await db["discount_codes"].find().sort("createdAt", -1).to_list(limit)
    for c in codes:
        c["_id"] = str(c["_id"])
    return codes


@router.post("/admin/alerts/test-low-stock")
async def test_low_stock_alert():
    """Manually trigger low stock alert check"""
    await check_low_stock_alerts()
    return {"success": True, "message": "Low stock check completed"}


@router.post("/admin/alerts/test-npn-expiry")
async def test_npn_expiry_alert():
    """Manually trigger NPN expiry check"""
    await check_npn_expiry_reminders()
    return {"success": True, "message": "NPN expiry check completed"}


@router.post("/admin/alerts/test-monthly-pnl")
async def test_monthly_pnl():
    """Manually trigger monthly P&L email"""
    await send_monthly_pnl()
    return {"success": True, "message": "Monthly P&L email sent"}
