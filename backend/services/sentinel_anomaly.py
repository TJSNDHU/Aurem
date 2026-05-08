"""
Sentinel Anomaly Detection — P1
=================================
7-day rolling baseline per tenant:
  - avg API calls, avg outreach volume, typical login hours, avg invoice amount
Alert if any metric > 3x baseline. Score 1-10. >7 = WhatsApp alert.
"""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_db = None


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


async def _compute_baseline(tenant_id: str) -> dict:
    """Compute 7-day rolling baseline for the tenant."""
    db = _get_db()
    if db is None:
        return {}

    cutoff_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # API calls (pipeline runs as proxy)
    pipeline_7d = await db.pipeline_runs.count_documents({
        "tenant_id": tenant_id, "started_at": {"$gte": cutoff_7d}
    })
    avg_api_calls = round(pipeline_7d / 7, 1) if pipeline_7d > 0 else 0

    # Outreach volume (episodic memory entries with outreach type)
    outreach_7d = await db.episodic_memory.count_documents({
        "tenant_id": tenant_id,
        "timestamp": {"$gte": cutoff_7d},
        "action_type": {"$in": ["queue_outreach", "send_reminder", "draft_ora_response"]},
    })
    avg_outreach = round(outreach_7d / 7, 1) if outreach_7d > 0 else 0

    # Login hours (from audit_log if exists)
    login_hours = []
    try:
        async for doc in db.audit_log.find(
            {"tenant_id": tenant_id, "action": "login", "timestamp": {"$gte": cutoff_7d}},
            {"_id": 0, "timestamp": 1}
        ).limit(100):
            ts = doc.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    login_hours.append(dt.hour)
                except Exception:
                    pass
    except Exception:
        pass
    avg_login_hour = round(sum(login_hours) / len(login_hours), 1) if login_hours else 12
    typical_login_range = (
        min(login_hours) if login_hours else 8,
        max(login_hours) if login_hours else 20,
    )

    # Invoice amount
    invoice_amounts = []
    try:
        async for doc in db.orders.find(
            {"tenant_id": tenant_id, "created_at": {"$gte": cutoff_7d}},
            {"_id": 0, "total": 1, "amount": 1}
        ).limit(100):
            amt = doc.get("total") or doc.get("amount") or 0
            if amt:
                invoice_amounts.append(float(amt))
    except Exception:
        pass
    avg_invoice = round(sum(invoice_amounts) / len(invoice_amounts), 2) if invoice_amounts else 0

    return {
        "tenant_id": tenant_id,
        "period_days": 7,
        "avg_api_calls_per_day": avg_api_calls,
        "avg_outreach_per_day": avg_outreach,
        "avg_login_hour": avg_login_hour,
        "typical_login_range": typical_login_range,
        "avg_invoice_amount": avg_invoice,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _get_current_metrics(tenant_id: str) -> dict:
    """Get today's metrics for comparison against baseline."""
    db = _get_db()
    if db is None:
        return {}

    cutoff_1d = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    api_calls_today = await db.pipeline_runs.count_documents({
        "tenant_id": tenant_id, "started_at": {"$gte": cutoff_1d}
    })
    outreach_today = await db.episodic_memory.count_documents({
        "tenant_id": tenant_id,
        "timestamp": {"$gte": cutoff_1d},
        "action_type": {"$in": ["queue_outreach", "send_reminder", "draft_ora_response"]},
    })

    # Latest login hour
    last_login_hour = None
    try:
        doc = await db.audit_log.find_one(
            {"tenant_id": tenant_id, "action": "login"},
            {"_id": 0, "timestamp": 1},
            sort=[("timestamp", -1)]
        )
        if doc and doc.get("timestamp"):
            dt = datetime.fromisoformat(doc["timestamp"].replace("Z", "+00:00"))
            last_login_hour = dt.hour
    except Exception:
        pass

    # Latest invoice
    latest_invoice = 0
    try:
        doc = await db.orders.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "total": 1, "amount": 1},
            sort=[("created_at", -1)]
        )
        if doc:
            latest_invoice = float(doc.get("total") or doc.get("amount") or 0)
    except Exception:
        pass

    return {
        "api_calls_today": api_calls_today,
        "outreach_today": outreach_today,
        "last_login_hour": last_login_hour,
        "latest_invoice_amount": latest_invoice,
    }


def _score_anomaly(metric_name: str, current: float, baseline: float) -> dict:
    """Score an individual metric. Returns anomaly dict with score 1-10."""
    if baseline <= 0:
        return {"metric": metric_name, "anomaly": False, "score": 0, "ratio": 0}

    ratio = current / baseline if baseline > 0 else 0
    anomaly = ratio > 3.0
    score = min(10, round(ratio * 2.5))

    return {
        "metric": metric_name,
        "current": current,
        "baseline": baseline,
        "ratio": round(ratio, 2),
        "anomaly": anomaly,
        "score": score,
    }


