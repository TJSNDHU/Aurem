"""
ReRoots — Waitlist → Restock Email Trigger
File: routes/waitlist_restock.py

WHAT THIS DOES:
  When any product transitions from 0 stock → available, this
  automatically finds all waitlist subscribers for that product,
  sends each a personalised restock notification email, marks them
  as notified (no duplicates), and tracks conversion.

WIRE IN 3 PLACES (see WIRING section at bottom):
  1. PUT /api/products/{id}     → manual admin stock update
  2. FlagShip inventory sync    → automated sync from carrier
  3. POST /api/orders           → conversion tracking

ALSO ADDS 2 ENDPOINTS:
  POST /api/admin/inventory/trigger-restock  → manual test trigger
  GET  /api/admin/restock-notifications/stats → dashboard stats
"""

from datetime import datetime
import os


# ── Restock email template ───────────────────────────────────────

def build_restock_email(name: str, product: dict, stock_qty: int) -> dict:
    first         = (name or "there").split()[0]
    product_name  = product.get("name", "Your waitlisted product")
    product_price = product.get("price", "")
    product_url   = product.get("url") or f"https://reroots.ca/products/{product.get('slug','')}"
    product_img   = product.get("image", "")
    is_limited    = stock_qty < 10

    badge = f"""
      <div style="display:inline-block;background:#D05858;color:#fff;
                  font-family:'Inter',sans-serif;font-size:10px;font-weight:600;
                  letter-spacing:0.1em;padding:4px 12px;border-radius:20px;
                  margin-bottom:16px;text-transform:uppercase;">
        Only {stock_qty} left
      </div>""" if is_limited else ""

    img_block = f"""
      <img src="{product_img}"
           style="width:80px;height:80px;border-radius:10px;
                  object-fit:cover;flex-shrink:0;" />""" if product_img else ""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
</head>
<body style="margin:0;padding:0;background:#F5EFEF;
             font-family:'Inter',Helvetica,sans-serif;">
<div style="max-width:520px;margin:0 auto;padding:32px 16px;">

  <div style="text-align:center;padding:24px 0 18px;">
    <p style="font-family:'Cormorant Garamond',Georgia,serif;font-size:26px;
              letter-spacing:0.28em;color:#2D2A2E;font-weight:300;margin:0;">
      RE<span style="color:#F8A5B8;">ROOTS</span></p>
    <p style="font-size:9px;letter-spacing:0.22em;color:#C4BAC0;
              text-transform:uppercase;margin:4px 0 0;">
      BIOTECH SKINCARE · TORONTO, CANADA</p>
  </div>

  <div style="background:#fff;border-radius:16px;overflow:hidden;
              box-shadow:0 2px 20px rgba(45,42,46,0.06);">
    <div style="height:3px;background:linear-gradient(to right,#F8A5B8,#D4788A);"></div>

    <div style="padding:36px 32px 24px;text-align:center;">
      {badge}
      <p style="font-size:11px;letter-spacing:0.2em;color:#F8A5B8;
                text-transform:uppercase;font-weight:500;margin:0 0 10px;">
        Back In Stock</p>
      <h1 style="font-family:'Cormorant Garamond',Georgia,serif;font-size:28px;
                 color:#2D2A2E;font-weight:300;margin:0 0 10px;">
        You're first in line, {first}</h1>
      <p style="font-size:14px;color:#8A8490;line-height:1.7;margin:0;">
        The product you waited for is available again —
        and you're hearing about it before the public.</p>
    </div>

    <div style="padding:0 32px 24px;">
      <div style="background:#FDF9F9;border:1px solid #F8A5B8;border-radius:12px;
                  padding:18px;margin-bottom:22px;
                  display:flex;align-items:center;gap:14px;">
        {img_block}
        <div>
          <p style="font-size:10px;letter-spacing:0.15em;color:#C4BAC0;
                    text-transform:uppercase;margin:0 0 5px;">Waitlisted Product</p>
          <p style="font-size:15px;color:#2D2A2E;font-weight:500;
                    margin:0 0 5px;">{product_name}</p>
          {f'<p style="font-size:17px;color:#F8A5B8;font-weight:600;margin:0;">{product_price} CAD</p>' if product_price else ''}
          {"<p style='font-size:11px;color:#D05858;font-weight:600;margin:5px 0 0;'>⚠ Limited — " + str(stock_qty) + " units remaining</p>" if is_limited else ""}
        </div>
      </div>

      <a href="{product_url}"
         style="display:block;background:#F8A5B8;color:#fff;text-align:center;
                padding:15px;border-radius:8px;text-decoration:none;
                font-family:'Inter',sans-serif;font-size:14px;font-weight:600;
                letter-spacing:0.04em;margin-bottom:14px;">
        {"Shop Before It's Gone →" if is_limited else "Shop Now →"}</a>

      <p style="font-size:12px;color:#8A8490;line-height:1.7;text-align:center;margin:0;">
        You're seeing this early because you joined the waitlist.<br/>
        This notification goes to a limited number of people.
      </p>
    </div>

    <div style="background:#FDF9F9;border-top:1px solid #F0E8E8;padding:16px 32px;">
      <p style="font-size:9px;letter-spacing:0.15em;color:#C4BAC0;
                text-transform:uppercase;margin:0 0 5px;">The Science</p>
      <p style="font-size:12px;color:#8A8490;line-height:1.6;margin:0;">
        PDRN 2% + TXA 5% + Argireline 17% — 37.25% total active concentration.
        Your 28-day protocol begins the day your order arrives.</p>
    </div>

    <div style="background:#FDF9F9;border-top:1px solid #F0E8E8;
                padding:18px 32px;text-align:center;">
      <p style="font-size:10px;color:#C4BAC0;letter-spacing:0.1em;
                text-transform:uppercase;margin:0 0 5px;">
        REROOTS AESTHETICS INC. · TORONTO, CANADA</p>
      <p style="font-size:10px;color:#D4C8C8;margin:0;">
        <a href="https://reroots.ca" style="color:#F8A5B8;text-decoration:none;">reroots.ca</a>
        &nbsp;·&nbsp;
        <a href="https://reroots.ca/pages/unsubscribe"
           style="color:#C4BAC0;text-decoration:none;">Unsubscribe</a>
      </p>
    </div>
  </div>
