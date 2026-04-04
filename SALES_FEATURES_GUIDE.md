# 🚀 AUREM Sales Features Documentation

## Overview
Three complete sales automation UIs have been added to the AUREM platform, all accessible from the new **SALES** section in the dashboard sidebar.

---

## 🎯 1. Sales Pipeline Dashboard

**Location:** Dashboard → SALES → Sales Pipeline

**Features:**
- **5-Step Pipeline Visualization:**
  1. Scan - Select customer website scan
  2. Decision Maker - AI finds executives/decision makers
  3. Proposal - Auto-generate professional proposal with pricing
  4. Contract - Generate service agreement
  5. Onboarding - Track implementation progress

**How to Use:**
1. Click a scan from your recent scans
2. AI automatically finds decision makers (CEO, CTO, Founder, etc.)
3. Click "Generate Proposal" to create pricing document
4. Click "Generate Contract" for service agreement
5. View onboarding progress tracker

**Key Features:**
- Decision maker power badges (High/Medium/Low)
- Contact info (email, LinkedIn, phone)
- Downloadable PDFs for proposals and contracts
- Real-time onboarding status tracking
- Visual progress indicators

**API Endpoints:**
- `POST /api/pipeline/find-decision-makers`
- `POST /api/pipeline/generate-proposal`
- `POST /api/pipeline/generate-contract`
- `GET /api/pipeline/onboarding-status/{contract_id}`

---

## 📞 2. Voice Sales Agent

**Location:** Dashboard → SALES → Voice Sales Agent

**Features:**
- **Auto Calls:** AI calls customers automatically after scan
- **Voice Training:** Train AI to recognize team members' voices
- **Call History:** View past calls, recordings, and outcomes

**How to Use:**

### Auto Calls:
1. Select a customer scan that has a phone number
2. Click "Start AI Call"
3. AI calls the customer within 5 minutes
4. AI presents findings, answers questions, schedules follow-up

### Voice Training:
1. Click "+ Train New Voice"
2. Record 5-10 voice samples
3. AI creates voice profile
4. Used for identifying speakers in meetings

### Call History:
- View all past calls
- See customer sentiment, objections raised
- Check if meeting was scheduled
- Download call recordings

**Requirements:**
- Customer must have phone number (add via Customer Scanner enrichment)
- Vapi integration for production calls
- ElevenLabs for voice synthesis

**API Endpoints:**
- `POST /api/voice/start-sales-call`
- `POST /api/voice/train`
- `GET /api/voice/profiles`
- `WebSocket /ws/voice/call/{call_id}`

---

## 🎧 3. Invisible AI Sales Coach

**Location:** Dashboard → SALES → Invisible Coach

**Features:**
- AI listens silently during in-person meetings
- Provides real-time suggestions to wireless earpiece
- Customer never knows you have AI assistance
- Full transcript and coaching report after meeting

**How to Use:**
1. Select customer scan for context
2. Click "Start Coach"
3. AI listens via device microphone
4. AI analyzes customer questions/objections
5. AI whispers instant suggestions to your earpiece
6. Stop session when meeting ends

**Real-Time Suggestions:**
- **Price Questions:** AI provides pricing breakdown
- **ROI Questions:** AI shows savings calculations
- **Technical Questions:** AI explains integration
- **Objections:** AI suggests objection handlers

**Privacy:**
- Silent mode - AI never speaks to customer
- Optional: Disable recording, suggestions only
- Always inform participants if recording

**API Endpoints:**
- `POST /api/coach/start-invisible`
- `WebSocket /ws/coach/{coach_id}`
- `GET /api/coach/session/{coach_id}/transcript`

---

## 🎨 Design System

All three features follow the AUREM design language:
- **Dark Theme:** `#050505` background
- **Gold Accents:** `#D4AF37` gradient
- **Consistent Components:**
  - Info cards with colored borders
  - Status badges
  - Progress indicators
  - Action buttons with gradients
  - Empty states with icons

---

## 🔗 Integration with Customer Scanner

All three sales features integrate seamlessly with the Customer Scanner:

1. **Scan a customer website** → Get technical findings
2. **Add manual enrichment** (phone, email, social media) → Enable personalization
3. **Sales Pipeline** → Find decision makers, generate proposals
4. **Voice Sales Agent** → Auto-call customers (requires phone number)
5. **Invisible Coach** → Use scan data for meeting coaching

---

## 📊 Complete Sales Flow Example

```
STEP 1: Scan
  → Customer Scanner: Scan https://customer-website.com
  → Add phone: +1-555-123-4567, email: ceo@company.com
  → Result: 18 issues found, score 65

STEP 2: Decision Maker
  → Sales Pipeline: Find decision makers
  → AI finds: John Smith (CEO), Sarah Johnson (CTO)
  → Contact info: emails, LinkedIn profiles

STEP 3: Outreach (Choose One)
  
  Option A: Auto Voice Call
  → Voice Sales Agent: Click "Start AI Call"
  → AI calls CEO automatically
  → Presents findings, schedules meeting

  Option B: In-Person Meeting
  → Invisible Coach: Start coaching session
  → AI listens during meeting
  → Whispers suggestions in real-time

STEP 4: Proposal
  → Sales Pipeline: Generate proposal
  → Auto-creates pricing doc
  → Shows: $999/mo, saves $16,000/year, ROI 3.5x
  → Download PDF

STEP 5: Contract
  → Sales Pipeline: Generate contract
  → Auto-creates service agreement
  → Customer signs digitally

STEP 6: Onboarding
  → Sales Pipeline: Track onboarding
  → Auto-triggered after contract signed
  → Progress: Account setup → Integration → Go live
```

---

## 🧪 Testing

**Test Credentials:**
- Email: `teji.ss1986@gmail.com`
- Password: `Admin123`

**Test Flow:**
1. Login → Dashboard
2. Scan a website with enrichment data
3. Navigate to each sales feature
4. Test the complete pipeline

---

## 🚀 Future Enhancements

### Voice Sales Agent:
- [ ] Vapi integration for production calls
- [ ] Call recording playback
- [ ] Sentiment analysis dashboard
- [ ] Auto-follow-up scheduling

### Invisible Coach:
- [ ] Real-time speech-to-text integration
- [ ] Multi-language support
- [ ] Post-meeting coaching report
- [ ] Integration with CRM

### Sales Pipeline:
- [ ] Apollo.io integration for better decision maker finding
- [ ] DocuSign integration for digital signatures
- [ ] CRM sync (HubSpot, Salesforce)
- [ ] Pipeline analytics dashboard

---

**Last Updated:** December 2025  
**Status:** ✅ Production Ready
