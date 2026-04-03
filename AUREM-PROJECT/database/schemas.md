# AUREM Database Schemas

## MongoDB Collections

This document describes the MongoDB collections used by the AUREM platform.

---

## Core Collections

### `platform_users`
Admin and platform users for authentication.

```javascript
{
  "_id": ObjectId,
  "email": "admin@company.com",           // Unique email
  "password_hash": "bcrypt_hash",          // Hashed password
  "role": "admin",                         // admin | user | viewer
  "tier_status": "enterprise",             // free | pro | enterprise
  "created_at": ISODate,
  "updated_at": ISODate,
  "last_login": ISODate,
  "permissions": ["read", "write", "admin"]
}
```

### `agent_sessions`
Conversation memory for AI sessions.

```javascript
{
  "_id": ObjectId,
  "session_id": "uuid-string",
  "user_id": ObjectId,
  "agent_type": "ora",                     // ora | scout | architect | envoy
  "messages": [
    {
      "role": "user",                      // user | assistant | system
      "content": "Message text",
      "timestamp": ISODate
    }
  ],
  "context": {
    "intent": "sales_inquiry",
    "entities": ["company_name", "budget"]
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

---

## Campaign Management

### `campaigns`
Marketing and outreach campaigns.

```javascript
{
  "_id": ObjectId,
  "name": "Q1 Enterprise Outreach",
  "status": "active",                      // draft | active | paused | completed
  "type": "multi_channel",                 // email | whatsapp | voice | multi_channel
  "created_by": ObjectId,
  "targets": [
    {
      "contact_id": ObjectId,
      "status": "pending",                 // pending | contacted | replied | converted
      "last_touch": ISODate
    }
  ],
  "sequences": [
    {
      "step": 1,
      "channel": "email",
      "template_id": ObjectId,
      "delay_hours": 0
    },
    {
      "step": 2,
      "channel": "whatsapp",
      "template_id": ObjectId,
      "delay_hours": 48
    }
  ],
  "metrics": {
    "sent": 150,
    "opened": 89,
    "replied": 23,
    "converted": 5
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### `contacts`
Contact database for outreach.

```javascript
{
  "_id": ObjectId,
  "email": "john@company.com",
  "phone": "+1234567890",
  "first_name": "John",
  "last_name": "Doe",
  "company": "Acme Corp",
  "title": "VP Sales",
  "linkedin_url": "https://linkedin.com/in/johndoe",
  "source": "scout_discovery",             // manual | import | scout_discovery
  "tags": ["enterprise", "saas"],
  "score": 85,                             // Lead score 0-100
  "last_contacted": ISODate,
  "created_at": ISODate
}
```

---

## Communication

### `outreach_logs`
All outbound communication records.

```javascript
{
  "_id": ObjectId,
  "contact_id": ObjectId,
  "campaign_id": ObjectId,
  "channel": "email",                      // email | whatsapp | sms | voice
  "direction": "outbound",                 // outbound | inbound
  "status": "delivered",                   // pending | sent | delivered | opened | replied | failed
  "content": {
    "subject": "Email subject",
    "body": "Message body",
    "template_id": ObjectId
  },
  "metadata": {
    "message_id": "provider-message-id",
    "provider": "resend",
    "opened_at": ISODate,
    "clicked_at": ISODate
  },
  "created_at": ISODate
}
```

### `unified_inbox`
Aggregated communication threads.

```javascript
{
  "_id": ObjectId,
  "contact_id": ObjectId,
  "channel": "email",
  "thread_id": "thread-uuid",
  "subject": "Re: Your inquiry",
  "messages": [
    {
      "id": "msg-uuid",
      "direction": "inbound",
      "content": "Thanks for reaching out...",
      "timestamp": ISODate,
      "read": true
    }
  ],
  "status": "open",                        // open | pending | resolved | archived
  "assigned_to": ObjectId,
  "priority": "high",                      // low | medium | high | urgent
  "created_at": ISODate,
  "updated_at": ISODate
}
```

---

## Billing & Deals

### `deals`
Sales pipeline and deal tracking.

```javascript
{
  "_id": ObjectId,
  "contact_id": ObjectId,
  "company": "Acme Corp",
  "value": 50000,
  "currency": "USD",
  "stage": "proposal",                     // lead | qualified | proposal | negotiation | won | lost
  "probability": 60,                       // Win probability %
  "products": [
    {
      "name": "Enterprise Plan",
      "quantity": 1,
      "price": 50000
    }
  ],
  "close_date": ISODate,
  "owner_id": ObjectId,
  "notes": "Meeting scheduled for demo",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### `invoices`
Billing and invoice records.

```javascript
{
  "_id": ObjectId,
  "invoice_number": "INV-2024-001",
  "deal_id": ObjectId,
  "customer_id": ObjectId,
  "items": [
    {
      "description": "Enterprise Plan - Annual",
      "quantity": 1,
      "unit_price": 50000,
      "amount": 50000
    }
  ],
  "subtotal": 50000,
  "tax": 6500,
  "total": 56500,
  "currency": "USD",
  "status": "paid",                        // draft | sent | paid | overdue | cancelled
  "due_date": ISODate,
  "paid_date": ISODate,
  "payment_method": "stripe",
  "payment_id": "pi_xxxxx",
  "created_at": ISODate
}
```

### `subscriptions`
Recurring subscription management.

```javascript
{
  "_id": ObjectId,
  "customer_id": ObjectId,
  "plan_id": "enterprise_monthly",
  "status": "active",                      // active | cancelled | past_due | paused
  "amount": 499,
  "currency": "USD",
  "interval": "month",                     // month | year
  "current_period_start": ISODate,
  "current_period_end": ISODate,
  "cancel_at_period_end": false,
  "stripe_subscription_id": "sub_xxxxx",
  "created_at": ISODate
}
```

---

## System & Security

### `audit_logs`
Activity tracking for compliance.

```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "action": "campaign.create",
  "resource_type": "campaign",
  "resource_id": ObjectId,
  "details": {
    "campaign_name": "Q1 Outreach",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  },
  "created_at": ISODate
}
```

### `api_keys`
API key management for integrations.

```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "name": "Production API Key",
  "key_hash": "sha256_hash",
  "prefix": "aurem_live_",
  "permissions": ["read:contacts", "write:campaigns"],
  "rate_limit": 1000,                      // Requests per hour
  "last_used": ISODate,
  "expires_at": ISODate,
  "created_at": ISODate
}
```

### `webhooks`
Webhook configuration for external integrations.

```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "url": "https://example.com/webhook",
  "events": ["deal.won", "contact.created"],
  "secret": "webhook_secret_hash",
  "status": "active",                      // active | disabled
  "last_triggered": ISODate,
  "failure_count": 0,
  "created_at": ISODate
}
```

---

## Indexes

### Recommended Indexes

```javascript
// platform_users
db.platform_users.createIndex({ "email": 1 }, { unique: true })

