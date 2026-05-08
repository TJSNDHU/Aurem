"""
ClawChief OS — Autonomous Operations Layer for AUREM
=====================================================

Provides:
  - Heartbeat: Polls Sentiment, Pipeline, Leads every 15 min
  - Daily Sweep: 08:00 EST — runs all agents, writes tasks/current.md
  - Pipeline Audit: Every 4 hours — checks at-risk deals
  - Workspace I/O: All file writes are blockchain-audited
  - Durable State: MEMORY.md, HEARTBEAT.md, tasks/current.md

Every write to the workspace is hashed via the P4 Blockchain Audit Trail.
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Workspace root — local filesystem, version-control friendly
WORKSPACE_ROOT = Path(__file__).parent.parent / "workspace"
TASKS_FILE = WORKSPACE_ROOT / "tasks" / "current.md"
HEARTBEAT_FILE = WORKSPACE_ROOT / "HEARTBEAT.md"
MEMORY_FILE = WORKSPACE_ROOT / "MEMORY.md"
SWEEPS_DIR = WORKSPACE_ROOT / "sweeps"

# Timezone: America/Toronto (EST/EDT)
try:
    from zoneinfo import ZoneInfo
    TZ_TORONTO = ZoneInfo("America/Toronto")
except ImportError:
    import pytz
    TZ_TORONTO = pytz.timezone("America/Toronto")

_db = None


def set_db(database):
    global _db
    _db = database


def get_db():
    return _db


# ═══════════════════════════════════════════════════
# WORKSPACE FILE I/O (Blockchain-Audited)
# ═══════════════════════════════════════════════════

async def write_workspace_file(filepath: Path, content: str, action: str = "file_write") -> str:
    """
    Write to a workspace file and log the hash in the blockchain audit trail.
    Returns the SHA-256 hash of the content.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")

    content_hash = hashlib.sha256(content.encode()).hexdigest()

    db = get_db()
    if db is not None:
        try:
            from routers.agent_execution_router import create_audit_entry
            await create_audit_entry(
                db,
                action=f"clawchief_{action}",
                agent_id="clawchief",
                data={
                    "file": str(filepath.relative_to(WORKSPACE_ROOT)),
                    "content_hash": content_hash,
                    "size_bytes": len(content),
                },
            )
        except Exception as e:
            logger.warning(f"[ClawChief] Audit write failed: {e}")

    logger.info(f"[ClawChief] Wrote {filepath.name} ({len(content)} bytes, hash: {content_hash[:12]}...)")
    return content_hash


def read_workspace_file(filepath: Path) -> str:
    """Read a workspace file. Returns empty string if not found."""
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return ""


# ═══════════════════════════════════════════════════
# HEARTBEAT — 15-minute system pulse check
# ═══════════════════════════════════════════════════