</div></body></html>"""

    prefix  = f"⚡ Only {stock_qty} left — " if is_limited else ""
    subject = f"{prefix}Back in stock: {product_name}, {first}"
    return {"html": html, "subject": subject}


# ── Central send helper ──────────────────────────────────────────

async def _send_email(to: str, subject: str, html: str) -> bool:
    api_key = os.getenv("SENDGRID_API_KEY", "")
    if not api_key:
        print(f"⚠️  SENDGRID_API_KEY not set — email to {to} skipped")
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        sg  = sendgrid.SendGridAPIClient(api_key=api_key)
        msg = Mail(
            from_email=(os.getenv("SENDGRID_FROM_EMAIL", "hello@reroots.ca"),
                        os.getenv("SENDGRID_FROM_NAME", "ReRoots")),
            to_emails=to, subject=subject, html_content=html,
        )
        r = sg.send(msg)
        return r.status_code in [200, 202]
    except Exception as e:
        print(f"❌ Email error ({to}): {e}")
        return False


# ── Core trigger ─────────────────────────────────────────────────

async def trigger_restock_notifications(
    db,
    product_id: str,
    new_stock_qty: int,
    previous_stock_qty: int = 0,
) -> dict:
    """
    Call when a product's stock changes.
    Only fires when transitioning 0 → available.

    Returns: {"fired": bool, "notified": int, "errors": int, ...}
    """
    from bson import ObjectId

    # Guard: only fire on 0 → positive transition
    if new_stock_qty <= 0:
        return {"fired": False, "reason": "stock still zero"}
    if previous_stock_qty > 0:
        return {"fired": False, "reason": "product was already in stock"}

    # Load product
    product = None
    try:
        product = await db.products.find_one({"_id": ObjectId(product_id)})
    except Exception:
        pass
    if not product:
        product = await db.products.find_one({
            "$or": [{"slug": product_id}, {"sku": product_id}]
        })
    if not product:
        return {"fired": False, "reason": f"product not found: {product_id}"}

    price_raw = product.get("price") or product.get("salePrice") or ""
    product_data = {
        "name":  product.get("name", ""),
        "price": f"${price_raw}" if price_raw and not str(price_raw).startswith("$") else str(price_raw),
        "url":   f"https://reroots.ca/products/{product.get('slug', str(product['_id']))}",
        "image": product.get("image") or product.get("imageUrl") or "",
        "slug":  product.get("slug", str(product["_id"])),
    }

    # Gather waitlist subscribers (both collections, deduplicate by email)
    product_waitlist = await db.waitlist_subscribers.find({
        "$or": [
            {"productId":   str(product["_id"])},
            {"productSlug": product.get("slug", "")},
            {"productId":   {"$exists": False}},
        ],
        "notified":     {"$ne": True},
        "unsubscribed": {"$ne": True},
    }).to_list(None)

    general_waitlist = await db.subscribers.find({
        "type":         "waitlist",
        "notified":     {"$ne": True},
        "unsubscribed": {"$ne": True},
    }).to_list(None)

    # Deduplicate by email
    seen    = {}
    all_subs = []
    for s in (product_waitlist + general_waitlist):
        email = (s.get("email") or "").lower().strip()
        if email and email not in seen:
            seen[email] = True
            all_subs.append(s)

    if not all_subs:
        return {
            "fired": True, "product": product_data["name"],
            "notified": 0, "reason": "no waitlist subscribers",
        }

    notified_emails = []
    error_emails    = []

    for sub in all_subs:
        email = (sub.get("email") or "").strip()
        name  = sub.get("name") or sub.get("firstName") or ""
        if not email:
            continue

        try:
            tmpl    = build_restock_email(name, product_data, new_stock_qty)
            success = await _send_email(email, tmpl["subject"], tmpl["html"])

            if success:
                # Mark notified in whichever collection it came from
                coll = "waitlist_subscribers" if sub in product_waitlist else "subscribers"
                await db[coll].update_one(
                    {"_id": sub["_id"]},
                    {"$set": {
                        "notified":        True,
                        "notifiedAt":      datetime.utcnow(),
                        "notifiedProduct": str(product["_id"]),
                    }}
                )
                # Audit log
                await db.restock_notifications.insert_one({
                    "email":       email,
                    "productId":   str(product["_id"]),
                    "productName": product_data["name"],
                    "sentAt":      datetime.utcnow(),
                    "stockQty":    new_stock_qty,
                    "converted":   False,
                })
                notified_emails.append(email)
            else:
                error_emails.append(email)

        except Exception as e:
            error_emails.append(f"{email}: {e}")

    print(f"✅ Restock: '{product_data['name']}' → {len(notified_emails)} notified, {len(error_emails)} errors")
    return {
        "fired":    True,
        "product":  product_data["name"],
        "notified": len(notified_emails),
        "errors":   len(error_emails),
        "errorList": error_emails[:5],
    }


async def mark_restock_conversion(db, email: str, product_id: str):
    """Call from order creation to track restock → purchase CVR."""
    await db.restock_notifications.update_many(
        {"email": email.lower(), "productId": product_id, "converted": False},
        {"$set": {"converted": True, "convertedAt": datetime.utcnow()}}
    )


# ════════════════════════════════════════════════════════════════
# WIRING GUIDE
# ════════════════════════════════════════════════════════════════
"""
IMPORT (top of server.py):
    from routes.waitlist_restock import (
        trigger_restock_notifications,
        mark_restock_conversion,
    )