// agent_sessions
db.agent_sessions.createIndex({ "session_id": 1 }, { unique: true })
db.agent_sessions.createIndex({ "user_id": 1, "created_at": -1 })

// campaigns
db.campaigns.createIndex({ "status": 1, "created_at": -1 })
db.campaigns.createIndex({ "created_by": 1 })

// contacts
db.contacts.createIndex({ "email": 1 }, { unique: true })
db.contacts.createIndex({ "tags": 1 })
db.contacts.createIndex({ "score": -1 })

// outreach_logs
db.outreach_logs.createIndex({ "contact_id": 1, "created_at": -1 })
db.outreach_logs.createIndex({ "campaign_id": 1 })

// deals
db.deals.createIndex({ "stage": 1, "close_date": 1 })
db.deals.createIndex({ "owner_id": 1 })

// audit_logs
db.audit_logs.createIndex({ "user_id": 1, "created_at": -1 })
db.audit_logs.createIndex({ "action": 1 })
db.audit_logs.createIndex({ "created_at": 1 }, { expireAfterSeconds: 7776000 }) // 90 days TTL
```

---

## Notes

- All `_id` fields are automatically generated MongoDB ObjectIds
- Timestamps use ISODate format (UTC)
- Password hashes use bcrypt with cost factor 12
- Sensitive fields (API keys, secrets) are stored hashed
- TTL indexes automatically clean up old audit logs