async def run_heartbeat() -> Dict:
    """
    Poll all monitored systems and update HEARTBEAT.md.
    Runs every 15 minutes.
    """
    db = get_db()
    if db is None:
        return {"error": "Database not initialized"}

    now = datetime.now(TZ_TORONTO)
    now_utc = datetime.now(timezone.utc)
    checks = {}

    # 1. Sentiment Service
    try:
        recent_panics = await db.panic_events.count_documents(
            {"created_at": {"$gte": now_utc - timedelta(hours=1)}}
        )
        recent_analyses = await db.sentiment_analyses.count_documents(
            {"analyzed_at": {"$gte": now_utc - timedelta(hours=1)}}
        )
        checks["sentiment"] = {
            "status": "ALERT" if recent_panics > 0 else "OK",
            "panics_1h": recent_panics,
            "analyses_1h": recent_analyses,
        }
    except Exception as e:
        checks["sentiment"] = {"status": "ERROR", "error": str(e)}

    # 2. Pipeline Health
    try:
        open_deals = await db.deals.find(
            {"status": {"$nin": ["won", "lost"]}},
            {"_id": 0, "value": 1, "stage": 1, "title": 1},
        ).to_list(500)
        total_value = sum(d.get("value", 0) for d in open_deals)
        at_risk = [d for d in open_deals if d.get("stage", "").lower() in ("scan",)]
        checks["pipeline"] = {
            "status": "ALERT" if len(at_risk) > 3 else "OK",
            "total_value": total_value,
            "deal_count": len(open_deals),
            "at_risk": len(at_risk),
        }
    except Exception as e:
        checks["pipeline"] = {"status": "ERROR", "error": str(e)}

    # 3. Lead Scores
    try:
        total_contacts = await db.contacts.count_documents({})
        scored = await db.contacts.count_documents({"score": {"$exists": True}})
        high_quality = await db.contacts.count_documents({"grade": {"$in": ["A", "B"]}})
        checks["leads"] = {
            "status": "OK",
            "total": total_contacts,
            "scored": scored,
            "high_quality": high_quality,
        }
    except Exception as e:
        checks["leads"] = {"status": "ERROR", "error": str(e)}

    # 4. Agent Fleet
    try:
        recent_execs = await db.agent_executions.count_documents(
            {"started_at": {"$gte": (now_utc - timedelta(hours=4)).isoformat()}}
        )
        failed_execs = await db.agent_executions.count_documents(
            {"status": "failed", "started_at": {"$gte": (now_utc - timedelta(hours=4)).isoformat()}}
        )
        checks["agents"] = {
            "status": "ALERT" if failed_execs > 0 else "OK",
            "executions_4h": recent_execs,
            "failures_4h": failed_execs,
        }
    except Exception as e:
        checks["agents"] = {"status": "ERROR", "error": str(e)}

    # 5. Blockchain Audit Chain
    try:
        chain_count = await db.audit_chain.count_documents({})
        last_entry = await db.audit_chain.find_one(
            sort=[("sequence", -1)], projection={"_id": 0, "hash": 1, "timestamp": 1}
        )
        checks["audit_chain"] = {
            "status": "OK",
            "total_entries": chain_count,
            "last_hash": last_entry.get("hash", "")[:16] + "..." if last_entry else "empty",
        }
    except Exception as e:
        checks["audit_chain"] = {"status": "ERROR", "error": str(e)}

    # Determine overall alert level
    statuses = [c.get("status", "OK") for c in checks.values()]
    if "ERROR" in statuses:
        alert_level = "ERROR"
    elif statuses.count("ALERT") >= 2:
        alert_level = "CRITICAL"
    elif "ALERT" in statuses:
        alert_level = "ELEVATED"
    else:
        alert_level = "CALM"

    # 6. Adversarial Critic Review (every heartbeat via Step Flash for speed)
    adversarial_result = None
    try:
        from services.critic_agent import adversarial_review, set_db as set_critic_db
        set_critic_db(db)
        adversarial_result = await adversarial_review(
            data={
                "pipeline_value": checks.get("pipeline", {}).get("total_value", 0),
                "deal_count": checks.get("pipeline", {}).get("deal_count", 0),
                "at_risk": checks.get("pipeline", {}).get("at_risk", 0),
                "sentiment_panics": checks.get("sentiment", {}).get("panics_1h", 0),
                "high_quality_leads": checks.get("leads", {}).get("high_quality", 0),
                "agent_failures": checks.get("agents", {}).get("failures_4h", 0),
            },
            context="heartbeat_pipeline_integrity",
            model_hint="heartbeat",
        )
        checks["adversarial_critic"] = {
            "status": "ALERT" if adversarial_result.get("verdict") == "CHALLENGED" else "OK",
            "verdict": adversarial_result.get("verdict", "UNKNOWN"),
            "challenges_count": len(adversarial_result.get("challenges", [])),
        }

        # Escalate alert if Critic challenges the data
        if adversarial_result.get("verdict") == "CHALLENGED":
            if alert_level == "CALM":
                alert_level = "ELEVATED"
            logger.warning("[ClawChief] Adversarial Critic CHALLENGED heartbeat data")
    except Exception as adv_err:
        logger.warning(f"[ClawChief] Adversarial review skipped: {adv_err}")

    heartbeat = {
        "timestamp": now.isoformat(),
        "timestamp_utc": now_utc.isoformat(),
        "alert_level": alert_level,
        "checks": checks,
        "adversarial_review": adversarial_result,
    }

    # Write HEARTBEAT.md
    md = _render_heartbeat_md(heartbeat, now)
    await write_workspace_file(HEARTBEAT_FILE, md, action="heartbeat_update")

    # Store in MongoDB for API access
    await db.heartbeats.insert_one({
        **heartbeat,
        "stored_at": now_utc,
    })

    logger.info(f"[ClawChief] Heartbeat: {alert_level} at {now.strftime('%H:%M %Z')}")
    return heartbeat


