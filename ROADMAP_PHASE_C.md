# PHASE C: HUMAN PANIC BUTTON - TECHNICAL SPEC

## Overview
Real-time sentiment analysis that detects frustrated/angry customers and instantly escalates to business owner via SMS/WhatsApp.

---

## Architecture

### 1. Sentiment Analysis Service
**File**: `/app/backend/services/sentiment_analyzer.py`

**Features**:
- Real-time analysis of every customer message
- Detects: Frustration, anger, confusion, urgency
- Keyword triggers: "manager", "lawyer", "cancel", "refund", "terrible", "allergic reaction"
- Emotion score: -1.0 (very negative) to +1.0 (very positive)
- Confidence level: How sure the AI is

**Technology**:
- Option A: `transformers` library (DistilBERT sentiment model)
- Option B: OpenAI API (more accurate, costs $0.0001/message)
- Option C: Emergent LLM (use existing key)

**Implementation**:
```python
class SentimentAnalyzer:
    def analyze(self, message: str) -> dict:
        """
        Returns:
        {
            "score": -0.85,  # Very frustrated
            "emotion": "frustrated",
            "confidence": 0.92,
            "triggers": ["manager", "terrible"],
            "should_escalate": True
        }
        """
```

---

### 2. Escalation Hook
**File**: `/app/backend/services/aurem_hooks/human_escalation_hook.py`

**Trigger Conditions** (Any of these):
- Sentiment score < -0.6 (frustrated)
- Keywords: "manager", "lawyer", "cancel", "allergic reaction"
- 3+ consecutive negative messages
- AI confidence drop (can't answer questions)
- Customer explicitly asks: "I want to speak to a human"

**Actions When Triggered**:
1. **Pause AI** - Stop auto-replies for this conversation
2. **Alert Owner** - Send SMS/WhatsApp/Email immediately
3. **Create Handoff** - Prepare conversation for human takeover
4. **Log Event** - Track escalation for analytics

**Alert Format** (SMS):
```
🚨 URGENT - Customer Escalation

Customer: Jennifer Williams
Issue: Frustrated about product delay
Sentiment: -0.85 (very negative)
Last message: "This is terrible! I want my money back!"

[Take Over Chat →] [View Transcript →]
```

---

### 3. Live Handover Dashboard
**File**: `/app/frontend/src/platform/LiveHandoverDashboard.jsx`

**Features**:
- Real-time conversation view
- Full transcript with sentiment markers
- One-click "Take Over" button
- Owner can type directly to customer
- AI resumes when owner leaves

**UI Mock**:
```
┌─────────────────────────────────────────────────┐
│  🚨 LIVE HANDOVER - Jennifer Williams           │
│  Sentiment: 😡 -0.85 (VERY FRUSTRATED)          │
├─────────────────────────────────────────────────┤
│  Conversation:                                  │
│                                                 │
│  [AI] Welcome! How can I help?                  │
│  [Customer] Where's my order? It's 3 days late!│
│  [AI] I apologize for the delay...             │
│  [Customer] This is TERRIBLE! I want a refund! │
│  🚨 ESCALATION TRIGGERED                        │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ [You're Live - Type to respond]         │   │
│  │ ________________________________        │   │
│  │ [Send] [End Handover] [View Order]     │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

### 4. SMS/WhatsApp Alerts
**Integration**: Twilio (already scaffolded in project)

**Setup**:
- Each tenant configures their own Twilio number (BYON)
- Alerts sent to business owner's mobile
- Click-to-open handover dashboard

**Cost**: $0.0075 per SMS (Twilio pricing)

---

### 5. Analytics Dashboard
**Track**:
- Escalation rate (% of conversations)
- Average sentiment score per customer
- Time to handover
- Resolution rate (did human fix it?)
- Customer satisfaction after handover

---

## Implementation Steps

### Step 1: Sentiment Analysis (2 hours)
1. Install `transformers` library
2. Create `sentiment_analyzer.py`
3. Test with sample frustrated messages
4. Integrate into chat pipeline

### Step 2: Escalation Hook (1 hour)
1. Create `human_escalation_hook.py`
2. Define trigger conditions
3. Connect to SMS service (Twilio)
4. Test with mock conversation

### Step 3: Live Handover UI (2 hours)
1. Build `LiveHandoverDashboard.jsx`
2. WebSocket connection for real-time updates
3. Owner typing interface
4. AI pause/resume logic

### Step 4: Testing (1 hour)
1. Simulate frustrated customer
2. Verify SMS arrives < 3 seconds
3. Test handover flow end-to-end
4. Check AI resumes correctly

---

## Business Model

### Pricing:
- **Free Plan**: No escalation (AI only)
- **Starter ($49/mo)**: Email alerts only
- **Pro ($99/mo)**: SMS + Live handover dashboard
- **Enterprise**: Custom escalation rules + priority alerts

### Customer Value:
*"Never lose a customer to AI mistakes. Our Panic Button detects frustration in REAL-TIME and hands off to you in 2 seconds."*

---

## Success Metrics

### Week 1:
- 3+ escalations captured
- < 5 second alert delivery
- 80%+ handover success rate

### Month 1:
- 100+ escalations handled
- 90%+ customer satisfaction post-handover
- 50%+ customers upgrade to Pro (for SMS alerts)

---

## Edge Cases to Handle

1. **False Positives**: Customer says "terrible weather" → Don't escalate
2. **Multiple Alerts**: Don't spam owner if already notified
3. **Off-Hours**: Queue alerts if owner offline, send in morning
4. **Language**: Sentiment works in English, Spanish, French (DistilBERT)

---

## Future Enhancements (Phase C+)

1. **Voice Escalation**: AI detects tone of voice in calls (Vapi integration)
2. **Video Handover**: Owner can video call customer directly
3. **Team Routing**: Route to specific team members (support vs sales)
4. **AI Learning**: Train AI on successful human responses
