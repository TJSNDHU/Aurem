# Operation Clean-Cut: Phase C Finalized Directive

> Source: User-provided final directive with refined Tone Tags (Lyra)
> Purpose: Complete execution plan for Sentiment Analyzer extraction
> Saved: February 2026

---

## Refined Tone Tags

| Tag | Purpose | War Room Trigger |
|-----|---------|-----------------|
| `Clinical_Inquiry` | Customers asking about PDRN, NAD+, active ingredients | Standard |
| `Efficacy_Concern` | Dissatisfaction with results | HIGH PRIORITY pulse |
| `Logistics_Update` | Shipment tracking (Mississauga, China supplier) | Low |
| `Aesthetic_Feedback` | User perception of Scientific-Luxe UI/UX | Medium |

### Updated Schema Snippet
```json
"analysis": {
  "@type": "SentimentScore",
  "tone_tags": ["Clinical_Inquiry", "Efficacy_Concern", "Logistics_Update", "Aesthetic_Feedback"]
}
```

---

## Official Directive: OPERATION CLEAN-CUT (PHASE C)

```
To: Emergent (Lead Architect)
Environment: Lenovo Legion 5i / Aurem Backend (40k Lines)
Tools: code-review-graph, AuremContextManager

Task:
1. Perform get_impact_radius check on SentimentAnalyzer module
2. Cross-reference all "Callers" against JSON-LD Tone Tags
   (Clinical, Logistics, Efficacy)
3. Identify the "UI-Pulse" Hook: locate exactly where the monolith
   triggers copper-wireframe animations

Output Requirement:
- Top 5 most critical dependencies that must be shimmed before extraction
- Risk Score for Rose-Gold UI stability
- DO NOT REWRITE CODE. Only provide the mapping.
```

---

## "Map First" Rationale

Forcing Emergent to map the UI-Pulse Hook before moving code protects the Scientific-Luxe brand experience. Blind extraction risks losing Rose-Gold pulsing alerts during critical sentiment events.

---

## Pending Decision
- [x] Execute directive on Lenovo Legion — COMPLETED (Apr 2026)
- [ ] Add Safety Buffer to Panic Hook logic to prevent false alarms during migration — COMPLETED (safety_buffer.py)
