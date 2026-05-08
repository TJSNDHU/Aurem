"""
Outreach tone tuner — iter 282ah (Prompt 5, Task A3).

Deterministic tone selector based on Yelp signals (rating × review count).
Pure function, no DB, no network. Never raises.
"""
from __future__ import annotations

TONE_PEER = (
    "Tone: professional and peer-level. This is an established business. "
    "Be direct and respectful. Lead with metrics and industry language. "
    "Avoid salesy language."
)
TONE_ENCOURAGE = (
    "Tone: friendly and encouraging. They're doing well. "
    "Offer to help them grow. Lead with opportunity, not problems."
)
TONE_EMPATHIC = (
    "Tone: empathetic and solution-focused. They may be struggling. "
    "Lead with value. Acknowledge challenges before pitching. "
    "Skip jargon."
)
TONE_NEUTRAL = "Tone: neutral and professional."


def _num(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def get_outreach_tone(lead: dict | None) -> str:
    """Return a tone instruction string ORA prepends before composing outreach.

    Routing:
      • rating ≥ 4.5 AND reviews ≥ 50  → peer-level / professional
      • rating ≥ 4.0  OR reviews ≥ 20  → encouraging
      • rating < 3.5  OR reviews < 5   → empathetic / solution-focused
      • otherwise                       → neutral

    Accepts `yelp_rating` / `rating` / `review_count` / `reviews` — any
    spelling; missing fields default to 0. Never raises.
    """
    lead = lead or {}
    rating = _num(lead.get("yelp_rating")
                   or lead.get("rating")
                   or lead.get("stars"))
    reviews = _num(lead.get("review_count")
                    or lead.get("reviews")
                    or lead.get("total_reviews"))

    if rating >= 4.5 and reviews >= 50:
        return TONE_PEER
    if rating >= 4.0 or reviews >= 20:
        return TONE_ENCOURAGE
    # Guard against "no data → empathetic" false positive.
    # Only downgrade to empathetic when we have SOME signal below threshold.
    if (rating > 0 and rating < 3.5) or (reviews > 0 and reviews < 5):
        return TONE_EMPATHIC
    return TONE_NEUTRAL


__all__ = ["get_outreach_tone", "TONE_PEER", "TONE_ENCOURAGE",
            "TONE_EMPATHIC", "TONE_NEUTRAL"]
