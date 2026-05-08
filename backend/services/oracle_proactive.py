"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Oracle Proactive Service
========================
Wires the Revenue Forecast into ORA's proactive voice:
  - STATUS_REPORT / FORECAST intents → live forecast data
  - Risk > 10% → suggests Proximity Blast
  - Low confidence → auto-triggers Scout background fill
  - Conversion feedback loop from Envoy response rates
  - Shadow-cache for <100ms reads
"""
import logging
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None
_forecast_cache = {}  # tenant_id → {data, cached_at}


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════
# FORECAST CACHE (Shadow-Save for <100ms reads)
# ═══════════════════════════════════════════════════════════════

async def get_cached_forecast(tenant_id: str) -> dict:
    """Get forecast from in-memory cache, falling back to DB shadow buffer."""
    # 1. In-memory cache (< 1ms)
    if tenant_id in _forecast_cache:
        cached = _forecast_cache[tenant_id]
        age_s = (datetime.now(timezone.utc) - cached["cached_at"]).total_seconds()
        if age_s < 300:  # 5 min cache
            return cached["data"]

    # 2. DB shadow buffer (< 50ms)
    db = _get_db()
    if db is not None:
        shadow = await db.forecast_shadow_cache.find_one(
            {"tenant_id": tenant_id}, {"_id": 0}
        )
        if shadow and shadow.get("data"):
            _forecast_cache[tenant_id] = {
                "data": shadow["data"],
                "cached_at": datetime.now(timezone.utc),
            }
            return shadow["data"]

    # 3. Compute fresh
    return await compute_and_cache_forecast(tenant_id)


async def compute_and_cache_forecast(tenant_id: str) -> dict:
    """Compute forecast and write to both in-memory + DB shadow cache."""
    try:
        from services.revenue_forecast import compute_90day_forecast
        forecast = await compute_90day_forecast(tenant_id)
    except Exception as e:
        logger.warning(f"[Oracle] Forecast compute error: {e}")
        forecast = {"forecast_available": False, "reason": str(e)}

    # Write to in-memory cache
    _forecast_cache[tenant_id] = {
        "data": forecast,
        "cached_at": datetime.now(timezone.utc),
    }

    # Write to DB shadow cache (zero-loss persistence)
    db = _get_db()
    if db is not None:
        try:
            await db.forecast_shadow_cache.update_one(
                {"tenant_id": tenant_id},
                {
                    "$set": {
                        "data": forecast,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "$setOnInsert": {
                        "tenant_id": tenant_id,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                },
                upsert=True,
            )
        except Exception:
            pass

    return forecast


# ═══════════════════════════════════════════════════════════════
# PROACTIVE ORACLE RESPONSE BUILDER
# ═══════════════════════════════════════════════════════════════

async def build_oracle_response(tenant_id: str) -> dict:
    """Build a proactive ORA response from the forecast.

    Returns:
        {
            "forecast_text": str,       # Human-readable forecast summary
            "risk_alert": bool,         # True if risk > 10%
            "risk_pct": float,          # Risk percentage
            "suggestion": str|None,     # Proactive suggestion if risk high
            "low_confidence": bool,     # True if pipeline < 3 leads
            "auto_scout_triggered": bool,  # True if Scout was auto-fired
            "trend": dict|None,         # Forward-loop trend data
        }
    """
    forecast = await get_cached_forecast(tenant_id)

    if not forecast.get("forecast_available"):
        return {
            "forecast_text": "I don't have enough data yet to generate a forecast. As leads and orders flow in, I'll build your 90-day projection automatically.",
            "risk_alert": False,
            "risk_pct": 0,
            "suggestion": None,
            "low_confidence": True,
            "auto_scout_triggered": False,
            "trend": None,
        }

    s = forecast.get("summary", {})
    p = forecast.get("pipeline", {})
    r = forecast.get("recurring", {})
    pend = forecast.get("pending", {})

    projected = s.get("projected_revenue", 0)
    at_risk = s.get("revenue_at_risk", 0)
    confidence = s.get("confidence", "low")
    active_leads = p.get("active_leads", 0)

    # Calculate risk percentage
    total_potential = projected + at_risk if (projected + at_risk) > 0 else 1
    risk_pct = round((at_risk / total_potential) * 100, 1)
    risk_alert = risk_pct > 10

    # Build the human-readable forecast
    parts = [
        f"Here's your 90-day outlook: **${projected:,.0f}** projected revenue.",
    ]
    if p.get("weighted_value"):
        parts.append(f"Pipeline contributes ${p['weighted_value']:,.0f} (weighted across {active_leads} active leads).")
    if r.get("projected_90d"):
        parts.append(f"Recurring revenue: ${r['projected_90d']:,.0f} based on recent order patterns.")
    if pend.get("expected_recovery"):
        parts.append(f"Pending recovery: ${pend['expected_recovery']:,.0f} at {(pend.get('historical_payment_rate', 0) * 100):.0f}% historical payment rate.")

    forecast_text = " ".join(parts)

    # Proactive suggestion if risk > 10%
    suggestion = None
    if risk_alert:
        suggestion = (
            f"We have **${at_risk:,.0f}** at risk this quarter ({risk_pct}% of potential revenue). "
            f"I recommend triggering a **15km Proximity Blast** to fill the gap. "
            f"Should I start the scan?"
        )

    # Low confidence check → auto-trigger Scout
    low_confidence = confidence == "low" or active_leads < 3
    auto_scout_triggered = False
    if low_confidence:
        auto_scout_triggered = await _trigger_background_scout(tenant_id)

    # Forward-loop trend data
    trend = await _get_forward_trend(tenant_id)

    return {
        "forecast_text": forecast_text,
        "risk_alert": risk_alert,
        "risk_pct": risk_pct,
        "suggestion": suggestion,
        "low_confidence": low_confidence,
        "auto_scout_triggered": auto_scout_triggered,
        "trend": trend,
        "confidence": confidence,
        "projected_revenue": projected,
        "revenue_at_risk": at_risk,
    }


# ═══════════════════════════════════════════════════════════════
# FORECAST-TO-ACTION: Auto-Scout on Low Confidence
# ═══════════════════════════════════════════════════════════════

async def _trigger_background_scout(tenant_id: str) -> bool:
    """When forecast confidence is low, auto-discover 10 local leads and queue in Envoy."""
    db = _get_db()
    if db is None:
        return False

    # Check if we already ran a scout fill in the last 24h
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent = await db.proximity_campaigns.find_one(
        {"tenant_id": tenant_id, "created_at": {"$gte": cutoff}, "source": "auto_scout"}
    )
    if recent:
        return False  # Already ran recently

    try:
        from services.proximity_blast import generate_simulated_leads

        # Get tenant location (default Toronto)
        config = await db.proximity_config.find_one(
            {"tenant_id": tenant_id}, {"_id": 0}
        )
        lat = config.get("business_lat", 43.6532) if config else 43.6532
        lng = config.get("business_lng", -79.3832) if config else -79.3832

        leads = generate_simulated_leads(lat, lng, 15, count=10)

        # Queue in envoy_outreach
        now_iso = datetime.now(timezone.utc).isoformat()
        outreach_tasks = []
        for lead in leads:
            outreach_tasks.append({
                "tenant_id": tenant_id,
                "lead_id": lead["lead_id"],
                "business_name": lead["business_name"],
                "owner_name": lead["owner_name"],
                "email": lead["email"],
                "phone": lead["phone"],
                "business_type": lead["business_type"],
                "distance_km": lead["distance_km"],
                "outreach_type": "auto_scout_fill",
                "status": "queued",
                "script": f"Hi {lead['owner_name']}, I noticed your {lead['business_type']} is nearby. We help local businesses automate lead generation. Would a quick 10-minute call work this week?",
                "created_at": now_iso,
            })

        if outreach_tasks:
            await db.envoy_outreach.insert_many(outreach_tasks)

        # Record the campaign
        await db.proximity_campaigns.insert_one({
            "tenant_id": tenant_id,
            "lat": lat, "lng": lng, "radius_km": 15,
            "leads_found": len(leads),
            "data_source": "simulated",
            "source": "auto_scout",
            "created_at": now_iso,
        })

        logger.info(f"[Oracle] Auto-Scout triggered for {tenant_id}: {len(leads)} leads queued")
        return True

    except Exception as e:
        logger.warning(f"[Oracle] Auto-Scout error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# FORWARD-LOOP TREND DATA
# ═══════════════════════════════════════════════════════════════

async def _get_forward_trend(tenant_id: str) -> dict:
    """Generate forward-looking trend insights from Scout/lead data."""
    db = _get_db()
    if db is None:
        return None

    # Count leads by business_type in envoy_outreach
    try:
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {"_id": "$business_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 3},
        ]
        top_types = await db.envoy_outreach.aggregate(pipeline).to_list(3)

        if not top_types:
            # Fallback: count from leads collection
            top_types = await db.leads.aggregate(pipeline).to_list(3)

        if top_types and top_types[0].get("_id"):
            trending_type = top_types[0]["_id"]
            trending_count = top_types[0]["count"]
            return {
                "trending_type": trending_type,
                "trending_count": trending_count,
                "insight": f"Trending: {trending_count} leads in {trending_type} sector detected in your area. This may signal a growth opportunity.",
                "top_sectors": [
                    {"type": t.get("_id", "Unknown"), "count": t.get("count", 0)}
                    for t in top_types
                ],
            }
    except Exception as e:
        logger.warning(f"[Oracle] Trend analysis error: {e}")

    return None


# ═══════════════════════════════════════════════════════════════
# CONVERSION FEEDBACK LOOP
# ═══════════════════════════════════════════════════════════════

async def update_envoy_response(tenant_id: str, lead_id: str, response_type: str) -> dict:
    """Track Envoy outreach response for feedback loop.
    response_type: 'opened', 'replied', 'converted', 'bounced', 'ignored'
    """
    db = _get_db()
    if db is None:
        return {"success": False}

    now_iso = datetime.now(timezone.utc).isoformat()

    # Update the outreach task
    await db.envoy_outreach.update_one(
        {"tenant_id": tenant_id, "lead_id": lead_id},
        {"$set": {
            "response_type": response_type,
            "response_at": now_iso,
            "status": "converted" if response_type == "converted" else "responded" if response_type in ("opened", "replied") else response_type,
        }},
    )

    # Record in conversion_feedback for the Oracle
    await db.conversion_feedback.insert_one({
        "tenant_id": tenant_id,
        "lead_id": lead_id,
        "response_type": response_type,
        "created_at": now_iso,
    })

    # Recalculate conversion rate and feed into win_probability
    await _recalculate_conversion_rate(tenant_id)

    return {"success": True, "response_type": response_type}


async def _recalculate_conversion_rate(tenant_id: str):
    """Recalculate envoy conversion rate → update pipeline win_probability."""
    db = _get_db()
    if db is None:
        return

    total = await db.envoy_outreach.count_documents({"tenant_id": tenant_id})
    converted = await db.envoy_outreach.count_documents(
        {"tenant_id": tenant_id, "response_type": "converted"}
    )
    replied = await db.envoy_outreach.count_documents(
        {"tenant_id": tenant_id, "response_type": {"$in": ["replied", "converted"]}}
    )

    if total == 0:
        return

    conversion_rate = round(converted / total, 4)
    response_rate = round(replied / total, 4)

    # Store the rate
    await db.conversion_metrics.update_one(
        {"tenant_id": tenant_id},
        {
            "$set": {
                "total_outreach": total,
                "total_converted": converted,
                "total_replied": replied,
                "conversion_rate": conversion_rate,
                "response_rate": response_rate,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )

    # Feed conversion rate into lead win_probability (weighted blend)
    if conversion_rate > 0:
        # Update unprocessed leads: blend existing prob with envoy conversion data
        blend_factor = min(conversion_rate * 2, 0.5)  # Cap influence at 50%
        async for lead in db.leads.find(
            {"tenant_id": tenant_id, "status": {"$in": ["new", "unprocessed"]}},
            {"_id": 1, "win_probability": 1}
        ).limit(100):
            current_prob = float(lead.get("win_probability", 0.3))
            new_prob = round(current_prob * (1 - blend_factor) + conversion_rate * blend_factor, 4)
            await db.leads.update_one(
                {"_id": lead["_id"]},
                {"$set": {"win_probability": new_prob, "prob_source": "oracle_feedback"}}
            )

    logger.info(f"[Oracle] Conversion rate updated for {tenant_id}: {conversion_rate:.2%} ({converted}/{total})")


async def get_conversion_metrics(tenant_id: str) -> dict:
    """Get the latest conversion metrics for a tenant."""
    db = _get_db()
    if db is None:
        return {"total_outreach": 0, "conversion_rate": 0, "response_rate": 0}

    metrics = await db.conversion_metrics.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    return metrics or {"total_outreach": 0, "conversion_rate": 0, "response_rate": 0}