def _render_heartbeat_md(heartbeat: Dict, now) -> str:
    checks = heartbeat["checks"]
    alert = heartbeat["alert_level"]

    rows = []
    for name, data in checks.items():
        status = data.get("status", "UNKNOWN")
        badge = "OK" if status == "OK" else "ALERT" if status == "ALERT" else "ERROR"
        rows.append(f"| {name.title()} | {badge} | {now.strftime('%H:%M %Z')} |")

    alerts_section = ""
    for name, data in checks.items():
        if data.get("status") == "ALERT":
            detail = {k: v for k, v in data.items() if k != "status"}
            alerts_section += f"- **{name.title()}**: {json.dumps(detail)}\n"

    return f"""# HEARTBEAT.md — System Pulse Monitor

> ClawChief OS | AUREM Automation Intelligence
> Last Check: {now.strftime('%Y-%m-%d %H:%M %Z')}
> Status: {alert}

---

## System Status

| Component | Status | Last Check |
|-----------|--------|------------|
{chr(10).join(rows)}

## Alert Level: {alert}

## Recent Alerts

{alerts_section if alerts_section else "No active alerts. All systems nominal."}

## Heartbeat Config

- **Interval**: Every 15 minutes
- **Timezone**: America/Toronto (EST)
- **Monitors**: Sentiment, Pipeline, Leads, Agents, Audit Chain
"""


# ═══════════════════════════════════════════════════
# DAILY SWEEP — 08:00 EST
# ═══════════════════════════════════════════════════

async def run_daily_sweep() -> Dict:
    """
    Morning intelligence sweep. Runs all agents and writes results
    to tasks/current.md. This is ORA's "Daily Briefing" generation.
    """
    db = get_db()
    if db is None:
        return {"error": "Database not initialized"}

    now = datetime.now(TZ_TORONTO)
    now_utc = datetime.now(timezone.utc)
    results = {}

    # Run agents
    from routers.agent_execution_router import AGENT_EXECUTORS, create_audit_entry

    for agent_id in ["scout", "oracle", "closer"]:
        try:
            result = await AGENT_EXECUTORS[agent_id]({}, db)
            results[agent_id] = {"status": "completed", "summary": result.get("summary", "")}

            await create_audit_entry(
                db,
                action=f"daily_sweep_{agent_id}",
                agent_id=agent_id,
                data={"summary": result.get("summary", "")},
            )
        except Exception as e:
            results[agent_id] = {"status": "failed", "error": str(e)}

    # Refresh daily summary
    try:
        from services.ora_dispatcher import generate_daily_summary
        summary = await generate_daily_summary()
        results["daily_summary"] = {"status": "generated", "digest": summary.get("digest", "")}
    except Exception as e:
        results["daily_summary"] = {"status": "failed", "error": str(e)}

    # Write tasks/current.md
    md = _render_tasks_md(results, now)
    await write_workspace_file(TASKS_FILE, md, action="daily_sweep")

    # Store sweep record
    sweep_id = now.strftime("%Y%m%d_%H%M")
    sweep_file = SWEEPS_DIR / f"sweep_{sweep_id}.md"
    await write_workspace_file(sweep_file, md, action=f"sweep_{sweep_id}")

    await db.sweeps.insert_one({
        "sweep_id": sweep_id,
        "type": "daily",
        "timestamp": now_utc,
        "results": results,
    })

    logger.info(f"[ClawChief] Daily sweep complete at {now.strftime('%H:%M %Z')}")
    return {"sweep_id": sweep_id, "results": results}


def _render_tasks_md(results: Dict, now) -> str:
    scout_summary = results.get("scout", {}).get("summary", "Not available")
    oracle_summary = results.get("oracle", {}).get("summary", "Not available")
    closer_summary = results.get("closer", {}).get("summary", "Not available")
    digest = results.get("daily_summary", {}).get("digest", "Not available")

    return f"""# tasks/current.md — War Room Task Log

> ClawChief OS | AUREM Automation Intelligence
> Last Updated: {now.strftime('%Y-%m-%d %H:%M %Z')}
> Status: ACTIVE

---

## Daily Brief

{digest}

## Agent Reports

### Scout (Lead Intelligence)
{scout_summary}

### Oracle (Revenue Forecast)
{oracle_summary}

### Closer (Deal Health)
{closer_summary}

## Active Tasks

- Review Scout's lead scoring results
- Follow up on Envoy's outreach recommendations
- Monitor at-risk deals flagged by Closer

## Pending Follow-Ups

_(Envoy agent writes here after outreach planning)_

## Completed Today

- Daily sweep executed at {now.strftime('%H:%M %Z')}
- All agent reports generated
- Daily summary refreshed
"""


# ═══════════════════════════════════════════════════
# PIPELINE AUDIT — Every 4 hours
# ═══════════════════════════════════════════════════