async def run_anomaly_detection(tenant_id: str) -> dict:
    """Run full anomaly detection for a tenant."""
    baseline = await _compute_baseline(tenant_id)
    current = await _get_current_metrics(tenant_id)

    anomalies = []
    anomalies.append(_score_anomaly(
        "api_calls", current.get("api_calls_today", 0), baseline.get("avg_api_calls_per_day", 0)
    ))
    anomalies.append(_score_anomaly(
        "outreach_volume", current.get("outreach_today", 0), baseline.get("avg_outreach_per_day", 0)
    ))

    # Login hour anomaly (outside typical range)
    login_hour = current.get("last_login_hour")
    login_range = baseline.get("typical_login_range", (8, 20))
    if login_hour is not None:
        outside = login_hour < login_range[0] or login_hour > login_range[1]
        anomalies.append({
            "metric": "login_hours",
            "current": login_hour,
            "baseline": f"{login_range[0]}-{login_range[1]}",
            "anomaly": outside,
            "score": 7 if outside else 1,
            "ratio": 0,
        })

    anomalies.append(_score_anomaly(
        "invoice_amount", current.get("latest_invoice_amount", 0), baseline.get("avg_invoice_amount", 0)
    ))

    # Overall score
    max_score = max((a.get("score", 0) for a in anomalies), default=0)
    has_critical = max_score > 7
    triggered = [a for a in anomalies if a.get("anomaly")]

    # Alert if critical (score > 7) — WhatsApp via Twilio + fallback to DB log
    alert_sent = False
    alert_channel = "none"
    if has_critical:
        alert_msg = (
            f"SENTINEL ANOMALY\nTenant: {tenant_id}\nMax Score: {max_score}/10\n"
            + "\n".join(f"- {a['metric']}: {a['current']} vs baseline {a['baseline']}" for a in triggered)
        )

        # Try WhatsApp via Twilio (normalized env resolver)
        try:
            import os
            from services.channel_config import get_twilio_credentials, get_twilio_whatsapp_from
            creds = get_twilio_credentials()
            twilio_sid = creds["sid"]
            twilio_token = creds["token"]
            twilio_whatsapp_from = get_twilio_whatsapp_from() or "whatsapp:+14155238886"
            alert_phone = os.environ.get("SENTINEL_ALERT_PHONE")

            if twilio_sid and twilio_token and alert_phone:
                from twilio.rest import Client as TwilioClient
                client = TwilioClient(twilio_sid, twilio_token)
                client.messages.create(
                    body=alert_msg,
                    from_=twilio_whatsapp_from,
                    to=f"whatsapp:{alert_phone}" if not alert_phone.startswith("whatsapp:") else alert_phone,
                )
                alert_sent = True
                alert_channel = "whatsapp"
                logger.info(f"[SENTINEL] WhatsApp alert sent to {alert_phone}")
            else:
                logger.info("[SENTINEL] No Twilio keys — WhatsApp alert skipped (graceful degradation)")
        except ImportError:
            logger.info("[SENTINEL] Twilio not installed — WhatsApp alert skipped")
        except Exception as e:
            logger.warning(f"[SENTINEL] WhatsApp alert error: {e}")

        # Fallback: store alert in DB for dashboard notification
        if not alert_sent:
            alert_channel = "db_only"
            db2 = _get_db()
            if db2 is not None:
                await db2.sentinel_alerts.insert_one({
                    "tenant_id": tenant_id,
                    "max_score": max_score,
                    "message": alert_msg,
                    "triggered_metrics": [a["metric"] for a in triggered],
                    "channel": "pending_whatsapp",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    # Store result
    db = _get_db()
    if db is not None:
        await db.anomaly_detections.insert_one({
            "tenant_id": tenant_id,
            "baseline": baseline,
            "current_metrics": current,
            "anomalies": anomalies,
            "max_score": max_score,
            "has_critical": has_critical,
            "triggered_count": len(triggered),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "tenant_id": tenant_id,
        "anomalies": anomalies,
        "max_score": max_score,
        "has_critical": has_critical,
        "triggered_count": len(triggered),
        "alert_sent": alert_sent,
        "alert_channel": alert_channel,
        "baseline": baseline,
        "current_metrics": current,
    }


async def get_anomaly_history(tenant_id: str = None, limit: int = 20) -> list:
    """Get recent anomaly detection results."""
    db = _get_db()
    if db is None:
        return []
    query = {"tenant_id": tenant_id} if tenant_id else {}
    cursor = db.anomaly_detections.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_anomaly_stats(tenant_id: str = None) -> dict:
    """Aggregate anomaly stats."""
    db = _get_db()
    if db is None:
        return {}
    query = {"tenant_id": tenant_id} if tenant_id else {}
    total = await db.anomaly_detections.count_documents(query)
    critical = await db.anomaly_detections.count_documents({**query, "has_critical": True})
    return {
        "total_scans": total,
        "critical_alerts": critical,
        "alert_rate": round((critical / total * 100) if total > 0 else 0, 1),
    }
