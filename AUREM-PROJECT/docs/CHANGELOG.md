# ReRoots WhatsApp Integration - CHANGELOG

## 2026-03-05 - WhatsApp via Web Links Implementation

### Overview
Semi-manual WhatsApp system using wa.me links. No API needed.

### Components Added/Modified

#### 1. Checkout Page Opt-In
**File:** `/app/frontend/src/components/checkout/SimpleCheckout.js`

Added:
- `whatsapp_opted_in` state field
- Checkbox after phone field: "💬 Get updates via WhatsApp"
- Saves to customer record on order completion

#### 2. Order Confirmation WhatsApp Button
**File:** `/app/frontend/src/components/product/PostPurchaseSuccess.js`

Added:
- "Message Us on WhatsApp" button with green gradient card
- Conditional display (opted-in OR first order)
- Pre-filled message with order ID

#### 3. Admin WhatsApp Broadcast Panel
**File:** `/app/frontend/src/components/admin/WhatsAppBroadcast.jsx` (NEW)

Features:
- Customer list with filters (All, Purchased, Quiz, VIP)
- Message template composer with placeholders
- wa.me link generator
- Copy All Links button
- Business number configuration display

#### 4. Footer WhatsApp Icon
**File:** `/app/frontend/src/App.js`

Added WhatsApp icon to social icons row with pre-filled message link.

#### 5. Backend Endpoint
**File:** `/app/backend/server.py`

New endpoint:
- `GET /api/admin/whatsapp-broadcast/customers`
- Returns opted-in customers with stats
- Filters: all, purchased, quiz_only, vip

### Configuration Required

Update `WHATSAPP_BUSINESS_NUMBER` in:
```
/app/frontend/src/components/admin/WhatsAppBroadcast.jsx
/app/frontend/src/components/product/PostPurchaseSuccess.js
/app/frontend/src/App.js
```

Replace `16475551234` with your actual Canadian WhatsApp Business number.

### How wa.me Links Work

```
https://wa.me/1XXXXXXXXXX?text=Your%20pre-filled%20message%20here
```

- No API authentication needed
- Opens WhatsApp Web/App directly
- Message is pre-filled, admin clicks Send
- Appropriate for scale up to ~500 customers

### Admin Panel Location

Admin → WhatsApp (group) → Broadcast

### Data Model

Customer record fields:
```
{
  whatsapp_opted_in: true,
  whatsapp_phone: "+14165551234"
}
```

Order record field:
```
{
  whatsapp_opted_in: true
}
```
