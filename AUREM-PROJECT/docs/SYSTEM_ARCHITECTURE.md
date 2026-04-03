# ReRoots System Architecture & Developer Guide

## Table of Contents
1. [System Overview](#system-overview)
2. [Data Flow Diagrams](#data-flow-diagrams)
3. [Module Connections](#module-connections)
4. [Developer Checklist by Module](#developer-checklist-by-module)
5. [API Endpoint Reference](#api-endpoint-reference)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              REROOTS PLATFORM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   CUSTOMER   │     │    ADMIN     │     │   PARTNER    │                │
│  │     PWA      │     │   DASHBOARD  │     │   PORTAL     │                │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                    │                    │                         │
│         └────────────────────┼────────────────────┘                         │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                         FASTAPI BACKEND                                │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │ │
│  │  │  Auth   │ │ Orders  │ │ Loyalty │ │  Email  │ │WhatsApp │         │ │
│  │  │ Module  │ │ Module  │ │ Module  │ │ Service │ │   AI    │         │ │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘         │ │
│  │       │           │           │           │           │               │ │
│  │       └───────────┴───────────┴───────────┴───────────┘               │ │
│  │                              │                                         │ │
│  └──────────────────────────────┼─────────────────────────────────────────┘ │
│                                 │                                           │
│                                 ▼                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                          MONGODB ATLAS                                 │ │
│  │  users │ products │ orders │ carts │ loyalty │ reviews │ automations  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### 1. ADMIN PRODUCT → CUSTOMER PAGE FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ADMIN ADDS/UPDATES PRODUCT                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ AdminPanel.jsx                                                               │
│ POST /api/products                                                           │
│ {name, price, description, images, stock, category, ingredients...}         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ server.py → create_product()                                                 │
│ 1. Validate product data                                                     │
│ 2. Generate slug from name                                                   │
│ 3. Upload images to Cloudinary (if provided)                                │
│ 4. Insert into db.products                                                   │
│ 5. Create inventory record in db.inventory                                   │
│ 6. If stock < reorder_point → Trigger LOW STOCK ALERT                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ AUTOMATIONS TRIGGERED:                                                       │
│ • Low Stock Alert → WhatsApp + Email to admin                               │
│ • Waitlist Notification → If product was out of stock, notify waitlist      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ CUSTOMER SEES PRODUCT:                                                       │
│ Shop.js → GET /api/products                                                  │
│ ProductDetailPage.js → GET /api/products/{slug}                             │
│ HomePage.js → GET /api/products?featured=true                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 2. COMPLETE ORDER FLOW (Payment → Inventory → Points → Email)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: CUSTOMER ADDS TO CART                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ Shop.js / ProductDetailPage.js                                               │
│ POST /api/cart/{session_id}/add                                              │
│ {product_id, quantity, variant}                                              │
│                                    │                                         │
│                                    ▼                                         │
│ server.py → add_to_cart()                                                    │
│ 1. Validate product exists & has stock                                       │
│ 2. Check if item already in cart → update quantity                          │
│ 3. Insert/Update db.carts                                                    │
│ 4. Start ABANDONED CART TIMER (1 hour)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: CHECKOUT INITIATED                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ CheckoutPage.js                                                              │
│ 1. GET /api/cart/{session_id} - Load cart items                             │
│ 2. GET /api/shipping/rates - Calculate shipping                              │
│ 3. GET /api/loyalty/balance?email={email} - Check points balance            │
│ 4. POST /api/discount/validate - Validate discount code                      │
│                                    │                                         │
│ FRAUD CHECK (parallel):                                                      │
│ POST /api/fraud/check-email → Email risk score                              │
│ POST /api/fraud/analyze → Device fingerprint + IP analysis                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: PAYMENT PROCESSING                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ CheckoutPage.js                                                              │
│                                                                              │
│ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│ │   STRIPE/CARD   │  │     PAYPAL      │  │  POINTS ONLY    │              │
│ │                 │  │                 │  │                 │              │
│ │ POST /api/      │  │ PayPal SDK      │  │ POST /api/      │              │
│ │ create-payment- │  │ creates order   │  │ orders          │              │
│ │ intent          │  │ on approval     │  │ payment_method: │              │
│ │                 │  │ POST /api/      │  │ "points"        │              │
│ │ On success:     │  │ paypal/capture  │  │                 │              │
│ │ POST /api/orders│  │                 │  │                 │              │
│ └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
│          │                    │                    │                        │
│          └────────────────────┴────────────────────┘                        │
│                              │                                              │
└──────────────────────────────┼──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: ORDER CREATION (server.py → create_order)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 4a. VALIDATE ORDER                                                      │ │
│  │ • Check all products exist                                              │ │
│  │ • Verify stock availability                                             │ │
│  │ • Validate shipping address                                             │ │
│  │ • Check discount code validity                                          │ │
│  │ • Verify payment completed                                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 4b. DEDUCT INVENTORY                                                    │ │
│  │ FOR each item in order:                                                 │ │
│  │   db.products.update_one(                                               │ │
│  │     {"_id": product_id},                                                │ │
│  │     {"$inc": {"stock": -quantity}}                                      │ │
│  │   )                                                                     │ │
│  │   IF new_stock < reorder_point:                                        │ │
│  │     → TRIGGER low_stock_alert()                                        │ │
│  │   IF new_stock == 0:                                                   │ │
│  │     → TRIGGER out_of_stock_notification()                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 4c. AWARD LOYALTY POINTS                                                │ │
│  │ points_earned = floor(order_total * points_per_dollar)                  │ │
│  │ DEFAULT: 1 point per $1 spent                                           │ │
│  │                                                                         │ │
│  │ db.loyalty.update_one(                                                  │ │
│  │   {"user_email": customer_email},                                       │ │
│  │   {"$inc": {                                                            │ │
│  │     "balance": points_earned,                                           │ │
│  │     "lifetime_earned": points_earned                                    │ │
│  │   }},                                                                   │ │
│  │   upsert=True                                                           │ │
│  │ )                                                                       │ │
│  │                                                                         │ │
│  │ → TRIGGER notify_points_earned() via WhatsApp                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 4d. HANDLE REFERRAL (if applicable)                                     │ │
│  │ IF order has referrer_code:                                             │ │
│  │   • Award referrer 60 points                                            │ │
│  │   • Award new customer 10% discount on next order                       │ │
│  │   • Check milestone progress (5, 10, 25 referrals)                      │ │
│  │   • IF milestone reached → Unlock special rewards                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 4e. SEND ORDER CONFIRMATION EMAIL                                       │ │
│  │ send_order_confirmation_email(order, customer_email)                    │ │
│  │ • Order number, items, totals                                           │ │
│  │ • Shipping address                                                      │ │
│  │ • Points earned notification                                            │ │
│  │ • Expected delivery estimate                                            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 4f. CLEAR CART & CANCEL ABANDONED CART TIMER                           │ │
│  │ db.carts.delete_one({"session_id": session_id})                        │ │
│  │ db.abandoned_cart_queue.delete_one({"session_id": session_id})         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 4g. ADMIN NOTIFICATIONS                                                 │ │
│  │ • WhatsApp notification to admin (new order)                            │ │
│  │ • Dashboard real-time update via WebSocket                              │ │
│  │ • If high-value order → Priority flag                                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 3. SHIPPING & DELIVERY FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ADMIN UPDATES SHIPPING                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ AdminPanel.jsx → Orders Tab                                                  │
│ PATCH /api/orders/{order_id}/shipping                                        │
│ {tracking_number, courier, status: "shipped"}                               │
│                                    │                                         │
│                                    ▼                                         │
│ server.py → update_order_shipping()                                          │
│ 1. Update order status to "shipped"                                          │
│ 2. Store tracking info                                                       │
│ 3. Calculate estimated delivery                                              │
│                                    │                                         │
│                                    ▼                                         │
│ PARALLEL NOTIFICATIONS:                                                      │
│ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│ │     EMAIL       │  │    WHATSAPP     │  │      SMS        │              │
│ │                 │  │                 │  │   (optional)    │              │
│ │ Tracking link   │  │ Tracking link   │  │ Tracking link   │              │
│ │ Courier info    │  │ Quick updates   │  │ Short message   │              │
│ │ Delivery ETA    │  │                 │  │                 │              │
│ └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                    │                                         │
│                                    ▼                                         │
│ ORDER STATUS PROGRESSION:                                                    │
│ pending → processing → shipped → out_for_delivery → delivered               │
│                                    │                                         │
│                                    ▼                                         │
│ ON DELIVERY (status: "delivered"):                                          │
│ 1. Schedule Day 21 review request                                            │
│ 2. Update customer lifetime value                                            │
│ 3. Check for tier upgrade eligibility                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 4. REVIEW & LOYALTY LOOP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ DAY 21 AFTER DELIVERY                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ CRON JOB: check_day21_review_requests()                                      │
│ Runs daily at 10 AM                                                          │
│                                    │                                         │
│                                    ▼                                         │
│ FOR each delivered order > 21 days ago without review:                       │
│   1. Generate review token                                                   │ 
│   2. Send review request email                                               │
│   3. Send WhatsApp reminder                                                  │
│   4. Offer 50 bonus points for review                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ CUSTOMER SUBMITS REVIEW                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ ReviewPage.js                                                                │
│ POST /api/reviews/submit                                                     │
│ {token, rating, title, content, photos}                                     │
│                                    │                                         │
│                                    ▼                                         │
│ server.py → submit_review()                                                  │
│ 1. Validate review token                                                     │
│ 2. Store review (status: "pending")                                          │
│ 3. Award 50 bonus points                                                     │
│ 4. Send thank you email                                                      │
│ 5. Notify admin for approval                                                 │
│                                    │                                         │
│ ADMIN APPROVES:                    │                                         │
│ PATCH /api/reviews/{id}/approve    │                                         │
│                                    ▼                                         │
│ • Review visible on product page                                             │
│ • If 5-star → Prompt for Google review (earn 100 more points)               │
│ • Update product average rating                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Connections

### Connection Matrix

| FROM → TO | Auth | Orders | Loyalty | Email | WhatsApp | Inventory | Fraud |
|-----------|------|--------|---------|-------|----------|-----------|-------|
| **Auth** | - | ✓ User lookup | ✓ Points balance | ✓ Welcome email | ✓ Verification | - | ✓ Risk check |
| **Orders** | ✓ Verify user | - | ✓ Award points | ✓ Confirmation | ✓ Updates | ✓ Deduct stock | ✓ Score order |
| **Loyalty** | ✓ User ID | ✓ Order history | - | ✓ Tier updates | ✓ Milestones | - | - |
| **Admin** | ✓ RBAC check | ✓ Manage orders | ✓ Adjust points | ✓ Bulk campaigns | ✓ Templates | ✓ Stock mgmt | ✓ View reports |
| **Checkout** | ✓ Get user | ✓ Create order | ✓ Redeem points | - | - | ✓ Check stock | ✓ Fraud check |

---

## Developer Checklist by Module

### 📦 PRODUCTS MODULE

**Files:**
- `backend/server.py` (lines 6000-8000) - Product CRUD
- `frontend/src/components/pages/ProductDetailPage.js`
- `frontend/src/components/Shop.js`
- `frontend/src/components/admin/CatalogManager.js`

**Checklist:**
- [ ] Product schema: `{name, slug, price, compare_price, description, images[], ingredients[], category, stock, sku, is_active, is_featured, created_at}`
- [ ] Slug generation: `slugify(name).lower()`
- [ ] Image upload to Cloudinary with WebP conversion
- [ ] Stock tracking linked to inventory system
- [ ] SEO metadata (meta_title, meta_description)
- [ ] Variant support (size, quantity)
- [ ] Category filtering & search indexing

**API Endpoints:**
```
GET    /api/products                 - List all (with filters)
GET    /api/products/{slug}          - Single product
POST   /api/products                 - Create (admin)
PUT    /api/products/{id}            - Update (admin)
DELETE /api/products/{id}            - Soft delete (admin)
GET    /api/products/search?q=       - Full-text search
```

---

### 🛒 CART MODULE

**Files:**
- `backend/server.py` (lines 8500-9500) - Cart operations
- `frontend/src/contexts/CartContext.js`
- `frontend/src/components/Cart.js`

**Checklist:**
- [ ] Session-based cart (guest) + User-linked cart (logged in)
- [ ] Cart merging on login
- [ ] Stock validation on add/update
- [ ] Quantity limits (max per product)
- [ ] Price recalculation on product price change
- [ ] Cart expiry (30 days inactive)
- [ ] Abandoned cart trigger (1 hour no activity)

**API Endpoints:**
```
GET    /api/cart/{session_id}              - Get cart
POST   /api/cart/{session_id}/add          - Add item
PATCH  /api/cart/{session_id}/update       - Update quantity
DELETE /api/cart/{session_id}/item/{id}    - Remove item
DELETE /api/cart/{session_id}              - Clear cart
POST   /api/cart/merge                     - Merge guest → user
```

---

### 💳 ORDERS MODULE

**Files:**
- `backend/routes/orders.py`
- `backend/server.py` (lines 10000-12000) - Order processing
- `frontend/src/components/pages/CheckoutPage.js`
- `frontend/src/components/pages/AccountPage.js`

**Checklist:**
- [ ] Order number generation: `RR-{YYYYMMDD}-{SEQUENCE}`
- [ ] Payment gateway integration (Stripe, PayPal)
- [ ] Points redemption at checkout
- [ ] Discount code validation
- [ ] Tax calculation by region
- [ ] Shipping rate calculation
- [ ] Inventory deduction (atomic operation)
- [ ] Order confirmation email
- [ ] Admin notification

**Order Status Flow:**
```
pending → payment_processing → paid → processing → shipped → delivered
                                   ↘ cancelled → refunded
```

**API Endpoints:**
```
POST   /api/orders                         - Create order
GET    /api/orders/{id}                    - Get order details
GET    /api/orders/user/{email}            - User's orders
PATCH  /api/orders/{id}/status             - Update status (admin)
PATCH  /api/orders/{id}/shipping           - Add tracking (admin)
POST   /api/orders/{id}/cancel             - Cancel order
POST   /api/orders/{id}/refund             - Process refund (admin)
```

---

### 🏆 LOYALTY MODULE

**Files:**
- `backend/routes/loyalty_bonuses.py`
- `backend/server.py` (lines 2500-3200) - Points & referrals
- `frontend/src/components/LoyaltyPointsWidget.js`
- `frontend/src/components/pages/AccountPage.js`

**Checklist:**
- [ ] Points earning: 1 point per $1 spent
- [ ] Points redemption: 100 points = $1 discount
- [ ] Referral system: 60 points per successful referral
- [ ] Tier system: Bronze → Silver → Gold → Platinum
- [ ] Birthday bonus (annual)
- [ ] Milestone rewards (5, 10, 25 referrals)
- [ ] Points expiry (optional, 12 months)
- [ ] Transaction history

**Tier Thresholds:**
```
Bronze:   0-499 lifetime points
Silver:   500-1499 lifetime points
Gold:     1500-4999 lifetime points  
Platinum: 5000+ lifetime points
```

**API Endpoints:**
```
GET    /api/loyalty/balance?email=         - Get balance & tier
GET    /api/loyalty/history?email=         - Transaction history
POST   /api/loyalty/redeem                 - Redeem points
GET    /api/loyalty/referral-stats?code=   - Referral progress
POST   /api/loyalty/adjust                 - Manual adjustment (admin)
```

---

### 📧 EMAIL SERVICE MODULE

**Files:**
- `backend/routers/email_service.py`
- `backend/routes/reroots_email_templates.py`
- `backend/routes/automations.py`

**Checklist:**
- [ ] SendGrid/Resend integration
- [ ] Template management (HTML + plain text)
- [ ] Variable substitution ({name}, {order_number}, etc.)
- [ ] Unsubscribe handling
- [ ] Bounce/complaint tracking
- [ ] Rate limiting (100/minute)
- [ ] Retry logic (3 attempts)

**Email Types:**
```
TRANSACTIONAL:
- Welcome email (on signup)
- Order confirmation
- Shipping notification
- Password reset
- Review request (Day 21)

MARKETING:
- Newsletter
- Promotional campaigns
- Abandoned cart recovery
- Restock notification
```

---

### 📱 WHATSAPP MODULE

**Files:**
- `backend/routes/whatsapp_ai_routes.py`
- `backend/routes/whatsapp_templates.py`
- `frontend/src/components/admin/WhatsAppManager.js`

**Checklist:**
- [ ] Twilio WhatsApp Business API integration
- [ ] Template approval workflow
- [ ] AI auto-reply for common questions
- [ ] Order status updates
- [ ] Promotional message opt-in
- [ ] Message logging
- [ ] Rate limiting (per user)

**Message Templates:**
```
- order_confirmation
- shipping_update
- delivery_confirmation
- points_earned
- review_request
- milestone_unlocked
- birthday_bonus
```

---

### 🔐 AUTH MODULE

**Files:**
- `backend/routes/auth.py`
- `frontend/src/contexts/AuthContext.js`
- `frontend/src/components/pages/LoginPage.js`

**Checklist:**
- [ ] JWT token authentication (24h expiry)
- [ ] Refresh token rotation
- [ ] Google OAuth integration
- [ ] Password hashing (bcrypt, 12 rounds)
- [ ] Email verification
- [ ] Password reset flow
- [ ] Session management
- [ ] RBAC for admin roles

**API Endpoints:**
```
POST   /api/auth/register              - Create account
POST   /api/auth/login                 - Login (email/password)
POST   /api/auth/google                - Google OAuth
POST   /api/auth/refresh               - Refresh token
POST   /api/auth/logout                - Invalidate token
POST   /api/auth/forgot-password       - Request reset
POST   /api/auth/reset-password        - Complete reset
GET    /api/auth/me                    - Current user info
```

---

### 🛡️ FRAUD PREVENTION MODULE

**Files:**
- `backend/routers/fraud_prevention.py`
- `frontend/src/hooks/useDeviceFingerprint.js`
- `frontend/src/components/admin/FraudDashboard.jsx`

**Checklist:**
- [ ] Email risk scoring (disposable domain check)
- [ ] IP geolocation & proxy detection
- [ ] Device fingerprinting
- [ ] Velocity checks (orders per hour)
- [ ] Address verification
- [ ] Payment pattern analysis
- [ ] Manual review queue

**Risk Score Calculation:**
```
0-30:   Low risk (auto-approve)
31-70:  Medium risk (review recommended)
71-100: High risk (manual review required)
```

---

### 🤖 ABANDONED CART AUTOMATION

**Files:**
- `backend/routes/abandoned_cart_automation.py`
- `backend/routes/automations.py`

**Checklist:**
- [ ] Cart tracking (session + user)
- [ ] 1-hour trigger delay
- [ ] Multi-channel: Email → WhatsApp → SMS
- [ ] Personalized discount offer
- [ ] Recovery link with cart restoration
- [ ] Suppression (don't send if purchased)
- [ ] Performance tracking (open rate, recovery rate)

**Sequence:**
```
T+1 hour:  Email reminder
T+4 hours: WhatsApp message
T+24 hours: Email with 10% discount
T+72 hours: Final reminder + 15% discount
```

---

### 📊 ADMIN DASHBOARD

**Files:**
- `frontend/src/components/admin/AdminDashboard.js`
- `frontend/src/pages/AdminPanel.jsx`
- `backend/routes/business_system.py`

**Tabs & Features:**
```
📊 Overview      - Sales metrics, charts, KPIs
🛍️ Catalog       - Products, categories, inventory
📋 Orders        - Order management, fulfillment
💰 Finance       - Revenue, refunds, payouts
👥 Customers     - CRM, segments, lifetime value
🎁 Loyalty       - Points management, tiers
📧 Marketing     - Campaigns, automations
🛡️ Fraud         - Risk scores, blocked users
👤 Team          - Staff accounts, permissions
⚙️ Settings      - Store config, shipping, tax
```

---

### 🌐 API URL CONFIGURATION

**CRITICAL: Dynamic URL Resolution**

All frontend files MUST use this pattern for API URLs:

```javascript
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // Localhost development
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    
    // Custom domains (reroots.ca) - use same origin
    if (!hostname.includes('preview.emergentagent.com') && 
        !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    
    // Preview/staging - use env var
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

const API = getBackendUrl() + '/api';
```

**Files that need this pattern:**
- [x] `App.js`
- [x] `lib/api.js`
- [x] `utils/api.js`
- [x] `SkincareSetsPage.js`
- [x] `ProductDetailPage.js`
- [x] `CheckoutPage.js`
- [x] `AccountPage.js`
- [x] `BioAgeScanPage.js`
- [x] `TrackOrderPage.jsx`
- [x] `ContactPage.js`
- [x] `WaitlistPage.js`
- [ ] + 15 more admin/component files

---

## Database Collections Reference

```
MongoDB Collections:
├── users              - User accounts & profiles
├── products           - Product catalog
├── orders             - Order records
├── carts              - Shopping carts
├── loyalty            - Points balances
├── loyalty_transactions - Points history
├── reviews            - Product reviews
├── discounts          - Discount codes
├── automations        - Email/SMS sequences
├── abandoned_carts    - Recovery queue
├── waitlist           - Product waitlist
├── referrals          - Referral tracking
├── fraud_scores       - Risk assessments
├── blog_posts         - Blog content
├── store_settings     - Configuration
└── admin_users        - Staff accounts
```

---

## Quick Reference: Event Triggers

| Event | Triggers |
|-------|----------|
| User Registration | Welcome email, Create loyalty account, Fraud check |
| Add to Cart | Start abandoned cart timer, Update cart analytics |
| Order Created | Deduct inventory, Award points, Send confirmation, Notify admin |
| Order Shipped | Email + WhatsApp notification, Update tracking |
| Order Delivered | Schedule Day 21 review, Update customer LTV |
| Review Submitted | Award bonus points, Notify admin for approval |
| Points Redeemed | Deduct balance, Log transaction, Update tier |
| Low Stock | Admin alert (WhatsApp + Email), Optional auto-reorder |
| Referral Success | Award referrer points, Check milestones |

---

*Last Updated: March 2026*
*Version: 2.0*
