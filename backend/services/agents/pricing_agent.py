"""
AUREM Pricing Agent — Council Voter (Phase 0)
==============================================
Advisory voter. Recommends a plan tier based on lead score + reviews.
Mutates `payload` in-place to surface `recommended_plan` + `recommended_price`.

Tiers (CAD):
  growth     $449/mo  — score ≥ 8 OR review_count > 100
  starter    $97/mo   — score ≥ 5
  skip       —        — score < 5
"""
from __future__ import annotations

from typing import Any, Dict, Tuple


async def vote(action: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    score = int(payload.get("hunter_score") or payload.get("score") or 5)
    reviews = int(payload.get("review_count") or 0)

    if score >= 8 or reviews > 100:
        plan = "growth"
        price = "$449 CAD"
    elif score >= 5:
        plan = "starter"
        price = "$97 CAD"
    else:
        plan = "skip"
        price = "—"

    # Mutate so downstream agents can read the recommendation
    payload["recommended_plan"] = plan
    payload["recommended_price"] = price

    return "APPROVE", f"Plan: {plan} ({price})"
