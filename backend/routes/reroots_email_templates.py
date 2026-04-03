"""
ReRoots — Production Email Templates
13 on-brand HTML email templates for the complete customer journey.

Usage:
    from routes.reroots_email_templates import order_confirmation
    tmpl = order_confirmation(order)
    await sendgrid_send_email(to=customer_email, subject=tmpl["subject"], html_body=tmpl["html"])
"""
from datetime import datetime, timezone


# ─── BRAND CONSTANTS ──────────────────────────────────────────────
BRAND = {
    "name": "ReRoots",
    "tagline": "Biotech Skincare",
    "location": "Toronto, Canada",
    "website": "https://reroots.ca",
    "logo_text": 'RE<span style="color:#F8A5B8;">ROOTS</span>',
}

COLORS = {
    "pink": "#F8A5B8",
    "pinkDeep": "#D4788F",
    "dark": "#2D2A2E",
    "text": "#8A8490",
    "textMuted": "#C4BAC0",
    "bg": "#FDF9F9",
    "surface": "#FFFFFF",
    "border": "#F0E8E8",
    "green": "#5BA87A",
    "gold": "#C4923A",
    "emerald": "#10B981",
}


def _roots_balance_footer(loyalty_balance: int = 0, points_earned: int = 0) -> str:
    """Generate Roots balance footer for emails (Task 8)."""
    if loyalty_balance <= 0 and points_earned <= 0:
        return ""
    
    balance_value = loyalty_balance * 0.05
    roots_to_goal = max(0, 600 - loyalty_balance)
    goal_msg = "You have enough for 30% off!" if loyalty_balance >= 600 else f"{roots_to_goal} Roots away from 30% off"
    
    earned_msg = ""
    if points_earned > 0:
        earned_msg = f'''
        <p style="margin: 0 0 8px; color: {COLORS["emerald"]}; font-weight: 500;">
          You earned {points_earned} Roots on this order!
        </p>
        '''
    
    return f'''
    <div style="background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 12px 16px; margin-top: 16px; text-align: center;">
      {earned_msg}
      <p style="margin: 0 0 4px; font-size: 12px; color: {COLORS["text"]};">
        Your Roots balance: <strong style="color: {COLORS["emerald"]};">{loyalty_balance} Roots</strong>
        (${balance_value:.2f} value)
      </p>
      <p style="margin: 0; font-size: 11px; color: {COLORS["textMuted"]};">
        {goal_msg}
      </p>
    </div>
    '''


def _base_wrapper(content: str, footer_extra: str = "") -> str:
    """Wraps content in standard ReRoots email template."""
    return f'''
    <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 520px; margin: 0 auto; padding: 40px 20px; background: {COLORS["bg"]};">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 28px; letter-spacing: 0.3em; color: {COLORS["dark"]}; font-weight: 300; margin: 0;">
          {BRAND["logo_text"]}
        </h1>
        <p style="font-size: 10px; letter-spacing: 0.2em; color: {COLORS["textMuted"]}; text-transform: uppercase; margin-top: 4px;">
          {BRAND["tagline"]} · {BRAND["location"]}
        </p>
      </div>
      
      <div style="background: {COLORS["surface"]}; border: 1px solid {COLORS["border"]}; border-radius: 12px; padding: 32px;">
        {content}
      </div>
      
      <div style="text-align: center; margin-top: 24px; font-size: 11px; color: {COLORS["textMuted"]}; letter-spacing: 0.1em;">
        {footer_extra}
        <p style="margin: 8px 0 0;">REROOTS AESTHETICS INC. · TORONTO, CANADA</p>
        <p style="margin: 4px 0 0;">Results may vary. Cosmetic use only.</p>
      </div>
    </div>
    '''


def _cta_button(text: str, url: str) -> str:
    """Standard CTA button."""
    return f'''
    <a href="{url}" style="display: block; background: {COLORS["pink"]}; color: #fff; text-align: center; padding: 14px 24px; border-radius: 8px; text-decoration: none; font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; letter-spacing: 0.05em; margin-top: 24px;">
      {text}
    </a>
    '''