── WIRE 1: PUT /api/products/{product_id} ──────────────────────
    # Before updating:
    existing   = await db.products.find_one({"_id": ObjectId(product_id)})
    prev_stock = (existing or {}).get("stock") or (existing or {}).get("quantity") or 0

    # After updating (your existing update logic here):
    new_stock = update_data.get("stock") or update_data.get("quantity") or 0
    if new_stock > 0 and prev_stock == 0:
        await trigger_restock_notifications(db, str(product_id), new_stock, prev_stock)

── WIRE 2: FlagShip inventory sync ─────────────────────────────
    for item in flagship_items:
        existing  = await db.products.find_one({"sku": item["sku"]})
        prev_qty  = (existing or {}).get("stock", 0)
        new_qty   = item["quantity"]
        await db.products.update_one({"sku": item["sku"]}, {"$set": {"stock": new_qty}})
        if new_qty > 0 and prev_qty == 0:
            await trigger_restock_notifications(db, str(existing["_id"]), new_qty, prev_qty)

── WIRE 3: POST /api/orders — conversion tracking ──────────────
    for item in order_data.get("items", []):
        await mark_restock_conversion(db, customer_email, str(item.get("productId","")))

── ADMIN ENDPOINTS (paste into server.py) ──────────────────────

@app.post("/api/admin/inventory/trigger-restock")
async def manual_restock_trigger(data: dict, db=Depends(get_db)):
    product_id = data.get("productId") or data.get("product_id")
    new_stock  = int(data.get("newStock") or data.get("stock") or 1)
    if not product_id:
        raise HTTPException(status_code=400, detail="productId required")
    return await trigger_restock_notifications(db, product_id, new_stock, 0)

@app.get("/api/admin/restock-notifications/stats")
async def restock_stats(db=Depends(get_db)):
    total_sent      = await db.restock_notifications.count_documents({})
    total_converted = await db.restock_notifications.count_documents({"converted": True})
    wl_a = await db.waitlist_subscribers.count_documents({"notified": {"$ne": True}})
    wl_b = await db.subscribers.count_documents({"type": "waitlist", "notified": {"$ne": True}})
    return {
        "waitlist_pending":   wl_a + wl_b,
        "notifications_sent": total_sent,
        "conversions":        total_converted,
        "cvr_pct": round(total_converted / total_sent * 100, 1) if total_sent else 0,
    }
"""
