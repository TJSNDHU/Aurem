# PHASE D: OMNICHANNEL COMMUNICATION HUB - TECHNICAL SPEC

## Overview
Unified inbox that consolidates WhatsApp, Email, SMS, Instagram DMs, and Web Chat into one interface. Business owners reply once, customer receives on their preferred channel.

---

## The Problem It Solves

**Current Pain**: Business owners juggle 5+ apps (WhatsApp Business, Gmail, SMS, Instagram, Website chat)

**Your Solution**: *"One inbox for everything. Reply to a WhatsApp message via email, or an Instagram DM via SMS. We route it correctly."*

---

## Architecture

### 1. Channel Adapters (Inbound)
**Purpose**: Receive messages from all platforms and normalize them

**Channels to Support**:
- ✅ **WhatsApp Business** (via Twilio/Meta API)
- ✅ **SMS** (via Twilio)
- ✅ **Email** (via IMAP/SendGrid)
- ✅ **Instagram DMs** (via Meta Graph API)
- ✅ **Web Chat** (already built - AUREM Chat)
- 🔜 **Facebook Messenger**
- 🔜 **Telegram**
- 🔜 **Voice Calls** (Vapi integration)

**Adapters Structure**:
```
/app/backend/services/channels/
├── whatsapp_adapter.py
├── sms_adapter.py
├── email_adapter.py
├── instagram_adapter.py
├── telegram_adapter.py
└── base_adapter.py (interface)
```

---

### 2. Unified Message Schema
**File**: `/app/backend/models/unified_message.py`

**Normalized Format**:
```python
{
    "message_id": "msg_abc123",
    "conversation_id": "conv_xyz789",
    "tenant_id": "reroots_aesthetics",
    "channel": "whatsapp",  # whatsapp, sms, email, instagram, web
    "direction": "inbound",  # inbound, outbound
    "sender": {
        "name": "Jennifer Williams",
        "phone": "+1-310-555-8822",
        "email": "jennifer@gmail.com",
        "instagram_handle": "@jenniferwilliams",
        "identifier": "whatsapp:+13105558822"  # Channel-specific ID
    },
    "content": {
        "type": "text",  # text, image, video, audio, file
        "text": "Hi! Do you have Rose-Gen in stock?",
        "media_url": null,
        "attachments": []
    },
    "metadata": {
        "received_at": "2025-02-01T14:30:00Z",
        "channel_metadata": {...}  # Platform-specific data
    },
    "ai_processed": true,
    "sentiment_score": 0.8,
    "lead_captured": false
}
```

---

### 3. Message Router (Outbound)
**File**: `/app/backend/services/message_router.py`

**Smart Routing Logic**:
1. Customer contacts via WhatsApp → Reply goes to WhatsApp
2. Owner replies via dashboard → System detects original channel
3. Customer switches channels → System links conversations
4. Owner can manually override channel

**Example**:
```python
class MessageRouter:
    async def send_reply(
        self,
        conversation_id: str,
        message: str,
        override_channel: str = None
    ):
        """
        Send reply to customer via their preferred channel
        or override to specific channel
        """
        # Get conversation history
        conv = await db.conversations.find_one({"id": conversation_id})
        
        # Determine channel
        channel = override_channel or conv["last_channel"]
        
        # Route to appropriate adapter
        if channel == "whatsapp":
            await WhatsAppAdapter.send(conv["customer_phone"], message)
        elif channel == "email":
            await EmailAdapter.send(conv["customer_email"], message)
        elif channel == "sms":
            await SMSAdapter.send(conv["customer_phone"], message)
        # etc.
```

---

### 4. Unified Inbox UI
**File**: `/app/frontend/src/platform/UnifiedInbox.jsx`

**Layout**:
```
┌────────────────────────────────────────────────────────────┐
│  💬 Unified Inbox - Reroots Aesthetics                     │
├──────────────┬─────────────────────────────────────────────┤
│              │  Conversation: Jennifer Williams            │
│ Conversations│  Channels: 📱 WhatsApp • 📧 Email          │
│              ├─────────────────────────────────────────────┤
│ 📱 Jennifer  │  [WhatsApp] 2:30 PM                        │
│    Williams  │  Hi! Do you have Rose-Gen in stock?        │
│    WhatsApp  │                                             │
│    2 min ago │  [AI] 2:31 PM                              │
│              │  Yes! We have 12 units. Would you like...  │
│ 📧 Sarah M.  │                                             │
│    Email     │  [WhatsApp] 2:35 PM                        │
│    5 min ago │  Great! Can I order 2?                     │
│              │                                             │
│ 💬 John D.   │  [You - via Email] 2:36 PM                 │
│    Web Chat  │  Absolutely! I'll send you the link...     │
│    10min ago │                                             │
│              ├─────────────────────────────────────────────┤
│ Filter:      │  Reply via: [WhatsApp ▼] [Email] [SMS]    │
│ [ ] All      │  ┌────────────────────────────────────┐    │
│ [x] Active   │  │ Type your message...               │    │
│ [ ] AI Only  │  │                                    │    │
│ [ ] Human    │  └────────────────────────────────────┘    │
│              │  [Send] [Attach] [AI Suggest] [Emoji]      │
└──────────────┴─────────────────────────────────────────────┘
```

**Features**:
- ✅ All channels in one view
- ✅ Channel icons for each message
- ✅ Reply from any channel
- ✅ Attach files (images, PDFs)
- ✅ AI-suggested replies
- ✅ Mark as resolved
- ✅ Assign to team members
- ✅ Search across all conversations
- ✅ Filter by channel/status/sentiment

---