# ══════════════════════════════════════════════════════════════════
# 1. ORDER CONFIRMATION
# ══════════════════════════════════════════════════════════════════
def order_confirmation(order: dict, loyalty_balance: int = 0, points_earned: int = 250) -> dict:
    """Sent immediately after order is placed."""
    order_id = str(order.get("_id", order.get("id", "N/A")))[:8]
    customer_name = order.get("customerName") or order.get("name") or "there"
    total = order.get("total") or order.get("amount") or 0
    items = order.get("items") or order.get("lineItems") or []
    
    items_html = ""
    for item in items:
        name = item.get("name") or item.get("productName", "Product")
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        items_html += f'''
        <div style="display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid {COLORS["border"]};">
          <div>
            <span style="font-size: 14px; color: {COLORS["dark"]};">{name}</span>
            <span style="font-size: 12px; color: {COLORS["text"]}; margin-left: 8px;">× {qty}</span>
          </div>
          <span style="font-size: 14px; color: {COLORS["dark"]};">${price:.2f}</span>
        </div>
        '''
    
    # Roots balance footer (Task 8)
    roots_footer = _roots_balance_footer(loyalty_balance, points_earned)
    
    content = f'''
    <div style="text-align: center; margin-bottom: 24px;">
      <div style="font-size: 42px; margin-bottom: 12px;">✓</div>
      <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 8px;">Order Confirmed</h2>
      <p style="font-size: 14px; color: {COLORS["text"]}; margin: 0;">Thank you, {customer_name}!</p>
    </div>
    
    <div style="background: {COLORS["bg"]}; border: 1px solid {COLORS["border"]}; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
      <div style="font-size: 11px; letter-spacing: 0.12em; color: {COLORS["textMuted"]}; text-transform: uppercase; margin-bottom: 4px;">Order Number</div>
      <div style="font-size: 18px; color: {COLORS["pink"]}; font-family: 'JetBrains Mono', monospace; letter-spacing: 0.1em;">#{order_id}</div>
    </div>
    
    <div style="margin-bottom: 20px;">
      <div style="font-size: 11px; letter-spacing: 0.12em; color: {COLORS["textMuted"]}; text-transform: uppercase; margin-bottom: 12px;">Your Items</div>
      {items_html if items_html else '<div style="padding: 12px 0; color: ' + COLORS["text"] + ';">Your PDRN ritual</div>'}
    </div>
    
    <div style="display: flex; justify-content: space-between; padding-top: 16px; border-top: 2px solid {COLORS["border"]};">
      <span style="font-size: 14px; font-weight: 600; color: {COLORS["dark"]};">Total</span>
      <span style="font-size: 18px; font-weight: 600; color: {COLORS["pink"]};">${total:.2f} CAD</span>
    </div>
    
    {roots_footer}
    
    <p style="font-size: 13px; color: {COLORS["text"]}; line-height: 1.7; margin-top: 24px;">
      We're preparing your order with care. You'll receive a shipping confirmation with tracking once it's on its way.
    </p>
    
    {_cta_button("View Order Status", f"{BRAND['website']}/account/orders")}
    '''
    
    return {
        "subject": f"Order confirmed — #{order_id}",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 2. SHIPPING NOTIFICATION
# ══════════════════════════════════════════════════════════════════
def shipping_notification(order: dict, tracking: str, carrier: str, tracking_url: str, est_delivery: str = None, loyalty_balance: int = 0) -> dict:
    """Sent when order ships."""
    customer_name = order.get("customerName") or order.get("name") or "there"
    
    roots_footer = _roots_balance_footer(loyalty_balance)
    
    content = f'''
    <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px;">Your PDRN ritual is on its way</h2>
    <p style="font-size: 14px; color: {COLORS["text"]}; margin: 0 0 24px;">Hi {customer_name} — your order has shipped.</p>
    
    <div style="background: {COLORS["bg"]}; border: 1px solid {COLORS["border"]}; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
      <div style="font-size: 11px; letter-spacing: 0.12em; color: {COLORS["textMuted"]}; text-transform: uppercase; margin-bottom: 6px;">Tracking Number</div>
      <div style="font-size: 18px; color: {COLORS["pink"]}; font-family: 'JetBrains Mono', monospace; letter-spacing: 0.1em;">{tracking}</div>
      <div style="font-size: 12px; color: {COLORS["text"]}; margin-top: 4px;">via {carrier}{f" · Est. {est_delivery}" if est_delivery else ""}</div>
    </div>
    
    {_cta_button("Track My Package →", tracking_url)}
    
    <p style="font-size: 13px; color: {COLORS["text"]}; line-height: 1.7; margin-top: 24px;">
      While you wait — your 28-day PDRN science protocol begins the day your order arrives. We'll send you a full guide on Day 1.
    </p>
    
    {roots_footer}
    '''
    
    return {
        "subject": f"Your ReRoots order is on its way — {tracking}",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 3. QUIZ RESULTS / PERSONALISED PROTOCOL
# ══════════════════════════════════════════════════════════════════
def quiz_protocol_email(name: str, concerns: list, recommended_product: str, product_url: str = None) -> dict:
    """Sent after quiz completion with personalised results."""
    first_name = name.split()[0] if name else "there"
    concern_text = ", ".join(concerns) if concerns else "aging and skin renewal"
    url = product_url or f"{BRAND['website']}/products/aura-gen-pdrn"
    
    content = f'''
    <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 8px;">Hi {first_name},</h2>
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      Based on your skin quiz — your top concerns are <strong style="color: {COLORS["dark"]};">{concern_text}</strong>.<br>
      We've matched you with the right PDRN protocol.
    </p>
    
    <div style="background: {COLORS["bg"]}; border: 1.5px solid {COLORS["pink"]}; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
      <div style="font-size: 11px; letter-spacing: 0.12em; color: {COLORS["textMuted"]}; text-transform: uppercase; margin-bottom: 8px;">Your Recommended Ritual</div>
      <div style="font-size: 18px; color: {COLORS["dark"]}; font-weight: 400; margin-bottom: 4px;">{recommended_product}</div>
      <div style="font-size: 14px; color: {COLORS["pink"]}; font-weight: 600;">$99</div>
      <p style="font-size: 12px; color: {COLORS["text"]}; margin-top: 12px; line-height: 1.6;">
        37.25% active concentration · PDRN 2% + TXA 5% + Argireline 17%<br>
        28-day science protocol included
      </p>
    </div>
    
    <div style="background: #FFFBF2; border: 1.5px dashed {COLORS["gold"]}; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px;">
      <div style="font-size: 11px; color: {COLORS["gold"]}; font-weight: 600; margin-bottom: 4px;">Quiz Exclusive — 10% Off</div>
      <div style="font-family: 'JetBrains Mono', monospace; font-size: 16px; color: {COLORS["gold"]}; letter-spacing: 0.1em; font-weight: 700;">QUIZ10</div>
    </div>
    
    {_cta_button("Start Your 28-Day Protocol →", url + "?discount=QUIZ10")}
    '''
    
    return {
        "subject": f"Your personalised PDRN protocol is ready, {first_name} — ReRoots",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 4. ABANDONED CART RECOVERY (Step 1 - Gentle reminder)
# ══════════════════════════════════════════════════════════════════
def abandoned_cart_step1(cart: dict) -> dict:
    """Sent 2 hours after cart abandonment."""
    customer_name = cart.get("customerName") or cart.get("name") or "there"
    recovery_url = cart.get("recovery_url") or f"{BRAND['website']}/cart"
    
    content = f'''
    <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px;">You left something behind</h2>
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      Hi {customer_name} — your PDRN ritual is still waiting. We've saved your cart for you.
    </p>
    
    <div style="background: {COLORS["bg"]}; border-radius: 8px; padding: 16px; margin-bottom: 20px; text-align: center;">
      <div style="font-size: 36px; margin-bottom: 8px;">🧬</div>
      <div style="font-size: 14px; color: {COLORS["dark"]};">Your cart is waiting</div>
    </div>
    
    {_cta_button("Complete My Order →", recovery_url)}
    
    <p style="font-size: 12px; color: {COLORS["textMuted"]}; text-align: center; margin-top: 20px;">
      Questions? Just reply to this email.
    </p>
    '''
    
    return {
        "subject": "You left something behind — ReRoots",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 5. ABANDONED CART RECOVERY (Step 2 - With discount)
# ══════════════════════════════════════════════════════════════════
def abandoned_cart_step2(cart: dict, discount_code: str = "COMEBACK10") -> dict:
    """Sent 24 hours after cart abandonment with discount."""
    customer_name = cart.get("customerName") or cart.get("name") or "there"
    recovery_url = cart.get("recovery_url") or f"{BRAND['website']}/cart?discount={discount_code}"
    
    content = f'''
    <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px;">Still thinking about it?</h2>
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      Hi {customer_name} — we get it. Good skincare is an investment. Here's something to help you decide.
    </p>
    
    <div style="background: {COLORS["bg"]}; border: 2px dashed {COLORS["pink"]}; border-radius: 10px; padding: 20px; margin-bottom: 24px; text-align: center;">
      <div style="font-size: 11px; letter-spacing: 0.12em; color: {COLORS["pink"]}; text-transform: uppercase; margin-bottom: 8px;">Your Exclusive Offer</div>
      <div style="font-size: 32px; color: {COLORS["pink"]}; font-weight: 300; margin-bottom: 4px;">10% OFF</div>
      <div style="font-family: 'JetBrains Mono', monospace; font-size: 18px; color: {COLORS["dark"]}; letter-spacing: 0.15em; font-weight: 600; margin-bottom: 8px;">{discount_code}</div>
      <div style="font-size: 12px; color: {COLORS["textMuted"]};">Expires in 48 hours</div>
    </div>
    
    {_cta_button("Claim My 10% Off →", recovery_url)}
    '''
    
    return {
        "subject": "10% off — just for you — ReRoots",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 6. ABANDONED CART RECOVERY (Step 3 - Final reminder)
# ══════════════════════════════════════════════════════════════════
def abandoned_cart_step3(cart: dict) -> dict:
    """Sent 72 hours after cart abandonment - final reminder."""
    customer_name = cart.get("customerName") or cart.get("name") or "there"
    recovery_url = cart.get("recovery_url") or f"{BRAND['website']}/cart"
    
    content = f'''
    <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px;">Last chance, {customer_name}</h2>
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      Your cart will expire soon. If now isn't the right time, no worries — your skin will be here when you're ready.
    </p>
    
    <div style="background: #FFF8F8; border: 1px solid #F8D0D0; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
      <div style="font-size: 13px; color: {COLORS["dark"]};">
        ⏰ Your saved cart expires in <strong>24 hours</strong>
      </div>
    </div>
    
    {_cta_button("Complete My Order →", recovery_url)}
    
    <p style="font-size: 12px; color: {COLORS["text"]}; margin-top: 24px; line-height: 1.6;">
      <strong>Why customers choose ReRoots:</strong><br>
      ✓ 37.25% active concentration<br>
      ✓ Health Canada compliant<br>
      ✓ 28-day science protocol included<br>
      ✓ Free shipping over $75
    </p>
    '''
    
    return {
        "subject": "Your cart is about to expire — ReRoots",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 6.5 CYCLE DAY 1 WELCOME (Your 28-day protocol begins!)
# ══════════════════════════════════════════════════════════════════
def cycle_day1_welcome(customer: dict, loyalty_balance: int = 0) -> dict:
    """Sent on Day 1 when order is delivered and PDRN cycle begins."""
    name = customer.get("name", "").split()[0] or "there"
    roots_footer = _roots_balance_footer(loyalty_balance)
    
    content = f'''
    <div style="text-align: center; margin-bottom: 20px;">
      <div style="font-size: 32px; margin-bottom: 8px;">🎉</div>
      <div style="font-size: 11px; letter-spacing: 0.15em; color: {COLORS["pink"]}; text-transform: uppercase;">Day 1 of 28</div>
    </div>
    
    <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px; text-align: center;">Welcome to your PDRN ritual, {name}</h2>
    
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      Your 28-day transformation starts today. Here's what to expect and how to get the best results.
    </p>
    
    <div style="background: {COLORS["bg"]}; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
      <div style="font-size: 11px; letter-spacing: 0.12em; color: {COLORS["textMuted"]}; text-transform: uppercase; margin-bottom: 12px;">Your Protocol</div>
      
      <div style="margin-bottom: 16px;">
        <div style="font-size: 14px; color: {COLORS["dark"]}; font-weight: 500; margin-bottom: 4px;">Morning</div>
        <div style="font-size: 13px; color: {COLORS["text"]};">Cleanse → Apply 3-4 drops AURA-GEN → SPF</div>
      </div>
      
      <div>
        <div style="font-size: 14px; color: {COLORS["dark"]}; font-weight: 500; margin-bottom: 4px;">Evening</div>
        <div style="font-size: 13px; color: {COLORS["text"]};">Cleanse → Apply 3-4 drops AURA-GEN → Moisturizer (optional)</div>
      </div>
    </div>
    
    <div style="background: {COLORS["greenFaint"]}; border: 1px solid {COLORS["green"]}25; border-radius: 10px; padding: 16px; margin-bottom: 24px;">
      <div style="font-size: 13px; color: {COLORS["dark"]};">
        <strong>Week 1:</strong> Your skin is adapting. You may notice slight tingling — that's the A2A receptors activating. Hydration improves first.
      </div>
    </div>
    
    {_cta_button("View Full Protocol Guide →", f"{BRAND['website']}/science")}
    
    {roots_footer}
    
    <p style="font-size: 12px; color: {COLORS["textMuted"]}; text-align: center; margin-top: 20px;">
      We'll check in on Day 7 to see how things are going.
    </p>
    '''
    
    return {
        "subject": f"Day 1 — your PDRN ritual begins, {name} 🧬",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 7. CYCLE DAY 7 CHECK-IN
# ══════════════════════════════════════════════════════════════════
def cycle_day7_checkin(customer: dict, loyalty_balance: int = 0) -> dict:
    """Sent on Day 7 of PDRN cycle."""
    name = customer.get("name", "").split()[0] or "there"
    roots_footer = _roots_balance_footer(loyalty_balance)
    
    content = f'''
    <div style="text-align: center; margin-bottom: 20px;">
      <div style="font-size: 32px; margin-bottom: 8px;">🧬</div>
      <div style="font-size: 11px; letter-spacing: 0.15em; color: {COLORS["pink"]}; text-transform: uppercase;">Day 7 of 28</div>
    </div>
    
    <h2 style="font-size: 22px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px; text-align: center;">One week in, {name}</h2>
    
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      Your skin is adjusting to the PDRN protocol. At this stage, you might notice:
    </p>
    
    <div style="background: {COLORS["bg"]}; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
      <div style="font-size: 13px; color: {COLORS["dark"]}; margin-bottom: 8px;">✓ Slight tingling — the A2A receptors activating</div>
      <div style="font-size: 13px; color: {COLORS["dark"]}; margin-bottom: 8px;">✓ More hydrated feeling — PDRN drawing moisture</div>
      <div style="font-size: 13px; color: {COLORS["dark"]};">✓ Texture starting to smooth — fibroblasts waking up</div>
    </div>
    
    <p style="font-size: 13px; color: {COLORS["text"]}; line-height: 1.7; margin-bottom: 20px;">
      <strong>Science tip:</strong> PDRN begins activating cell regeneration within 72 hours. The visible results compound through Day 14–28.
    </p>
    
    {_cta_button("Track My Progress →", f"{BRAND['website']}/account")}
    
    {roots_footer}
    '''
    
    return {
        "subject": f"Day 7 — how's your skin feeling, {name}?",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 8. CYCLE DAY 14 PROGRESS
# ══════════════════════════════════════════════════════════════════
def cycle_day14_progress(customer: dict, loyalty_balance: int = 0) -> dict:
    """Sent on Day 14 - halfway point."""
    name = customer.get("name", "").split()[0] or "there"
    roots_footer = _roots_balance_footer(loyalty_balance)
    
    content = f'''
    <div style="text-align: center; margin-bottom: 20px;">
      <div style="font-size: 32px; margin-bottom: 8px;">🔬</div>
      <div style="font-size: 11px; letter-spacing: 0.15em; color: {COLORS["pink"]}; text-transform: uppercase;">Day 14 of 28</div>
    </div>
    
    <h2 style="font-size: 22px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px; text-align: center;">Halfway there, {name}</h2>
    
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      This is where the science gets exciting. By Day 14, clinical studies show:
    </p>
    
    <div style="background: linear-gradient(135deg, {COLORS["bg"]}, #F8F0F4); border-radius: 10px; padding: 20px; margin-bottom: 24px;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 16px;">
        <div style="text-align: center; flex: 1;">
          <div style="font-size: 28px; color: {COLORS["pink"]}; font-weight: 300;">72%</div>
          <div style="font-size: 11px; color: {COLORS["text"]};">Fibroblast activity</div>
        </div>
        <div style="text-align: center; flex: 1;">
          <div style="font-size: 28px; color: {COLORS["pink"]}; font-weight: 300;">45%</div>
          <div style="font-size: 11px; color: {COLORS["text"]};">Hydration increase</div>
        </div>
      </div>
      <div style="font-size: 11px; color: {COLORS["textMuted"]}; text-align: center;">Based on PDRN clinical data at 2% concentration</div>
    </div>
    
    <p style="font-size: 13px; color: {COLORS["text"]}; line-height: 1.7;">
      Keep going — the next 14 days are when the real transformation happens. Your skin is building new collagen scaffolding right now.
    </p>
    
    {_cta_button("See Full Protocol Guide →", f"{BRAND['website']}/science")}
    
    {roots_footer}
    '''
    
    return {
        "subject": f"Day 14 — you're halfway to results, {name}",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 9. CYCLE DAY 21 REVIEW REQUEST
# ══════════════════════════════════════════════════════════════════
def review_request_d21(customer: dict, loyalty_balance: int = 0) -> dict:
    """Sent on Day 21 to request a review."""
    name = customer.get("name", "").split()[0] or "there"
    roots_footer = _roots_balance_footer(loyalty_balance)
    
    content = f'''
    <div style="text-align: center; margin-bottom: 20px;">
      <div style="font-size: 32px; margin-bottom: 8px;">⭐</div>
      <div style="font-size: 11px; letter-spacing: 0.15em; color: {COLORS["gold"]}; text-transform: uppercase;">Day 21 of 28</div>
    </div>
    
    <h2 style="font-size: 22px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px; text-align: center;">Seeing results, {name}?</h2>
    
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      You're 3 weeks into your PDRN ritual. We'd love to hear how it's going — your honest feedback helps others find their right protocol too.
    </p>
    
    <div style="background: {COLORS["bg"]}; border-radius: 8px; padding: 20px; margin-bottom: 24px; text-align: center;">
      <div style="font-size: 14px; color: {COLORS["dark"]}; margin-bottom: 12px;">How would you rate your results so far?</div>
      <div style="font-size: 28px; letter-spacing: 8px;">⭐⭐⭐⭐⭐</div>
      <p style="font-size: 12px; color: {COLORS["emerald"]}; margin: 12px 0 0;">Leave a review and earn 100 Roots!</p>
    </div>
    
    {_cta_button("Leave a Review →", f"{BRAND['website']}/review")}
    
    {roots_footer}
    
    <p style="font-size: 12px; color: {COLORS["textMuted"]}; text-align: center; margin-top: 20px;">
      Takes 60 seconds · Your feedback shapes our science
    </p>
    '''
    
    return {
        "subject": f"Day 21 — how's the protocol working for you, {name}?",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 10. CYCLE DAY 25 NUDGE (Running Low)
# ══════════════════════════════════════════════════════════════════
def cycle_day25_nudge(customer: dict, loyalty_balance: int = 0) -> dict:
    """Sent on Day 25 - running low reminder."""
    name = customer.get("name", "").split()[0] or "there"
    roots_footer = _roots_balance_footer(loyalty_balance)
    
    content = f'''
    <div style="text-align: center; margin-bottom: 20px;">
      <div style="font-size: 32px; margin-bottom: 8px;">⏰</div>
      <div style="font-size: 11px; letter-spacing: 0.15em; color: {COLORS["pink"]}; text-transform: uppercase;">Day 25 of 28</div>
    </div>
    
    <h2 style="font-size: 22px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px; text-align: center;">Running low, {name}?</h2>
    
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      Your PDRN ritual is almost complete. If you're seeing results (and we hope you are), now's the time to restock so you don't break the cycle.
    </p>
    
    <div style="background: #FFF8F2; border: 1.5px solid {COLORS["gold"]}; border-radius: 10px; padding: 20px; margin-bottom: 24px; text-align: center;">
      <div style="font-size: 11px; letter-spacing: 0.12em; color: {COLORS["gold"]}; text-transform: uppercase; margin-bottom: 8px;">Loyal Customer Offer</div>
      <div style="font-size: 24px; color: {COLORS["gold"]}; font-weight: 300; margin-bottom: 4px;">15% OFF</div>
      <div style="font-family: 'JetBrains Mono', monospace; font-size: 16px; color: {COLORS["dark"]}; letter-spacing: 0.12em; font-weight: 600;">CYCLE15</div>
      <div style="font-size: 12px; color: {COLORS["textMuted"]}; margin-top: 8px;">Your exclusive reorder code</div>
    </div>
    
    {_cta_button("Restock My Ritual →", f"{BRAND['website']}/products/aura-gen-pdrn?discount=CYCLE15")}
    
    {roots_footer}
    
    <p style="font-size: 12px; color: {COLORS["text"]}; line-height: 1.6; margin-top: 20px;">
      <strong>Why continue?</strong> PDRN results compound over time. Breaking the cycle means starting over. Consistency = visible results.
    </p>
    '''
    
    return {
        "subject": f"Running low? Restock with 15% off, {name}",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 11. WELCOME SUBSCRIBER
# ══════════════════════════════════════════════════════════════════
def welcome_subscriber(email: str, name: str = None) -> dict:
    """Sent when someone subscribes to the newsletter."""
    first_name = (name or "").split()[0] or "there"
    
    content = f'''
    <div style="text-align: center; margin-bottom: 24px;">
      <div style="font-size: 42px; margin-bottom: 12px;">🧬</div>
      <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 8px;">Welcome to the ritual, {first_name}</h2>
      <p style="font-size: 14px; color: {COLORS["text"]}; margin: 0;">You're in. Here's what comes next.</p>
    </div>
    
    <div style="background: {COLORS["bg"]}; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
      <div style="font-size: 13px; color: {COLORS["dark"]}; margin-bottom: 12px;">✓ Early access to new formulations</div>
      <div style="font-size: 13px; color: {COLORS["dark"]}; margin-bottom: 12px;">✓ Subscriber-only discounts</div>
      <div style="font-size: 13px; color: {COLORS["dark"]}; margin-bottom: 12px;">✓ Science updates (not fluff)</div>
      <div style="font-size: 13px; color: {COLORS["dark"]};">✓ Priority customer support</div>
    </div>
    
    <div style="background: {COLORS["bg"]}; border: 1.5px dashed {COLORS["pink"]}; border-radius: 10px; padding: 16px; margin-bottom: 24px; text-align: center;">
      <div style="font-size: 11px; color: {COLORS["pink"]}; font-weight: 600; margin-bottom: 4px;">Your Welcome Gift — 10% Off</div>
      <div style="font-family: 'JetBrains Mono', monospace; font-size: 18px; color: {COLORS["dark"]}; letter-spacing: 0.12em; font-weight: 600;">WELCOME10</div>
    </div>
    
    {_cta_button("Shop Now →", f"{BRAND['website']}/products?discount=WELCOME10")}
    '''
    
    return {
        "subject": f"Welcome to ReRoots, {first_name} — here's 10% off",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 12. WAITLIST RESTOCK ALERT
# ══════════════════════════════════════════════════════════════════
def waitlist_restock(contact: dict, product: dict) -> dict:
    """Sent when a waitlisted product is back in stock."""
    name = (contact.get("name") or "").split()[0] or "there"
    product_name = product.get("name", "Your waitlisted product")
    product_id = str(product.get("_id", product.get("id", "")))
    
    content = f'''
    <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 12px;">It's back, {name}</h2>
    <p style="font-size: 14px; color: {COLORS["text"]}; line-height: 1.7; margin: 0 0 24px;">
      <strong>{product_name}</strong> is back in stock. You're getting early access because you asked to be notified.
    </p>
    
    <div style="background: {COLORS["bg"]}; border-radius: 10px; padding: 20px; margin-bottom: 24px; text-align: center;">
      <div style="font-size: 42px; margin-bottom: 12px;">🎉</div>
      <div style="font-size: 16px; color: {COLORS["dark"]}; font-weight: 400;">{product_name}</div>
      <div style="font-size: 12px; color: {COLORS["green"]}; margin-top: 8px;">✓ In Stock — Limited Quantity</div>
    </div>
    
    {_cta_button("Shop Now — Early Access →", f"{BRAND['website']}/products/{product_id}")}
    
    <p style="font-size: 12px; color: {COLORS["textMuted"]}; text-align: center; margin-top: 20px;">
      Stock is limited. Waitlist members get first access.
    </p>
    '''
    
    return {
        "subject": f"{product_name} is back — early access for you",
        "html": _base_wrapper(content)
    }


# ══════════════════════════════════════════════════════════════════
# 13. PARTNER WELCOME / ACTIVATION
# ══════════════════════════════════════════════════════════════════
def partner_welcome(partner: dict) -> dict:
    """Sent when a partner application is approved."""
    name = (partner.get("name") or partner.get("contactName", "")).split()[0] or "Partner"
    code = partner.get("code") or partner.get("referralCode", "YOUR-CODE")
    commission = partner.get("commissionRate", 0.10) * 100
    
    content = f'''
    <div style="text-align: center; margin-bottom: 24px;">
      <div style="font-size: 42px; margin-bottom: 12px;">🤝</div>
      <h2 style="font-size: 24px; color: {COLORS["dark"]}; font-weight: 300; margin: 0 0 8px;">Welcome to the team, {name}</h2>
      <p style="font-size: 14px; color: {COLORS["text"]}; margin: 0;">Your partner account is now active.</p>
    </div>
    
    <div style="background: {COLORS["bg"]}; border: 2px solid {COLORS["pink"]}; border-radius: 10px; padding: 20px; margin-bottom: 24px; text-align: center;">
      <div style="font-size: 11px; letter-spacing: 0.12em; color: {COLORS["textMuted"]}; text-transform: uppercase; margin-bottom: 8px;">Your Partner Code</div>
      <div style="font-family: 'JetBrains Mono', monospace; font-size: 22px; color: {COLORS["pink"]}; letter-spacing: 0.15em; font-weight: 700;">{code}</div>
      <div style="font-size: 13px; color: {COLORS["text"]}; margin-top: 8px;">{commission:.0f}% commission on every sale</div>
    </div>
    
    <div style="background: {COLORS["bg"]}; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
      <div style="font-size: 13px; color: {COLORS["dark"]}; margin-bottom: 10px;"><strong>How it works:</strong></div>
      <div style="font-size: 13px; color: {COLORS["text"]}; margin-bottom: 8px;">1. Share your code with your audience</div>
      <div style="font-size: 13px; color: {COLORS["text"]}; margin-bottom: 8px;">2. They get 10% off their order</div>
      <div style="font-size: 13px; color: {COLORS["text"]};">3. You earn {commission:.0f}% commission</div>
    </div>
    
    {_cta_button("Access Partner Dashboard →", f"{BRAND['website']}/partner/dashboard")}
    '''
    
    return {
        "subject": f"You're in, {name} — your partner code is ready",
        "html": _base_wrapper(content)
    }
