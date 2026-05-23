# AUREM Sentiment Analysis — JSON-LD Schema & Emergent Execution Directive

> Source: User-provided schema design + execution directive (Lyra)
> Purpose: Communication contract for Phase C Sentiment Analyzer extraction
> Saved: February 2026

---

## JSON-LD Schema: SentimentAnalysisEvent

```json
{
  "@context": "https://schema.aurem.ai/",
  "@type": "SentimentAnalysisEvent",
  "identifier": "uuid-v4-string",
  "timestamp": "2026-04-05T23:22:00Z",
  "subject": {
    "@type": "CommunicationTrace",
    "source": "SMS_Gateway_Android_Node_01",
    "content_hash": "sha256-hash-of-input"
  },
  "analysis": {
    "@type": "SentimentScore",
    "polarity": -0.85,
    "subjectivity": 0.9,
    "confidence": 0.98,
    "tone_tags": ["Urgent", "Dissatisfied", "Clinical_Inquiry"]
  },
  "aurem_gen_trigger": {
    "@type": "UIEvent",
    "pulse_color": "#B8860B",
    "animation_style": "Copper_Wireframe_Pulse",
    "panic_hook_active": true
  }
}
```

### Schema Features
- **Traceability**: `source` tracks which hardware (Android SMS gateways) sent the data
- **Aesthetic Sync**: `aurem_gen_trigger` carries Rose-Gold/Copper UI instructions
- **Token Efficiency**: Strict schema means no guessing on data format

---

## Emergent Execution Directive

```
"Emergent, use the AuremContextManager bridge. Perform an impact-radius
check on the SentimentAnalyzer class within the 40k-line monolith.

Goal: Identify all functions that currently pass raw strings to this class.

Requirement: Reference the newly designed JSON-LD Sentiment Schema.
Propose a plan to intercept these raw strings and wrap them in the
schema format before they reach the new service.

Constraint: Provide only the Risk Assessment and the specific function
names. Do not rewrite the code yet."
```

---

## Pending Decision
- [x] Execute directive on Lenovo Legion — COMPLETED (Apr 2026)
- [ ] Adjust Tone Tags to include specific clinical skincare categories