### 5. Cross-Channel Identity Linking
**File**: `/app/backend/services/identity_linker.py`

**Challenge**: Same customer contacts via WhatsApp (phone) and Email (different identifier)

**Solution**: Link identities based on:
1. **Name matching**: "Jennifer Williams" appears in both
2. **Contact info**: Phone number mentioned in email signature
3. **Conversation context**: AI detects same person
4. **Manual linking**: Owner can merge conversations

**Example**:
```python
# Customer contacts via WhatsApp
{"sender": "whatsapp:+13105558822", "name": "Jennifer"}

# Later contacts via Email
{"sender": "jennifer@gmail.com", "name": "Jennifer Williams"}

# System links them:
{
    "customer_id": "cust_jennifer_williams",
    "identities": [
        {"channel": "whatsapp", "id": "+13105558822"},
        {"channel": "email", "id": "jennifer@gmail.com"},
        {"channel": "instagram", "id": "@jenniferwilliams"}
    ],
    "unified_profile": {
        "name": "Jennifer Williams",
        "phone": "+1-310-555-8822",
        "email": "jennifer@gmail.com"
    }
}
```

---

### 6. Channel-Specific Features

#### WhatsApp Adapter
**Tech**: Twilio WhatsApp API or Meta Cloud API
**Features**:
- Read receipts
- Typing indicators
- Media sharing (images, videos, voice notes)
- Quick reply buttons
- Message templates (for broadcasts)

#### Email Adapter
**Tech**: IMAP (receive) + SMTP/SendGrid (send)
**Features**:
- Thread linking
- Attachments
- HTML formatting
- Auto-signatures
- CC/BCC support

#### Instagram DM Adapter
**Tech**: Meta Graph API
**Features**:
- Story replies
- Image sharing
- Quick replies
- Message reactions

#### SMS Adapter
**Tech**: Twilio SMS API
**Features**:
- MMS (images)
- Link shortening
- Delivery receipts
- Auto-responders

---

### 7. AI Integration Points

**AI Assistance**:
1. **Smart Replies**: Suggest 3 responses based on conversation
2. **Auto-Draft**: AI writes reply, owner edits before sending
3. **Sentiment Alerts**: Flag negative messages
4. **Lead Detection**: Auto-tag potential leads
5. **Language Translation**: Detect customer language, reply in their language

**Example UI**:
```
┌────────────────────────────────────────┐
│ 🤖 AI Suggested Replies:              │
├────────────────────────────────────────┤
│ 1. "Yes! We have Rose-Gen in stock.   │
│     Would you like to place an order?"│
│                                        │
│ 2. "Great question! Rose-Gen is...    │
│     [View full suggestion]"           │
│                                        │
│ 3. "I can help with that! Let me...   │
│     [View full suggestion]"           │
└────────────────────────────────────────┘
[Use Suggestion 1] [Edit] [Ignore]
```

---

## Implementation Steps

### Phase D.1: Foundation (4 hours)
1. Build `base_adapter.py` interface
2. Create `UnifiedInbox.jsx` UI shell
3. Implement conversation storage schema
4. Build message router

### Phase D.2: Channel Integration (8 hours)
1. **WhatsApp**: Twilio integration (2 hours)
2. **Email**: IMAP/SMTP setup (2 hours)
3. **SMS**: Twilio SMS (1 hour)
4. **Instagram**: Meta Graph API (2 hours)
5. **Web Chat**: Connect existing AUREM chat (1 hour)

### Phase D.3: Identity Linking (2 hours)
1. Build identity_linker.py
2. Implement name/contact matching
3. Manual merge UI

### Phase D.4: AI Enhancements (2 hours)
1. Smart reply suggestions
2. Auto-draft responses
3. Sentiment tagging

### Phase D.5: Testing (2 hours)
1. End-to-end cross-channel test
2. Load testing (100 concurrent conversations)
3. Channel failover testing

**Total Time**: ~18 hours (2-3 days)

---

## Business Model

### Pricing Tiers:
- **Free**: Web Chat only
- **Starter ($49/mo)**: + Email + SMS (1 channel)
- **Pro ($99/mo)**: + WhatsApp + Instagram (3 channels)
- **Enterprise ($299/mo)**: All channels + team inbox + analytics

### Upsell Path:
1. Customer starts with web chat (free)
2. Adds WhatsApp (upgrade to Starter)
3. Needs Instagram DMs (upgrade to Pro)
4. Hires team, needs multi-user (upgrade to Enterprise)

---

## Competitive Advantage

**Competitors**:
- Front ($49/mo) - Email only
- Intercom ($74/mo) - Web chat focused
- Zendesk ($55/mo) - Support tickets
- **None have**: AI-powered cross-channel with sentiment analysis + lead capture

**Your Edge**:
*"The only inbox that captures leads, detects sentiment, and syncs inventory—all while unifying WhatsApp, Email, SMS, and Instagram."*

---

## Success Metrics

### Week 1:
- 100+ messages routed correctly
- < 1% cross-channel delivery failures
- 5+ customers using 2+ channels

### Month 1:
- 10,000+ messages processed
- 30+ businesses using omnichannel
- 50%+ customers upgrade to Pro
- 4.8+ star rating for inbox UX

---

## Future Enhancements (Phase D+)

1. **Voice Integration**: Vapi calls in unified inbox
2. **Team Collaboration**: Assign conversations, internal notes
3. **Chatbot Builder**: Visual flow builder for AI responses
4. **Broadcast Messages**: Send to all customers at once
5. **Analytics Dashboard**: Channel performance, response times
6. **Mobile App**: iOS/Android unified inbox
7. **API Access**: Customers can build custom integrations
