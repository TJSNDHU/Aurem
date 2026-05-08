"""
AUREM Case Study Builder — Data Aggregator
═══════════════════════════════════════════════════════════════════════════════
Pulls real telemetry from:
  • db.site_monitor_endpoints + db.site_monitor_logs + db.site_monitor_incidents
  • db.qa_bot_runs + db.qa_bot_endpoint_log
  • db.client_errors + db.repair_suggestions (Sentinel)
  • db.voice_call_logs (Retell)
  • db.agents_runs (ORA)
  • db.customer_subscriptions + db.service_catalog (MRR/spend)

Produces a single JSON "report payload" that feeds the PDF template AND
the admin/customer preview JSON endpoint.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

ASSUMED_HOURLY_RATE = 45  # CAD — mid-tier knowledge worker
AVG_SECONDS_PER_LEAD = 180  # 3 min per lead (research + qualify)
AVG_SECONDS_PER_VOICE_CALL = 240
AVG_SECONDS_PER_BRIEF = 900
AVG_SECONDS_PER_PULSE = 120
AVG_SECONDS_PER_INCIDENT_AVOIDED = 1800  # 30 min human triage


def _classify_uptime(pct: float) -> str:
    if pct >= 99.9: return "positive"
    if pct >= 99.0: return "positive"
    if pct >= 95.0: return "warning"
    return "danger"


def _format_duration_s(seconds: float) -> str:
    s = int(seconds)
    if s < 60: return f"{s}s"
    m = s // 60
    if m < 60: return f"{m}m {s % 60}s"
    h = m // 60
    return f"{h}h {m % 60}m"


def _format_human_period(start: datetime, end: datetime) -> str:
    return f"{start.strftime('%b %d, %Y')} — {end.strftime('%b %d, %Y')}"


def _period_word(days: int) -> str:
    if days <= 8: return "week"
    if days <= 35: return "month"
    if days <= 100: return "quarter"
    return "period"


async def aggregate_report_data(
    db,
    *,
    customer_email: str,
    customer_bin: Optional[str],
    customer_name: str,
    period_start: datetime,
    period_end: datetime,
    report_type: str = "monthly",  # monthly | quarterly | custom
) -> Dict[str, Any]:
    """Build the full report payload from real DB telemetry."""

    days = max(1, (period_end - period_start).days)
    start_iso = period_start.isoformat()
    end_iso = period_end.isoformat()
    report_id = f"AUREM-{period_end.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    # ═════════════════════════════════════════════════════════════════
    # UPTIME — Site Monitor
    # ═════════════════════════════════════════════════════════════════
    endpoints_q: Dict[str, Any] = {"active": True}
    if customer_email:
        endpoints_q["email"] = customer_email.lower()
    endpoints_cursor = db.site_monitor_endpoints.find(endpoints_q, {"_id": 0})
    endpoints = [e async for e in endpoints_cursor]

    url_count = len(endpoints)
    endpoint_rows = []
    total_checks = 0
    total_passed = 0
    total_latency_ms = 0
    total_latency_count = 0

    for ep in endpoints:
        ep_id = ep.get("endpoint_id")
        logs_cursor = db.site_monitor_logs.find(
            {"endpoint_id": ep_id, "ts": {"$gte": start_iso, "$lt": end_iso}},
            {"_id": 0, "passed": 1, "latency_ms": 1},
        )
        checks = 0
        passed = 0
        lat_sum = 0
        lat_n = 0
        async for lg in logs_cursor:
            checks += 1
            if lg.get("passed"):
                passed += 1
            lat = lg.get("latency_ms")
            if isinstance(lat, (int, float)) and lat > 0:
                lat_sum += lat
                lat_n += 1
        total_checks += checks
        total_passed += passed
        total_latency_ms += lat_sum
        total_latency_count += lat_n
        uptime_pct = round((passed / checks * 100), 2) if checks else 100.0
        avg_lat = round(lat_sum / lat_n) if lat_n else 0

        incidents_count = await db.site_monitor_incidents.count_documents({
            "endpoint_id": ep_id, "started_at": {"$gte": start_iso, "$lt": end_iso}
        })

        endpoint_rows.append({
            "url": ep.get("url") or "—",
            "checks": checks,
            "uptime_pct": uptime_pct,
            "uptime_cls": _classify_uptime(uptime_pct),
            "avg_latency_ms": avg_lat,
            "incidents": incidents_count,
        })

    # Global uptime %
    global_uptime_pct = round((total_passed / total_checks * 100), 2) if total_checks else 100.0

    # Uptime days strip (one bar per day)
    days_strip: List[Dict[str, Any]] = []
    for i in range(min(days, 45)):  # cap at 45 to fit the strip
        day = period_start + timedelta(days=i)
        day_start = day.isoformat()
        day_end = (day + timedelta(days=1)).isoformat()
        # simple count from logs
        ck = await db.site_monitor_logs.count_documents({
            "email": customer_email.lower() if customer_email else {"$exists": True},
            "ts": {"$gte": day_start, "$lt": day_end}
        })
        ps = await db.site_monitor_logs.count_documents({
            "email": customer_email.lower() if customer_email else {"$exists": True},
            "ts": {"$gte": day_start, "$lt": day_end},
            "passed": True,
        })
        pct = round((ps / ck * 100), 1) if ck else 0
        if ck == 0:
            cls = "none"
        elif pct >= 99.5:
            cls = ""  # green default
        elif pct >= 95:
            cls = "partial"
        else:
            cls = "down"
        days_strip.append({"day": day.strftime("%b %d"), "pct": pct, "cls": cls})

    # Top incidents
    top_incidents: List[Dict[str, Any]] = []
    inc_cursor = db.site_monitor_incidents.find(
        {"started_at": {"$gte": start_iso, "$lt": end_iso},
         **({"email": customer_email.lower()} if customer_email else {})},
        {"_id": 0},
    ).sort("started_at", -1).limit(8)
    async for inc in inc_cursor:
        try:
            started = datetime.fromisoformat(inc["started_at"].replace("Z", "+00:00"))
            dur_s = int(inc.get("duration_s") or 0)
            status = inc.get("status") or "open"
            top_incidents.append({
                "started_human": started.strftime("%b %d, %H:%M"),
                "url": inc.get("url") or "—",
                "duration_human": _format_duration_s(dur_s) if dur_s else "ongoing",
                "status": status,
                "badge_cls": "ok" if status == "resolved" else "warn",
            })
        except Exception:
            continue

    incidents_total = await db.site_monitor_incidents.count_documents({
        "started_at": {"$gte": start_iso, "$lt": end_iso},
        **({"email": customer_email.lower()} if customer_email else {})
    })
    incidents_resolved = await db.site_monitor_incidents.count_documents({
        "started_at": {"$gte": start_iso, "$lt": end_iso}, "status": "resolved",
        **({"email": customer_email.lower()} if customer_email else {})
    })
    avg_mttr_s = 0
    mttr_pipeline = [
        {"$match": {"started_at": {"$gte": start_iso, "$lt": end_iso}, "status": "resolved",
                    **({"email": customer_email.lower()} if customer_email else {})}},
        {"$group": {"_id": None, "avg": {"$avg": "$duration_s"}}},
    ]
    async for d in db.site_monitor_incidents.aggregate(mttr_pipeline):
        avg_mttr_s = int(d.get("avg") or 0)

    # ═════════════════════════════════════════════════════════════════
    # SENTINEL — client errors
    # ═════════════════════════════════════════════════════════════════
    sentinel_q: Dict[str, Any] = {"ts": {"$gte": start_iso, "$lt": end_iso}}
    if customer_email:
        sentinel_q["user_email"] = customer_email.lower()
    total_captured = await db.client_errors.count_documents(sentinel_q)
    auto_healed = await db.client_errors.count_documents({**sentinel_q, "auto_heal_key": {"$ne": None}})
    unique_users_pipe = [
        {"$match": sentinel_q},
        {"$group": {"_id": "$user_email"}},
        {"$count": "n"},
    ]
    unique_users = 0
    async for d in db.client_errors.aggregate(unique_users_pipe):
        unique_users = int(d.get("n") or 0)

    # Top error types
    top_types_pipe = [
        {"$match": sentinel_q},
        {"$group": {"_id": "$classification", "count": {"$sum": 1},
                    "users": {"$addToSet": "$user_email"},
                    "any_autoheal": {"$first": "$auto_heal_key"}}},
        {"$sort": {"count": -1}},
        {"$limit": 6},
    ]
    LABEL = {
        "stale_preview_pod": "Stale Preview Pod URL",
        "chunk_load_error": "Chunk Load Error",
        "auth_token_expired": "Auth Token Expired",
        "rate_limited_429": "Rate Limit (429)",
        "network_failure": "Network Failure",
        "backend_5xx": "Backend 5xx",
        "client_4xx": "Client 4xx",
        "js_exception": "JS Exception",
        "unhandled_rejection": "Unhandled Promise Rejection",
        "console_error": "Console Error",
        "resource_load_failure": "Resource 404",
        "unknown": "Unknown",
    }
    top_types: List[Dict[str, Any]] = []
    async for d in db.client_errors.aggregate(top_types_pipe):
        uu = len([u for u in (d.get("users") or []) if u])
        disposition = "auto-healed" if d.get("any_autoheal") else "logged"
        top_types.append({
            "label": LABEL.get(d["_id"], d["_id"] or "unknown"),
            "count": int(d["count"]),
            "unique_users": uu,
            "disposition": disposition,
            "badge_cls": "ok" if disposition == "auto-healed" else "warn",
        })

    spikes_pipe = [
        {"$match": sentinel_q},
        {"$group": {"_id": "$signature", "count": {"$sum": 1}, "users": {"$addToSet": "$user_email"}}},
        {"$match": {"count": {"$gte": 5}}},
    ]
    spike_count = 0
    async for d in db.client_errors.aggregate(spikes_pipe):
        if len([u for u in (d.get("users") or []) if u]) >= 3:
            spike_count += 1

    ai_diagnoses = await db.repair_suggestions.count_documents({
        "created_at": {"$gte": start_iso, "$lt": end_iso}
    })

    # ═════════════════════════════════════════════════════════════════
    # ORA workforce
    # ═════════════════════════════════════════════════════════════════
    async def _safe_count(coll, q):
        try:
            return await db[coll].count_documents(q)
        except Exception:
            return 0

    voice_calls = await _safe_count("voice_call_logs", {
        "created_at": {"$gte": start_iso, "$lt": end_iso},
        **({"email": customer_email.lower()} if customer_email else {})
    })
    # ORA hunts/leads — best-effort across possible collection names
    ora_hunts = await _safe_count("agents_runs", {
        "ts": {"$gte": start_iso, "$lt": end_iso}, "agent_id": {"$regex": "hunter"}
    })
    if ora_hunts == 0:
        ora_hunts = await _safe_count("agent_runs", {
            "ts": {"$gte": start_iso, "$lt": end_iso}, "agent_id": {"$regex": "hunter"}
        })
    leads = await _safe_count("leads", {
        "created_at": {"$gte": start_iso, "$lt": end_iso}
    })
    briefs = await _safe_count("morning_briefs", {
        "ts": {"$gte": start_iso, "$lt": end_iso}
    })
    pulse_sweeps = await _safe_count("qa_bot_runs", {
        "ts": {"$gte": start_iso, "$lt": end_iso}
    })

    # Equivalent human time
    seconds_saved = (
        leads * AVG_SECONDS_PER_LEAD
        + voice_calls * AVG_SECONDS_PER_VOICE_CALL
        + briefs * AVG_SECONDS_PER_BRIEF
        + pulse_sweeps * AVG_SECONDS_PER_PULSE
        + incidents_resolved * AVG_SECONDS_PER_INCIDENT_AVOIDED
        + auto_healed * 600  # 10 min per auto-healed bug
    )
    hours_saved = round(seconds_saved / 3600, 1)
    dollars_saved = int(hours_saved * ASSUMED_HOURLY_RATE)
    equivalent_ftes = round(hours_saved / (8 * days), 2) if days else 0

    # Period spend (sum of active customer_subscriptions prices pro-rated)
    period_spend = 0
    if customer_email:
        subs_cursor = db.customer_subscriptions.find(
            {"email": customer_email.lower(), "status": "active"},
            {"_id": 0, "service_id": 1, "price_snapshot": 1},
        )
        async for s in subs_cursor:
            p = s.get("price_snapshot")
            if isinstance(p, (int, float)):
                period_spend += float(p) * (days / 30.0)
    period_spend = int(period_spend)

    roi_multiplier = round(dollars_saved / max(period_spend, 1), 1) if period_spend else round(dollars_saved / max(97, 1), 1)
    roi_multiplier = min(roi_multiplier, 99.9)  # sanity cap

    exec_summary = {
        "total_actions": leads + voice_calls + briefs + pulse_sweeps + auto_healed,
        "incidents_prevented": incidents_resolved + auto_healed,
        "leads_handled": leads,
        "errors_captured": total_captured,
        "uptime_pct": global_uptime_pct,
        "uptime_class": _classify_uptime(global_uptime_pct),
        "uptime_trend": f"{total_checks} checks across {url_count} endpoints",
        "incidents_resolved": incidents_resolved,
        "avg_mttr_human": _format_duration_s(avg_mttr_s) if avg_mttr_s else "n/a",
        "hours_saved": hours_saved,
        "dollars_saved": dollars_saved,
        "ai_actions": leads + voice_calls + briefs + pulse_sweeps + auto_healed,
        "period_spend": period_spend or 97,  # floor so ROI is computable
        "roi_multiplier": roi_multiplier,
    }

    payload = {
        "report_id": report_id,
        "report_type": report_type,
        "report_type_label": report_type.upper(),
        "report_period_label": _format_human_period(period_start, period_end),
        "period_start_human": period_start.strftime("%b %d, %Y"),
        "period_end_human": period_end.strftime("%b %d, %Y"),
        "period_word": _period_word(days),
        "days": days,
        "issued_at_iso": datetime.now(timezone.utc).isoformat(),
        "issued_at_human": datetime.now(timezone.utc).strftime("%b %d, %Y · %H:%M UTC"),
        "customer_name": customer_name or "Valued Customer",
        "customer_email": customer_email,
        "customer_bin": customer_bin,
        "exec": exec_summary,
        "uptime": {
            "url_count": url_count,
            "interval_human": "5 minutes",
            "days_strip": days_strip,
            "endpoints": endpoint_rows,
            "top_incidents": top_incidents,
            "incidents_total": incidents_total,
        },
        "sentinel": {
            "total_captured": total_captured,
            "auto_healed": auto_healed,
            "auto_healed_pct": round((auto_healed / total_captured * 100), 1) if total_captured else 0,
            "unique_users": unique_users,
            "spikes": spike_count,
            "spike_cls": "warning" if spike_count > 0 else "positive",
            "ai_diagnoses": ai_diagnoses,
            "top_types": top_types,
        },
        "ora": {
            "hunts": ora_hunts,
            "hunts_hh": _format_duration_s(ora_hunts * 600),
            "leads": leads,
            "leads_hh": _format_duration_s(leads * AVG_SECONDS_PER_LEAD),
            "voice_calls": voice_calls,
            "voice_hh": _format_duration_s(voice_calls * AVG_SECONDS_PER_VOICE_CALL),
            "briefs": briefs,
            "briefs_hh": _format_duration_s(briefs * AVG_SECONDS_PER_BRIEF),
            "pulse_sweeps": pulse_sweeps,
            "pulse_hh": _format_duration_s(pulse_sweeps * AVG_SECONDS_PER_PULSE),
            "equivalent_ftes": equivalent_ftes,
            "assumed_hourly_rate": ASSUMED_HOURLY_RATE,
        },
        "verification": {
            "endpoint_count": url_count,
            "data_point_count": total_checks + total_captured + voice_calls + leads,
        },
    }
    return payload