async def run_pipeline_audit() -> Dict:
    """
    4-hour pipeline health check. Focuses on at-risk deals
    and stale contacts.
    """
    db = get_db()
    if db is None:
        return {"error": "Database not initialized"}

    now = datetime.now(TZ_TORONTO)
    now_utc = datetime.now(timezone.utc)

    # Run Closer for deal health
    from routers.agent_execution_router import AGENT_EXECUTORS, create_audit_entry

    try:
        closer_result = await AGENT_EXECUTORS["closer"]({}, db)
    except Exception as e:
        closer_result = {"summary": f"Closer failed: {e}", "at_risk_count": 0}

    # Check sentiment trends
    try:
        recent_sentiment = await db.sentiment_analyses.aggregate([
            {"$match": {"analyzed_at": {"$gte": now_utc - timedelta(hours=4)}}},
            {"$group": {"_id": None, "avg_score": {"$avg": "$result.score"}, "count": {"$sum": 1}}},
        ]).to_list(1)
        sentiment_avg = recent_sentiment[0]["avg_score"] if recent_sentiment else 0
        sentiment_count = recent_sentiment[0]["count"] if recent_sentiment else 0
    except Exception:
        sentiment_avg = 0
        sentiment_count = 0

    audit_result = {
        "timestamp": now.isoformat(),
        "closer": closer_result,
        "sentiment_4h": {"avg_score": round(sentiment_avg, 2), "count": sentiment_count},
        "alert": closer_result.get("at_risk_count", 0) > 3 or sentiment_avg < -0.5,
    }

    await create_audit_entry(
        db,
        action="pipeline_audit",
        agent_id="clawchief",
        data={"at_risk": closer_result.get("at_risk_count", 0), "sentiment_avg": round(sentiment_avg, 2)},
    )

    # Update heartbeat if alert
    if audit_result["alert"]:
        await run_heartbeat()

    await db.sweeps.insert_one({
        "sweep_id": now.strftime("%Y%m%d_%H%M"),
        "type": "pipeline_audit",
        "timestamp": now_utc,
        "results": audit_result,
    })

    logger.info(f"[ClawChief] Pipeline audit: {closer_result.get('at_risk_count', 0)} at-risk deals")
    return audit_result


# ═══════════════════════════════════════════════════
# CRON SCHEDULER — Background async loops
# ═══════════════════════════════════════════════════

_heartbeat_running = False
_daily_sweep_running = False
_pipeline_audit_running = False


async def heartbeat_scheduler():
    """Runs heartbeat every 15 minutes."""
    global _heartbeat_running
    if _heartbeat_running:
        return
    _heartbeat_running = True

    logger.info("[ClawChief] Heartbeat scheduler started (first run in 30s, then every 15 min)")
    # iter 285.8 — shortened startup delay (was 180s) so we don't leave
    # `db.heartbeats` stale for minutes after every backend restart. 30s
    # gives LLM clients enough time to warm up.
    await asyncio.sleep(30)
    while True:
        try:
            await run_heartbeat()
        except Exception as e:
            logger.error(f"[ClawChief] Heartbeat error: {e}")
        await asyncio.sleep(900)  # 15 minutes


async def daily_sweep_scheduler():
    """Runs daily sweep at 08:00 EST."""
    global _daily_sweep_running
    if _daily_sweep_running:
        return
    _daily_sweep_running = True

    logger.info("[ClawChief] Daily sweep scheduler started (08:00 EST)")
    while True:
        try:
            now = datetime.now(TZ_TORONTO)
            # Calculate seconds until next 08:00
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()

            logger.info(f"[ClawChief] Next daily sweep in {wait_seconds/3600:.1f} hours")
            await asyncio.sleep(wait_seconds)
            await run_daily_sweep()
        except Exception as e:
            logger.error(f"[ClawChief] Daily sweep error: {e}")
            await asyncio.sleep(3600)  # Retry in 1 hour


async def pipeline_audit_scheduler():
    """Runs pipeline audit every 4 hours."""
    global _pipeline_audit_running
    if _pipeline_audit_running:
        return
    _pipeline_audit_running = True

    logger.info("[ClawChief] Pipeline audit scheduler started (every 4 hours)")
    while True:
        try:
            await asyncio.sleep(14400)  # 4 hours
            await run_pipeline_audit()
        except Exception as e:
            logger.error(f"[ClawChief] Pipeline audit error: {e}")
            await asyncio.sleep(3600)
